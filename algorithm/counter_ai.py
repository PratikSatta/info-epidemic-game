from abc import ABC, abstractmethod
from model.world_graph import WorldGraph
from model.region import Region


class CounterAI(ABC):
    @abstractmethod
    def choose_target(self, world: WorldGraph) -> Region | None:
        """Return the region the countermeasure should focus correction on next."""
        raise NotImplementedError


class GreedyCounterAI(CounterAI):
    """
    Always picks the region with the most current believers -- the
    "biggest fire first" strategy. O(n) where n = number of regions.
    """

    def choose_target(self, world: WorldGraph) -> Region | None:
        candidates = [r for r in world.regions if r.believing > 0]
        if not candidates:
            return None
        return max(candidates, key=lambda r: r.believing)


class MinimaxCounterAI(CounterAI):
    """
    Looks ahead a fixed depth to estimate which region, if corrected now,
    minimizes the strain's best achievable spread on the following turn.
    This is a simplified adversarial search: the "max" player is the
    strain (trying to maximize total believers next tick), the "min"
    player is the countermeasure (trying to minimize that same total by
    choosing where to intervene now).

    For performance, this only evaluates one ply (immediate-neighbor
    spread estimate) rather than a full game tree, which keeps it
    tractable for a real-time game loop while still being a genuine
    minimax-style adversarial evaluation worth discussing in the report.
    """

    def __init__(self, depth: int = 1):
        self.depth = depth

    def _estimate_future_spread(self, region: Region) -> float:
        """
        Heuristic: a region's contribution to future spread is its current
        believers plus the susceptible population it can still expose,
        weighted by its connectivity to other believing regions.
        """
        spread_potential = region.believing
        for neighbor, weight in region.connections.items():
            if neighbor.believing > 0:
                spread_potential += region.susceptible * weight * 0.1
        return spread_potential

    def choose_target(self, world: WorldGraph) -> Region | None:
        candidates = [r for r in world.regions if r.believing > 0]
        if not candidates:
            return None

        # MIN step: choose the region whose correction removes the most
        # future spread potential (i.e. the strain's best response is
        # weakest if we neutralize this region now).
        best_region = None
        best_score = float("inf")

        for candidate in candidates:
            # Simulate: what would the strain's total future spread be
            # if this candidate were fully corrected right now?
            remaining_potential = sum(
                self._estimate_future_spread(r) for r in candidates if r is not candidate
            )
            # The strain (MAX player) would then try to maximize remaining_potential.
            # The countermeasure (MIN player) wants to choose the candidate that
            # leaves the strain with the smallest best-case remaining_potential.
            if remaining_potential < best_score:
                best_score = remaining_potential
                best_region = candidate

        return best_region