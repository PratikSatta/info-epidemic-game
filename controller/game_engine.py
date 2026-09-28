from model.world_graph import WorldGraph
from model.info_strain import InfoStrain
from model.countermeasure import CounterMeasure
from model.trait import Trait
from model.effect import ActiveEffect
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
                 activation_threshold: float = 0.20, points_per_tick: int = 1):
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
        # Signals that expired on the most recent tick, so the UI can announce
        # e.g. "Bot Amplification Surge has ended" without re-deriving them.
        self.last_expired_effects: list = []

        # Time-series telemetry for real-time analytics & academic report export
        self.telemetry_history: list[dict] = []

        # Active Tactical Powers state
        self.active_abilities: dict[str, dict] = {
            "bot_surge": {"cooldown": 0, "cost": 15, "cooldown_max": 8},
            "echo_chamber": {"cooldown": 0, "cost": 20, "cooldown_max": 10},
            "sensationalist_blitz": {"cooldown": 0, "cost": 12, "cooldown_max": 6},
        }

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
          6. Count down ability cooldowns and expire timed ability effects.
          7. Record telemetry snapshot for analytics & academic report export.
          8. Re-check win/loss conditions.
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

        # Count down active ability cooldowns
        for ability_key in self.active_abilities:
            if self.active_abilities[ability_key]["cooldown"] > 0:
                self.active_abilities[ability_key]["cooldown"] -= 1

        # Expire any tactical-ability modifiers whose duration has run out.
        # Kept deliberately separate from the cooldown countdown above: the
        # cooldown gates when an ability may be cast again, the duration governs
        # how long its effect lasts. Nothing tracked the latter before, which is
        # why Bot Surge's advertised "3 turns" was silently permanent.
        self.last_expired_effects = self.strain.tick_effects()
        self.last_expired_effects.extend(self.world.tick_region_effects())

        self.tick_count += 1
        self._record_telemetry()
        self._check_game_over()

    def _check_game_over(self) -> None:
        if self.world.is_world_saturated():
            self.state = GameState.WON
        elif self.world.is_world_corrected():
            self.state = GameState.LOST

    def _record_telemetry(self) -> None:
        """
        Record a snapshot of the current simulation state for real-time analytics
        display and academic report export. Computes $R_t$ (effective reproduction
        number) at the current tick.
        """
        total_b = self.world.total_believing()
        total_e = self.world.total_exposed()
        total_k = self.world.total_skeptical()
        total_n = self.world.total_population()
        total_s = total_n - total_b - total_e - total_k

        # Effective reproduction number: R_t = (beta / gamma) * (S / N)
        # beta is the EFFECTIVE transmission rate, so an active tactical boost
        # is reflected in the reported R_t rather than being invisible to it.
        beta = self.strain.effective_transmission_rate
        gamma = self.counter.effective_strength_against(self.strain) if self.counter.active else 0.001
        r_t = (beta / gamma) * (total_s / max(1, total_n))

        self.telemetry_history.append({
            "tick": self.tick_count,
            "susceptible": total_s,
            "exposed": total_e,
            "believing": total_b,
            "skeptical": total_k,
            "population": total_n,
            "r_t": round(r_t, 3),
            "counter_active": self.counter.active,
        })

    def use_tactical_ability(self, ability_name: str,
                            target_region_name: str = None) -> dict:
        """
        Player-facing tactical abilities with cooldowns and point costs.
        Returns {"success": bool, "message": str, "effect": dict}.

        Effects are registered as timed ActiveEffect modifiers (see
        model/effect.py) rather than applied by mutating the strain directly.
        That is what makes every ability expire on schedule, and what stops a
        temporary boost from leaking permanently into the trait-driven base
        values.
        """
        if ability_name not in self.active_abilities:
            return {"success": False, "message": "Unknown ability.", "effect": {}}

        ability = self.active_abilities[ability_name]
        if ability["cooldown"] > 0:
            return {
                "success": False,
                "message": f"On cooldown ({ability['cooldown']} turns remaining).",
                "effect": {}
            }

        if self.strain.points_available < ability["cost"]:
            return {
                "success": False,
                "message": f"Not enough points (need {ability['cost']}, have {self.strain.points_available}).",
                "effect": {}
            }

        # Validate the target BEFORE any points are charged, so a missing or
        # unknown region costs the player nothing.
        target_region = None
        if ability_name == "echo_chamber":
            if not target_region_name:
                return {"success": False, "message": "Requires target region.", "effect": {}}
            target_region = self.world.get_region(target_region_name)
            if target_region is None:
                return {"success": False, "message": "Region not found.", "effect": {}}

        # Execute ability
        effect = {}
        if ability_name == "bot_surge":
            # Bot Amplification Surge: +30% of the current permanent
            # transmission rate, for 3 turns. Stored as a fixed additive delta
            # computed once here, so expiry restores the exact prior value and
            # repeated casts cannot compound.
            delta = self.strain.transmission_rate * 0.30
            self.strain.add_effect(ActiveEffect(
                source="bot_surge", attr="transmission_rate", delta=delta,
                duration=3, label="Bot Amplification Surge",
            ))
            effect = {"type": "global_transmission_boost", "delta": round(delta, 4),
                      "duration": 3}

        elif ability_name == "echo_chamber":
            # Echo Chamber Silo: +50% internal believability in the chosen
            # region for 4 turns. Applies to that region's within-region spread
            # only (region.believability_multiplier), not to arrivals over an
            # edge from a neighbour.
            target_region.add_effect(ActiveEffect(
                source="echo_chamber", attr="region_believability", delta=0.50,
                duration=4, target=target_region.name, label="Echo Chamber Silo",
            ))
            effect = {"type": "region_believability_boost", "target": target_region.name,
                      "magnitude": 0.50, "duration": 4}

        elif ability_name == "sensationalist_blitz":
            # Sensationalist Blitz: immediate conversion of 10% of the
            # Susceptible population in every region that already has
            # believers. Routed through the active spread model, so these people
            # land in whichever compartment that model uses for a fresh
            # encounter -- Believing under SIR, Exposed under SEIR.
            converted = 0
            for region in self.world.regions:
                if region.believing > 0 and region.susceptible > 0:
                    amount = int(region.susceptible * 0.10)
                    if amount > 0:
                        self.spread_algo.inject_exposure(region, amount)
                        converted += amount
            effect = {"type": "instant_conversion", "total_converted": converted}

        # Deduct cost and set cooldown
        self.strain.points_available -= ability["cost"]
        ability["cooldown"] = ability["cooldown_max"]

        return {
            "success": True,
            "message": f"{ability_name} activated successfully!",
            "effect": effect
        }

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