from model.world_graph import WorldGraph
from model.info_strain import InfoStrain
from model.countermeasure import CounterMeasure
from model.trait import Trait
from algorithm.spread_model import SpreadAlgorithm
from algorithm.counter_ai import CounterAI
from algorithm.strike_manager import StrikeManager


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
        self.strike_manager = StrikeManager(counter_ai)

        self.activation_threshold = activation_threshold  # global infection ratio that triggers the countermeasure
        self.points_per_tick = points_per_tick

        self.tick_count = 0
        self.state = GameState.RUNNING
        self.current_ai_focus = None
        self.last_strike_result = None

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
             -- this already includes the ambient, gradual correction mechanic,
             unchanged from before this redesign.
          2. Check if the countermeasure should auto-activate.
          3. Update the StrikeManager: count down any pending telegraphed
             strike (executing it at zero) or schedule a new one. This is
             the NEW layer added on top of ambient correction, giving the
             player a specific, advance-warned threat to react to rather
             than just watching aggregate numbers drift.
          4. Let the counter-AI pick its (informational) focus region for
             the map highlight -- separate from StrikeManager's own target
             selection, since the AI may be "watching" one region while a
             strike is queued on another.
          5. Award upgrade points to the player, respecting InfoStrain's cap.
          6. Re-check win/loss conditions.
        """
        if self.state != GameState.RUNNING:
            return

        if not self.counter.active:
            # detection_risk (raised by VisualTrait/EmotionalTrait -- see
            # model/trait.py) lowers the EFFECTIVE activation threshold:
            # a louder, more attention-grabbing strain gets noticed by
            # fact-checkers sooner than a quieter one at the same belief
            # level. This is what makes detection_risk a real tradeoff
            # rather than a cosmetic number -- it changes WHEN the
            # countermeasure turns on, not just how strong it eventually is.
            effective_threshold = max(0.02, self.activation_threshold - self.strain.detection_risk)
            if self.world.global_infection_ratio() >= effective_threshold:
                self.counter.activate()

        self.spread_algo.tick(self.world, self.strain, self.counter)

        if self.counter.active:
            self.strike_manager.update(self.world)
            self.last_strike_result = self.strike_manager.last_strike_result
        else:
            self.last_strike_result = None

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