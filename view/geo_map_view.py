import pygame
from model.region import Region
from model.world_graph import WorldGraph
from model import geo_data
from view import theme


def _lerp_color(c1, c2, t: float):
    t = max(0.0, min(1.0, t))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def _infection_color(ratio: float):
    if ratio < 0.5:
        return _lerp_color(theme.REGION_LOW, theme.REGION_MID, ratio / 0.5)
    return _lerp_color(theme.REGION_MID, theme.REGION_HIGH, (ratio - 0.5) / 0.5)


def _point_in_polygon(point: tuple[float, float], polygon: list[list[float]]) -> bool:
    """Standard ray-casting point-in-polygon test, used for real-shape hit-testing."""
    x, y = point
    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside


class GeoMapView:
    ZOOM_WORLD = "world"
    ZOOM_NEPAL = "nepal"

    def __init__(self, rect: pygame.Rect, font: pygame.font.Font, small_font: pygame.font.Font):
        self.rect = rect
        self.font = font
        self.small_font = small_font
        self.zoom_level = self.ZOOM_WORLD

        world_geo = geo_data.load_world_countries()
        self._world_bounds = (world_geo["bounds_lon"], world_geo["bounds_lat"])
        nepal_geo = geo_data.load_nepal_districts()
        self._nepal_bounds = (nepal_geo["bounds_lon"], nepal_geo["bounds_lat"])

    # ---- Projection helpers ----

    PLATFORM_COLUMN_WIDTH = 110   # reserved right-hand strip, world view only

    def _project_world(self, nx: float, ny: float) -> tuple[float, float]:
        """
        Project a 0-1 normalized world coordinate onto screen space,
        preserving real aspect ratio. Reserves PLATFORM_COLUMN_WIDTH on
        the right edge so the map geography never extends into the
        platform-node column and the two can't visually overlap (a real
        bug found during testing: Australia and the Encrypted Messaging
        platform square collided at this panel's aspect ratio before this
        reservation was added).
        """
        lon_range = self._world_bounds[0][1] - self._world_bounds[0][0]
        lat_range = self._world_bounds[1][1] - self._world_bounds[1][0]
        aspect = lat_range / lon_range
        usable_w = self.rect.width - 40 - self.PLATFORM_COLUMN_WIDTH
        usable_h = usable_w * aspect
        if usable_h > self.rect.height - 40:
            usable_h = self.rect.height - 40
            usable_w = usable_h / aspect
        ox = self.rect.x + 20
        oy = self.rect.y + 20
        return (ox + nx * usable_w, oy + ny * usable_h)

    def _project_nepal(self, nx: float, ny: float) -> tuple[float, float]:
        lon_range = self._nepal_bounds[0][1] - self._nepal_bounds[0][0]
        lat_range = self._nepal_bounds[1][1] - self._nepal_bounds[1][0]
        aspect = lat_range / lon_range
        usable_w = self.rect.width - 40
        usable_h = usable_w * aspect
        if usable_h > self.rect.height - 40:
            usable_h = self.rect.height - 40
            usable_w = usable_h / aspect
        ox = self.rect.x + (self.rect.width - usable_w) / 2
        oy = self.rect.y + 20
        return (ox + nx * usable_w, oy + ny * usable_h)

    # ---- Lookup helpers: map model Region/PlatformNode objects to geo names ----

    def _platform_nodes(self, world: WorldGraph) -> list[Region]:
        return [r for r in world.regions if getattr(r, "node_type", "geographic") == "platform"]

    def set_zoom(self, level: str) -> None:
        if level in (self.ZOOM_WORLD, self.ZOOM_NEPAL):
            self.zoom_level = level

    def screen_pos(self, world: WorldGraph, region: Region) -> tuple[int, int] | None:
        """
        Returns the current screen position a given region/platform is
        rendered at, or None if it isn't visible at the current zoom
        level (e.g. a province during world zoom, before zooming in).
        Used by main.py to anchor visual effects (ring pulses, floating
        text) to "wherever this region currently is," without main.py
        needing to know anything about projection math or zoom state.
        """
        if getattr(region, "node_type", "geographic") == "platform":
            if self.zoom_level != self.ZOOM_WORLD:
                return None
            platforms = self._platform_nodes(world)
            if region not in platforms:
                return None
            col_x = self.rect.right - self.PLATFORM_COLUMN_WIDTH / 2 - 10
            spacing = (self.rect.height - 40) / max(1, len(platforms))
            i = platforms.index(region)
            return (col_x, self.rect.y + 30 + i * spacing)

        if self.zoom_level == self.ZOOM_WORLD:
            centroids = geo_data.load_world_country_centroids()
            if region.name not in centroids:
                return None
            nx, ny = centroids[region.name]
            return self._project_world(nx, ny)
        else:
            centroids = geo_data.load_nepal_province_centroids()
            if region.name in centroids:
                nx, ny = centroids[region.name]
                return self._project_nepal(nx, ny)
            # Country-level "Nepal" region (zoomed in from the world map,
            # no real per-province data -- see _draw_nepal's docstring):
            # anchor effects to the panel's visual center instead.
            if region.name == "Nepal":
                return (self.rect.x + self.rect.width // 2, self.rect.y + self.rect.height // 2)
            return None

    # ---- Drawing ----

    def draw(self, surface: pygame.Surface, world: WorldGraph, focus_region: Region | None = None,
              selected_region: Region | None = None, hovered_region: Region | None = None) -> None:
        pygame.draw.rect(surface, theme.PANEL_BG, self.rect, border_radius=10)
        pygame.draw.rect(surface, theme.PANEL_BORDER, self.rect, width=2, border_radius=10)

        if self.zoom_level == self.ZOOM_WORLD:
            self._draw_world(surface, world, focus_region, selected_region, hovered_region)
        else:
            self._draw_nepal(surface, world, focus_region, selected_region, hovered_region)

    def _draw_world(self, surface, world, focus_region, selected_region, hovered_region):
        countries_geo = geo_data.load_world_countries()["countries"]
        by_name = {r.name: r for r in world.regions}

        for country_name, outline in countries_geo.items():
            region = by_name.get(country_name)
            points = [self._project_world(x, y) for x, y in outline]
            if len(points) < 3:
                continue

            ratio = region.infection_ratio() if region else 0.0
            color = _infection_color(ratio)
            pygame.draw.polygon(surface, color, points)
            pygame.draw.polygon(surface, theme.PANEL_BORDER, points, width=1)

            if region is not None:
                self._draw_marker_and_overlays(surface, region, points, focus_region, selected_region, hovered_region)
                label = self.small_font.render(region.name, True, theme.TEXT_PRIMARY)
                cx = sum(p[0] for p in points) / len(points)
                cy = sum(p[1] for p in points) / len(points)
                surface.blit(label, (cx - label.get_width() // 2, cy - label.get_height() // 2))

        self._draw_platform_column(surface, world, focus_region, selected_region, hovered_region)

    def _draw_nepal(self, surface, world, focus_region, selected_region, hovered_region):
        """
        Renders Nepal's district outlines. Two distinct data situations,
        both handled correctly here:
          1. Playing the NEPAL MAP itself: world.regions contains real
             province-level Region objects ("Bagmati", "Koshi", etc.) --
             each district is colored by ITS OWN province's real belief
             ratio, exactly as granular as the simulation actually is.
          2. Zoomed in FROM THE WORLD MAP (clicked on Nepal-the-country):
             world.regions has no province-level data at all, only a
             single "Nepal" country Region. There is no real per-province
             belief data to show in this situation -- the simulation
             genuinely only tracks Nepal as one node here. Rather than
             silently default every district to a misleading 0% (which
             would look like "no belief in Nepal" even when the country
             is heavily infected), every district is colored by NEPAL'S
             OWN country-level ratio, honestly representing what the
             simulation actually knows: one number for the whole country,
             visually spread across its districts for geographic context.
             This is a deliberate, named simplification -- not real
             district-level granularity -- worth stating explicitly if
             you discuss this feature in your report.
        """
        nepal_geo = geo_data.load_nepal_districts()["districts"]
        by_name = {r.name: r for r in world.regions}

        has_province_level_data = any(
            province in by_name for province in {"Bagmati", "Koshi", "Madhesh", "Gandaki", "Lumbini", "Karnali", "Sudurpashchim"}
        )
        nepal_country_region = by_name.get("Nepal") if not has_province_level_data else None

        for district_name, info in nepal_geo.items():
            province_name = info["province"]
            if has_province_level_data:
                region = by_name.get(province_name)
            else:
                region = nepal_country_region
            points = [self._project_nepal(x, y) for x, y in info["outline"]]
            if len(points) < 3:
                continue

            ratio = region.infection_ratio() if region else 0.0
            color = _infection_color(ratio)
            pygame.draw.polygon(surface, color, points)
            pygame.draw.polygon(surface, theme.PANEL_BORDER, points, width=1)

        if not has_province_level_data:
            # No real per-province markers to draw in this situation --
            # just label the country-level region once, centered, and
            # skip the per-province marker loop entirely (it would have
            # nothing real to attach to).
            if nepal_country_region is not None:
                cx = self.rect.x + self.rect.width // 2
                cy = self.rect.y + 16
                label = self.font.render(
                    f"{nepal_country_region.name} — {nepal_country_region.infection_ratio()*100:.1f}% belief "
                    f"(country-level data; districts shown for geographic context only)",
                    True, theme.TEXT_SECONDARY,
                )
                surface.blit(label, (cx - label.get_width() // 2, cy))
            return

        # Province-level markers + overlays + labels drawn once per province
        # (not per district) at the province's real centroid.
        centroids = geo_data.load_nepal_province_centroids()
        for province_name, (nx, ny) in centroids.items():
            region = by_name.get(province_name)
            if region is None:
                continue
            pos = self._project_nepal(nx, ny)
            self._draw_marker_and_overlays(surface, region, None, focus_region, selected_region, hovered_region, center=pos)
            label = self.small_font.render(region.name, True, theme.TEXT_PRIMARY)
            surface.blit(label, (pos[0] - label.get_width() // 2, pos[1] + 10))

    def _draw_platform_column(self, surface, world, focus_region, selected_region, hovered_region):
        platforms = self._platform_nodes(world)
        if not platforms:
            return
        col_x = self.rect.right - self.PLATFORM_COLUMN_WIDTH / 2 - 10
        spacing = (self.rect.height - 40) / max(1, len(platforms))
        for i, platform in enumerate(platforms):
            cy = self.rect.y + 30 + i * spacing
            pos = (col_x, cy)
            radius = 20
            ratio = platform.infection_ratio()
            color = _infection_color(ratio)
            rect = pygame.Rect(pos[0] - radius, pos[1] - radius, radius * 2, radius * 2)
            pygame.draw.rect(surface, color, rect, border_radius=6)
            pygame.draw.rect(surface, theme.PANEL_BORDER, rect, width=2, border_radius=6)
            self._draw_marker_and_overlays(surface, platform, None, focus_region, selected_region, hovered_region, center=pos, base_radius=radius)
            label = self.small_font.render(platform.name, True, theme.TEXT_PRIMARY)
            surface.blit(label, (pos[0] - label.get_width() // 2, pos[1] + radius + 6))

    def _draw_marker_and_overlays(self, surface, region, polygon_points, focus_region,
                                    selected_region, hovered_region, center=None, base_radius=5):
        """
        Small, deliberately unobtrusive marker at the region's center (a
        thin ring, not a filled shape) plus the existing overlay rings
        (exposed/skeptical/focus/selection) -- all drawn AT THE SAME small
        scale so they don't dominate the real geographic shape underneath.
        """
        if center is None:
            if not polygon_points:
                return
            center = (sum(p[0] for p in polygon_points) / len(polygon_points),
                       sum(p[1] for p in polygon_points) / len(polygon_points))

        pygame.draw.circle(surface, theme.PANEL_BORDER, center, base_radius, width=1)

        if region.exposed > 0:
            exposed_ratio = region.exposed_ratio()
            pygame.draw.circle(surface, theme.REGION_EXPOSED_OVERLAY, center,
                                base_radius + 3, width=max(1, int(3 * exposed_ratio)))
        if region.skeptical > 0:
            skeptical_ratio = region.skeptical / region.population if region.population else 0
            pygame.draw.circle(surface, theme.REGION_SKEPTICAL_OVERLAY, center,
                                base_radius + 6, width=max(1, int(3 * skeptical_ratio)))
        if region is focus_region:
            pygame.draw.circle(surface, theme.TEXT_WARNING, center, base_radius + 9, width=2)
        if region is selected_region:
            pygame.draw.circle(surface, theme.REGION_SELECTED_OUTLINE, center, base_radius + 12, width=2)
        elif region is hovered_region:
            pygame.draw.circle(surface, theme.REGION_HOVER_OUTLINE, center, base_radius + 12, width=1)

    # ---- Hit-testing ----

    def region_at_point(self, world: WorldGraph, point: tuple[int, int]) -> Region | None:
        if self.zoom_level == self.ZOOM_WORLD:
            return self._region_at_point_world(world, point)
        return self._region_at_point_nepal(world, point)

    def _region_at_point_world(self, world, point):
        by_name = {r.name: r for r in world.regions}

        # Platform column first (small fixed squares, checked by simple
        # bounding box rather than polygon containment).
        platforms = self._platform_nodes(world)
        if platforms:
            col_x = self.rect.right - self.PLATFORM_COLUMN_WIDTH / 2 - 10
            spacing = (self.rect.height - 40) / max(1, len(platforms))
            for i, platform in enumerate(platforms):
                cy = self.rect.y + 30 + i * spacing
                if abs(point[0] - col_x) <= 20 and abs(point[1] - cy) <= 20:
                    return platform

        countries_geo = geo_data.load_world_countries()["countries"]
        for country_name, outline in countries_geo.items():
            region = by_name.get(country_name)
            if region is None:
                continue
            points = [self._project_world(x, y) for x, y in outline]
            if _point_in_polygon(point, points):
                return region
        return None

    def _region_at_point_nepal(self, world, point):
        by_name = {r.name: r for r in world.regions}
        has_province_level_data = any(
            province in by_name for province in {"Bagmati", "Koshi", "Madhesh", "Gandaki", "Lumbini", "Karnali", "Sudurpashchim"}
        )
        nepal_geo = geo_data.load_nepal_districts()["districts"]
        for district_name, info in nepal_geo.items():
            points = [self._project_nepal(x, y) for x, y in info["outline"]]
            if _point_in_polygon(point, points):
                if has_province_level_data:
                    return by_name.get(info["province"])
                return by_name.get("Nepal")
        return None

    def country_at_point_is_nepal(self, point: tuple[int, int]) -> bool:
        """Used by main.py to decide whether a click at world-zoom should trigger zooming into Nepal."""
        if self.zoom_level != self.ZOOM_WORLD:
            return False
        countries_geo = geo_data.load_world_countries()["countries"]
        nepal_outline = countries_geo.get("Nepal")
        if nepal_outline is None:
            return False
        points = [self._project_world(x, y) for x, y in nepal_outline]
        return _point_in_polygon(point, points)
