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