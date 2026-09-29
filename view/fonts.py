"""Fonts with per-character fallback.

SDL_ttf renders a whole string with exactly one face and performs no font
fallback, so any character that face lacks is drawn as a tofu box. The
interface labels itself with symbol and emoji glyphs -- the close button is a
multiplication X, the turn counter a stopwatch, a selected territory a pushpin
-- and those live in Segoe UI Symbol and Segoe UI Emoji, not in Segoe UI.
Measured against the face the app was actually rendering with, 34 of the 38
distinct non-ASCII characters in its string literals were tofu: the close
button and nearly every icon in the game were drawn as boxes.

FallbackFont composites runs of text from whichever installed face has the
glyph, the way a browser does, while exposing the part of pygame's Font API
this codebase uses (render, get_linesize) so no call site changes.
"""

import pygame

# Faces carrying the symbol and emoji glyphs on Windows. Names that are not
# installed are skipped, so a machine with none of them degrades to the
# previous single-face behaviour instead of failing to start.
FALLBACK_FONTS = ("Segoe UI Symbol", "Segoe UI Emoji")

# Which fallback face draws which codepoint. Emoji wins by default: both faces
# cover most of these codepoints, but Symbol draws thin monochrome outlines --
# at the 15px body size its bar chart and world map are indistinguishable from
# empty rectangles, which is what made the Analytics button look like it had a
# box on it even once the fallback was working.
#
# The Arrows block is the exception. Emoji renders ↕ as a filled blue button,
# far too loud for a subtle "this panel scrolls" hint, where Symbol draws a
# plain thin arrow. Symbol is also the fallback of last resort for the handful
# of codepoints Emoji lacks (⟲, for one), which is handled by trying the other
# face when the preferred one has nothing.
_ARROWS = range(0x2190, 0x2200)

# A private-use codepoint no font defines. Whatever a face draws for it is that
# face's missing-glyph bitmap, which is what a tofu box is. This is preferred
# over Font.metrics(), which reports notdef metrics for an unsupported
# character rather than reporting that it is unsupported -- every missing glyph
# in a face returns the same tuple, so metrics cannot distinguish "this face
# has no such character" from "this character is exactly that wide".
_ABSENT = ""

# Rendered surfaces are cached because the same labels (the 📍 territory
# header, the 🛡️ defence bar) are re-rendered every frame. The cache is capped
# rather than unbounded because several labels contain live numbers --
# "Believing: 222 (3.6%)" is a different string every tick -- and those
# entries are never reused, so an unbounded cache would grow for the life of
# the process.
_CACHE_LIMIT = 512


def _missing_glyph_bitmap(font: pygame.font.Font) -> bytes:
    """The bytes this face draws for a character it does not have."""
    return pygame.image.tobytes(font.render(_ABSENT, True, (255, 255, 255)), "RGBA")


def _render_or_empty(font: pygame.font.Font, text: str, antialias: bool,
                     color) -> pygame.Surface:
    """Render `text`, or an empty surface if it has no advance width.

    A variation selector (U+FE0F, which follows most emoji) or a combining mark
    has no width of its own, and pygame raises "Text has zero width" rather
    than returning an empty surface. Such a character only ever appears
    attached to the character it modifies, so when one is rendered on its own
    the correct output is nothing at all.
    """
    try:
        return font.render(text, antialias, color)
    except (pygame.error, ValueError):
        # pygame raises this as pygame.error, not ValueError.
        return pygame.Surface((0, 0), pygame.SRCALPHA)


class FallbackFont:
    """A pygame-like Font that falls back per character.

    Only render() and get_linesize() are used by the view layer; the remaining
    delegation exists so this is a drop-in for pygame.font.Font wherever a
    panel accepts one.
    """

    def __init__(self, name: str, size: int, bold: bool = False):
        self.primary = pygame.font.SysFont(name, size, bold=bold)
        # Built in order so each fallback's index into _faces is its actual
        # position: a machine missing the first fallback but having the second
        # would otherwise record an index past the end of the list.
        self._faces = [self.primary]
        self._fallbacks = []          # (index into _faces, face name, face)
        for face_name in FALLBACK_FONTS:
            if pygame.font.match_font(face_name):
                face = pygame.font.SysFont(face_name, size, bold=bold)
                self._fallbacks.append((len(self._faces), face_name, face))
                self._faces.append(face)
        self._notdef = [_missing_glyph_bitmap(f) for f in self._faces]
        self._face_of: dict[str, int] = {}      # char -> index into _faces
        self._plain: dict[str, bool] = {}       # text -> primary face covers it
        self._cache: dict[tuple, pygame.Surface] = {}

    def _face_index(self, ch: str) -> int:
        """Which face draws `ch`. Index 0 is the primary, so plain Latin text
        and anything the primary already covers keeps its existing rendering."""
        index = self._face_of.get(ch)
        if index is None:
            index = 0
            if not self._has(self.primary, 0, ch):
                # Preferred face first, the other as the fallback of last
                # resort for codepoints it lacks.
                order = self._fallbacks if ord(ch) in _ARROWS else list(reversed(self._fallbacks))
                for i, _, face in order:
                    if self._has(face, i, ch):
                        index = i
                        break
            self._face_of[ch] = index
        return index

    def _has(self, font: pygame.font.Font, index: int, ch: str) -> bool:
        try:
            return (pygame.image.tobytes(font.render(ch, True, (255, 255, 255)), "RGBA")
                    != self._notdef[index])
        except (pygame.error, ValueError):
            return False

    def _covers(self, text: str) -> bool:
        """True if the primary face alone can draw every character of `text`."""
        cached = self._plain.get(text)
        if cached is None:
            cached = all(self._face_index(c) == 0 for c in text)
            self._plain[text] = cached
        return cached

    def render(self, text: str, antialias: bool, color, background=None) -> pygame.Surface:
        # Text the primary face covers takes the untouched pygame path: same
        # kerning, same metrics, no composite surface. Only strings that
        # actually contain a glyph the primary lacks are composited, so nothing
        # about the existing ASCII labels changes.
        if self._covers(text):
            if background is None:
                return _render_or_empty(self.primary, text, antialias, color)
            return self.primary.render(text, antialias, color, background)

        key = (text, color, background)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        # Group consecutive characters by the face that draws them, so each run
        # keeps its own kerning and only the boundaries between runs lose it.
        runs: list[tuple[int, list[str]]] = []
        for ch in text:
            index = self._face_index(ch)
            if runs and runs[-1][0] == index:
                runs[-1][1].append(ch)
            else:
                runs.append((index, [ch]))

        pieces = [(self._faces[i], _render_or_empty(self._faces[i], "".join(chars),
                                                    antialias, color))
                  for i, chars in runs]

        # The composite is sized and baselined exactly like a plain render, so a
        # string containing an icon has the same box as one that does not.
        # Sizing it to the tallest run instead would make the two differ --
        # Segoe UI Emoji at this point size is 14px tall against Segoe UI's 20px
        # -- and every label pairing an icon with a value (the "⏱ Turns: 24"
        # row puts an icon label beside a plain one) would draw its two halves
        # on different baselines.
        ascent = self.primary.get_ascent()
        width = sum(s.get_width() for _, s in pieces)

        surface = pygame.Surface((max(1, width), max(1, self.primary.get_height())),
                                 pygame.SRCALPHA)
        if background is not None:
            surface.fill(background)
        x = 0
        for face, piece in pieces:
            surface.blit(piece, (x, ascent - face.get_ascent()))
            x += piece.get_width()

        if len(self._cache) >= _CACHE_LIMIT:
            self._cache.clear()
        self._cache[key] = surface
        return surface

    def has_glyph(self, ch: str) -> bool:
        """True if some installed face can draw `ch` rather than a tofu box."""
        # A face index of 0 is ambiguous on its own: it is also what an
        # unrenderable character gets when no face has it. Asking the primary
        # face directly separates the two.
        return self._face_index(ch) != 0 or self._has(self.primary, 0, ch)

    def get_linesize(self) -> int:
        """The primary face's line height, so layout arithmetic is unchanged.

        Deliberately not the tallest face: every panel that sizes itself from
        this would otherwise grow the moment an icon appeared in a label.
        """
        return self.primary.get_linesize()

    def size(self, text: str) -> tuple[int, int]:
        return self.render(text, True, (255, 255, 255)).get_size()

    def get_height(self) -> int:
        return self.primary.get_height()

    def get_ascent(self) -> int:
        return self.primary.get_ascent()

    def get_descent(self) -> int:
        return self.primary.get_descent()


def load_font(name: str, size: int, bold: bool = False) -> FallbackFont:
    """Load a font with per-character fallback. See the module docstring."""
    return FallbackFont(name, size, bold)
