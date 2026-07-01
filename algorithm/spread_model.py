from abc import ABC, abstractmethod
from model.world_graph import WorldGraph
from model.info_strain import InfoStrain
from model.countermeasure import CounterMeasure


class SpreadAlgorithm(ABC):
    @abstractmethod
    def tick(self, world: WorldGraph, strain: InfoStrain, counter: CounterMeasure) -> None:
        raise NotImplementedError


class SIRSpreadModel(SpreadAlgorithm):
    def tick(self, world: WorldGraph, strain: InfoStrain, counter: CounterMeasure) -> None:
        """
        Advance the simulation by one tick. Two passes are used:
          1) Compute new exposures for every region based on current state
             (snapshotted) so updates don't cascade unrealistically within
             a single tick.
          2) Apply all computed deltas simultaneously.
        """
        counter.tick_growth()
        exposure_deltas: dict = {}
        correction_deltas: dict = {}

        for region in world.regions:
            # --- New believers from within-region spread ---
            if region.believing > 0 and region.susceptible > 0:
                internal_exposure_rate = strain.believability_rate * (region.believing / region.population)
                new_from_internal = int(region.susceptible * internal_exposure_rate)
            else:
                new_from_internal = 0

            # --- New believers from neighboring regions (cross-edge spread) ---
            new_from_neighbors = 0
            for neighbor, weight in region.connections.items():
                if neighbor.believing == 0:
                    continue
                effective_weight = min(1.0, weight + strain.edge_weight_bonus)
                spread_chance = strain.transmission_rate * effective_weight
                neighbor_pressure = neighbor.believing / neighbor.population
                new_from_neighbors += int(region.susceptible * spread_chance * neighbor_pressure)

            total_new = min(region.susceptible, new_from_internal + new_from_neighbors)
            exposure_deltas[region] = total_new

            # --- Corrections from countermeasure ---
            # A region's base_resistance models its innate media literacy.
            # Higher media literacy means corrections land MORE easily, so it
            # acts as a multiplier > 1 on the countermeasure's effective strength.
            # correction_resistance_multiplier (1.0 for plain Region, higher
            # for PlatformNode categories like private messaging/close groups)
            # works the opposite way: it DIVIDES effectiveness, since those
            # spaces are harder to moderate regardless of local media literacy.
            if region.believing > 0 and counter.active:
                effective_strength = counter.effective_strength_against(strain)
                literacy_multiplier = 1.0 + region.base_resistance
                node_resistance = region.correction_resistance_multiplier
                corrected = int(region.believing * effective_strength * literacy_multiplier / node_resistance)
                correction_deltas[region] = min(region.believing, corrected)
            else:
                correction_deltas[region] = 0

        # --- Apply all deltas ---
        for region in world.regions:
            if exposure_deltas[region] > 0:
                region.expose(exposure_deltas[region])
            if correction_deltas[region] > 0:
                region.correct(correction_deltas[region])


class SEIRSpreadModel(SpreadAlgorithm):
    """
    SEIR-derived diffusion model: adds an Exposed (E) compartment between
    Susceptible and Believing, modeling a latency/incubation period where
    someone has encountered the information but hasn't yet been convinced
    enough to believe and start spreading it themselves.

      S -> E : driven by transmission_rate (cross-region) and exposure
                 pressure from believing neighbors/within-region believers --
                 i.e. "how many people simply SAW the rumor this tick"
      E -> B : driven by strain.incubation_rate -- "of those who saw it,
                 how many are now convinced enough to believe and share it"
      B -> K : identical correction mechanic to SIRSpreadModel

    This generally produces a more realistic, slightly delayed growth curve
    compared to SIRSpreadModel, since believers (the only compartment that
    actively spreads to others) take a tick or more to "ramp up" through the
    Exposed stage rather than instantly converting on contact.
    """

    def tick(self, world: WorldGraph, strain: InfoStrain, counter: CounterMeasure) -> None:
        counter.tick_growth()
        new_exposed_deltas: dict = {}
        new_believing_deltas: dict = {}
        correction_deltas: dict = {}

        for region in world.regions:
            # --- Susceptible -> Exposed ---
            # Same exposure-pressure math as SIR's S->B step, but the result
            # lands in `exposed` instead of `believing` -- this is the only
            # structural difference at this stage.
            if region.believing > 0 and region.susceptible > 0:
                internal_exposure_rate = strain.believability_rate * (region.believing / region.population)
                new_from_internal = int(region.susceptible * internal_exposure_rate)
            else:
                new_from_internal = 0

            new_from_neighbors = 0
            for neighbor, weight in region.connections.items():
                if neighbor.believing == 0:
                    continue
                effective_weight = min(1.0, weight + strain.edge_weight_bonus)
                spread_chance = strain.transmission_rate * effective_weight
                neighbor_pressure = neighbor.believing / neighbor.population
                new_from_neighbors += int(region.susceptible * spread_chance * neighbor_pressure)

            total_new_exposed = min(region.susceptible, new_from_internal + new_from_neighbors)
            new_exposed_deltas[region] = total_new_exposed

            # --- Exposed -> Believing ---
            # Of the people already sitting in the Exposed compartment (from
            # previous ticks), some fraction become convinced this tick.
            if region.exposed > 0:
                new_believing_deltas[region] = int(region.exposed * strain.incubation_rate)
            else:
                new_believing_deltas[region] = 0

            # --- Believing -> Skeptical (identical to SIR, including the
            # node-type correction_resistance_multiplier) ---
            if region.believing > 0 and counter.active:
                effective_strength = counter.effective_strength_against(strain)
                literacy_multiplier = 1.0 + region.base_resistance
                node_resistance = region.correction_resistance_multiplier
                corrected = int(region.believing * effective_strength * literacy_multiplier / node_resistance)
                correction_deltas[region] = min(region.believing, corrected)
            else:
                correction_deltas[region] = 0

        # --- Apply all deltas simultaneously ---
        # Order matters here only in that we must convert Exposed->Believing
        # using the PRE-tick exposed count (already captured above) before
        # adding this tick's new S->E arrivals, so nobody skips the latency
        # period entirely within a single tick.
        for region in world.regions:
            if new_believing_deltas[region] > 0:
                region.convert_exposed_to_believing(new_believing_deltas[region])
            if new_exposed_deltas[region] > 0:
                region.move_to_exposed(new_exposed_deltas[region])
            if correction_deltas[region] > 0:
                region.correct(correction_deltas[region])
