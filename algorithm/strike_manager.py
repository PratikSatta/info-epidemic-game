from model.world_graph import WorldGraph
from model.region import Region
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

    def __init__(self, counter_ai: CounterAI, warning_turns: int = 2,
                 strike_strength: float = 0.35, cooldown_turns: int = 3,
                 crackdown_belief_threshold: float = 0.40, max_concurrent_strikes: int = 3):
        self.counter_ai = counter_ai
        self.warning_turns = warning_turns        # how many turns of advance warning a strike gives
        self.strike_strength = strike_strength       # fraction of the target's CURRENT believers removed on impact
        self.cooldown_turns = cooldown_turns           # minimum turns between a SLOT's strikes
        self.crackdown_belief_threshold = crackdown_belief_threshold   # global belief ratio that unlocks multi-strike
        self.max_concurrent_strikes = max_concurrent_strikes             # ceiling on simultaneous pending strikes once unlocked

        self.pending: list[PendingStrike] = []
        self._cooldown_remaining = 0
        self.last_strike_results: list[dict] = []    # for the UI: every strike that landed THIS tick (usually 0 or 1, can be more in Crackdown)
        self.is_crackdown_active = False                # for the UI to announce the phase transition once

    @property
    def last_strike_result(self) -> dict | None:
        """Backward-compatible single-result accessor: the first strike landed this tick, if any."""
        return self.last_strike_results[0] if self.last_strike_results else None

    def _current_concurrency_cap(self, world: WorldGraph) -> int:
        return self.max_concurrent_strikes if world.global_infection_ratio() >= self.crackdown_belief_threshold else 1

    def update(self, world: WorldGraph) -> None:
        """
        Advance the strike state machine by one tick. Should be called
        AFTER the spread algorithm's ambient correction has already been
        applied for this tick, so a strike's "current believers" reflects
        the post-ambient-correction state, not a stale pre-tick snapshot.
        """
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
        # Base removal: fraction of current believers.
        removed = int(target.believing * self.strike_strength)
        # Population-relative ceiling: a single strike cannot remove more than
        # 8% of the region's TOTAL population in one shot. This prevents strikes
        # on populous regions (which hold a large fraction of total world pop on
        # small maps like Nepal) from single-handedly swinging global belief by
        # 20%+ in one tick -- the root cause diagnosed during balance testing
        # that made Nepal nearly unwinnable regardless of other tuning.
        # See Section 10 (Known Tuning Notes) for the full diagnosis.
        pop_ceiling = int(target.population * 0.08)
        removed = min(target.believing, removed, pop_ceiling)
        if removed > 0:
            target.correct(removed)
        self.last_strike_results.append({"region_name": target.name, "removed": removed})
        self._cooldown_remaining = self.cooldown_turns

    def get_warning(self) -> dict | None:
        """Backward-compatible single-warning accessor: the first pending strike, if any."""
        warnings = self.get_warnings()
        return warnings[0] if warnings else None

    def get_warnings(self) -> list[dict]:
        """For the UI: returns a list of {'region_name': str, 'turns_remaining': int} for every pending strike."""
        return [{"region_name": s.target.name, "turns_remaining": s.turns_remaining} for s in self.pending]
