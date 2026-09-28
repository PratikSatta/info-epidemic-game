from abc import ABC, abstractmethod
from model.world_graph import WorldGraph
from model.info_strain import InfoStrain
from model.countermeasure import CounterMeasure


class SpreadAlgorithm(ABC):
    @abstractmethod
    def tick(self, world: WorldGraph, strain: InfoStrain, counter: CounterMeasure) -> None:
        raise NotImplementedError


class SIRSpreadModel(SpreadAlgorithm):
    def __init__(self):
        # Carries the fractional remainder of computed exposure per region
        # across ticks, keyed by region identity. Without this, int()
        # truncation silently discards any tick where susceptible * rate
        # computes to e.g. 0.97 new believers -- at low seed counts (a
        # handful of believers in a region of thousands) BOTH the internal
        # and cross-edge terms regularly compute to fractions just under 1.0,
        # which without carry-over means the simulation can stall at exactly
        # the seed amount forever, with transmission_rate climbing every
        # tick but believing never moving. The remainder is preserved here
        # and added back in on the next tick so genuine sub-1 growth
        # eventually accumulates into a real new believer instead of being
        # discarded every single tick.
        self._exposure_carry: dict = {}

        # Waning immunity: fraction of Skeptical (corrected) population that
        # drifts back to Susceptible each tick, modelling the real-world
        # finding that belief corrections decay rapidly over time.
        #
        # RESEARCH BASIS:
        # Guess et al. (2023) "Correcting COVID-19 vaccine misinformation in
        # 10 countries" found that only 39% of the initial correction accuracy
        # increase persisted when participants were recontacted two weeks later
        # -- meaning 61% of the correction effect decayed within ~14 days.
        # Modelling each tick as roughly one day, 61% decay over 14 ticks
        # gives a per-tick reversion rate of 1 - (0.39)^(1/14) ≈ 0.067.
        # We use 0.05 (slightly conservative, acknowledging that reversion
        # is not perfectly linear and that some corrected people do retain
        # their skepticism longer-term).
        #
        # This also converts the SIR model into an SIRS (Susceptible →
        # Believing → Skeptical → Susceptible) model, which is the standard
        # epidemiological approach when immunity is not permanent -- directly
        # analogous to seasonal flu models where prior immunity wanes.
        self._waning_immunity_rate: float = 0.05
        self._waning_carry: dict = {}

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
                new_from_internal = region.susceptible * internal_exposure_rate
            else:
                new_from_internal = 0.0

            # --- New believers from neighboring regions (cross-edge spread) ---
            new_from_neighbors = 0.0
            for neighbor, weight in region.connections.items():
                if neighbor.believing == 0:
                    continue
                effective_weight = min(1.0, weight + strain.edge_weight_bonus)
                spread_chance = strain.transmission_rate * effective_weight
                neighbor_pressure = neighbor.believing / neighbor.population
                new_from_neighbors += region.susceptible * spread_chance * neighbor_pressure

            # Add in any fractional remainder carried over from previous
            # ticks before truncating, so sub-1 growth accumulates instead
            # of being discarded every tick.
            raw_total = new_from_internal + new_from_neighbors + self._exposure_carry.get(region, 0.0)
            total_new = min(region.susceptible, int(raw_total))
            self._exposure_carry[region] = raw_total - total_new
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

            # --- Waning immunity (K → S reversion) ---
            # Corrected (Skeptical) people gradually drift back to
            # Susceptible, modelling the 61% correction decay found
            # by Guess et al. (2023) over ~14 days. See __init__ for
            # the full research justification and rate derivation.
            if region.skeptical > 0:
                raw_waning = region.skeptical * self._waning_immunity_rate + \
                             self._waning_carry.get(region, 0.0)
                waned = min(region.skeptical, int(raw_waning))
                self._waning_carry[region] = raw_waning - waned
                if waned > 0:
                    region.skeptical -= waned
                    region.susceptible += waned


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

    def __init__(self):
        # See SIRSpreadModel.__init__ for the rationale: int() truncation on
        # sub-1 per-tick growth can silently stall the simulation forever at
        # low seed counts. Two separate carries are needed here since S->E
        # and E->B are two independent fractional accumulations.
        self._exposed_carry: dict = {}
        self._believing_carry: dict = {}
        # Waning immunity carry -- same research basis as SIRSpreadModel.
        self._waning_immunity_rate: float = 0.05
        self._waning_carry: dict = {}

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
                new_from_internal = region.susceptible * internal_exposure_rate
            else:
                new_from_internal = 0.0

            new_from_neighbors = 0.0
            for neighbor, weight in region.connections.items():
                if neighbor.believing == 0:
                    continue
                effective_weight = min(1.0, weight + strain.edge_weight_bonus)
                spread_chance = strain.transmission_rate * effective_weight
                neighbor_pressure = neighbor.believing / neighbor.population
                new_from_neighbors += region.susceptible * spread_chance * neighbor_pressure

            raw_exposed = new_from_internal + new_from_neighbors + self._exposed_carry.get(region, 0.0)
            total_new_exposed = min(region.susceptible, int(raw_exposed))
            self._exposed_carry[region] = raw_exposed - total_new_exposed
            new_exposed_deltas[region] = total_new_exposed

            # --- Exposed -> Believing ---
            # Of the people already sitting in the Exposed compartment (from
            # previous ticks), some fraction become convinced this tick.
            if region.exposed > 0:
                raw_believing = region.exposed * strain.incubation_rate + self._believing_carry.get(region, 0.0)
                new_believing = min(region.exposed, int(raw_believing))
                self._believing_carry[region] = raw_believing - new_believing
                new_believing_deltas[region] = new_believing
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

            # --- Waning immunity (K → S reversion) ---
            # Same research basis as SIRSpreadModel: Guess et al. (2023)
            # found 61% of correction effects decay within 2 weeks.
            if region.skeptical > 0:
                raw_waning = region.skeptical * self._waning_immunity_rate + \
                             self._waning_carry.get(region, 0.0)
                waned = min(region.skeptical, int(raw_waning))
                self._waning_carry[region] = raw_waning - waned
                if waned > 0:
                    region.skeptical -= waned
                    region.susceptible += waned