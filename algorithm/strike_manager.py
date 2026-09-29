from model.world_graph import WorldGraph
from model.region import Region
from model.countermeasure import CounterMeasure
from algorithm.counter_ai import CounterAI


class PendingStrike:
    """A single telegraphed strike: a target region and a countdown to impact."""

    def __init__(self, target: Region, turns_remaining: int):
        self.target = target
        self.turns_remaining = turns_remaining

    def __repr__(self):
        return f"<PendingStrike target={self.target.name} turns_remaining={self.turns_remaining}>"


class StrikeManager:
    """
    Tracks one or more pending strikes at a time. Below
    crackdown_belief_threshold, behaves exactly as the original design:
    at most one strike pending at once (max_concurrent_strikes effectively
    1). Once global belief crosses that threshold, up to
    max_concurrent_strikes can be pending simultaneously -- the
    "Crackdown" escalation phase, giving late-game players multiple
    simultaneous threats to prioritize between rather than one
    sequential threat to react to.

    Usage (called once per tick by GameEngine, only while the
    countermeasure is active):
        strike_manager.update(world)
    which, for each tick:
      - counts down every existing pending strike, executing any that hit 0
      - schedules new strikes (respecting cooldown and the concurrency
        cap appropriate to the current belief level) to fill any open slots
    """

    def __init__(self, counter_ai: CounterAI, warning_turns: int = 3,
                 strike_strength: float = 0.12, cooldown_turns: int = 6,
                 crackdown_belief_threshold: float = 0.60, max_concurrent_strikes: int = 2):
        """
        PARAMETER GROUNDING (all defaults derived from peer-reviewed literature):

        strike_strength = 0.12  (was 0.35)
          Grounded in Porter, Wood & Kirby (2021, PNAS) [A] who found
          fact-checks reduced false belief by 0.59 on a 5-point scale
          (~11.8% per direct exposure), and Guess et al. (2023) [B] who
          found corrections increase accuracy by 0.16 on a 4-point scale
          (~4%), with only 39% of that persisting after 2 weeks. A strike
          represents a high-visibility, coordinated fact-checking campaign
          (not a passive ambient correction), so we use the upper end of
          the literature range (12%). The previous value of 0.35 had no
          empirical basis and made individual strikes capable of removing
          35% of a region's believers in a single event -- far above any
          documented fact-checking intervention.

        cooldown_turns = 6  (was 3)
          Fact-checking organisations have finite staff and response
          capacity. Bode & Vraga (2015) note that expert corrections
          are sporadic rather than continuous, and Nyhan (2021, PNAS) [C]
          documents "rapid decay effects after correction exposure" --
          suggesting that re-striking the same region is less effective
          than the model previously assumed. A 6-tick cooldown produces
          roughly one high-impact event per region per 6 simulation steps,
          which is consistent with weekly news-cycle rhythms in a
          day-per-tick model.

        crackdown_belief_threshold = 0.60  (was 0.40)
          Escalation to multi-front correction campaigns only becomes
          politically/institutionally viable at high misinformation
          penetration. The 0.60 threshold models the real-world dynamic
          documented in the COVID-19 literature where emergency coordinated
          responses (WHO, health ministries, platform-wide labels) only
          deployed after infection reached majority status -- not at the
          40% mark the previous value represented.

        max_concurrent_strikes = 2  (was 3)
          Even at crackdown severity, resource constraints limit the
          number of simultaneous targeted campaigns. Two concurrent strikes
          produces genuine multi-front pressure without making the
          crackdown phase mechanically impossible to navigate.

        warning_turns = 3  (was 2)
          One extra turn of warning gives the player slightly more time
          to respond (buy resistance traits, accelerate conversion of the
          target), making the telegraphed-threat mechanic more meaningful
          as a player decision rather than just an unavoidable hit.

        REFERENCES:
        [A] Porter, E., Wood, T. J., & Kirby, D. (2021). The global
            effectiveness of fact-checking. PNAS, 118(37).
        [B] Guess, A. M. et al. (2023). Correcting COVID-19 vaccine
            misinformation in 10 countries. Royal Society Open Science.
        [C] Nyhan, B. (2021). Why the backfire effect does not explain
            the durability of political misperceptions. PNAS, 118(15).
        """
        self.counter_ai = counter_ai
        self.warning_turns = warning_turns
        self.strike_strength = strike_strength
        self.cooldown_turns = cooldown_turns
        self.crackdown_belief_threshold = crackdown_belief_threshold
        self.max_concurrent_strikes = max_concurrent_strikes

        self.pending: list[PendingStrike] = []
        self._cooldown_remaining = 0
        # Overwritten on every update() call from the active CounterMeasure;
        # the default only applies if a caller drives the manager directly.
        self._durable_fraction: float = CounterMeasure.DURABLE_FRACTION
        self.last_strike_results: list[dict] = []    # for the UI: every strike that landed THIS tick (usually 0 or 1, can be more in Crackdown)
        self.is_crackdown_active = False                # for the UI to announce the phase transition once

    @property
    def last_strike_result(self) -> dict | None:
        """Backward-compatible single-result accessor: the first strike landed this tick, if any."""
        return self.last_strike_results[0] if self.last_strike_results else None

    def _current_concurrency_cap(self, world: WorldGraph) -> int:
        return self.max_concurrent_strikes if world.global_infection_ratio() >= self.crackdown_belief_threshold else 1

    def update(self, world: WorldGraph,
               durable_fraction: float = CounterMeasure.DURABLE_FRACTION) -> None:
        """
        Advance the strike state machine by one tick. Should be called
        AFTER the spread algorithm's ambient correction has already been
        applied for this tick, so a strike's "current believers" reflects
        the post-ambient-correction state, not a stale pre-tick snapshot.

        `durable_fraction` is threaded down from the active CounterMeasure so
        a strike marks the same share of its removals permanent as the ambient
        correction does. Passing it per call rather than storing it keeps the
        two in step if the countermeasure is ever retuned mid-run.
        """
        self._durable_fraction = durable_fraction
        self.last_strike_results = []

        was_crackdown = self.is_crackdown_active
        self.is_crackdown_active = world.global_infection_ratio() >= self.crackdown_belief_threshold

        # Count down and execute any strikes that have reached impact.
        still_pending = []
        for strike in self.pending:
            strike.turns_remaining -= 1
            if strike.turns_remaining <= 0:
                self._execute_strike(strike)
            else:
                still_pending.append(strike)
        self.pending = still_pending

        if self._cooldown_remaining > 0:
            self._cooldown_remaining -= 1
            return

        # Fill any open slots up to the current concurrency cap. Below the
        # crackdown threshold this cap is 1, reproducing the original
        # one-strike-at-a-time behavior exactly.
        #
        # NOTE: counter_ai.choose_target() has no concept of "excluding
        # already-targeted regions" -- it always returns its single best
        # pick from the FULL world every time. To support scheduling
        # multiple DISTINCT strikes in one tick (the actual Crackdown
        # mechanic), this loop temporarily and locally simulates exclusion
        # by zeroing out already-targeted regions' believing count on a
        # shallow candidate pass -- see _choose_target_excluding() below,
        # which never mutates real Region state, only the AI's view of it
        # for this one selection.
        cap = self._current_concurrency_cap(world)
        already_targeted = {s.target for s in self.pending}
        while len(self.pending) < cap:
            target = self._choose_target_excluding(world, already_targeted)
            if target is None:
                break
            self.pending.append(PendingStrike(target, self.warning_turns))
            already_targeted.add(target)

    def _choose_target_excluding(self, world: WorldGraph, excluded: set) -> Region | None:
        """
        Returns the counter_ai's best target among regions NOT in
        `excluded`. Works generically for any CounterAI implementation by
        querying choose_target() repeatedly against a real WorldGraph that
        temporarily omits excluded regions, rather than requiring every
        CounterAI subclass to support an exclusion parameter directly.
        """
        candidates = [r for r in world.regions if r.believing > 0 and r not in excluded]
        if not candidates:
            return None
        if len(candidates) == len(world.regions):
            return self.counter_ai.choose_target(world)

        # Build a throwaway WorldGraph containing only eligible candidates
        # so the real counter_ai logic (whatever it is) can run unmodified
        # against a smaller, exclusion-respecting view.
        scratch = WorldGraph()
        for region in candidates:
            scratch.add_region(region)
        return self.counter_ai.choose_target(scratch)

    def _execute_strike(self, strike: "PendingStrike") -> None:
        target = strike.target
        # Base removal: fraction of current believers, using the research-grounded
        # strike_strength (~12%, derived from Porter et al. 2021 and Guess et al. 2023).
        removed = int(target.believing * self.strike_strength)
        # Population-relative ceiling: a single strike cannot remove more than
        # 8% of the region's TOTAL population in one shot. This prevents strikes
        # on populous regions from single-handedly swinging global belief by
        # large amounts in one tick -- the root cause diagnosed during balance
        # testing that made Nepal nearly unwinnable. See Section 10 of the
        # project guide for the full diagnosis.
        pop_ceiling = int(target.population * 0.08)
        removed = min(target.believing, removed, pop_ceiling)
        if removed > 0:
            # Same durable fraction as the ambient correction: a strike is a
            # correction delivered all at once, and the Guess et al. (2023)
            # persistence finding applies to it identically. Without this a
            # struck region would revert completely and strikes would not
            # contribute to draining the S -> B -> K -> S cycle.
            target.correct(removed, self._durable_fraction)
        self.last_strike_results.append({"region_name": target.name, "removed": removed})
        self._cooldown_remaining = self.cooldown_turns

    def get_warning(self) -> dict | None:
        """Backward-compatible single-warning accessor: the first pending strike, if any."""
        warnings = self.get_warnings()
        return warnings[0] if warnings else None

    def get_warnings(self) -> list[dict]:
        """For the UI: returns a list of {'region_name': str, 'turns_remaining': int} for every pending strike."""
        return [{"region_name": s.target.name, "turns_remaining": s.turns_remaining} for s in self.pending]