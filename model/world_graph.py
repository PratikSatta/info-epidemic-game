from model.region import Region


# The two game-ending thresholds. Both are shares, but of DIFFERENT
# denominators, and confusing the two was a real bug -- see is_world_corrected.
#
#   WIN_BELIEF_SHARE  -- share of TOTAL population that believes  (B / N)
#   LOSS_MINDSHARE    -- share of the POPULATION HOLDING AN OPINION that is
#                        skeptical  (K / (K + B))
#
# WIN_BELIEF_SHARE = 0.70 (was 0.75):
#   Measured peak belief on the default Nepal scenario is 72.9-74.7% under
#   every play policy, and 60.7-62.5% under SEIR, so a 0.75 line left the
#   default scenario unwinnable no matter how well it was played -- the only
#   reachable ending was the loss. 0.70 makes the default SIR game winnable
#   while leaving the loss reachable (default SEIR still loses).
#   NOTE: this is a stopgap. The player's abilities move peak belief by only
#   1-2 percentage points, because the countermeasure activates early and
#   ramps to full strength in ~37 ticks. Until that is rebalanced there is no
#   value of this threshold at which play, rather than scenario/model choice,
#   decides the outcome. See Section 10 of the project guide.
WIN_BELIEF_SHARE = 0.70
LOSS_MINDSHARE = 0.90


class WorldGraph:
    def __init__(self):
        self.regions: list[Region] = []

    def add_region(self, region: Region) -> None:
        self.regions.append(region)

    def get_region(self, name: str) -> Region | None:
        for r in self.regions:
            if r.name == name:
                return r
        return None

    def total_population(self) -> int:
        return sum(r.population for r in self.regions)

    def total_believing(self) -> int:
        return sum(r.believing for r in self.regions)

    def total_exposed(self) -> int:
        """SEIR-mode only: total population currently exposed but not yet believing."""
        return sum(r.exposed for r in self.regions)

    def total_skeptical(self) -> int:
        return sum(r.skeptical for r in self.regions)

    def tick_region_effects(self) -> list:
        """
        Advance every region's temporary modifiers by one tick, returning the
        ones that expired this tick. Region-scoped tactical abilities (Echo
        Chamber) live on the region they were cast on, so the engine ticks them
        all in one place here rather than reaching into regions itself.
        """
        expired = []
        for region in self.regions:
            expired.extend(region.tick_effects())
        return expired

    def global_infection_ratio(self) -> float:
        total_pop = self.total_population()
        return self.total_believing() / total_pop if total_pop else 0.0

    def is_world_saturated(self, threshold: float = WIN_BELIEF_SHARE) -> bool:
        """Win condition: has belief captured enough of the total population?

        A share of TOTAL population (B / N), including people who have not
        engaged with the claim at all. Threshold rationale: near-universal
        saturation is not the realistic target to model -- Vosoughi, Roy &
        Aral (2018) found false-news cascades reached far fewer total users
        than true ones before being corrected -- so the line is crossed at a
        strong majority rather than at 95%. The exact value is calibrated
        against measured peaks rather than asserted; see WIN_BELIEF_SHARE.
        """
        return self.global_infection_ratio() >= threshold

    def corrected_mindshare(self) -> float:
        """Share of the ENGAGED population that is skeptical: K / (K + B).

        The denominator is everyone holding an opinion about the claim --
        believers plus skeptics -- and excludes the untouched Susceptible
        population. Returns 0.0 before anyone has engaged, so the ratio is
        never undefined and never fires spuriously on an empty world.
        """
        believing = self.total_believing()
        skeptical = self.total_skeptical()
        engaged = believing + skeptical
        return (skeptical / engaged) if engaged > 0 else 0.0

    def is_world_corrected(self, threshold: float = LOSS_MINDSHARE) -> bool:
        """Loss condition: have the fact-checkers won the argument?

        Deliberately a MINDSHARE test, K / (K + B), not a share of total
        population. The previous formulation was K / N >= 0.90, which is
        bounded above by the fraction of people who EVER pass through
        Believing -- so any mechanism that lowers peak belief also lowers the
        reachable ceiling on K, and the loss becomes unreachable.

        Measured on the default Nepal scenario, K / N >= 0.90 is not reached
        until tick 2742, even though belief goes extinct around tick 259 and
        the mindshare test is already satisfied at tick 75. The ~2,500 ticks
        in between are a decided game still accepting input, because K / N
        can only creep up as the last few stragglers are corrected a handful
        of people per tick. The mindshare form ends the game when it is
        actually decided.

        Note this keeps the rule mechanism-independent: adding waning
        immunity, novelty decay or durable skepticism moves peak belief
        around, but K / (K + B) still crosses at roughly the same moment,
        because both numerator and denominator are driven by the same
        epidemic.
        """
        return self.corrected_mindshare() >= threshold

    def __repr__(self):
        return f"<WorldGraph regions={len(self.regions)} pop={self.total_population()}>"