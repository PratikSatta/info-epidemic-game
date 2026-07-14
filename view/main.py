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
from view.ui_panels import StatsPanel, TraitPanel, NewsTicker, RaceBar, AdvanceButton, RegionDetailPanel, StrikeWarningPanel, EffectsLayer


STATE_MENU = "menu"
STATE_PLAYING = "playing"
STATE_GAME_OVER = "game_over"

# Well-known paths checked at startup for "bring your own data" CSV files.
# If present, the menu offers to load them via key 4 (see App._build_game
# and App.handle_events). Edit these paths, or just replace the files at
# these locations, to point at your own data without touching any code.
CUSTOM_REGIONS_CSV_PATH = "data/regions_example.csv"
CUSTOM_STRAIN_CSV_PATH = "data/strain_config_example.csv"

# Educational layer: standard media-literacy guidance consistent with
# practices used by IFCN-aligned fact-checking organizations (e.g. South
# Asia Check, Nepal's own IFCN-certified fact-checker). These are general,
# widely-taught verification habits, not paraphrased from any single
# article -- shown after every round to give the simulation a genuine
# public-education purpose alongside the academic/algorithmic one.
MEDIA_LITERACY_TIPS = [
    "Check who is sharing the claim, not just what it says — is the source identifiable and credible?",
    "Slow down before resharing during emergencies — disaster-context rumors spread fastest and verify slowest.",
    "Search for the same claim on an established fact-checking site before trusting or sharing it.",
    "Be extra cautious of content designed to trigger strong emotion — that's often a deliberate spread tactic.",
]


def build_world() -> WorldGraph:
    """
    Builds the starting map from real Nepal provincial data (see
    model/real_world_data.py for sources and citations) rather than
    arbitrary placeholder values. Each of Nepal's 7 actual provinces
    becomes a Region, with population and base_resistance derived from
    real internet-access statistics. Connections mirror Nepal's actual
    province adjacency (a province only connects to provinces it
    genuinely borders), so the graph itself -- not just the node values --
    reflects something real.

    Edge weights are still a modeling choice (no single sourced "rumor
    transmission strength between province X and Y" statistic exists),
    so they're estimated based on relative population/connectivity as a
    reasonable proxy and should be named as an assumption in your report.
    """
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

    # Real adjacency: Nepal's 7 provinces border each other roughly west to
    # east as: Sudurpashchim - Karnali - Lumbini - Gandaki - Bagmati -
    # Madhesh/Koshi, with Madhesh bordering both Lumbini, Bagmati and Koshi
    # along the southern plains, and Koshi bordering both Bagmati and
    # Madhesh in the east. Edge weights are an estimated connectivity proxy
    # (higher = stronger assumed information flow), not a sourced figure.
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
        pygame.display.set_caption("InfoSpread Simulator")
        self.screen = pygame.display.set_mode((theme.WINDOW_WIDTH, theme.WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()

        self.font_title = pygame.font.SysFont(theme.FONT_NAME, theme.FONT_SIZE_TITLE, bold=True)
        self.font_header = pygame.font.SysFont(theme.FONT_NAME, theme.FONT_SIZE_HEADER, bold=True)
        self.font_body = pygame.font.SysFont(theme.FONT_NAME, theme.FONT_SIZE_BODY)
        self.font_small = pygame.font.SysFont(theme.FONT_NAME, theme.FONT_SIZE_SMALL)

        self.state = STATE_MENU
        self.selected_model_name = "SIR"   # default; changed via menu key press
        self.selected_scenario_name = "default"   # default; changed via menu key press
        self.use_custom_data = False   # default; toggled via menu key press
        self.selected_map_name = "nepal"   # "nepal" or "world"; toggled via menu key press
        self.custom_data_available = (
            os.path.exists(CUSTOM_REGIONS_CSV_PATH) and os.path.exists(CUSTOM_STRAIN_CSV_PATH)
        )
        # NOTE: there is deliberately NO pygame.time.set_timer() here anymore.
        # The simulation used to advance automatically every 600ms regardless
        # of what the player did, which made the game play itself rather than
        # respond to the player -- the single biggest piece of feedback that
        # drove this rework. Now nothing advances until the player explicitly
        # clicks the AdvanceButton or presses Space/Enter (see handle_events).
        self.selected_region = None   # last region the player clicked, shown in RegionDetailPanel
        self.hovered_region = None     # region currently under the mouse, for hover feedback
        self.effects = EffectsLayer(self.font_small)   # juice layer: ring pulses + floating text for
                                                          # player actions and game events (see ui_panels.py)

        self._build_game()

    def _build_default_world(self) -> WorldGraph:
        """Returns either the Nepal province map or the 16-country + 4-platform world map, per selected_map_name."""
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
                # Fall back to the currently-selected built-in map rather than
                # crashing -- a malformed CSV should degrade gracefully, not
                # break the game.
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

        # Layout for the enlarged 1280x820 window: map takes the left ~800px,
        # a right-hand column of fixed-height panels takes the remaining
        # ~440px. The race bar sits above the map (full width) since it's
        # the single most important glanceable stat and deserves top
        # billing; the strike warning banner sits below the map (also full
        # width) since it's the second most urgent thing to notice and
        # deserves its own dedicated, hard-to-miss space rather than being
        # squeezed into the sidebar.
        race_bar_rect = pygame.Rect(20, 20, 800, 56)
        map_rect = pygame.Rect(20, 88, 800, 612)
        strike_rect = pygame.Rect(20, 712, 800, 88)

        stats_rect = pygame.Rect(840, 20, 420, 130)
        detail_rect = pygame.Rect(840, 158, 420, 150)
        trait_rect = pygame.Rect(840, 316, 420, 230)
        news_rect = pygame.Rect(840, 554, 420, 130)
        advance_rect = pygame.Rect(840, 692, 420, 108)

        self.race_bar = RaceBar(race_bar_rect, self.font_body, self.font_header)
        # Custom CSV-loaded maps have no real geographic data (arbitrary
        # region names, no matching country/district outlines), so they
        # use the old abstract node-and-edge MapView as a fallback. The
        # two BUILT-IN maps (Nepal, world) use the real-geography
        # GeoMapView. This check must happen AFTER the custom-data load
        # attempt above, since _using_custom_data_this_round reflects
        # whether it actually succeeded (not just whether it was toggled).
        if self._using_custom_data_this_round:
            self.map_view = MapView(map_rect, self.font_body, self.font_small)
        else:
            if not isinstance(getattr(self, "map_view", None), GeoMapView):
                self.map_view = GeoMapView(map_rect, self.font_body, self.font_small)
            self.map_view.set_zoom(GeoMapView.ZOOM_NEPAL if self.selected_map_name == "nepal" else GeoMapView.ZOOM_WORLD)
        self.strike_panel = StrikeWarningPanel(strike_rect, self.font_body, self.font_header)
        self.stats_panel = StatsPanel(stats_rect, self.font_body, self.font_header)
        self.detail_panel = RegionDetailPanel(detail_rect, self.font_body, self.font_header)
        self.trait_panel = TraitPanel(trait_rect, self.font_body, self.font_header, self.trait_catalog)
        self.news_ticker = NewsTicker(news_rect, self.font_small)
        self.advance_button = AdvanceButton(advance_rect, self.font_header)

        self._seeded = False
        self._last_state = GameState.RUNNING

    def _largest_region_name(self) -> str:
        """
        Seed region selection that works regardless of whether the world
        came from the built-in Nepal map, the built-in world map, or an
        arbitrary custom CSV: pick whichever GEOGRAPHIC region has the
        largest population, falling back to the largest node of any type
        only if no geographic regions exist at all. This avoids seeding
        the very first outbreak directly in a platform/spread-point node
        (which tend to have larger modeled "reach" pools than any single
        country) -- outbreaks should start somewhere real and reach
        platforms afterward, matching the Plague-Inc framing of a
        geographic patient zero.
        """
        geographic = [r for r in self.world.regions if getattr(r, "node_type", "geographic") == "geographic"]
        candidates = geographic if geographic else self.world.regions
        return max(candidates, key=lambda r: r.population).name

    def start_game(self) -> None:
        seed_region = self._largest_region_name()
        self.engine.start(seed_region_name=seed_region, seed_amount=8)
        self.news_ticker.push(f"Rumor seeded in {seed_region}.")
        for warning in self._pending_data_warnings[:3]:  # cap to avoid flooding the ticker
            self.news_ticker.push(f"[data] {warning}")
        self.selected_region = None
        self.hovered_region = None
        self._seeded = True
        self.state = STATE_PLAYING

    def _region_screen_pos(self, region):
        """
        Looks up where a region currently renders on screen, working with
        EITHER map view class (GeoMapView's signature takes the world
        graph too; the abstract MapView fallback for custom CSV data does
        not). Returns None if the region isn't visible right now (e.g.
        wrong zoom level) -- callers should skip the effect in that case
        rather than guess a position.
        """
        if isinstance(self.map_view, GeoMapView):
            return self.map_view.screen_pos(self.world, region)
        return self.map_view.screen_pos(region)

    def _advance_one_tick(self) -> None:
        """
        Advances the simulation by exactly one tick. This is now the ONLY
        way the simulation moves forward -- called from the AdvanceButton
        click handler or the Space/Enter keydown handler in handle_events.
        There is no automatic timer; if the player does nothing, nothing
        happens, which is the core fix for "the rumor spreads without any
        player interactivity."
        """
        if self.engine.state != GameState.RUNNING:
            return
        self.engine.tick()
        self._check_for_news_events()

        # Visual feedback for landed strikes -- a strike is a dramatic
        # game event (a chunk of believers corrected at once) and
        # deserves a visible flash on the map itself, not just a panel/
        # ticker update easy to miss while looking elsewhere.
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
                    else:
                        self.start_game()
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    self.start_game()

            elif self.state == STATE_PLAYING:
                if event.type == pygame.KEYDOWN and event.key in (pygame.K_SPACE, pygame.K_RETURN):
                    self._advance_one_tick()

                if event.type == pygame.MOUSEMOTION:
                    self.hovered_region = self.map_view.region_at_point(self.world, event.pos)
                    self.advance_button.update_hover(event.pos)

                if event.type == pygame.KEYDOWN and event.key in (pygame.K_BACKSPACE, pygame.K_ESCAPE):
                    if isinstance(self.map_view, GeoMapView) and self.map_view.zoom_level == GeoMapView.ZOOM_NEPAL \
                            and self.selected_map_name != "nepal":
                        # Only zoom back out if we zoomed IN from the world
                        # map -- if the player chose the Nepal map itself
                        # from the menu, there is no "world" level above it.
                        self.map_view.set_zoom(GeoMapView.ZOOM_WORLD)
                        self.selected_region = None

                if event.type == pygame.MOUSEBUTTONDOWN:
                    if self.advance_button.is_clicked(event.pos):
                        self.effects.spawn_ring(self.advance_button.rect.center, theme.ACCENT_BRIGHT,
                                                 start_radius=8, end_radius=70, duration=0.35)
                        self._advance_one_tick()
                        continue

                    clicked_trait = self.trait_panel.handle_click(event.pos)
                    if clicked_trait is not None:
                        success = self.engine.attempt_trait_acquisition(clicked_trait)
                        if success:
                            new_level = self.strain.trait_level(clicked_trait)
                            self.news_ticker.push(f"{clicked_trait.name} leveled up to Lv.{new_level}")
                            # Floating "+1 Lv" feedback right where the player
                            # clicked, plus a quick ring on the button itself --
                            # a purchase should feel like it registered, not
                            # just silently update a number in the panel below.
                            self.effects.spawn_text(event.pos, f"Lv.{new_level}!", theme.ACCENT_BRIGHT)
                            for button, trait in self.trait_panel.buttons:
                                if trait is clicked_trait:
                                    self.effects.spawn_ring(button.rect.center, theme.ACCENT,
                                                             start_radius=4, end_radius=50, duration=0.4)
                                    break
                        continue

                    # Clicking Nepal specifically while at world zoom (and
                    # the world map, not the Nepal-only map, is active)
                    # zooms in to the district view instead of just
                    # selecting it -- the geographic equivalent of
                    # Plague-Inc-style "click a region to see more detail."
                    if (isinstance(self.map_view, GeoMapView)
                            and self.map_view.zoom_level == GeoMapView.ZOOM_WORLD
                            and self.map_view.country_at_point_is_nepal(event.pos)):
                        self.map_view.set_zoom(GeoMapView.ZOOM_NEPAL)
                        self.selected_region = self.world.get_region("Nepal")
                        continue

                    # Clicking the map (and not a button) selects a region for
                    # inspection in RegionDetailPanel -- pure information, no
                    # simulation effect, addressing feedback that the map felt
                    # like a static, unresponsive backdrop.
                    clicked_region = self.map_view.region_at_point(self.world, event.pos)
                    if clicked_region is not None:
                        self.selected_region = clicked_region

            elif self.state == STATE_GAME_OVER:
                if event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONDOWN:
                    self._build_game()
                    self.state = STATE_MENU

    def _check_for_news_events(self) -> None:
        if self.counter.active and not getattr(self, "_announced_counter", False):
            self.news_ticker.push("Fact-checkers have noticed the rumor.")
            self._announced_counter = True
        for region in self.world.regions:
            if region.skeptical > region.population * 0.5 and region.name not in getattr(self, "_announced_skeptical", set()):
                if not hasattr(self, "_announced_skeptical"):
                    self._announced_skeptical = set()
                self._announced_skeptical.add(region.name)
                self.news_ticker.push(f"{region.name} is now majority skeptical.")

        # Strike telegraph announcements -- each newly-scheduled strike
        # (one the ticker hasn't announced yet, tracked by region name in
        # a SET now rather than a single value, since Crackdown can have
        # several concurrent pending strikes) gets a one-time push; every
        # landed strike always gets a push since last_strike_results only
        # contains entries on the exact tick each one executes.
        if not hasattr(self, "_announced_strike_targets"):
            self._announced_strike_targets = set()

        warnings = self.engine.strike_manager.get_warnings()
        currently_pending_names = {w["region_name"] for w in warnings}
        for warning in warnings:
            if warning["region_name"] not in self._announced_strike_targets:
                self._announced_strike_targets.add(warning["region_name"])
                prefix = "[CRACKDOWN]" if self.engine.strike_manager.is_crackdown_active else "[ALERT]"
                self.news_ticker.push(
                    f"{prefix} Fact-checkers are mobilizing against {warning['region_name']} "
                    f"— impact in {warning['turns_remaining']} turns."
                )
        # Drop announcement-tracking for any target that's no longer
        # pending (it either landed or was otherwise cleared), so if the
        # same region becomes a target again later it gets a fresh announcement.
        self._announced_strike_targets &= currently_pending_names

        for result in self.engine.strike_manager.last_strike_results:
            self.news_ticker.push(
                f"Strike landed on {result['region_name']}: {result['removed']:,} corrected."
            )

    def draw_menu(self) -> None:
        self.screen.fill(theme.BG_COLOR)
        title = self.font_title.render("InfoSpread Simulator", True, theme.TEXT_PRIMARY)
        self.screen.blit(title, (theme.WINDOW_WIDTH // 2 - title.get_width() // 2, 70))

        # --- Settings panel: model / scenario / map / data source toggles ---
        settings_rect = pygame.Rect(theme.WINDOW_WIDTH // 2 - 420, 140, 840, 190)
        pygame.draw.rect(self.screen, theme.PANEL_BG, settings_rect, border_radius=12)
        pygame.draw.rect(self.screen, theme.PANEL_BORDER, settings_rect, width=2, border_radius=12)

        model_line = self.font_body.render(
            f"Model: {self.selected_model_name}  —  press 1 for SIR, 2 for SEIR", True, theme.ACCENT
        )
        scenario_label = "2015 Earthquake Rumors (calibrated)" if self.selected_scenario_name == "earthquake_2015" else "Default (uncalibrated)"
        scenario_line = self.font_body.render(
            f"Scenario: {scenario_label}  —  press 3 to toggle", True, theme.ACCENT
        )
        builtin_map_label = "World Map (16 countries + 4 platforms)" if self.selected_map_name == "world" else "Nepal Provinces (7 regions)"
        map_line = self.font_body.render(
            f"Map: {builtin_map_label}  —  press 5 to toggle", True, theme.ACCENT
        )
        if self.custom_data_available:
            data_label = "Custom CSV data" if self.use_custom_data else f"Built-in — {builtin_map_label}"
            data_color = theme.ACCENT
            data_text = f"Data source: {data_label}  —  press 4 to toggle"
        else:
            data_color = theme.TEXT_SECONDARY
            data_text = "Data source: built-in map only (no custom CSV files found in data/)"
        data_line = self.font_body.render(data_text, True, data_color)

        for i, line in enumerate([model_line, scenario_line, map_line, data_line]):
            self.screen.blit(line, (theme.WINDOW_WIDTH // 2 - line.get_width() // 2, 168 + i * 36))

        subtitle = self.font_body.render(
            "Click anywhere or press Space to seed the rumor and begin", True, theme.TEXT_SECONDARY
        )
        self.screen.blit(subtitle, (theme.WINDOW_WIDTH // 2 - subtitle.get_width() // 2, 350))

        # --- How-to-play panel: fills the lower half with real content
        # instead of empty space, and doubles as a quick rules reference. ---
        howto_rect = pygame.Rect(theme.WINDOW_WIDTH // 2 - 420, 410, 840, 330)
        pygame.draw.rect(self.screen, theme.PANEL_BG, howto_rect, border_radius=12)
        pygame.draw.rect(self.screen, theme.PANEL_BORDER, howto_rect, width=2, border_radius=12)

        howto_header = self.font_header.render("How to Play", True, theme.ACCENT)
        self.screen.blit(howto_header, (howto_rect.x + 24, howto_rect.y + 18))

        howto_lines = [
            "This game does NOT play itself — nothing happens until YOU act.",
            "",
            "• Click \"Advance\" (or press Space/Enter) to move forward one step at a time.",
            "• Spend belief points on traits — some trade reach for a higher risk of being noticed.",
            "• The map shows real geography: regions are colored shapes, platforms are squares.",
            "  Click Nepal on the world map to zoom into its real districts; Backspace to zoom out.",
            "• Click any region or platform to inspect its stats.",
            "• Watch the Belief vs. Countermeasure bar — you're racing to 95% belief before they",
            "  correct 90% of the world back to skeptical.",
            "• Fact-checkers telegraph strikes 1-2 turns ahead — react before they land. Past ~40%",
            "  belief, multiple strikes can threaten different regions at once (\"Crackdown\").",
        ]
        y = howto_rect.y + 50
        for line in howto_lines:
            color = theme.TEXT_SECONDARY if line.startswith("•") or line.startswith("  ") else theme.TEXT_PRIMARY
            text_surf = self.font_body.render(line, True, color)
            self.screen.blit(text_surf, (howto_rect.x + 24, y))
            y += 24

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
        self.trait_panel.draw(self.screen, self.strain)
        self.news_ticker.draw(self.screen)
        self.advance_button.draw(self.screen)
        self.strike_panel.draw(
            self.screen,
            self.engine.strike_manager.get_warnings(),
            self.engine.strike_manager.last_strike_results,
            is_crackdown=self.engine.strike_manager.is_crackdown_active,
        )
        self.effects.draw(self.screen)   # always last: overlays on top of every other panel/the map

    def draw_game_over(self) -> None:
        self.screen.fill(theme.BG_COLOR)
        summary = self.engine.get_score_summary()
        won = summary["state"] == GameState.WON
        result_text = "RUMOR WENT VIRAL" if won else "FACT-CHECKERS WON"
        result_color = theme.TEXT_WARNING if won else theme.ACCENT

        title = self.font_title.render(result_text, True, result_color)
        self.screen.blit(title, (theme.WINDOW_WIDTH // 2 - title.get_width() // 2, 56))

        # --- Results panel: real numbers from THIS playthrough, not just
        # two floating lines -- gives the bigger window real content and
        # doubles as a basis for the "what would you try differently"
        # reflection a report's Result Analysis section can draw on. ---
        results_rect = pygame.Rect(theme.WINDOW_WIDTH // 2 - 420, 130, 840, 150)
        pygame.draw.rect(self.screen, theme.PANEL_BG, results_rect, border_radius=12)
        pygame.draw.rect(self.screen, theme.PANEL_BORDER, results_rect, width=2, border_radius=12)

        total_trait_levels = sum(self.strain.trait_levels.values()) if self.strain.trait_levels else 0
        most_resistant = max(self.world.regions, key=lambda r: r.skeptical, default=None)

        stat_lines = [
            f"Turns played: {summary['ticks']}",
            f"Peak global belief: {summary['global_infection_ratio'] * 100:.1f}%",
            f"Total believers at end: {summary['total_believing']:,}",
            f"Total corrected (skeptical): {summary['total_skeptical']:,}",
            f"Trait levels purchased: {total_trait_levels}",
        ]
        if most_resistant is not None and most_resistant.skeptical > 0:
            stat_lines.append(f"Hardest-fought region: {most_resistant.name} ({most_resistant.skeptical:,} corrected)")

        col_split = len(stat_lines) // 2 + len(stat_lines) % 2
        for i, line in enumerate(stat_lines):
            text_surf = self.font_body.render(line, True, theme.TEXT_PRIMARY)
            col = 0 if i < col_split else 1
            row = i if i < col_split else i - col_split
            x = results_rect.x + 32 + col * 420
            y = results_rect.y + 20 + row * 30
            self.screen.blit(text_surf, (x, y))

        # --- Educational panel: real media-literacy takeaway, shown every
        # round, now in its own bordered panel rather than floating text. ---
        edu_rect = pygame.Rect(theme.WINDOW_WIDTH // 2 - 420, 300, 840, 240)
        pygame.draw.rect(self.screen, theme.PANEL_BG, edu_rect, border_radius=12)
        pygame.draw.rect(self.screen, theme.PANEL_BORDER, edu_rect, width=2, border_radius=12)

        edu_header = self.font_header.render("Before you go — spotting real misinformation", True, theme.ACCENT)
        self.screen.blit(edu_header, (edu_rect.x + 24, edu_rect.y + 18))

        y = edu_rect.y + 56
        for tip in MEDIA_LITERACY_TIPS:
            tip_surf = self.font_body.render(f"• {tip}", True, theme.TEXT_PRIMARY)
            self.screen.blit(tip_surf, (edu_rect.x + 24, y))
            y += 28

        y += 10
        if self._using_custom_data_this_round:
            citation_text = "Verify claims via the International Fact-Checking Network (170+ orgs worldwide) — ifcncodeofprinciples.poynter.org"
        elif self.selected_map_name == "world":
            citation_text = "Global fact-checking: International Fact-Checking Network (IFCN) — ifcncodeofprinciples.poynter.org"
        else:
            citation_text = "Nepal's IFCN-certified fact-checker: South Asia Check — southasiacheck.org"
        citation_surf = self.font_small.render(citation_text, True, theme.TEXT_SECONDARY)
        self.screen.blit(citation_surf, (edu_rect.x + 24, y))

        prompt_surf = self.font_body.render("Press any key or click to return to menu", True, theme.TEXT_SECONDARY)
        self.screen.blit(prompt_surf, (theme.WINDOW_WIDTH // 2 - prompt_surf.get_width() // 2, edu_rect.bottom + 26))

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