from model.world_graph import WorldGraph
from model.info_strain import InfoStrain
from model.countermeasure import CounterMeasure
from model.trait import Trait
from algorithm.spread_model import SpreadAlgorithm
from algorithm.counter_ai import CounterAI


class GameState:
    RUNNING = "running"
    WON = "won"
    LOST = "lost"


class GameEngine:
    def __init__(self, world: WorldGraph, strain: InfoStrain, counter: CounterMeasure,
                 spread_algo: SpreadAlgorithm, counter_ai: CounterAI,
                 activation_threshold: float = 0.10, points_per_tick: int = 1):
        self.world = world
        self.strain = strain
        self.counter = counter
        self.spread_algo = spread_algo
        self.counter_ai = counter_ai

        self.activation_threshold = activation_threshold  # global infection ratio that triggers the countermeasure
        self.points_per_tick = points_per_tick

        self.tick_count = 0
        self.state = GameState.RUNNING

    def start(self, seed_region_name: str, seed_amount: int = 5) -> None:
        """Seed the initial outbreak in a chosen region."""
        region = self.world.get_region(seed_region_name)
        if region is None:
            raise ValueError(f"No region named '{seed_region_name}' in world graph")
        region.seed_outbreak(seed_amount)

    def attempt_trait_acquisition(self, trait: Trait) -> bool:
        """Player-facing action: try to buy/unlock a trait. Returns success bool."""
        return self.strain.acquire_trait(trait)

    def tick(self) -> None:
        """
        Advance the simulation by one step:
          1. Run the spread algorithm (Susceptible -> Believing, Believing -> Skeptical)
          2. Check if the countermeasure should auto-activate
          3. Let the counter-AI pick its focus region (informational; the
             SIR tick already applies correction world-wide, but the AI's
             choice can be surfaced in the UI as "currently investigating: X")
          4. Award upgrade points to the player
          5. Re-check win/loss conditions
        """
        if self.state != GameState.RUNNING:
            return

        if not self.counter.active and self.world.global_infection_ratio() >= self.activation_threshold:
            self.counter.activate()

        self.spread_algo.tick(self.world, self.strain, self.counter)

        self.current_ai_focus = self.counter_ai.choose_target(self.world) if self.counter.active else None

        self.strain.award_points(self.points_per_tick)
        self.tick_count += 1

        self._check_game_over()

    def _check_game_over(self) -> None:
        if self.world.is_world_saturated():
            self.state = GameState.WON
        elif self.world.is_world_corrected():
            self.state = GameState.LOST

    def is_running(self) -> bool:
        return self.state == GameState.RUNNING

    def get_score_summary(self) -> dict:
        return {
            "ticks": self.tick_count,
            "global_infection_ratio": round(self.world.global_infection_ratio(), 3),
            "total_exposed": self.world.total_exposed(),
            "total_believing": self.world.total_believing(),
            "total_skeptical": self.world.total_skeptical(),
            "state": self.state,
        }