import pygame
from view import theme
from model.trait import Trait


class Button:
    """Small reusable clickable rectangle with a label -- used by TraitPanel."""

    def __init__(self, rect: pygame.Rect, label: str, enabled: bool = True):
        self.rect = rect
        self.label = label
        self.enabled = enabled

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        bg = theme.ACCENT_DIM if self.enabled else theme.PANEL_BORDER
        pygame.draw.rect(surface, bg, self.rect, border_radius=6)
        pygame.draw.rect(surface, theme.ACCENT if self.enabled else theme.TEXT_SECONDARY,
                          self.rect, width=1, border_radius=6)
        text_color = theme.TEXT_PRIMARY if self.enabled else theme.TEXT_SECONDARY
        label_surf = font.render(self.label, True, text_color)
        surface.blit(label_surf, (
            self.rect.x + (self.rect.width - label_surf.get_width()) // 2,
            self.rect.y + (self.rect.height - label_surf.get_height()) // 2
        ))

    def is_clicked(self, point: tuple[int, int]) -> bool:
        return self.enabled and self.rect.collidepoint(point)


class StatsPanel:
    def __init__(self, rect: pygame.Rect, font: pygame.font.Font, header_font: pygame.font.Font):
        self.rect = rect
        self.font = font
        self.header_font = header_font

    def draw(self, surface: pygame.Surface, summary: dict, strain_name: str, model_name: str = "") -> None:
        pygame.draw.rect(surface, theme.PANEL_BG, self.rect, border_radius=10)
        pygame.draw.rect(surface, theme.PANEL_BORDER, self.rect, width=2, border_radius=10)

        x, y = self.rect.x + 16, self.rect.y + 14
        header_text = f"{strain_name} ({model_name})" if model_name else strain_name
        header = self.header_font.render(header_text, True, theme.ACCENT)
        surface.blit(header, (x, y))
        y += 32

        lines = [
            f"Tick: {summary['ticks']}",
            f"Global belief: {summary['global_infection_ratio'] * 100:.1f}%",
        ]
        if summary.get("total_exposed", 0) > 0:
            lines.append(f"Exposed (not yet believing): {summary['total_exposed']}")
        lines += [
            f"Believing: {summary['total_believing']}",
            f"Skeptical: {summary['total_skeptical']}",
            f"Status: {summary['state'].upper()}",
        ]
        for line in lines:
            text_surf = self.font.render(line, True, theme.TEXT_PRIMARY)
            surface.blit(text_surf, (x, y))
            y += 24


class TraitPanel:
    def __init__(self, rect: pygame.Rect, font: pygame.font.Font, header_font: pygame.font.Font,
                 available_traits: list[Trait]):
        self.rect = rect
        self.font = font
        self.header_font = header_font
        self.available_traits = available_traits
        self.buttons: list[tuple[Button, Trait]] = []
        self._build_buttons()

    def _build_buttons(self) -> None:
        self.buttons = []
        x, y = self.rect.x + 16, self.rect.y + 44
        btn_height = 36
        spacing = 8
        for trait in self.available_traits:
            rect = pygame.Rect(x, y, self.rect.width - 32, btn_height)
            label = f"{trait.name} ({trait.cost} pts)"
            self.buttons.append((Button(rect, label), trait))
            y += btn_height + spacing

    def draw(self, surface: pygame.Surface, strain) -> None:
        """
        Renders each trait as a button showing its current level (if any)
        and the cost to acquire the next level. Buttons only disable when
        the player can't afford the next level right now -- they re-enable
        automatically once enough points accumulate, since traits can be
        re-leveled indefinitely (see InfoStrain.acquire_trait()).
        """
        pygame.draw.rect(surface, theme.PANEL_BG, self.rect, border_radius=10)
        pygame.draw.rect(surface, theme.PANEL_BORDER, self.rect, width=2, border_radius=10)

        header = self.header_font.render(f"Traits — {strain.points_available} pts", True, theme.ACCENT)
        surface.blit(header, (self.rect.x + 16, self.rect.y + 12))

        for button, trait in self.buttons:
            level = strain.trait_level(trait)
            next_cost = trait.next_cost(level)
            level_suffix = f" Lv.{level}" if level > 0 else ""
            button.label = f"{trait.name}{level_suffix}  -  {next_cost} pts"
            button.enabled = next_cost <= strain.points_available
            button.draw(surface, self.font)

    def handle_click(self, point: tuple[int, int]) -> Trait | None:
        for button, trait in self.buttons:
            if button.is_clicked(point):
                return trait
        return None


class NewsTicker:
    """Keeps a short rolling list of recent events, newest first."""

    def __init__(self, rect: pygame.Rect, font: pygame.font.Font, max_items: int = 6):
        self.rect = rect
        self.font = font
        self.max_items = max_items
        self.events: list[str] = []

    def push(self, message: str) -> None:
        self.events.insert(0, message)
        self.events = self.events[: self.max_items]

    def draw(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, theme.PANEL_BG, self.rect, border_radius=10)
        pygame.draw.rect(surface, theme.PANEL_BORDER, self.rect, width=2, border_radius=10)

        x, y = self.rect.x + 16, self.rect.y + 10
        for event in self.events:
            text_surf = self.font.render(event, True, theme.TEXT_SECONDARY)
            surface.blit(text_surf, (x, y))
            y += 20


class RaceBar:
    """
    The single most important at-a-glance widget: a head-to-head bar
    showing global belief % (red, growing from the left) against
    countermeasure strength % (teal, growing from the right). Modeled
    directly on Plague Inc's infection-vs-cure race, which is the genre's
    standard way of making "who's currently winning" readable in under a
    second without reading any numbers at all.

    Countermeasure strength is shown relative to its own cap (see
    CounterMeasure.cap in model/countermeasure.py) so the bar always
    spans the same visual range regardless of the actual cap value chosen.
    """

    def __init__(self, rect: pygame.Rect, font: pygame.font.Font, header_font: pygame.font.Font):
        self.rect = rect
        self.font = font
        self.header_font = header_font

    def draw(self, surface: pygame.Surface, belief_ratio: float, counter_strength: float,
              counter_cap: float, counter_active: bool) -> None:
        pygame.draw.rect(surface, theme.PANEL_BG, self.rect, border_radius=10)
        pygame.draw.rect(surface, theme.PANEL_BORDER, self.rect, width=2, border_radius=10)

        pad = 16
        label_y = self.rect.y + 12
        belief_label = self.font.render(f"Belief {belief_ratio * 100:.1f}%", True, theme.RACE_BAR_BELIEF)
        counter_text = f"Countermeasure {counter_strength * 100:.0f}%" if counter_active else "Countermeasure (dormant)"
        counter_label = self.font.render(counter_text, True, theme.RACE_BAR_COUNTER)
        surface.blit(belief_label, (self.rect.x + pad, label_y))
        surface.blit(counter_label, (self.rect.right - pad - counter_label.get_width(), label_y))

        bar_y = label_y + 26
        bar_height = 18
        bar_rect = pygame.Rect(self.rect.x + pad, bar_y, self.rect.width - pad * 2, bar_height)
        pygame.draw.rect(surface, theme.RACE_BAR_TRACK, bar_rect, border_radius=9)

        # Belief fills from the left, countermeasure fills from the right --
        # the gap left in the middle is "ground neither side has taken yet."
        belief_fraction = max(0.0, min(1.0, belief_ratio))
        counter_fraction = max(0.0, min(1.0, counter_strength / counter_cap)) if counter_cap > 0 else 0.0

        belief_width = int(bar_rect.width * belief_fraction)
        counter_width = int(bar_rect.width * counter_fraction)

        if belief_width > 0:
            belief_rect = pygame.Rect(bar_rect.x, bar_rect.y, belief_width, bar_height)
            pygame.draw.rect(surface, theme.RACE_BAR_BELIEF, belief_rect,
                              border_top_left_radius=9, border_bottom_left_radius=9)
        if counter_width > 0:
            counter_rect = pygame.Rect(bar_rect.right - counter_width, bar_rect.y, counter_width, bar_height)
            pygame.draw.rect(surface, theme.RACE_BAR_COUNTER, counter_rect,
                              border_top_right_radius=9, border_bottom_right_radius=9)

        pygame.draw.rect(surface, theme.PANEL_BORDER, bar_rect, width=1, border_radius=9)


class AdvanceButton:
    """
    The control that replaces the old automatic 600ms timer. Nothing in
    the simulation advances until the player clicks this (or presses the
    bound keys in main.py) -- this is the single change that turns the
    game from "plays itself while you watch" into something the player is
    actually responsible for pacing. Hover state gives immediate visual
    feedback that it's clickable, addressing feedback that the UI felt
    inert/unresponsive.
    """

    def __init__(self, rect: pygame.Rect, font: pygame.font.Font):
        self.rect = rect
        self.font = font
        self.hovered = False

    def update_hover(self, mouse_pos: tuple[int, int]) -> None:
        self.hovered = self.rect.collidepoint(mouse_pos)

    def draw(self, surface: pygame.Surface, label: str = "Advance  (Space)") -> None:
        bg = theme.ADVANCE_BUTTON_BG_HOVER if self.hovered else theme.ADVANCE_BUTTON_BG
        pygame.draw.rect(surface, bg, self.rect, border_radius=10)
        pygame.draw.rect(surface, theme.ACCENT_BRIGHT if self.hovered else theme.ACCENT,
                          self.rect, width=2, border_radius=10)
        label_surf = self.font.render(label, True, theme.ADVANCE_BUTTON_TEXT)
        surface.blit(label_surf, (
            self.rect.x + (self.rect.width - label_surf.get_width()) // 2,
            self.rect.y + (self.rect.height - label_surf.get_height()) // 2
        ))

    def is_clicked(self, point: tuple[int, int]) -> bool:
        return self.rect.collidepoint(point)


class RegionDetailPanel:
    """
    Shows stats for whichever region/platform the player last clicked on
    the map. This is what makes the map a real, clickable source of
    information rather than a decorative backdrop -- addressing feedback
    that the map felt static. Deliberately read-only: clicking a region
    inspects it, it does not act on it, keeping the player's only lever
    over the simulation as the trait economy (consistent with the
    project's existing, tested game-balance design).
    """

    def __init__(self, rect: pygame.Rect, font: pygame.font.Font, header_font: pygame.font.Font):
        self.rect = rect
        self.font = font
        self.header_font = header_font

    def draw(self, surface: pygame.Surface, region) -> None:
        pygame.draw.rect(surface, theme.PANEL_BG_RAISED, self.rect, border_radius=10)
        pygame.draw.rect(surface, theme.PANEL_BORDER, self.rect, width=2, border_radius=10)

        x, y = self.rect.x + 16, self.rect.y + 12

        if region is None:
            hint = self.font.render("Click a region on the map to inspect it.", True, theme.TEXT_SECONDARY)
            surface.blit(hint, (x, y))
            return

        node_kind = "Platform" if getattr(region, "node_type", "geographic") == "platform" else "Region"
        header = self.header_font.render(f"{region.name}  ({node_kind})", True, theme.ACCENT)
        surface.blit(header, (x, y))
        y += 30

        believing_pct = region.infection_ratio() * 100
        skeptical_pct = (region.skeptical / region.population * 100) if region.population else 0
        lines = [
            f"Population: {region.population:,}",
            f"Believing: {region.believing:,} ({believing_pct:.1f}%)",
        ]
        if region.exposed > 0:
            lines.append(f"Exposed (not yet believing): {region.exposed:,}")
        lines += [
            f"Skeptical: {region.skeptical:,} ({skeptical_pct:.1f}%)",
            f"Media-literacy resistance: {region.base_resistance:.2f}",
        ]
        multiplier = getattr(region, "correction_resistance_multiplier", 1.0)
        if multiplier != 1.0:
            lines.append(f"Correction resistance multiplier: {multiplier:.1f}x")
        lines.append(f"Connections: {len(region.connections)}")

        for line in lines:
            text_surf = self.font.render(line, True, theme.TEXT_PRIMARY)
            surface.blit(text_surf, (x, y))
            y += 22


class StrikeWarningPanel:
    """
    Shows the telegraphed countermeasure strike(s), if any are pending --
    the core new tension mechanic (see algorithm/strike_manager.py). This
    is deliberately the most visually urgent widget in the playing screen
    (bright orange-red, pulsing border) since its entire purpose is to
    make the player look up from the trait shop and react to a specific,
    nameable, time-limited threat.

    Once StrikeManager's Crackdown phase activates (multiple concurrent
    strikes possible), this panel shows EVERY pending strike, not just
    one -- the visual escalation that makes late-game genuinely feel
    different in kind (multiple simultaneous threats to prioritize
    between) rather than just a faster version of the same single threat.
    """

    def __init__(self, rect: pygame.Rect, font: pygame.font.Font, header_font: pygame.font.Font):
        self.rect = rect
        self.font = font
        self.header_font = header_font
        self._pulse_t = 0.0

    def update(self, dt_seconds: float) -> None:
        """Advances the pulse animation clock; call once per frame from the main loop."""
        self._pulse_t += dt_seconds

    def draw(self, surface: pygame.Surface, warnings: list[dict], strike_results: list[dict],
              is_crackdown: bool = False) -> None:
        pygame.draw.rect(surface, theme.PANEL_BG_RAISED, self.rect, border_radius=10)

        if not warnings and not strike_results:
            pygame.draw.rect(surface, theme.PANEL_BORDER, self.rect, width=2, border_radius=10)
            hint = self.font.render("No countermeasure strike currently threatened.", True, theme.TEXT_SECONDARY)
            surface.blit(hint, (self.rect.x + 16, self.rect.y + 16))
            return

        if strike_results:
            pygame.draw.rect(surface, theme.STRIKE_ALERT, self.rect, width=2, border_radius=10)
            header_text = "Strikes landed!" if len(strike_results) > 1 else "Strike landed!"
            header = self.header_font.render(header_text, True, theme.STRIKE_ALERT)
            surface.blit(header, (self.rect.x + 16, self.rect.y + 14))
            y = self.rect.y + 46
            for result in strike_results[:3]:   # cap at 3 lines to stay within the panel
                detail = self.font.render(
                    f"{result['removed']:,} believers corrected in {result['region_name']}.",
                    True, theme.TEXT_PRIMARY,
                )
                surface.blit(detail, (self.rect.x + 16, y))
                y += 22
            return

        # Pulsing border intensity (sine-wave-free, simple back-and-forth
        # via a triangle wave on _pulse_t) -- gives the warning a sense of
        # urgency without needing any image assets or external libraries.
        pulse = abs((self._pulse_t * 1.5) % 2.0 - 1.0)  # 0..1..0 triangle wave
        border_color = tuple(
            int(theme.STRIKE_ALERT_DIM[i] + (theme.STRIKE_ALERT[i] - theme.STRIKE_ALERT_DIM[i]) * pulse)
            for i in range(3)
        )
        pygame.draw.rect(surface, border_color, self.rect, width=3, border_radius=10)

        header_text = "CRACKDOWN — multiple strikes incoming!" if is_crackdown else "Countermeasure strike incoming!"
        header = self.header_font.render(header_text, True, theme.STRIKE_ALERT)
        surface.blit(header, (self.rect.x + 16, self.rect.y + 14))

        y = self.rect.y + 46
        for warning in warnings[:3]:   # cap at 3 lines to stay within the panel
            turns = warning["turns_remaining"]
            turn_word = "turn" if turns == 1 else "turns"
            detail = self.font.render(
                f"Target: {warning['region_name']}  —  impact in {turns} {turn_word}", True, theme.TEXT_PRIMARY,
            )
            surface.blit(detail, (self.rect.x + 16, y))
            y += 22


class _RingEffect:
    """An expanding, fading ring -- one-shot, removes itself once its lifetime elapses."""

    def __init__(self, center: tuple[int, int], color: tuple[int, int, int],
                 start_radius: float = 6, end_radius: float = 34, duration: float = 0.5):
        self.center = center
        self.color = color
        self.start_radius = start_radius
        self.end_radius = end_radius
        self.duration = duration
        self.age = 0.0

    def update(self, dt: float) -> bool:
        """Returns False once the effect has finished and should be removed."""
        self.age += dt
        return self.age < self.duration

    def draw(self, surface: pygame.Surface) -> None:
        t = min(1.0, self.age / self.duration)
        radius = self.start_radius + (self.end_radius - self.start_radius) * t
        alpha_fraction = 1.0 - t   # fades out as it expands
        width = max(1, int(3 * alpha_fraction) + 1)
        # Pygame's draw functions don't support per-shape alpha directly,
        # so the fade is approximated by blending the ring color toward
        # the panel background as it ages -- cheap and good enough for a
        # quick one-shot effect with no persistent state to manage.
        faded_color = tuple(
            int(theme.PANEL_BG[i] + (self.color[i] - theme.PANEL_BG[i]) * alpha_fraction)
            for i in range(3)
        )
        pygame.draw.circle(surface, faded_color, self.center, int(radius), width=width)


class _FloatingTextEffect:
    """Small text that rises and fades -- one-shot, removes itself once its lifetime elapses."""

    def __init__(self, position: tuple[int, int], text: str, color: tuple[int, int, int],
                 font: pygame.font.Font, duration: float = 0.9, rise_pixels: float = 28):
        self.position = position
        self.text = text
        self.color = color
        self.font = font
        self.duration = duration
        self.rise_pixels = rise_pixels
        self.age = 0.0

    def update(self, dt: float) -> bool:
        self.age += dt
        return self.age < self.duration

    def draw(self, surface: pygame.Surface) -> None:
        t = min(1.0, self.age / self.duration)
        alpha_fraction = 1.0 - t
        faded_color = tuple(
            int(theme.PANEL_BG[i] + (self.color[i] - theme.PANEL_BG[i]) * alpha_fraction)
            for i in range(3)
        )
        y_offset = -self.rise_pixels * t
        label = self.font.render(self.text, True, faded_color)
        surface.blit(label, (self.position[0] - label.get_width() // 2, self.position[1] + y_offset))


class EffectsLayer:
    """
    A generic, reusable container for short-lived visual feedback effects
    (ring pulses, floating text) -- the "juice" layer addressing feedback
    that player actions (buying a trait, advancing a turn) and game events
    (a strike landing) had no visible feedback beyond an instant, silent
    number change. Any part of main.py can call spawn_ring()/spawn_text()
    without needing to know how effects are stored or animated; this class
    owns that bookkeeping and self-prunes finished effects every frame.

    Deliberately built on simple primitives (circles, text, a linear/
    triangle-wave fade) rather than image assets or a particle library --
    consistent with the rest of this project's zero-asset-dependency
    approach (everything is drawn procedurally with pygame.draw and
    pygame.font), and easy to explain/defend in viva.

    DEFENSIVE CAP: max_effects bounds the list regardless of spawn rate or
    whether update() is being called on schedule. Found during testing --
    a headless test script that drove handle_events()/draw_playing()
    directly without ever calling the real run() loop's update() call
    accumulated 60+ effects with nothing ever expiring, since nothing was
    advancing their age. The real run() loop always calls update() every
    frame, so this shouldn't occur in normal play, but bounding it here
    means a stutter, an unusually fast click sequence during Crackdown's
    multi-strike bursts, or any future caller that forgets to call
    update() can't cause unbounded memory/render growth -- oldest effects
    are dropped first since they're closest to expiring anyway.
    """

    def __init__(self, font: pygame.font.Font, max_effects: int = 40):
        self.font = font
        self.max_effects = max_effects
        self._effects: list = []

    def spawn_ring(self, center: tuple[int, int], color: tuple[int, int, int], **kwargs) -> None:
        self._effects.append(_RingEffect(center, color, **kwargs))
        self._enforce_cap()

    def spawn_text(self, position: tuple[int, int], text: str, color: tuple[int, int, int], **kwargs) -> None:
        self._effects.append(_FloatingTextEffect(position, text, color, self.font, **kwargs))
        self._enforce_cap()

    def _enforce_cap(self) -> None:
        if len(self._effects) > self.max_effects:
            self._effects = self._effects[-self.max_effects:]

    def update(self, dt_seconds: float) -> None:
        self._effects = [e for e in self._effects if e.update(dt_seconds)]

    def draw(self, surface: pygame.Surface) -> None:
        for effect in self._effects:
            effect.draw(surface)

    def __len__(self) -> int:
        return len(self._effects)
