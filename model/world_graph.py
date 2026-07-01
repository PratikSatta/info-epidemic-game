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

    def is_world_saturated(self, threshold: float = 0.95) -> bool:
        """Win condition check: has belief saturated the world?"""
        return self.global_infection_ratio() >= threshold

    def is_world_corrected(self, threshold: float = 0.90) -> bool:
        """Loss condition check: have countermeasures corrected most of the world?"""
        total_pop = self.total_population()
        if total_pop == 0:
            return False
        return (self.total_skeptical() / total_pop) >= threshold

    def __repr__(self):
        return f"<WorldGraph regions={len(self.regions)} pop={self.total_population()}>"