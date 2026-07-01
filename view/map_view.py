import pygame
from model.region import Region
from model.world_graph import WorldGraph
from view import theme


def _lerp_color(c1, c2, t: float):
    t = max(0.0, min(1.0, t))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def _infection_color(ratio: float):
    if ratio < 0.5:
        return _lerp_color(theme.REGION_LOW, theme.REGION_MID, ratio / 0.5)
    return _lerp_color(theme.REGION_MID, theme.REGION_HIGH, (ratio - 0.5) / 0.5)


class MapView:
    def __init__(self, rect: pygame.Rect, font: pygame.font.Font, small_font: pygame.font.Font):
        self.rect = rect
        self.font = font
        self.small_font = small_font
        self.hovered_region: Region | None = None

    def _node_radius(self, region: Region, max_population: int) -> int:
        # Scale node size relative to the LARGEST population currently on
        # the map (passed in by draw()/region_at_point(), computed fresh
        # from world.regions each call) rather than a fixed constant. This
        # keeps size variation meaningful across very different map scales
        # -- the original Nepal province map (populations in the hundreds),
        # the world map (populations in the thousands, platform "reach"
        # pools potentially even larger), and arbitrary custom CSV data --
        # without every node maxing out at the same radius on larger maps.
        if max_population <= 0:
            return theme.NODE_RADIUS_MIN
        pop_fraction = min(1.0, region.population / max_population)
        return int(theme.NODE_RADIUS_MIN + (theme.NODE_RADIUS_MAX - theme.NODE_RADIUS_MIN) * pop_fraction)

    def screen_pos(self, region: Region) -> tuple[int, int]:
        return (self.rect.x + region.x, self.rect.y + region.y)

    def _is_platform(self, region: Region) -> bool:
        return getattr(region, "node_type", "geographic") == "platform"

    def _draw_node_shape(self, surface: pygame.Surface, region: Region, pos: tuple[int, int],
                          radius: int, color, border_width: int = 2) -> None:
        """Circle for geographic regions, rounded square for platform nodes."""
        if self._is_platform(region):
            rect = pygame.Rect(pos[0] - radius, pos[1] - radius, radius * 2, radius * 2)
            pygame.draw.rect(surface, color, rect, border_radius=6)
            pygame.draw.rect(surface, theme.PANEL_BORDER, rect, width=border_width, border_radius=6)
        else:
            pygame.draw.circle(surface, color, pos, radius)
            pygame.draw.circle(surface, theme.PANEL_BORDER, pos, radius, width=border_width)

    def _draw_overlay_ring(self, surface: pygame.Surface, region: Region, pos: tuple[int, int],
                            radius: int, color, width: int) -> None:
        """Ring overlay for circles, rect outline overlay for squares -- same visual language, different shape."""
        if self._is_platform(region):
            rect = pygame.Rect(pos[0] - radius, pos[1] - radius, radius * 2, radius * 2)
            pygame.draw.rect(surface, color, rect, width=width, border_radius=6)
        else:
            pygame.draw.circle(surface, color, pos, radius, width=width)

    def draw(self, surface: pygame.Surface, world: WorldGraph, focus_region: Region | None = None) -> None:
        # Panel background for the map area
        pygame.draw.rect(surface, theme.PANEL_BG, self.rect, border_radius=10)
        pygame.draw.rect(surface, theme.PANEL_BORDER, self.rect, width=2, border_radius=10)

        max_population = max((r.population for r in world.regions), default=0)

        drawn_edges = set()
        for region in world.regions:
            p1 = self.screen_pos(region)
            for neighbor in region.connections:
                edge_key = frozenset((region.name, neighbor.name))
                if edge_key in drawn_edges:
                    continue
                drawn_edges.add(edge_key)
                p2 = self.screen_pos(neighbor)
                is_focus_edge = focus_region in (region, neighbor) and focus_region is not None
                color = theme.EDGE_HIGHLIGHT if is_focus_edge else theme.EDGE_COLOR
                width = 3 if is_focus_edge else 1
                pygame.draw.line(surface, color, p1, p2, width)

        for region in world.regions:
            pos = self.screen_pos(region)
            radius = self._node_radius(region, max_population)
            ratio = region.infection_ratio()
            color = _infection_color(ratio)

            self._draw_node_shape(surface, region, pos, radius, color)

            # Exposed overlay ring (SEIR only -- stays at 0 and draws nothing under SIR)
            if region.exposed > 0:
                exposed_ratio = region.exposed_ratio()
                self._draw_overlay_ring(surface, region, pos, radius + 2,
                                         theme.REGION_EXPOSED_OVERLAY, max(2, int(4 * exposed_ratio)))

            # Skeptical overlay ring -- shows correction progress visually
            if region.skeptical > 0:
                skeptical_ratio = region.skeptical / region.population if region.population else 0
                self._draw_overlay_ring(surface, region, pos, radius + 4,
                                         theme.REGION_SKEPTICAL_OVERLAY, max(2, int(4 * skeptical_ratio)))

            # Highlight ring if this is the AI's current focus
            if region is focus_region:
                self._draw_overlay_ring(surface, region, pos, radius + 8, theme.TEXT_WARNING, 2)

            label = self.small_font.render(region.name, True, theme.TEXT_PRIMARY)
            surface.blit(label, (pos[0] - label.get_width() // 2, pos[1] + radius + 6))

    def region_at_point(self, world: WorldGraph, point: tuple[int, int]) -> Region | None:
        """Hit-test: which region (if any) contains the given screen point."""
        max_population = max((r.population for r in world.regions), default=0)
        for region in world.regions:
            pos = self.screen_pos(region)
            radius = self._node_radius(region, max_population)
            if self._is_platform(region):
                # Square hit-test
                if (pos[0] - radius <= point[0] <= pos[0] + radius and
                        pos[1] - radius <= point[1] <= pos[1] + radius):
                    return region
            else:
                dx, dy = point[0] - pos[0], point[1] - pos[1]
                if dx * dx + dy * dy <= radius * radius:
                    return region
        return None