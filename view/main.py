import sys
import os
import pygame

from model.region import Region
from model.world_graph import WorldGraph
from model.countermeasure import CounterMeasure
from model.trait import VisualTrait, EmotionalTrait, PlatformTrait, ResistanceTrait
from model.real_world_data import build_province_layout
from model.world_map_data import build_global_world
from model.scenarios import default_unverified_rumor, earthquake_rumor_scenario
from model.csv_loader import build_world_from_csv, build_strain_from_csv, CSVLoadError

from algorithm.spread_model import SIRSpreadModel, SEIRSpreadModel
from algorithm.counter_ai import GreedyCounterAI

from controller.game_engine import GameEngine, GameState

from view import theme
from view.geo_map_view import GeoMapView
from view.map_view import MapView
from view.ui_panels import (
    StatsPanel, TraitPanel, NewsTicker, RaceBar, AdvanceButton,
    RegionDetailPanel, StrikeWarningPanel, EffectsLayer
)
from view.analytics_modal import AnalyticsModal
from view.tactical_abilities_panel import TacticalAbilitiesPanel


STATE_MENU = "menu"
STATE_PLAYING = "playing"
STATE_GAME_OVER = "game_over"

CUSTOM_REGIONS_CSV_PATH = "data/regions_example.csv"
CUSTOM_STRAIN_CSV_PATH = "data/strain_config_example.csv"

MEDIA_LITERACY_TIPS = [
    "Check who is sharing the claim, not just what it says — is the source identifiable and credible?",
    "Slow down before resharing during emergencies — disaster-context rumors spread fastest and verify slowest.",
    "Search for the same claim on an established fact-checking site before trusting or sharing it.",
    "Be extra cautious of content designed to trigger strong emotion — that's often a deliberate spread tactic.",
]


def build_world() -> WorldGraph:
    world = WorldGraph()
    layout = build_province_layout()

    regions = {}
    for province, data in layout.items():
        regions[province] = Region(
            province,
            population=data["population"],
            x=data["x"],
            y=data["y"],
            base_resistance=data["base_resistance"],
        )
        world.add_region(regions[province])

    regions["Sudurpashchim"].connect(regions["Karnali"], 0.5)
    regions["Karnali"].connect(regions["Lumbini"], 0.4)
    regions["Karnali"].connect(regions["Gandaki"], 0.3)
    regions["Lumbini"].connect(regions["Gandaki"], 0.5)
    regions["Gandaki"].connect(regions["Bagmati"], 0.6)
    regions["Lumbini"].connect(regions["Madhesh"], 0.4)
    regions["Bagmati"].connect(regions["Madhesh"], 0.5)
    regions["Bagmati"].connect(regions["Koshi"], 0.5)
    regions["Madhesh"].connect(regions["Koshi"], 0.4)

    return world


def build_trait_catalog() -> list:
    return [VisualTrait(), EmotionalTrait(), PlatformTrait(), ResistanceTrait()]


class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("InfoSpread Simulator - Tactical Command")

        # Start in windowed mode with resizable window
        self.windowed_size = (theme.DEFAULT_WINDOW_WIDTH, theme.DEFAULT_WINDOW_HEIGHT)
        self.screen = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)
        self.fullscreen = False
        self.clock = pygame.time.Clock()

        self.font_title = pygame.font.SysFont(theme.FONT_NAME, theme.FONT_SIZE_TITLE, bold=True)
        self.font_header = pygame.font.SysFont(theme.FONT_NAME, theme.FONT_SIZE_HEADER, bold=True)
        self.font_body = pygame.font.SysFont(theme.FONT_NAME, theme.FONT_SIZE_BODY)
        self.font_small = pygame.font.SysFont(theme.FONT_NAME, theme.FONT_SIZE_SMALL)

        self.state = STATE_MENU
        self.selected_model_name = "SIR"
        self.selected_scenario_name = "default"
        self.use_custom_data = False
        self.selected_map_name = "nepal"
        self.custom_data_available = (
            os.path.exists(CUSTOM_REGIONS_CSV_PATH) and os.path.exists(CUSTOM_STRAIN_CSV_PATH)
        )

        self.selected_region = None
        self.hovered_region = None
        self.effects = EffectsLayer(self.font_small)

        self._build_game()
        self._rebuild_layout()

    def _get_current_window_size(self) -> tuple[int, int]:
        """Get current window dimensions."""
        return self.screen.get_size()

    def _rebuild_layout(self) -> None:
        """Rebuild all UI panel rectangles based on current window size."""
        w, h = self._get_current_window_size()

        # Update theme dimensions
        theme.WINDOW_WIDTH = w
        theme.WINDOW_HEIGHT = h

        # Responsive margins - scale with window size
        margin = max(12, int(w * 0.012))  # 1.2% margin, min 12px

        # Left panel width (map area) - 60% of window width
        left_w = int(w * 0.60)

        # Right panel width - remaining space minus margins
        right_w = w - left_w - margin * 3

        # Menu clickable option rects (rebuilt for menu state)
        self.opt_rect_model = pygame.Rect(w // 2 - 380, int(h * 0.18), 360, 52)
        self.opt_rect_scenario = pygame.Rect(w // 2 + 20, int(h * 0.18), 360, 52)
        self.opt_rect_map = pygame.Rect(w // 2 - 380, int(h * 0.25), 360, 52)
        self.opt_rect_data = pygame.Rect(w // 2 + 20, int(h * 0.25), 360, 52)
        self.btn_launch_menu = pygame.Rect(w // 2 - 180, int(h * 0.33), 360, 56)
        self.btn_play_again = pygame.Rect(w // 2 - 140, int(h * 0.68), 280, 48)

        # Playing state layout - MUCH MORE SPACE FOR ABILITIES AND TRAITS
        # Top section
        race_bar_h = max(50, int(h * 0.065))  # Race bar
        map_top = margin * 2 + race_bar_h
        strike_h = max(80, int(h * 0.10))  # Strike panel at bottom
        map_h = h - map_top - strike_h - margin * 2  # Map fills the rest

        race_bar_rect = pygame.Rect(margin, margin, left_w, race_bar_h)
        map_rect = pygame.Rect(margin, map_top, left_w, map_h)
        strike_rect = pygame.Rect(margin, map_rect.bottom + margin, left_w, strike_h)

        # Right panel heights - GENEROUS SIZING
        right_x = left_w + margin * 2
        current_y = margin

        # Stats panel - compact
        stats_h = max(100, int(h * 0.12))
        stats_rect = pygame.Rect(right_x, current_y, right_w, stats_h)
        current_y = stats_rect.bottom + margin

        # Detail panel - medium
        detail_h = max(120, int(h * 0.14))
        detail_rect = pygame.Rect(right_x, current_y, right_w, detail_h)
        current_y = detail_rect.bottom + margin

        # Tactical Abilities - LARGE (3 buttons stacked vertically with room to breathe)
        abilities_h = max(180, int(h * 0.20))
        abilities_rect = pygame.Rect(right_x, current_y, right_w, abilities_h)
        current_y = abilities_rect.bottom + margin

        # Trait Evolution - LARGE (4 trait cards with full visibility)
        trait_h = max(200, int(h * 0.22))
        trait_rect = pygame.Rect(right_x, current_y, right_w, trait_h)
        current_y = trait_rect.bottom + margin

        # News ticker - medium
        news_h = max(100, int(h * 0.12))
        news_rect = pygame.Rect(right_x, current_y, right_w, news_h)
        current_y = news_rect.bottom + margin

        # Advance button - use remaining space
        advance_h = max(80, h - current_y - margin)
        advance_rect = pygame.Rect(right_x, current_y, right_w, advance_h)

        # Analytics Modal (86% of screen, centered)
        modal_w = int(w * 0.86)
        modal_h = int(h * 0.88)
        modal_rect = pygame.Rect(
            (w - modal_w) // 2,
            (h - modal_h) // 2,
            modal_w,
            modal_h
        )

        # Rebuild all panels
        self.race_bar = RaceBar(race_bar_rect, self.font_body, self.font_header)

        if hasattr(self, 'map_view'):
            self.map_view.rect = map_rect

        self.strike_panel = StrikeWarningPanel(strike_rect, self.font_body, self.font_header)
        self.stats_panel = StatsPanel(stats_rect, self.font_body, self.font_header)
        self.detail_panel = RegionDetailPanel(detail_rect, self.font_body, self.font_header)
        self.abilities_panel = TacticalAbilitiesPanel(abilities_rect, self.font_body, self.font_header)
        self.trait_panel = TraitPanel(trait_rect, self.font_body, self.font_header, self.trait_catalog)
        self.news_ticker = NewsTicker(news_rect, self.font_small)
        self.advance_button = AdvanceButton(advance_rect, self.font_header)
        self.analytics_modal = AnalyticsModal(modal_rect, self.font_body, self.font_header)

    def _build_default_world(self) -> WorldGraph:
        if self.selected_map_name == "world":
            return build_global_world()
        return build_world()

    def _build_game(self) -> None:
        self._pending_data_warnings = []

        if self.use_custom_data and self.custom_data_available:
            try:
                self.world, world_warnings = build_world_from_csv(CUSTOM_REGIONS_CSV_PATH)
                self.strain, strain_warnings = build_strain_from_csv(CUSTOM_STRAIN_CSV_PATH)
                self._pending_data_warnings = world_warnings + strain_warnings
                self._using_custom_data_this_round = True
            except CSVLoadError as e:
                self._pending_data_warnings = [f"Custom data failed to load ({e}); using built-in map instead."]
                self.world = self._build_default_world()
                strain_factory = earthquake_rumor_scenario if self.selected_scenario_name == "earthquake_2015" else default_unverified_rumor
                self.strain = strain_factory()
                self._using_custom_data_this_round = False
        else:
            self.world = self._build_default_world()
            strain_factory = earthquake_rumor_scenario if self.selected_scenario_name == "earthquake_2015" else default_unverified_rumor
            self.strain = strain_factory()
            self._using_custom_data_this_round = False

        self.counter = CounterMeasure()
        spread_algo = SEIRSpreadModel() if self.selected_model_name == "SEIR" else SIRSpreadModel()
        self.engine = GameEngine(
            world=self.world,
            strain=self.strain,
            counter=self.counter,
            spread_algo=spread_algo,
            counter_ai=GreedyCounterAI(),
        )
        self.engine.current_ai_focus = None
        self.trait_catalog = build_trait_catalog()
        self.selected_region = None
        self.hovered_region = None

        # Map view setup
        if self._using_custom_data_this_round:
            self.map_view = MapView(pygame.Rect(0, 0, 100, 100), self.font_body, self.font_small)
        else:
            if not isinstance(getattr(self, "map_view", None), GeoMapView):
                self.map_view = GeoMapView(pygame.Rect(0, 0, 100, 100), self.font_body, self.font_small)
            self.map_view.set_zoom(GeoMapView.ZOOM_NEPAL if self.selected_map_name == "nepal" else GeoMapView.ZOOM_WORLD)

        self._seeded = False

    def _largest_region_name(self) -> str:
        geographic = [r for r in self.world.regions if getattr(r, "node_type", "geographic") == "geographic"]
        candidates = geographic if geographic else self.world.regions
        return max(candidates, key=lambda r: r.population).name

    def start_game(self) -> None:
        seed_region = self._largest_region_name()
        self.engine.start(seed_region_name=seed_region, seed_amount=8)
        self.news_ticker.push(f"Rumor seeded in {seed_region}.")
        for warning in self._pending_data_warnings[:3]:
            self.news_ticker.push(f"[DATA] {warning}")
        self.selected_region = None
        self.hovered_region = None
        self._seeded = True
        self.state = STATE_PLAYING

    def _region_screen_pos(self, region):
        if isinstance(self.map_view, GeoMapView):
            return self.map_view.screen_pos(self.world, region)
        return self.map_view.screen_pos(region)

    def _advance_one_tick(self) -> None:
        if self.engine.state != GameState.RUNNING:
            return
        self.engine.tick()
        self._check_for_news_events()

        for result in self.engine.strike_manager.last_strike_results:
            region = self.world.get_region(result["region_name"])
            if region is None:
                continue
            pos = self._region_screen_pos(region)
            if pos is not None:
                self.effects.spawn_ring(pos, theme.STRIKE_ALERT, start_radius=6, end_radius=60, duration=0.55)
                self.effects.spawn_text(pos, f"-{result['removed']:,}", theme.STRIKE_ALERT, duration=1.0)

        if self.engine.state != GameState.RUNNING:
            self.state = STATE_GAME_OVER

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)

            if self.state == STATE_MENU:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_1:
                        self.selected_model_name = "SIR"
                        self._build_game()
                    elif event.key == pygame.K_2:
                        self.selected_model_name = "SEIR"
                        self._build_game()
                    elif event.key == pygame.K_3:
                        self.selected_scenario_name = (
                            "earthquake_2015" if self.selected_scenario_name == "default" else "default"
                        )
                        self._build_game()
                    elif event.key == pygame.K_4 and self.custom_data_available:
                        self.use_custom_data = not self.use_custom_data
                        self._build_game()
                    elif event.key == pygame.K_5:
                        self.selected_map_name = "world" if self.selected_map_name == "nepal" else "nepal"
                        self._build_game()
                    elif event.key in (pygame.K_SPACE, pygame.K_RETURN):
                        self.start_game()
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    pos = event.pos
                    if self.opt_rect_model.collidepoint(pos):
                        self.selected_model_name = "SEIR" if self.selected_model_name == "SIR" else "SIR"
                        self._build_game()
                    elif self.opt_rect_scenario.collidepoint(pos):
                        self.selected_scenario_name = (
                            "earthquake_2015" if self.selected_scenario_name == "default" else "default"
                        )
                        self._build_game()
                    elif self.opt_rect_map.collidepoint(pos):
                        self.selected_map_name = "world" if self.selected_map_name == "nepal" else "nepal"
                        self._build_game()
                    elif self.opt_rect_data.collidepoint(pos) and self.custom_data_available:
                        self.use_custom_data = not self.use_custom_data
                        self._build_game()
                    elif self.btn_launch_menu.collidepoint(pos):
                        self.start_game()

            elif self.state == STATE_PLAYING:
                # Analytics modal handling (highest priority for clicks)
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if self.analytics_modal.handle_click(event.pos):
                        continue

                # Keyboard shortcuts
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_SPACE, pygame.K_RETURN):
                        self._advance_one_tick()
                    elif event.key == pygame.K_a:
                        # Toggle analytics modal with 'A' key
                        self.analytics_modal.toggle()
                    elif event.key == pygame.K_e and self.engine.telemetry_history:
                        # Export academic report with 'E' key
                        self._export_academic_report()
                    elif event.key == pygame.K_f or event.key == pygame.K_F11:
                        # Toggle fullscreen with 'F' or F11
                        self._toggle_fullscreen()
                    elif event.key in (pygame.K_BACKSPACE, pygame.K_ESCAPE):
                        if self.analytics_modal.visible:
                            self.analytics_modal.visible = False
                        elif isinstance(self.map_view, GeoMapView) and self.map_view.zoom_level == GeoMapView.ZOOM_NEPAL \
                                and self.selected_map_name != "nepal":
                            self.map_view.set_zoom(GeoMapView.ZOOM_WORLD)
                            self.map_view.reset_zoom()
                            self.selected_region = None

                # Handle window resize
                if event.type == pygame.VIDEORESIZE:
                    if not self.fullscreen:
                        self.windowed_size = (event.w, event.h)
                    self._rebuild_layout()

                if event.type == pygame.MOUSEMOTION:
                    self.hovered_region = self.map_view.region_at_point(self.world, event.pos)
                    self.advance_button.update_hover(event.pos)
                    if isinstance(self.map_view, GeoMapView):
                        self.map_view.handle_mousemove(event.pos)

                if event.type == pygame.MOUSEWHEEL:
                    mouse_pos = pygame.mouse.get_pos()
                    # Try scrollable panels first
                    if self.abilities_panel.handle_scroll(mouse_pos, event.y):
                        continue
                    if self.trait_panel.handle_scroll(mouse_pos, event.y):
                        continue
                    # Then map view
                    if isinstance(self.map_view, GeoMapView):
                        self.map_view.handle_scroll(mouse_pos, event.y)

                if event.type == pygame.MOUSEBUTTONUP:
                    if isinstance(self.map_view, GeoMapView):
                        self.map_view.handle_mouseup()

                if event.type == pygame.MOUSEBUTTONDOWN:
                    if isinstance(self.map_view, GeoMapView) and self.map_view.handle_mousedown(event.pos):
                        continue

                    if event.button in (2, 3) and isinstance(self.map_view, GeoMapView):
                        self.map_view.handle_mousedown(event.pos)
                        continue

                    if self.advance_button.is_clicked(event.pos):
                        self.effects.spawn_ring(self.advance_button.rect.center, theme.ACCENT_BRIGHT,
                                                 start_radius=8, end_radius=70, duration=0.35)
                        self._advance_one_tick()
                        continue

                    # Tactical abilities handling
                    clicked_ability = self.abilities_panel.handle_click(event.pos)
                    if clicked_ability is not None:
                        result = self.engine.use_tactical_ability(clicked_ability, target_region_name=self.selected_region.name if self.selected_region else None)
                        if result["success"]:
                            self.news_ticker.push(f"[TACTICAL] {result['message']}")
                            self.effects.spawn_text(event.pos, "ACTIVATED!", theme.ACCENT_BRIGHT, duration=1.2)
                        else:
                            self.news_ticker.push(f"[TACTICAL] {result['message']}")
                        continue

                    clicked_trait = self.trait_panel.handle_click(event.pos)
                    if clicked_trait is not None:
                        success = self.engine.attempt_trait_acquisition(clicked_trait)
                        if success:
                            new_level = self.strain.trait_level(clicked_trait)
                            self.news_ticker.push(f"[UPGRADE] {clicked_trait.name} reached Lv.{new_level}")
                            self.effects.spawn_text(event.pos, f"Lv.{new_level}!", theme.ACCENT_BRIGHT)
                            for button in self.trait_panel.buttons:
                                if button.trait is clicked_trait:
                                    self.effects.spawn_ring(button.rect.center, theme.ACCENT,
                                                             start_radius=4, end_radius=50, duration=0.4)
                                    break
                        continue

                    if (isinstance(self.map_view, GeoMapView)
                            and self.map_view.zoom_level == GeoMapView.ZOOM_WORLD
                            and self.map_view.country_at_point_is_nepal(event.pos)):
                        self.map_view.set_zoom(GeoMapView.ZOOM_NEPAL)
                        self.selected_region = self.world.get_region("Nepal")
                        continue

                    clicked_region = self.map_view.region_at_point(self.world, event.pos)
                    if clicked_region is not None:
                        self.selected_region = clicked_region

            elif self.state == STATE_GAME_OVER:
                if event.type == pygame.KEYDOWN and event.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_ESCAPE):
                    self._build_game()
                    self.state = STATE_MENU
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if self.btn_play_again.collidepoint(event.pos):
                        self._build_game()
                        self.state = STATE_MENU

    def _export_academic_report(self) -> None:
        """Export academic report package for TU BCA final project."""
        from algorithm.export_report_figures import export_academic_report

        result = export_academic_report(
            self.engine.telemetry_history,
            self.strain.name,
            self.selected_model_name,
            output_dir="report_exports"
        )

        if result["success"]:
            self.news_ticker.push(f"[EXPORT] Academic report exported to {result['output_dir']}")
            self.news_ticker.push(f"[EXPORT] {len(result['files'])} files generated")
        else:
            self.news_ticker.push(f"[EXPORT] {result['message']}")

    def _toggle_fullscreen(self) -> None:
        """Toggle between fullscreen and windowed mode."""
        self.fullscreen = not self.fullscreen

        if self.fullscreen:
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)

        self._rebuild_layout()

        if self.news_ticker:
            mode_text = "fullscreen" if self.fullscreen else "windowed"
            self.news_ticker.push(f"[DISPLAY] Switched to {mode_text} mode (F or F11 to toggle)")

    def _check_for_news_events(self) -> None:
        if self.counter.active and not getattr(self, "_announced_counter", False):
            self.news_ticker.push("[FACT-CHECK] Fact-checkers have launched response.")
            self._announced_counter = True
        for region in self.world.regions:
            if region.skeptical > region.population * 0.5 and region.name not in getattr(self, "_announced_skeptical", set()):
                if not hasattr(self, "_announced_skeptical"):
                    self._announced_skeptical = set()
                self._announced_skeptical.add(region.name)
                self.news_ticker.push(f"[RESISTANCE] {region.name} is now majority skeptical.")

        if not hasattr(self, "_announced_strike_targets"):
            self._announced_strike_targets = set()

        warnings = self.engine.strike_manager.get_warnings()
        currently_pending_names = {w["region_name"] for w in warnings}
        for warning in warnings:
            if warning["region_name"] not in self._announced_strike_targets:
                self._announced_strike_targets.add(warning["region_name"])
                prefix = "[CRACKDOWN]" if self.engine.strike_manager.is_crackdown_active else "[ALERT]"
                self.news_ticker.push(
                    f"{prefix} Fact-checkers targeting {warning['region_name']} (in {warning['turns_remaining']} turns)"
                )
        self._announced_strike_targets &= currently_pending_names

        for result in self.engine.strike_manager.last_strike_results:
            self.news_ticker.push(
                f"[STRIKE] Impact on {result['region_name']}: {result['removed']:,} corrected."
            )

    def draw_menu(self) -> None:
        self.screen.fill(theme.BG_COLOR)
        mouse_pos = pygame.mouse.get_pos()

        # Title Hero Banner
        title_surf = self.font_title.render("INFOSPREAD SIMULATOR", True, theme.TEXT_HIGHLIGHT)
        self.screen.blit(title_surf, (theme.WINDOW_WIDTH // 2 - title_surf.get_width() // 2, 45))

        sub_surf = self.font_body.render("Tactical Information Contagion & Fact-Checking Dynamics", True, theme.ACCENT)
        self.screen.blit(sub_surf, (theme.WINDOW_WIDTH // 2 - sub_surf.get_width() // 2, 90))

        # Main Settings Container
        settings_rect = pygame.Rect(theme.WINDOW_WIDTH // 2 - 420, 135, 840, 240)
        pygame.draw.rect(self.screen, theme.PANEL_BG, settings_rect, border_radius=14)
        pygame.draw.rect(self.screen, theme.PANEL_BORDER, settings_rect, width=1, border_radius=14)

        # Draw Option Cards (Clickable)
        opts = [
            (self.opt_rect_model, "🔬 Spread Model", f"{self.selected_model_name} (SIR / SEIR)", "Press 1 or 2"),
            (self.opt_rect_scenario, "📋 Scenario", "2015 Earthquake" if self.selected_scenario_name == "earthquake_2015" else "Default Rumor", "Press 3"),
            (self.opt_rect_map, "🗺️ Simulation Map", "World (202 Nations)" if self.selected_map_name == "world" else "Nepal (7 Provinces)", "Press 5"),
            (self.opt_rect_data, "📁 Data Source", "Custom CSV" if self.use_custom_data else "Built-In Real Data", "Press 4" if self.custom_data_available else "Not Found"),
        ]

        for rect, label, val, shortcut in opts:
            is_hover = rect.collidepoint(mouse_pos)
            bg = theme.PANEL_BG_LIGHT if is_hover else theme.PANEL_BG_RAISED
            b_col = theme.ACCENT if is_hover else theme.PANEL_BORDER_BRIGHT
            pygame.draw.rect(self.screen, bg, rect, border_radius=8)
            pygame.draw.rect(self.screen, b_col, rect, width=1, border_radius=8)

            lbl_surf = self.font_small.render(label, True, theme.TEXT_MUTED)
            val_surf = self.font_body.render(val, True, theme.TEXT_PRIMARY)
            sc_surf = self.font_small.render(shortcut, True, theme.ACCENT)

            self.screen.blit(lbl_surf, (rect.x + 12, rect.y + 8))
            self.screen.blit(val_surf, (rect.x + 12, rect.y + 26))
            self.screen.blit(sc_surf, (rect.right - sc_surf.get_width() - 12, rect.y + 16))

        # Launch Button
        btn_hover = self.btn_launch_menu.collidepoint(mouse_pos)
        btn_bg = theme.ADVANCE_BUTTON_BG_HOVER if btn_hover else theme.ADVANCE_BUTTON_BG
        pygame.draw.rect(self.screen, btn_bg, self.btn_launch_menu, border_radius=10)
        pygame.draw.rect(self.screen, theme.ACCENT_BRIGHT if btn_hover else theme.ACCENT, self.btn_launch_menu, width=2, border_radius=10)

        launch_txt = self.font_header.render("🚀  LAUNCH SIMULATION", True, theme.TEXT_HIGHLIGHT)
        self.screen.blit(launch_txt, (
            self.btn_launch_menu.x + (self.btn_launch_menu.width - launch_txt.get_width()) // 2,
            self.btn_launch_menu.y + (self.btn_launch_menu.height - launch_txt.get_height()) // 2
        ))

        # How to Play Container
        howto_rect = pygame.Rect(theme.WINDOW_WIDTH // 2 - 420, 395, 840, 380)
        pygame.draw.rect(self.screen, theme.PANEL_BG, howto_rect, border_radius=14)
        pygame.draw.rect(self.screen, theme.PANEL_BORDER, howto_rect, width=1, border_radius=14)

        howto_header = self.font_header.render("TACTICAL DIRECTIVES", True, theme.ACCENT)
        self.screen.blit(howto_header, (howto_rect.x + 24, howto_rect.y + 18))

        directives = [
            ("▶ Player-Paced Turns:", "The simulation advances step-by-step when you click ADVANCE or press SPACE."),
            ("🧬 Trait Evolution:", "Spend accumulated Belief Points on contagion vectors and resistance shields."),
            ("🌍 Real Geography & Networks:", "Hover and click nations or platforms. Click Nepal to drill into districts."),
            ("🏁 Infection Race:", "Reach 95% global belief before fact-checkers establish 90% skeptical immunity."),
            ("⚠️ Strike Alerts & Crackdown:", "Fact-checkers telegraph targeted strikes 1-3 turns ahead — defend in time!"),
        ]

        y = howto_rect.y + 54
        for title, desc in directives:
            t_surf = self.font_body.render(title, True, theme.TEXT_PRIMARY)
            d_surf = self.font_body.render(desc, True, theme.TEXT_SECONDARY)
            self.screen.blit(t_surf, (howto_rect.x + 24, y))
            self.screen.blit(d_surf, (howto_rect.x + 24, y + 22))
            y += 56

    def draw_playing(self) -> None:
        self.screen.fill(theme.BG_COLOR)
        self.map_view.draw(
            self.screen, self.world,
            focus_region=self.engine.current_ai_focus,
            selected_region=self.selected_region,
            hovered_region=self.hovered_region,
        )
        self.race_bar.draw(
            self.screen,
            belief_ratio=self.world.global_infection_ratio(),
            counter_strength=self.counter.strength,
            counter_cap=self.counter.cap,
            counter_active=self.counter.active,
        )
        self.stats_panel.draw(self.screen, self.engine.get_score_summary(), self.strain.name,
                               model_name=self.selected_model_name)
        self.detail_panel.draw(self.screen, self.selected_region)
        self.abilities_panel.draw(self.screen, self.engine)
        self.trait_panel.draw(self.screen, self.strain)
        self.news_ticker.draw(self.screen)
        self.advance_button.draw(self.screen)
        self.strike_panel.draw(
            self.screen,
            self.engine.strike_manager.get_warnings(),
            self.engine.strike_manager.last_strike_results,
            is_crackdown=self.engine.strike_manager.is_crackdown_active,
        )
        self.effects.draw(self.screen)

        # Analytics modal overlay (drawn last so it appears on top)
        self.analytics_modal.draw(self.screen, self.engine.telemetry_history)

        # Analytics toggle button (bottom-left corner)
        if not self.analytics_modal.visible:
            analytics_btn_rect = pygame.Rect(20, theme.WINDOW_HEIGHT - 50, 140, 36)
            mouse_pos = pygame.mouse.get_pos()
            btn_hover = analytics_btn_rect.collidepoint(mouse_pos)
            btn_bg = theme.ACCENT_BRIGHT if btn_hover else theme.ACCENT
            pygame.draw.rect(self.screen, btn_bg, analytics_btn_rect, border_radius=8)
            btn_text = self.font_body.render("📊 Analytics [A]", True, theme.TEXT_HIGHLIGHT)
            self.screen.blit(btn_text, (
                analytics_btn_rect.x + (analytics_btn_rect.width - btn_text.get_width()) // 2,
                analytics_btn_rect.y + (analytics_btn_rect.height - btn_text.get_height()) // 2
            ))

            # Handle click on analytics button
            if pygame.mouse.get_pressed()[0] and btn_hover:
                self.analytics_modal.toggle()

    def draw_game_over(self) -> None:
        self.screen.fill(theme.BG_COLOR)
        mouse_pos = pygame.mouse.get_pos()

        summary = self.engine.get_score_summary()
        won = summary["state"] == GameState.WON
        result_text = "RUMOR WENT VIRAL — VICTORY" if won else "FACT-CHECKERS CONTAINED THE SPREAD"
        result_color = theme.COLOR_BELIEF if won else theme.COLOR_CURE

        title = self.font_title.render(result_text, True, result_color)
        self.screen.blit(title, (theme.WINDOW_WIDTH // 2 - title.get_width() // 2, 45))

        # Metrics Panel
        results_rect = pygame.Rect(theme.WINDOW_WIDTH // 2 - 420, 110, 840, 150)
        pygame.draw.rect(self.screen, theme.PANEL_BG, results_rect, border_radius=12)
        pygame.draw.rect(self.screen, theme.PANEL_BORDER, results_rect, width=1, border_radius=12)

        total_traits = sum(self.strain.trait_levels.values()) if self.strain.trait_levels else 0
        most_resistant = max(self.world.regions, key=lambda r: r.skeptical, default=None)

        stat_lines = [
            f"⏱ Turns Played: {summary['ticks']}",
            f"📈 Peak Belief: {summary['global_infection_ratio'] * 100:.1f}%",
            f"👥 Total Believers: {summary['total_believing']:,}",
            f"🛡️ Total Corrected: {summary['total_skeptical']:,}",
            f"🧬 Trait Upgrades: {total_traits}",
        ]
        if most_resistant is not None and most_resistant.skeptical > 0:
            stat_lines.append(f"Hardest Territory: {most_resistant.name} ({most_resistant.skeptical:,} Skeptical)")

        col_split = 3
        for i, line in enumerate(stat_lines):
            col = 0 if i < col_split else 1
            row = i if i < col_split else i - col_split
            text_surf = self.font_body.render(line, True, theme.TEXT_PRIMARY)
            x = results_rect.x + 32 + col * 400
            y = results_rect.y + 24 + row * 34
            self.screen.blit(text_surf, (x, y))

        # Educational Takeaways
        edu_rect = pygame.Rect(theme.WINDOW_WIDTH // 2 - 420, 280, 840, 250)
        pygame.draw.rect(self.screen, theme.PANEL_BG, edu_rect, border_radius=12)
        pygame.draw.rect(self.screen, theme.PANEL_BORDER, edu_rect, width=1, border_radius=12)

        edu_header = self.font_header.render("MEDIA LITERACY TAKEAWAYS (IFCN STANDARDS)", True, theme.ACCENT)
        self.screen.blit(edu_header, (edu_rect.x + 24, edu_rect.y + 18))

        y = edu_rect.y + 54
        for tip in MEDIA_LITERACY_TIPS:
            tip_surf = self.font_body.render(f"• {tip}", True, theme.TEXT_PRIMARY)
            self.screen.blit(tip_surf, (edu_rect.x + 24, y))
            y += 28

        # Play Again Button
        pa_hover = self.btn_play_again.collidepoint(mouse_pos)
        pa_bg = theme.ADVANCE_BUTTON_BG_HOVER if pa_hover else theme.ADVANCE_BUTTON_BG
        pygame.draw.rect(self.screen, pa_bg, self.btn_play_again, border_radius=8)
        pygame.draw.rect(self.screen, theme.ACCENT_BRIGHT if pa_hover else theme.ACCENT, self.btn_play_again, width=1, border_radius=8)

        pa_text = self.font_header.render("⟲  PLAY AGAIN", True, theme.TEXT_HIGHLIGHT)
        self.screen.blit(pa_text, (
            self.btn_play_again.x + (self.btn_play_again.width - pa_text.get_width()) // 2,
            self.btn_play_again.y + (self.btn_play_again.height - pa_text.get_height()) // 2
        ))

        # Academic Export Hint (for TU BCA defense)
        export_hint = self.font_small.render("📄 Press [E] during game to export academic report figures", True, theme.TEXT_MUTED)
        self.screen.blit(export_hint, (theme.WINDOW_WIDTH // 2 - export_hint.get_width() // 2, theme.WINDOW_HEIGHT - 30))

    def run(self) -> None:
        while True:
            dt_ms = self.clock.get_time()
            if self.state == STATE_PLAYING:
                self.strike_panel.update(dt_ms / 1000.0)
                self.effects.update(dt_ms / 1000.0)

            self.handle_events()

            if self.state == STATE_MENU:
                self.draw_menu()
            elif self.state == STATE_PLAYING:
                self.draw_playing()
            elif self.state == STATE_GAME_OVER:
                self.draw_game_over()

            pygame.display.flip()
            self.clock.tick(theme.FPS)


if __name__ == "__main__":
    App().run()
