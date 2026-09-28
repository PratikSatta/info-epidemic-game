import pygame
from model.region import Region
from model.world_graph import WorldGraph
from model import geo_data
from view import theme


def _lerp_color(c1, c2, t: float):
    t = max(0.0, min(1.0, t))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def _infection_color(ratio: float):
    if ratio < 0.05:
        return theme.REGION_LOW
    elif ratio < 0.5:
        return _lerp_color(theme.REGION_LOW, theme.REGION_MID, ratio / 0.5)
    return _lerp_color(theme.REGION_MID, theme.REGION_HIGH, (ratio - 0.5) / 0.5)


def _point_in_polygon(point: tuple[float, float], polygon: list[list[float]]) -> bool:
    """Standard ray-casting point-in-polygon test."""
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

    # Scroll-wheel zoom limits
    _MIN_ZOOM = 1.0
    _MAX_ZOOM = 12.0
    _ZOOM_STEP = 0.20

    PLATFORM_COLUMN_WIDTH = 120

    def __init__(self, rect: pygame.Rect, font: pygame.font.Font, small_font: pygame.font.Font):
        self.rect = rect
        self.font = font
        self.small_font = small_font
        self.zoom_level = self.ZOOM_WORLD

        world_geo = geo_data.load_world_countries()
        self._world_bounds = (world_geo["bounds_lon"], world_geo["bounds_lat"])
        nepal_geo = geo_data.load_nepal_districts()
        self._nepal_bounds = (nepal_geo["bounds_lon"], nepal_geo["bounds_lat"])

        # Scroll-wheel zoom + pan state (world view only)
        self._zoom: float = 1.0          # current zoom multiplier
        self._pan_x: float = 0.0         # pan offset in screen pixels
        self._pan_y: float = 0.0
        self._dragging: bool = False
        self._drag_start: tuple[int, int] = (0, 0)
        self._pan_start: tuple[float, float] = (0.0, 0.0)

        # On-screen navigation buttons. Positioned by _layout_nav_buttons(),
        # which the rect setter calls -- see the property below.
        self._layout_nav_buttons()
        self._last_mouse_pos = (0, 0)

    # ── Layout ─────────────────────────────────────────────────────────────

    @property
    def rect(self) -> pygame.Rect:
        return self._rect

    @rect.setter
    def rect(self, value: pygame.Rect) -> None:
        """
        Reposition the view.

        main.py moves the map by assigning a new rect on every layout pass
        (startup, window resize, fullscreen toggle). The zoom buttons are
        positioned relative to that rect, so they must be recomputed here.

        They used to be built once in __init__, from the 100x100 placeholder
        rect the view is constructed with and which _rebuild_layout() is the
        only thing to correct. The result was zoom controls drawn over the race
        bar at the top-left of the window, while their clickable areas sat at
        that same wrong place -- invisible in the map where the player would
        look for them, but still live.
        """
        self._rect = value
        self._layout_nav_buttons()

    def _layout_nav_buttons(self) -> None:
        btn_y = self._rect.y + 14
        self.btn_zoom_in = pygame.Rect(self._rect.x + 16, btn_y, 28, 28)
        self.btn_zoom_out = pygame.Rect(self._rect.x + 48, btn_y, 28, 28)
        self.btn_reset = pygame.Rect(self._rect.x + 80, btn_y, 28, 28)

    # ── Projection helpers ──────────────────────────────────────────────────

    def _base_world_rect(self) -> tuple[float, float, float, float]:
        """
        Returns (ox, oy, usable_w, usable_h) — un-zoomed/un-panned map
        rect fitting inside self.rect minus platform column.
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
        oy = self.rect.y + (self.rect.height - usable_h) / 2
        return ox, oy, usable_w, usable_h

    def _project_world(self, nx: float, ny: float) -> tuple[float, float]:
        """Project 0-1 normalized world coordinates to screen space with zoom/pan."""
        ox, oy, usable_w, usable_h = self._base_world_rect()
        sx = ox + nx * usable_w * self._zoom + self._pan_x
        sy = oy + ny * usable_h * self._zoom + self._pan_y
        return (sx, sy)

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
        oy = self.rect.y + (self.rect.height - usable_h) / 2
        return (ox + nx * usable_w, oy + ny * usable_h)

    # ── Zoom / pan event handling ──────────────────────────────────────────

    def handle_scroll(self, mouse_pos: tuple[int, int], dy: int) -> None:
        """Zooms centred on mouse cursor in world view."""
        if self.zoom_level != self.ZOOM_WORLD:
            return
        if not self.rect.collidepoint(mouse_pos):
            return

        old_zoom = self._zoom
        factor = 1.0 + self._ZOOM_STEP * abs(dy)
        if dy > 0:
            new_zoom = min(self._MAX_ZOOM, old_zoom * factor)
        else:
            new_zoom = max(self._MIN_ZOOM, old_zoom / factor)

        if new_zoom == old_zoom:
            return

        mx, my = mouse_pos
        ox, oy, _, _ = self._base_world_rect()
        base_x = mx - ox - self._pan_x
        base_y = my - oy - self._pan_y
        scale_ratio = new_zoom / old_zoom
        self._pan_x = mx - ox - base_x * scale_ratio
        self._pan_y = my - oy - base_y * scale_ratio
        self._zoom = new_zoom
        self._clamp_pan()

    def zoom_in(self) -> None:
        center = self.rect.center
        self.handle_scroll(center, 1)

    def zoom_out(self) -> None:
        center = self.rect.center
        self.handle_scroll(center, -1)

    def handle_mousedown(self, pos: tuple[int, int]) -> bool:
        """Handle button click or start drag."""
        if self.btn_zoom_in.collidepoint(pos):
            self.zoom_in()
            return True
        if self.btn_zoom_out.collidepoint(pos):
            self.zoom_out()
            return True
        if self.btn_reset.collidepoint(pos):
            self.reset_zoom()
            return True

        if self.zoom_level == self.ZOOM_WORLD and self._zoom > 1.0:
            self._dragging = True
            self._drag_start = pos
            self._pan_start = (self._pan_x, self._pan_y)
        return False

    def handle_mouseup(self) -> None:
        self._dragging = False

    def handle_mousemove(self, pos: tuple[int, int]) -> None:
        self._last_mouse_pos = pos
        if self._dragging:
            dx = pos[0] - self._drag_start[0]
            dy = pos[1] - self._drag_start[1]
            self._pan_x = self._pan_start[0] + dx
            self._pan_y = self._pan_start[1] + dy
            self._clamp_pan()

    def _clamp_pan(self) -> None:
        _, _, usable_w, usable_h = self._base_world_rect()
        map_w = usable_w * self._zoom
        map_h = usable_h * self._zoom
        max_pan_x = map_w * 0.5
        min_pan_x = -(map_w - usable_w) - map_w * 0.5
        max_pan_y = map_h * 0.5
        min_pan_y = -(map_h - usable_h) - map_h * 0.5
        self._pan_x = max(min_pan_x, min(max_pan_x, self._pan_x))
        self._pan_y = max(min_pan_y, min(max_pan_y, self._pan_y))

    def reset_zoom(self) -> None:
        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0

    def set_zoom(self, level: str) -> None:
        if level in (self.ZOOM_WORLD, self.ZOOM_NEPAL):
            self.zoom_level = level

    # ── Screen position helper ─────────────────────────────────────────────

    def _platform_nodes(self, world: WorldGraph) -> list[Region]:
        return [r for r in world.regions if getattr(r, "node_type", "geographic") == "platform"]

    def screen_pos(self, world: WorldGraph, region: Region) -> tuple[int, int] | None:
        if getattr(region, "node_type", "geographic") == "platform":
            if self.zoom_level != self.ZOOM_WORLD:
                return None
            platforms = self._platform_nodes(world)
            if region not in platforms:
                return None
            col_x = self.rect.right - self.PLATFORM_COLUMN_WIDTH / 2 - 10
            spacing = (self.rect.height - 50) / max(1, len(platforms))
            i = platforms.index(region)
            return (int(col_x), int(self.rect.y + 45 + i * spacing + 15))

        if self.zoom_level == self.ZOOM_WORLD:
            centroids = geo_data.load_world_country_centroids()
            if region.name not in centroids:
                return None
            nx, ny = centroids[region.name]
            pos = self._project_world(nx, ny)
            return (int(pos[0]), int(pos[1]))
        else:
            centroids = geo_data.load_nepal_province_centroids()
            if region.name in centroids:
                nx, ny = centroids[region.name]
                pos = self._project_nepal(nx, ny)
                return (int(pos[0]), int(pos[1]))
            if region.name == "Nepal":
                return (self.rect.x + self.rect.width // 2, self.rect.y + self.rect.height // 2)
            return None

    # ── Drawing ────────────────────────────────────────────────────────────

    def draw(self, surface: pygame.Surface, world: WorldGraph,
             focus_region: Region | None = None, selected_region: Region | None = None,
             hovered_region: Region | None = None) -> None:
        # 1. Base Map Frame
        pygame.draw.rect(surface, theme.PANEL_BG, self.rect, border_radius=12)
        pygame.draw.rect(surface, theme.PANEL_BORDER, self.rect, width=2, border_radius=12)

        # 2. Clip all drawing inside map viewport
        clip = surface.get_clip()
        surface.set_clip(self.rect)

        if self.zoom_level == self.ZOOM_WORLD:
            self._draw_world(surface, world, focus_region, selected_region, hovered_region)
            self._draw_platform_column(surface, world, focus_region, selected_region, hovered_region)
        else:
            self._draw_nepal(surface, world, focus_region, selected_region, hovered_region)

        # 3. Floating HUD / Controls Overlay (drawn inside clip)
        self._draw_map_hud(surface, world, hovered_region)

        surface.set_clip(clip)

    def _draw_world(self, surface: pygame.Surface, world: WorldGraph,
                    focus_region: Region | None, selected_region: Region | None,
                    hovered_region: Region | None):
        countries_geo = geo_data.load_world_countries()["countries"]
        centroids = geo_data.load_world_country_centroids()
        by_name = {r.name: r for r in world.regions}

        # First pass: Render country polygon fills
        for country_name, outline in countries_geo.items():
            points = [self._project_world(x, y) for x, y in outline]
            if len(points) < 3:
                continue

            region = by_name.get(country_name)
            is_hover = (region is hovered_region) and (region is not None)
            is_select = (region is selected_region) and (region is not None)
            is_focus = (region is focus_region) and (region is not None)

            if region:
                ratio = region.infection_ratio()
                base_col = _infection_color(ratio)
                if is_hover:
                    fill_color = tuple(min(255, c + 35) for c in base_col)
                else:
                    fill_color = base_col
            else:
                fill_color = theme.REGION_UNINVOLVED

            pygame.draw.polygon(surface, fill_color, points)

            # Draw borders
            if is_select:
                pygame.draw.polygon(surface, theme.REGION_SELECTED_OUTLINE, points, width=2)
            elif is_focus:
                pygame.draw.polygon(surface, theme.STRIKE_ALERT, points, width=2)
            elif is_hover:
                pygame.draw.polygon(surface, theme.REGION_HOVER_OUTLINE, points, width=2)
            else:
                border_col = (70, 85, 115) if region else theme.REGION_UNINVOLVED_BORDER
                pygame.draw.polygon(surface, border_col, points, width=1)

        # Second pass: ONLY when zoomed in (zoom >= 2.5x), render clean country labels and markers
        if self._zoom >= 2.5:
            for country_name, (nx, ny) in centroids.items():
                region = by_name.get(country_name)
                if not region:
                    continue
                pos = self._project_world(nx, ny)
                # Check if on-screen
                if not self.rect.collidepoint(pos):
                    continue

                # Clean small label pill
                label_surf = self.small_font.render(country_name, True, theme.TEXT_PRIMARY)
                lx = int(pos[0] - label_surf.get_width() // 2)
                ly = int(pos[1] - label_surf.get_height() // 2)

                pill_rect = pygame.Rect(lx - 4, ly - 2, label_surf.get_width() + 8, label_surf.get_height() + 4)
                pygame.draw.rect(surface, (12, 16, 24, 200), pill_rect, border_radius=4)
                pygame.draw.rect(surface, theme.PANEL_BORDER, pill_rect, width=1, border_radius=4)
                surface.blit(label_surf, (lx, ly))

    def _draw_nepal(self, surface: pygame.Surface, world: WorldGraph,
                    focus_region: Region | None, selected_region: Region | None,
                    hovered_region: Region | None):
        nepal_geo = geo_data.load_nepal_districts()["districts"]
        by_name = {r.name: r for r in world.regions}

        has_province_level_data = any(
            province in by_name for province in
            {"Bagmati", "Koshi", "Madhesh", "Gandaki", "Lumbini", "Karnali", "Sudurpashchim"}
        )
        nepal_country_region = by_name.get("Nepal") if not has_province_level_data else None

        for info in nepal_geo.values():
            province_name = info["province"]
            region = by_name.get(province_name) if has_province_level_data else nepal_country_region
            points = [self._project_nepal(x, y) for x, y in info["outline"]]
            if len(points) < 3:
                continue

            is_hover = (region is hovered_region) and (region is not None)
            is_select = (region is selected_region) and (region is not None)
            is_focus = (region is focus_region) and (region is not None)

            ratio = region.infection_ratio() if region else 0.0
            base_col = _infection_color(ratio)
            fill_color = tuple(min(255, c + 30) for c in base_col) if is_hover else base_col

            pygame.draw.polygon(surface, fill_color, points)

            if is_select:
                pygame.draw.polygon(surface, theme.REGION_SELECTED_OUTLINE, points, width=2)
            elif is_focus:
                pygame.draw.polygon(surface, theme.STRIKE_ALERT, points, width=2)
            elif is_hover:
                pygame.draw.polygon(surface, theme.REGION_HOVER_OUTLINE, points, width=2)
            else:
                pygame.draw.polygon(surface, (45, 60, 85), points, width=1)

        # Province labels (clean pills on province centers)
        if has_province_level_data:
            centroids = geo_data.load_nepal_province_centroids()
            for province_name, (nx, ny) in centroids.items():
                region = by_name.get(province_name)
                if region is None:
                    continue
                pos = self._project_nepal(nx, ny)
                label_text = f"{region.name} ({region.infection_ratio()*100:.0f}%)"
                label_surf = self.small_font.render(label_text, True, theme.TEXT_PRIMARY)
                lx = int(pos[0] - label_surf.get_width() // 2)
                ly = int(pos[1] - label_surf.get_height() // 2)
                pill_rect = pygame.Rect(lx - 5, ly - 3, label_surf.get_width() + 10, label_surf.get_height() + 6)
                pygame.draw.rect(surface, (16, 22, 34), pill_rect, border_radius=4)
                pygame.draw.rect(surface, theme.PANEL_BORDER, pill_rect, width=1, border_radius=4)
                surface.blit(label_surf, (lx, ly))

    def _draw_platform_column(self, surface: pygame.Surface, world: WorldGraph,
                              focus_region: Region | None, selected_region: Region | None,
                              hovered_region: Region | None):
        platforms = self._platform_nodes(world)
        if not platforms:
            return

        col_rect = pygame.Rect(
            self.rect.right - self.PLATFORM_COLUMN_WIDTH - 12,
            self.rect.y + 12,
            self.PLATFORM_COLUMN_WIDTH,
            self.rect.height - 24
        )
        pygame.draw.rect(surface, (15, 20, 30), col_rect, border_radius=8)
        pygame.draw.rect(surface, theme.PANEL_BORDER, col_rect, width=1, border_radius=8)

        # Header
        hdr = self.small_font.render("NETWORKS", True, theme.TEXT_SECONDARY)
        surface.blit(hdr, (col_rect.x + (col_rect.width - hdr.get_width()) // 2, col_rect.y + 8))

        spacing = (col_rect.height - 40) / max(1, len(platforms))
        icons = {
            "Public Social Media": "📱",
            "Short-Video Platforms": "📹",
            "Encrypted Messaging": "🔒",
            "Close Group Chats": "👥",
        }

        for i, platform in enumerate(platforms):
            card_y = int(col_rect.y + 32 + i * spacing)
            card_rect = pygame.Rect(col_rect.x + 6, card_y, col_rect.width - 12, int(spacing - 8))

            is_hover = platform is hovered_region
            is_select = platform is selected_region
            is_focus = platform is focus_region

            bg = theme.PANEL_BG_RAISED if is_hover else theme.PANEL_BG
            pygame.draw.rect(surface, bg, card_rect, border_radius=6)

            border_col = theme.REGION_SELECTED_OUTLINE if is_select else (
                theme.STRIKE_ALERT if is_focus else (
                    theme.REGION_HOVER_OUTLINE if is_hover else theme.PANEL_BORDER
                )
            )
            pygame.draw.rect(surface, border_col, card_rect, width=2 if (is_hover or is_select) else 1, border_radius=6)

            # Icon + Name
            short_name = platform.name.split()[0]
            icon = icons.get(platform.name, "🌐")
            name_surf = self.small_font.render(f"{icon} {short_name}", True, theme.TEXT_PRIMARY)
            surface.blit(name_surf, (card_rect.x + 6, card_rect.y + 6))

            # Mini infection progress bar
            ratio = platform.infection_ratio()
            bar_rect = pygame.Rect(card_rect.x + 6, card_rect.bottom - 12, card_rect.width - 12, 6)
            pygame.draw.rect(surface, (30, 38, 52), bar_rect, border_radius=3)
            fill_w = int(bar_rect.width * ratio)
            if fill_w > 0:
                fill_rect = pygame.Rect(bar_rect.x, bar_rect.y, fill_w, bar_rect.height)
                pygame.draw.rect(surface, _infection_color(ratio), fill_rect, border_radius=3)

            # Percentage text
            pct_surf = self.small_font.render(f"{ratio*100:.0f}%", True, theme.TEXT_SECONDARY)
            surface.blit(pct_surf, (card_rect.right - pct_surf.get_width() - 6, card_rect.y + 6))

    def _draw_map_hud(self, surface: pygame.Surface, world: WorldGraph, hovered_region: Region | None):
        """Draws clean tactical on-screen controls, mode badge, and hover tooltip."""
        # 1. Navigation Buttons (Top-Left)
        for btn, label in [(self.btn_zoom_in, "+"), (self.btn_zoom_out, "-"), (self.btn_reset, "⟲")]:
            is_btn_hover = btn.collidepoint(self._last_mouse_pos)
            btn_bg = theme.PANEL_BG_RAISED if is_btn_hover else theme.PANEL_BG
            pygame.draw.rect(surface, btn_bg, btn, border_radius=6)
            pygame.draw.rect(surface, theme.ACCENT if is_btn_hover else theme.PANEL_BORDER, btn, width=1, border_radius=6)
            t_surf = self.small_font.render(label, True, theme.ACCENT_BRIGHT if is_btn_hover else theme.TEXT_PRIMARY)
            surface.blit(t_surf, (btn.x + (btn.width - t_surf.get_width()) // 2, btn.y + (btn.height - t_surf.get_height()) // 2))

        # 2. Mode Badge & Hints (Top Center-Left)
        mode_text = "🌍 GLOBAL OUTBREAK" if self.zoom_level == self.ZOOM_WORLD else "🇳🇵 NEPAL PROVINCES"
        badge_surf = self.small_font.render(mode_text, True, theme.ACCENT)
        badge_rect = pygame.Rect(self.rect.x + 120, self.rect.y + 14, badge_surf.get_width() + 16, 28)
        pygame.draw.rect(surface, (16, 22, 34), badge_rect, border_radius=6)
        pygame.draw.rect(surface, theme.PANEL_BORDER, badge_rect, width=1, border_radius=6)
        surface.blit(badge_surf, (badge_rect.x + 8, badge_rect.y + (badge_rect.height - badge_surf.get_height()) // 2))

        # Hint text
        if self.zoom_level == self.ZOOM_WORLD:
            hint_text = "Scroll to Zoom · Click Nepal to drill in · Right-drag to pan"
        else:
            hint_text = "Backspace / ESC to return to World View"
        hint_surf = self.small_font.render(hint_text, True, theme.TEXT_MUTED)
        surface.blit(hint_surf, (self.rect.x + 16, self.rect.bottom - hint_surf.get_height() - 10))

        # 3. Mini Heatmap Legend (Bottom Right of map)
        legend_x = self.rect.right - 280 if self.zoom_level == self.ZOOM_NEPAL else self.rect.right - self.PLATFORM_COLUMN_WIDTH - 200
        legend_y = self.rect.bottom - 26
        legend_w, legend_h = 100, 8
        pygame.draw.rect(surface, (20, 26, 38), (legend_x - 40, legend_y - 4, 220, 20), border_radius=4)
        for i in range(legend_w):
            ratio = i / legend_w
            col = _infection_color(ratio)
            pygame.draw.line(surface, col, (legend_x + i, legend_y), (legend_x + i, legend_y + legend_h))
        lbl_s = self.small_font.render("0%", True, theme.TEXT_MUTED)
        lbl_e = self.small_font.render("100%", True, theme.TEXT_MUTED)
        surface.blit(lbl_s, (legend_x - lbl_s.get_width() - 4, legend_y - 2))
        surface.blit(lbl_e, (legend_x + legend_w + 4, legend_y - 2))

        # 4. Floating HUD Tooltip when hovering over a region
        if hovered_region:
            mx, my = self._last_mouse_pos
            if self.rect.collidepoint((mx, my)):
                tip_w, tip_h = 190, 72
                tip_x = mx + 16
                tip_y = my + 16
                # Boundary clamping
                if tip_x + tip_w > self.rect.right - 10:
                    tip_x = mx - tip_w - 10
                if tip_y + tip_h > self.rect.bottom - 10:
                    tip_y = my - tip_h - 10

                tip_rect = pygame.Rect(tip_x, tip_y, tip_w, tip_h)
                pygame.draw.rect(surface, (14, 18, 28), tip_rect, border_radius=8)
                pygame.draw.rect(surface, theme.ACCENT, tip_rect, width=1, border_radius=8)

                # Territory Title
                kind_icon = "📱" if getattr(hovered_region, "node_type", "geographic") == "platform" else "📍"
                title_surf = self.small_font.render(f"{kind_icon} {hovered_region.name}", True, theme.TEXT_PRIMARY)
                surface.blit(title_surf, (tip_x + 8, tip_y + 8))

                # Infection & Population
                ratio = hovered_region.infection_ratio()
                inf_col = _infection_color(ratio)
                ratio_surf = self.small_font.render(f"Belief: {ratio*100:.1f}%", True, inf_col)
                surface.blit(ratio_surf, (tip_x + 8, tip_y + 28))

                pop_surf = self.small_font.render(f"Pop: {hovered_region.population:,}", True, theme.TEXT_SECONDARY)
                surface.blit(pop_surf, (tip_x + 8, tip_y + 48))

    # ── Hit-testing ────────────────────────────────────────────────────────

    def region_at_point(self, world: WorldGraph, point: tuple[int, int]) -> Region | None:
        if self.zoom_level == self.ZOOM_WORLD:
            return self._region_at_point_world(world, point)
        return self._region_at_point_nepal(world, point)

    def _region_at_point_world(self, world, point):
        # 1. Check Platform nodes
        platforms = self._platform_nodes(world)
        if platforms:
            col_rect = pygame.Rect(
                self.rect.right - self.PLATFORM_COLUMN_WIDTH - 12,
                self.rect.y + 12,
                self.PLATFORM_COLUMN_WIDTH,
                self.rect.height - 24
            )
            if col_rect.collidepoint(point):
                spacing = (col_rect.height - 40) / max(1, len(platforms))
                for i, platform in enumerate(platforms):
                    card_y = int(col_rect.y + 32 + i * spacing)
                    card_rect = pygame.Rect(col_rect.x + 6, card_y, col_rect.width - 12, int(spacing - 8))
                    if card_rect.collidepoint(point):
                        return platform

        # 2. Check Countries
        by_name = {r.name: r for r in world.regions}
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
            province in by_name for province in
            {"Bagmati", "Koshi", "Madhesh", "Gandaki", "Lumbini", "Karnali", "Sudurpashchim"}
        )
        nepal_geo = geo_data.load_nepal_districts()["districts"]
        for info in nepal_geo.values():
            points = [self._project_nepal(x, y) for x, y in info["outline"]]
            if _point_in_polygon(point, points):
                if has_province_level_data:
                    return by_name.get(info["province"])
                return by_name.get("Nepal")
        return None

    def country_at_point_is_nepal(self, point: tuple[int, int]) -> bool:
        if self.zoom_level != self.ZOOM_WORLD:
            return False
        countries_geo = geo_data.load_world_countries()["countries"]
        nepal_outline = countries_geo.get("Nepal")
        if nepal_outline is None:
            return False
        points = [self._project_world(x, y) for x, y in nepal_outline]
        return _point_in_polygon(point, points)
