import pygame
from view import theme
from model.trait import Trait
from view.scrollable_panel_base import ScrollablePanel


def _lerp(c1, c2, t: float):
    t = max(0.0, min(1.0, t))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


class TraitButton:
    """Modern interactive trait upgrade card with level pips and cost badge."""

    TRAIT_ICONS = {
        "Visual Hook": "👁️",
        "Emotional Urgency": "⚡",
        "Platform Diversification": "🌐",
        "Correction Resistance": "🛡️",
    }

    def __init__(self, rect: pygame.Rect, trait: Trait):
        self.rect = rect
        self.trait = trait
        self.hovered = False
        # False until update_state() has confirmed this card is affordable.
        # update_state runs during draw, so a click arriving on a frame before
        # the first paint after a layout rebuild would otherwise see the old
        # default of True and read as a purchase.
        self.enabled = False
        self.level = 0
        self.next_cost = trait.cost

    def update_state(self, current_level: int, points_available: int, mouse_pos: tuple[int, int]) -> None:
        self.level = current_level
        self.next_cost = self.trait.next_cost(current_level)
        self.enabled = self.next_cost <= points_available
        self.hovered = self.rect.collidepoint(mouse_pos)

    def draw(self, surface: pygame.Surface, font: pygame.font.Font, small_font: pygame.font.Font) -> None:
        # Background
        if not self.enabled:
            bg = (16, 20, 30)
            border_col = (35, 45, 65)
        elif self.hovered:
            bg = theme.PANEL_BG_LIGHT
            border_col = theme.ACCENT_BRIGHT
        else:
            bg = theme.PANEL_BG_RAISED
            border_col = theme.PANEL_BORDER_BRIGHT

        pygame.draw.rect(surface, bg, self.rect, border_radius=8)
        pygame.draw.rect(surface, border_col, self.rect, width=1, border_radius=8)

        # Icon + Name
        icon = self.TRAIT_ICONS.get(self.trait.name, "🧬")
        name_text = f"{icon} {self.trait.name}"
        name_col = theme.TEXT_PRIMARY if self.enabled else theme.TEXT_MUTED
        name_surf = font.render(name_text, True, name_col)
        surface.blit(name_surf, (self.rect.x + 10, self.rect.y + 7))

        # Level Pips (●●○○○)
        max_display_pips = 5
        pip_x = self.rect.x + 12
        pip_y = self.rect.bottom - 12
        for i in range(max_display_pips):
            pip_col = theme.ACCENT if i < self.level else (40, 50, 70)
            pygame.draw.circle(surface, pip_col, (pip_x + i * 10, pip_y), 3)

        if self.level > 0:
            lvl_surf = small_font.render(f"Lv.{self.level}", True, theme.ACCENT if self.enabled else theme.TEXT_MUTED)
            surface.blit(lvl_surf, (pip_x + max_display_pips * 10 + 4, pip_y - 7))

        # Cost Badge
        cost_badge_w = 64
        cost_badge_h = 24
        cost_rect = pygame.Rect(self.rect.right - cost_badge_w - 8, self.rect.y + 11, cost_badge_w, cost_badge_h)
        badge_bg = (14, 116, 144) if (self.enabled and self.hovered) else ((20, 35, 50) if self.enabled else (25, 30, 42))
        badge_border = theme.ACCENT if self.enabled else (45, 55, 75)
        pygame.draw.rect(surface, badge_bg, cost_rect, border_radius=6)
        pygame.draw.rect(surface, badge_border, cost_rect, width=1, border_radius=6)

        cost_text = f"{self.next_cost} pts"
        cost_col = theme.TEXT_HIGHLIGHT if self.enabled else theme.TEXT_MUTED
        cost_surf = small_font.render(cost_text, True, cost_col)
        surface.blit(cost_surf, (
            cost_rect.x + (cost_rect.width - cost_surf.get_width()) // 2,
            cost_rect.y + (cost_rect.height - cost_surf.get_height()) // 2
        ))

    def is_clicked(self, point: tuple[int, int]) -> bool:
        return self.enabled and self.rect.collidepoint(point)


class StatsPanel:
    """Tactical overview panel displaying global progress metrics."""

    def __init__(self, rect: pygame.Rect, font: pygame.font.Font, header_font: pygame.font.Font):
        self.rect = rect
        self.font = font
        self.header_font = header_font

    def draw(self, surface: pygame.Surface, summary: dict, strain_name: str, model_name: str = "") -> None:
        pygame.draw.rect(surface, theme.PANEL_BG, self.rect, border_radius=12)
        pygame.draw.rect(surface, theme.PANEL_BORDER, self.rect, width=1, border_radius=12)

        # Header with badge
        x, y = self.rect.x + 16, self.rect.y + 12
        header_text = strain_name.upper()
        header = self.header_font.render(header_text, True, theme.ACCENT)
        surface.blit(header, (x, y))

        if model_name:
            model_badge = self.font.render(f"[{model_name}]", True, theme.TEXT_SECONDARY)
            surface.blit(model_badge, (self.rect.right - model_badge.get_width() - 16, y + 2))

        # Metrics Grid (2 columns)
        y += 32
        col1_x = self.rect.x + 16
        col2_x = self.rect.x + self.rect.width // 2 + 8

        inf_pct = summary["global_infection_ratio"] * 100
        inf_color = theme.COLOR_BELIEF if inf_pct > 30 else theme.ACCENT

        row1 = [
            ("⏱ Turns:", f"{summary['ticks']}", theme.TEXT_PRIMARY),
            ("🔴 Belief:", f"{inf_pct:.1f}%", inf_color),
        ]
        row2 = [
            ("👥 Believing:", f"{summary['total_believing']:,}", theme.TEXT_PRIMARY),
            ("🛡️ Skeptical:", f"{summary['total_skeptical']:,}", theme.COLOR_CURE),
        ]

        for i, (label, val, col) in enumerate(row1):
            cx = col1_x if i == 0 else col2_x
            l_surf = self.font.render(label, True, theme.TEXT_MUTED)
            v_surf = self.font.render(val, True, col)
            surface.blit(l_surf, (cx, y))
            surface.blit(v_surf, (cx + l_surf.get_width() + 6, y))

        y += 24
        for i, (label, val, col) in enumerate(row2):
            cx = col1_x if i == 0 else col2_x
            l_surf = self.font.render(label, True, theme.TEXT_MUTED)
            v_surf = self.font.render(val, True, col)
            surface.blit(l_surf, (cx, y))
            surface.blit(v_surf, (cx + l_surf.get_width() + 6, y))

        # Mini status footer if exposed exists
        if summary.get("total_exposed", 0) > 0:
            y += 22
            exp_surf = self.font.render(f"🟣 Latent / Exposed: {summary['total_exposed']:,}", True, theme.COLOR_EXPOSED)
            surface.blit(exp_surf, (col1_x, y))


class TraitPanel(ScrollablePanel):
    """Evolution & strategy center for unlocking rumor traits. Now supports scrolling."""

    def __init__(self, rect: pygame.Rect, font: pygame.font.Font, header_font: pygame.font.Font,
                 available_traits: list[Trait]):
        super().__init__(rect)
        self.font = font
        self.header_font = header_font
        self.available_traits = available_traits
        self.buttons: list[TraitButton] = []
        self._build_buttons()

    def _build_buttons(self) -> None:
        self.buttons = []
        x = self.rect.x + 14
        y_start = self.rect.y + self.header_height + 8
        btn_height = 42
        spacing = 8

        for i, trait in enumerate(self.available_traits):
            y = y_start + i * (btn_height + spacing)
            rect = pygame.Rect(x, y, self.rect.width - 28, btn_height)
            self.buttons.append(TraitButton(rect, trait))

        # Calculate total content height for scrolling
        total_height = len(self.available_traits) * (btn_height + spacing)
        self.update_scroll_bounds(total_height)

    def draw(self, surface: pygame.Surface, strain) -> None:
        mouse_pos = pygame.mouse.get_pos()
        content_rect = self.get_content_rect()

        # Draw panel background
        pygame.draw.rect(surface, theme.PANEL_BG, self.rect, border_radius=12)
        pygame.draw.rect(surface, theme.PANEL_BORDER, self.rect, width=1, border_radius=12)

        # Header + DNA Points Pill (fixed, not scrolled)
        header = self.header_font.render("TRAIT EVOLUTION", True, theme.TEXT_PRIMARY)
        surface.blit(header, (self.rect.x + 16, self.rect.y + 12))

        pts_text = f"🧬 {strain.points_available} PTS"
        pts_surf = self.font.render(pts_text, True, theme.ACCENT_BRIGHT)
        pts_rect = pygame.Rect(self.rect.right - pts_surf.get_width() - 24, self.rect.y + 10, pts_surf.get_width() + 14, 26)
        pygame.draw.rect(surface, (12, 45, 60), pts_rect, border_radius=6)
        pygame.draw.rect(surface, theme.ACCENT, pts_rect, width=1, border_radius=6)
        surface.blit(pts_surf, (pts_rect.x + 7, pts_rect.y + 3))

        # Hover only counts inside the scrollable area. Without this, pointing at
        # the fixed header highlights whichever card is scrolled underneath it.
        if content_rect.collidepoint(mouse_pos):
            adjusted_mouse = (mouse_pos[0], mouse_pos[1] + self.scroll_offset)
        else:
            adjusted_mouse = (-1, -1)

        # Clip to the content area so a partially-scrolled card is cut off at
        # the header edge instead of painting over it and out of the panel.
        previous_clip = surface.get_clip()
        surface.set_clip(content_rect)
        try:
            for button in self.buttons:
                current_lvl = strain.trait_level(button.trait)
                button.update_state(current_lvl, strain.points_available, adjusted_mouse)

                # Draw button with scroll offset applied
                scrolled_rect = button.rect.copy()
                scrolled_rect.y -= self.scroll_offset

                # Skip anything scrolled entirely out of view
                if scrolled_rect.bottom <= content_rect.top or scrolled_rect.top >= content_rect.bottom:
                    continue

                # Temporarily modify button rect for drawing
                original_rect = button.rect
                button.rect = scrolled_rect
                button.draw(surface, self.font, self.font)
                button.rect = original_rect
        finally:
            surface.set_clip(previous_clip)

        # Draw scroll indicator if scrollable
        if self.max_scroll > 0:
            indicator = self.font.render("↕", True, theme.TEXT_MUTED)
            surface.blit(indicator, (self.rect.right - 24, self.rect.y + 14))

    def handle_click(self, point: tuple[int, int]) -> Trait | None:
        # Button rects are stored in CONTENT space (unscrolled), so a screen
        # point anywhere in the window can coincidentally map onto one. Clicking
        # this panel's own header, or the news feed below it, used to buy
        # whichever trait happened to land there. Bound the hit test to the
        # panel's scrollable area first.
        if not self.get_content_rect().collidepoint(point):
            return None
        adjusted_point = self.adjust_point_for_scroll(point)
        for button in self.buttons:
            if button.is_clicked(adjusted_point):
                return button.trait
        return None


class NewsTicker:
    """Tactical mission feed displaying real-time simulation events."""

    TAG_COLORS = {
        "[CRACKDOWN]": theme.STRIKE_ALERT,
        "[ALERT]": theme.COLOR_WARNING,
        "[STRIKE]": theme.COLOR_DANGER,
        "[DATA]": theme.ACCENT,
    }

    def __init__(self, rect: pygame.Rect, font: pygame.font.Font, max_items: int = 5):
        self.rect = rect
        self.font = font
        self.max_items = max_items
        self.events: list[str] = []

    def push(self, message: str) -> None:
        self.events.insert(0, message)
        self.events = self.events[: self.max_items]

    def draw(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, theme.PANEL_BG, self.rect, border_radius=12)
        pygame.draw.rect(surface, theme.PANEL_BORDER, self.rect, width=1, border_radius=12)

        # Title
        hdr_surf = self.font.render("LIVE INTELLIGENCE FEED", True, theme.TEXT_MUTED)
        surface.blit(hdr_surf, (self.rect.x + 16, self.rect.y + 10))

        y = self.rect.y + 32
        for i, event in enumerate(self.events):
            # Format color by tag
            color = theme.TEXT_PRIMARY if i == 0 else theme.TEXT_SECONDARY
            for tag, tag_col in self.TAG_COLORS.items():
                if event.upper().startswith(tag):
                    color = tag_col
                    break

            text_surf = self.font.render(event, True, color)
            surface.blit(text_surf, (self.rect.x + 16, y))
            y += 18


class RaceBar:
    """Modern dual progress bar: Belief Contagion vs Countermeasure Defence."""

    def __init__(self, rect: pygame.Rect, font: pygame.font.Font, header_font: pygame.font.Font):
        self.rect = rect
        self.font = font
        self.header_font = header_font

    def draw(self, surface: pygame.Surface, belief_ratio: float, counter_strength: float,
              counter_cap: float, counter_active: bool) -> None:
        pygame.draw.rect(surface, theme.PANEL_BG, self.rect, border_radius=12)
        pygame.draw.rect(surface, theme.PANEL_BORDER, self.rect, width=1, border_radius=12)

        pad = 16
        label_y = self.rect.y + 8

        # Belief stats (left)
        b_pct = belief_ratio * 100
        b_text = f"🔴 RUMOR BELIEF {b_pct:.1f}%"
        belief_label = self.font.render(b_text, True, theme.COLOR_BELIEF)
        surface.blit(belief_label, (self.rect.x + pad, label_y))

        # Countermeasure stats (right)
        if counter_active:
            c_pct = (counter_strength / counter_cap * 100) if counter_cap > 0 else 0
            c_text = f"🛡️ FACT-CHECK DEFENCE {c_pct:.0f}%"
            c_col = theme.COLOR_CURE
        else:
            c_text = "🛡️ FACT-CHECK DEFENCE (DORMANT)"
            c_col = theme.TEXT_MUTED

        counter_label = self.font.render(c_text, True, c_col)
        surface.blit(counter_label, (self.rect.right - pad - counter_label.get_width(), label_y))

        # Progress bar
        bar_y = label_y + 24
        bar_height = 14
        bar_rect = pygame.Rect(self.rect.x + pad, bar_y, self.rect.width - pad * 2, bar_height)
        pygame.draw.rect(surface, theme.RACE_BAR_TRACK, bar_rect, border_radius=7)

        belief_fraction = max(0.0, min(1.0, belief_ratio))
        counter_fraction = max(0.0, min(1.0, counter_strength / counter_cap)) if counter_cap > 0 else 0.0

        belief_width = int(bar_rect.width * belief_fraction)
        counter_width = int(bar_rect.width * counter_fraction)

        if belief_width > 0:
            b_fill = pygame.Rect(bar_rect.x, bar_rect.y, belief_width, bar_height)
            pygame.draw.rect(surface, theme.COLOR_BELIEF, b_fill, border_radius=7)
        if counter_width > 0:
            c_fill = pygame.Rect(bar_rect.right - counter_width, bar_rect.y, counter_width, bar_height)
            pygame.draw.rect(surface, theme.COLOR_CURE, c_fill, border_radius=7)

        pygame.draw.rect(surface, theme.PANEL_BORDER, bar_rect, width=1, border_radius=7)


class AdvanceButton:
    """Tactical pulse advance button for player-paced simulation steps."""

    def __init__(self, rect: pygame.Rect, font: pygame.font.Font):
        self.rect = rect
        self.font = font
        self.hovered = False

    def update_hover(self, mouse_pos: tuple[int, int]) -> None:
        self.hovered = self.rect.collidepoint(mouse_pos)

    def draw(self, surface: pygame.Surface, label: str = "ADVANCE SIMULATION") -> None:
        bg = theme.ADVANCE_BUTTON_BG_HOVER if self.hovered else theme.ADVANCE_BUTTON_BG
        border_col = theme.ACCENT_BRIGHT if self.hovered else theme.ACCENT

        pygame.draw.rect(surface, bg, self.rect, border_radius=12)
        pygame.draw.rect(surface, border_col, self.rect, width=2, border_radius=12)

        # Title
        label_surf = self.font.render(f"▶  {label}", True, theme.ADVANCE_BUTTON_TEXT)
        surface.blit(label_surf, (
            self.rect.x + (self.rect.width - label_surf.get_width()) // 2,
            self.rect.y + 24
        ))

        # Keybind Hint
        hint_surf = self.font.render("[ SPACE / ENTER ]", True, (200, 240, 255))
        surface.blit(hint_surf, (
            self.rect.x + (self.rect.width - hint_surf.get_width()) // 2,
            self.rect.y + 56
        ))

    def is_clicked(self, point: tuple[int, int]) -> bool:
        return self.rect.collidepoint(point)


class RegionDetailPanel:
    """Detailed telemetry for selected territory or platform."""

    def __init__(self, rect: pygame.Rect, font: pygame.font.Font, header_font: pygame.font.Font):
        self.rect = rect
        self.font = font
        self.header_font = header_font

    def draw(self, surface: pygame.Surface, region) -> None:
        pygame.draw.rect(surface, theme.PANEL_BG, self.rect, border_radius=12)
        pygame.draw.rect(surface, theme.PANEL_BORDER, self.rect, width=1, border_radius=12)

        x, y = self.rect.x + 16, self.rect.y + 12

        if region is None:
            hint_title = self.header_font.render("TERRITORY TELEMETRY", True, theme.TEXT_MUTED)
            hint_sub = self.font.render("Click any region or platform node to inspect.", True, theme.TEXT_SECONDARY)
            surface.blit(hint_title, (x, y))
            surface.blit(hint_sub, (x, y + 36))
            return

        is_platform = getattr(region, "node_type", "geographic") == "platform"
        icon = "📱" if is_platform else "📍"
        header = self.header_font.render(f"{icon} {region.name}", True, theme.ACCENT)
        surface.blit(header, (x, y))
        y += 30

        believing_pct = region.infection_ratio() * 100
        skeptical_pct = (region.skeptical / region.population * 100) if region.population else 0

        # Mini distribution bar
        bar_w = self.rect.width - 32
        bar_h = 8
        pygame.draw.rect(surface, (30, 38, 52), (x, y, bar_w, bar_h), border_radius=4)
        b_w = int(bar_w * (region.believing / max(1, region.population)))
        s_w = int(bar_w * (region.skeptical / max(1, region.population)))
        if b_w > 0:
            pygame.draw.rect(surface, theme.COLOR_BELIEF, (x, y, b_w, bar_h), border_radius=4)
        if s_w > 0:
            pygame.draw.rect(surface, theme.COLOR_CURE, (x + bar_w - s_w, y, s_w, bar_h), border_radius=4)
        y += 16

        lines = [
            f"Population: {region.population:,}",
            f"Believing: {region.believing:,} ({believing_pct:.1f}%)",
            f"Skeptical: {region.skeptical:,} ({skeptical_pct:.1f}%)",
            f"Media Literacy: {region.base_resistance:.2f}",
        ]
        if region.exposed > 0:
            lines.insert(2, f"Latent Exposed: {region.exposed:,}")

        for line in lines:
            text_surf = self.font.render(line, True, theme.TEXT_PRIMARY)
            surface.blit(text_surf, (x, y))
            y += 20


class StrikeWarningPanel:
    """Tactical alert strip displaying upcoming telegraphed fact-checker strikes."""

    def __init__(self, rect: pygame.Rect, font: pygame.font.Font, header_font: pygame.font.Font):
        self.rect = rect
        self.font = font
        self.header_font = header_font
        self._pulse_t = 0.0

    def update(self, dt_seconds: float) -> None:
        self._pulse_t += dt_seconds

    def draw(self, surface: pygame.Surface, warnings: list[dict], strike_results: list[dict],
              is_crackdown: bool = False) -> None:
        pygame.draw.rect(surface, theme.PANEL_BG, self.rect, border_radius=12)

        if not warnings and not strike_results:
            pygame.draw.rect(surface, theme.PANEL_BORDER, self.rect, width=1, border_radius=12)
            calm_surf = self.font.render("🛡️ No imminent fact-checker strikes detected.", True, theme.TEXT_MUTED)
            surface.blit(calm_surf, (self.rect.x + 16, self.rect.y + 32))
            return

        # Pulsing warning border
        pulse = abs((self._pulse_t * 2.0) % 2.0 - 1.0)
        border_col = _lerp(theme.STRIKE_ALERT_DIM, theme.STRIKE_ALERT, pulse)
        pygame.draw.rect(surface, border_col, self.rect, width=2, border_radius=12)

        x, y = self.rect.x + 16, self.rect.y + 12
        if strike_results:
            hdr_text = "⚡ STRIKE LANDED — FACT-CHECK IMPACT!"
            hdr_surf = self.header_font.render(hdr_text, True, theme.COLOR_DANGER)
            surface.blit(hdr_surf, (x, y))
            y += 28
            for res in strike_results[:2]:
                detail = self.font.render(
                    f"• {res['removed']:,} believers corrected in {res['region_name']}",
                    True, theme.TEXT_PRIMARY
                )
                surface.blit(detail, (x, y))
                y += 20
            return

        hdr_text = "⚠️ [CRACKDOWN] MULTIPLE STRIKES MOBILIZING!" if is_crackdown else "⚠️ FACT-CHECKER STRIKE TELEGRAPHED!"
        hdr_surf = self.header_font.render(hdr_text, True, theme.STRIKE_ALERT)
        surface.blit(hdr_surf, (x, y))
        y += 28

        for w in warnings[:2]:
            turns = w["turns_remaining"]
            turn_str = "1 turn" if turns == 1 else f"{turns} turns"
            detail = self.font.render(
                f"• Target: {w['region_name']}  —  Impact in: {turn_str}",
                True, theme.TEXT_PRIMARY
            )
            surface.blit(detail, (x, y))
            y += 20


class _RingEffect:
    def __init__(self, center: tuple[int, int], color: tuple[int, int, int],
                 start_radius: float = 6, end_radius: float = 34, duration: float = 0.5):
        self.center = center
        self.color = color
        self.start_radius = start_radius
        self.end_radius = end_radius
        self.duration = duration
        self.age = 0.0

    def update(self, dt: float) -> bool:
        self.age += dt
        return self.age < self.duration

    def draw(self, surface: pygame.Surface) -> None:
        t = min(1.0, self.age / self.duration)
        radius = self.start_radius + (self.end_radius - self.start_radius) * t
        alpha_fraction = 1.0 - t
        width = max(1, int(3 * alpha_fraction) + 1)
        faded_color = tuple(
            int(theme.PANEL_BG[i] + (self.color[i] - theme.PANEL_BG[i]) * alpha_fraction)
            for i in range(3)
        )
        pygame.draw.circle(surface, faded_color, self.center, int(radius), width=width)


class _FloatingTextEffect:
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
    """Juice layer for smooth visual feedback."""

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
