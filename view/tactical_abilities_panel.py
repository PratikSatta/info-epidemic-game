"""
Tactical Abilities Panel for Active Player Powers

Displays cooldown-based tactical abilities that the player can activate
mid-game to gain strategic advantages against fact-checker countermeasures.

Abilities:
1. Bot Amplification Surge - Global transmission rate boost
2. Echo Chamber Silo - Targeted region believability increase
3. Sensationalist Blitz - Immediate mass conversion pulse
"""

import pygame
from view import theme
from view.scrollable_panel_base import ScrollablePanel


class AbilityButton:
    """Individual tactical ability card with cooldown tracking and cost display."""

    ABILITY_ICONS = {
        "bot_surge": "🤖",
        "echo_chamber": "🔊",
        "sensationalist_blitz": "⚡",
    }

    ABILITY_NAMES = {
        "bot_surge": "Bot Amplification",
        "echo_chamber": "Echo Chamber",
        "sensationalist_blitz": "Sensationalist Blitz",
    }

    ABILITY_DESCRIPTIONS = {
        "bot_surge": "+30% transmission for 3 turns",
        "echo_chamber": "+50% internal spread (select region)",
        "sensationalist_blitz": "+10% instant conversion globally",
    }

    def __init__(self, rect: pygame.Rect, ability_key: str, cost: int, cooldown_max: int):
        self.rect = rect
        self.ability_key = ability_key
        self.cost = cost
        self.cooldown_max = cooldown_max
        self.cooldown_remaining = 0
        self.hovered = False
        # Set here, not only in update_state: update_state runs during draw, and
        # a click can be processed on a frame before the first draw after a
        # layout rebuild. is_clicked() reads this attribute, so leaving it unset
        # meant click-before-first-paint raised AttributeError.
        self.enabled = False

    def update_state(self, cooldown: int, points_available: int, mouse_pos: tuple[int, int]) -> None:
        self.cooldown_remaining = cooldown
        self.enabled = cooldown == 0 and points_available >= self.cost
        self.hovered = self.rect.collidepoint(mouse_pos)

    def draw(self, surface: pygame.Surface, font: pygame.font.Font, small_font: pygame.font.Font) -> None:
        # Background
        if self.cooldown_remaining > 0:
            bg = (20, 25, 35)
            border_col = (40, 50, 70)
        elif not self.enabled:
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
        icon = self.ABILITY_ICONS.get(self.ability_key, "⚙️")
        name = self.ABILITY_NAMES.get(self.ability_key, self.ability_key)
        name_text = f"{icon} {name}"

        if self.cooldown_remaining > 0:
            name_col = theme.TEXT_MUTED
        elif self.enabled:
            name_col = theme.TEXT_PRIMARY
        else:
            name_col = theme.TEXT_MUTED

        name_surf = font.render(name_text, True, name_col)
        surface.blit(name_surf, (self.rect.x + 10, self.rect.y + 8))

        # Description
        desc = self.ABILITY_DESCRIPTIONS.get(self.ability_key, "")
        desc_col = theme.TEXT_SECONDARY if self.enabled else theme.TEXT_MUTED
        desc_surf = small_font.render(desc, True, desc_col)
        surface.blit(desc_surf, (self.rect.x + 10, self.rect.y + 30))

        # Cooldown overlay or cost badge
        if self.cooldown_remaining > 0:
            cooldown_text = f"🕒 {self.cooldown_remaining}T"
            cd_surf = font.render(cooldown_text, True, theme.COLOR_WARNING)
            surface.blit(cd_surf, (self.rect.right - cd_surf.get_width() - 10, self.rect.y + 12))
        else:
            # Cost badge
            cost_badge_w = 64
            cost_badge_h = 24
            cost_rect = pygame.Rect(self.rect.right - cost_badge_w - 8, self.rect.y + 11, cost_badge_w, cost_badge_h)
            badge_bg = (14, 116, 144) if (self.enabled and self.hovered) else ((20, 35, 50) if self.enabled else (25, 30, 42))
            badge_border = theme.ACCENT if self.enabled else (45, 55, 75)
            pygame.draw.rect(surface, badge_bg, cost_rect, border_radius=6)
            pygame.draw.rect(surface, badge_border, cost_rect, width=1, border_radius=6)

            cost_text = f"{self.cost} pts"
            cost_col = theme.TEXT_HIGHLIGHT if self.enabled else theme.TEXT_MUTED
            cost_surf = small_font.render(cost_text, True, cost_col)
            surface.blit(cost_surf, (
                cost_rect.x + (cost_rect.width - cost_surf.get_width()) // 2,
                cost_rect.y + (cost_rect.height - cost_surf.get_height()) // 2
            ))

    def is_clicked(self, point: tuple[int, int]) -> bool:
        return self.enabled and self.rect.collidepoint(point)


class TacticalAbilitiesPanel(ScrollablePanel):
    """
    Panel displaying three active tactical abilities the player can trigger
    with cooldowns and point costs for mid-game strategic advantages.
    Now supports scrolling when content exceeds panel height.
    """

    def __init__(self, rect: pygame.Rect, font: pygame.font.Font, header_font: pygame.font.Font):
        super().__init__(rect)
        self.font = font
        self.header_font = header_font
        self.buttons: list[AbilityButton] = []
        self._build_buttons()

    def _build_buttons(self) -> None:
        """Build ability button layout (3 cards stacked vertically for scrolling)."""
        self.buttons = []
        btn_w = self.rect.width - 28
        btn_h = 56
        x = self.rect.x + 14
        y_start = self.rect.y + self.header_height + 8

        abilities = [
            ("bot_surge", 15, 8),
            ("echo_chamber", 20, 10),
            ("sensationalist_blitz", 12, 6),
        ]

        for i, (key, cost, cooldown_max) in enumerate(abilities):
            btn_rect = pygame.Rect(x, y_start + i * (btn_h + 8), btn_w, btn_h)
            self.buttons.append(AbilityButton(btn_rect, key, cost, cooldown_max))

        # Calculate total content height for scrolling
        total_height = len(abilities) * (btn_h + 8)
        self.update_scroll_bounds(total_height)

    def draw(self, surface: pygame.Surface, engine) -> None:
        """Draw the panel with all ability buttons, clipped with scroll."""
        mouse_pos = pygame.mouse.get_pos()
        content_rect = self.get_content_rect()

        # Draw panel background
        pygame.draw.rect(surface, theme.PANEL_BG, self.rect, border_radius=12)
        pygame.draw.rect(surface, theme.PANEL_BORDER, self.rect, width=1, border_radius=12)

        # Header (fixed, not scrolled)
        header = self.header_font.render("⚡ TACTICAL POWERS", True, theme.TEXT_PRIMARY)
        surface.blit(header, (self.rect.x + 16, self.rect.y + 12))

        # Hover only counts inside the scrollable area. Without this, pointing at
        # the fixed header lights up whichever card is scrolled underneath it.
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
                ability_state = engine.active_abilities.get(button.ability_key, {})
                cooldown = ability_state.get("cooldown", 0)
                button.update_state(cooldown, engine.strain.points_available, adjusted_mouse)

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

    def handle_click(self, point: tuple[int, int]) -> str | None:
        """Returns the ability key if a button was clicked, None otherwise."""
        # Button rects are stored in CONTENT space (unscrolled), so a screen
        # point anywhere in the window can coincidentally map onto one. Clicking
        # the trait panel's header, a few pixels below this panel, used to fire
        # whichever ability happened to land there. Bound the hit test to the
        # panel's own scrollable area first.
        if not self.get_content_rect().collidepoint(point):
            return None
        adjusted_point = self.adjust_point_for_scroll(point)
        for button in self.buttons:
            if button.is_clicked(adjusted_point):
                return button.ability_key
        return None
