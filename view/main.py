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
from view.map_view import MapView
from view.ui_panels import StatsPanel, TraitPanel, NewsTicker


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
        self.tick_event = pygame.USEREVENT + 1
        pygame.time.set_timer(self.tick_event, 600)  # simulation advances every 600ms

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

        map_rect = pygame.Rect(20, 20, 680, 560)
        stats_rect = pygame.Rect(720, 20, 360, 160)
        trait_rect = pygame.Rect(720, 196, 360, 230)
        news_rect = pygame.Rect(720, 442, 360, 138)

        self.map_view = MapView(map_rect, self.font_body, self.font_small)
        self.stats_panel = StatsPanel(stats_rect, self.font_body, self.font_header)
        self.trait_panel = TraitPanel(trait_rect, self.font_body, self.font_header, self.trait_catalog)
        self.news_ticker = NewsTicker(news_rect, self.font_small)

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
        self._seeded = True
        self.state = STATE_PLAYING

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
                if event.type == self.tick_event:
                    self.engine.tick()
                    self._check_for_news_events()
                    if self.engine.state != GameState.RUNNING:
                        self.state = STATE_GAME_OVER

                if event.type == pygame.MOUSEBUTTONDOWN:
                    clicked_trait = self.trait_panel.handle_click(event.pos)
                    if clicked_trait is not None:
                        success = self.engine.attempt_trait_acquisition(clicked_trait)
                        if success:
                            new_level = self.strain.trait_level(clicked_trait)
                            self.news_ticker.push(f"{clicked_trait.name} leveled up to Lv.{new_level}")

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

    def draw_menu(self) -> None:
        self.screen.fill(theme.BG_COLOR)
        title = self.font_title.render("InfoSpread Simulator", True, theme.TEXT_PRIMARY)
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

        subtitle = self.font_body.render(
            "Click or press any other key to seed the rumor and begin", True, theme.TEXT_SECONDARY
        )
        self.screen.blit(title, (theme.WINDOW_WIDTH // 2 - title.get_width() // 2, 190))
        self.screen.blit(model_line, (theme.WINDOW_WIDTH // 2 - model_line.get_width() // 2, 260))
        self.screen.blit(scenario_line, (theme.WINDOW_WIDTH // 2 - scenario_line.get_width() // 2, 295))
        self.screen.blit(map_line, (theme.WINDOW_WIDTH // 2 - map_line.get_width() // 2, 330))
        self.screen.blit(data_line, (theme.WINDOW_WIDTH // 2 - data_line.get_width() // 2, 365))
        self.screen.blit(subtitle, (theme.WINDOW_WIDTH // 2 - subtitle.get_width() // 2, 415))

    def draw_playing(self) -> None:
        self.screen.fill(theme.BG_COLOR)
        self.map_view.draw(self.screen, self.world, focus_region=self.engine.current_ai_focus)
        self.stats_panel.draw(self.screen, self.engine.get_score_summary(), self.strain.name,
                               model_name=self.selected_model_name)
        self.trait_panel.draw(self.screen, self.strain)
        self.news_ticker.draw(self.screen)

    def draw_game_over(self) -> None:
        self.screen.fill(theme.BG_COLOR)
        summary = self.engine.get_score_summary()
        result_text = "RUMOR WENT VIRAL" if summary["state"] == GameState.WON else "FACT-CHECKERS WON"
        result_color = theme.TEXT_WARNING if summary["state"] == GameState.WON else theme.ACCENT

        title = self.font_title.render(result_text, True, result_color)
        self.screen.blit(title, (theme.WINDOW_WIDTH // 2 - title.get_width() // 2, 60))

        lines = [
            f"Ticks survived: {summary['ticks']}",
            f"Peak global belief: {summary['global_infection_ratio'] * 100:.1f}%",
        ]
        y = 120
        for line in lines:
            text_surf = self.font_body.render(line, True, theme.TEXT_PRIMARY)
            self.screen.blit(text_surf, (theme.WINDOW_WIDTH // 2 - text_surf.get_width() // 2, y))
            y += 28

        # --- Educational layer: real media-literacy takeaway, shown every round ---
        y += 20
        edu_header = self.font_header.render("Before you go — spotting real misinformation:", True, theme.ACCENT)
        self.screen.blit(edu_header, (theme.WINDOW_WIDTH // 2 - edu_header.get_width() // 2, y))
        y += 32

        for tip in MEDIA_LITERACY_TIPS:
            tip_surf = self.font_small.render(f"• {tip}", True, theme.TEXT_PRIMARY)
            self.screen.blit(tip_surf, (theme.WINDOW_WIDTH // 2 - tip_surf.get_width() // 2, y))
            y += 22

        y += 14
        if self._using_custom_data_this_round:
            citation_text = "Verify claims via the International Fact-Checking Network (170+ orgs worldwide) — ifcncodeofprinciples.poynter.org"
        elif self.selected_map_name == "world":
            citation_text = "Global fact-checking: International Fact-Checking Network (IFCN) — ifcncodeofprinciples.poynter.org"
        else:
            citation_text = "Nepal's IFCN-certified fact-checker: South Asia Check — southasiacheck.org"
        citation_surf = self.font_small.render(citation_text, True, theme.TEXT_SECONDARY)
        self.screen.blit(citation_surf, (theme.WINDOW_WIDTH // 2 - citation_surf.get_width() // 2, y))
        y += 30

        prompt_surf = self.font_body.render("Press any key to return to menu", True, theme.TEXT_SECONDARY)
        self.screen.blit(prompt_surf, (theme.WINDOW_WIDTH // 2 - prompt_surf.get_width() // 2, y))

    def run(self) -> None:
        while True:
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