from model.region import Region


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

    def global_infection_ratio(self) -> float:
        total_pop = self.total_population()
        return self.total_believing() / total_pop if total_pop else 0.0

    def is_world_saturated(self, threshold: float = 0.75) -> bool:
        """Win condition check: has belief reached majority saturation?
        Threshold set at 75% rather than 95% -- consistent with research
        showing even highly viral misinformation rarely achieves universal
        penetration, but reaching supermajority (3/4 of the population)
        represents a decisive information-environment capture. Vosoughi,
        Roy & Aral (2018) found false news cascades reached far fewer
        total users than true news before being corrected, suggesting
        near-universal saturation is not the realistic target to model."""
        return self.global_infection_ratio() >= threshold

    def is_world_corrected(self, threshold: float = 0.90) -> bool:
        """Loss condition check: have countermeasures corrected most of the world?"""
        total_pop = self.total_population()
        if total_pop == 0:
            return False
        return (self.total_skeptical() / total_pop) >= threshold

    def __repr__(self):
        return f"<WorldGraph regions={len(self.regions)} pop={self.total_population()}>"