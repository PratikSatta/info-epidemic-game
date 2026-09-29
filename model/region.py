from model.effect import EffectHost


class Region(EffectHost):
    node_type: str = "geographic"   # overridden by PlatformNode subclasses

    def __init__(self, name: str, population: int, x: int, y: int,
                 base_resistance: float = 0.05):
        self.name = name
        self.population = population
        self.x = x   # screen coordinates for rendering, also usable for distance calc
        self.y = y
        self.base_resistance = base_resistance  # innate media-literacy level (0-1)

        # Compartments (counts, not fractions). `exposed` is unused by
        # SIRSpreadModel and stays at 0 in that mode; SEIRSpreadModel uses it.
        self.susceptible = population
        self.exposed = 0
        self.believing = 0
        self.skeptical = 0
        # Sub-count of `skeptical`: people whose correction is permanent and
        # who will never wane back to Susceptible. Deliberately a sub-count
        # rather than a fifth compartment, so `population` is still exactly
        # the sum of the compartments, `total_skeptical()` still reports
        # everyone skeptical, and every existing reader of `skeptical` (win/
        # loss, telemetry, map colouring, panels) keeps working untouched.
        # See CounterMeasure.DURABLE_FRACTION for why this exists.
        self.durable_skeptical = 0
        self._durable_carry = 0.0

        self.connections: dict["Region", float] = {}   # neighbor -> edge weight (0-1)
        self._init_effects()                           # temporary region-scoped modifiers

    # ---- Temporary region-scoped modifiers (tactical abilities) ----
    @property
    def believability_multiplier(self) -> float:
        """
        Multiplier on this region's INTERNAL exposure rate, from temporary
        region-scoped abilities (Echo Chamber Silo). 1.0 = no effect, which is
        the default for every region with nothing active on it. This applies
        only to within-region spread, not to cross-edge arrivals from
        neighbours -- the ability is advertised as an internal boost.
        """
        return max(0.0, 1.0 + self.temp_delta("region_believability"))

    # ---- Correction-resistance hook (overridden by PlatformNode) ----
    @property
    def correction_resistance_multiplier(self) -> float:
        """
        Multiplier applied to CounterMeasure effectiveness when correcting
        believers in THIS node specifically (separate from the strain's own
        resistance_to_correction). 1.0 = no effect (the default, used by all
        plain geographic Region instances -- existing behavior is unchanged).
        PlatformNode subclasses override this to model how private/encrypted
        spaces resist moderation more than public ones (see
        model/platform_node.py for the real-research grounding).
        """
        return 1.0

    # ---- Graph construction ----
    def connect(self, other: "Region", weight: float = 0.5) -> None:
        """Create a bidirectional weighted edge between two regions."""
        self.connections[other] = weight
        other.connections[self] = weight

    # ---- State mutation (encapsulated) ----
    def seed_outbreak(self, amount: int = 1) -> None:
        """Introduce the strain into this region for the first time (direct to Believing)."""
        amount = min(amount, self.susceptible)
        self.susceptible -= amount
        self.believing += amount

    def expose(self, new_believers: int) -> None:
        """SIR-style direct transition: Susceptible -> Believing (no latency)."""
        new_believers = max(0, min(new_believers, self.susceptible))
        self.susceptible -= new_believers
        self.believing += new_believers

    def move_to_exposed(self, amount: int) -> None:
        """SEIR-style transition: Susceptible -> Exposed (seen it, not convinced yet)."""
        amount = max(0, min(amount, self.susceptible))
        self.susceptible -= amount
        self.exposed += amount

    def convert_exposed_to_believing(self, amount: int) -> None:
        """SEIR-style transition: Exposed -> Believing (now convinced, starts spreading)."""
        amount = max(0, min(amount, self.exposed))
        self.exposed -= amount
        self.believing += amount

    def correct(self, corrected: int, durable_fraction: float = 0.0) -> None:
        """
        Believing -> Skeptical, used identically by both SIR and SEIR models.

        `durable_fraction` of the corrected people are additionally marked as
        permanently skeptical. They still count toward `skeptical` like
        everyone else; the difference is that the waning-immunity step in the
        spread models will not return them to Susceptible. A fraction of 0.0
        (the default) reproduces the previous behaviour exactly, which is what
        any caller that does not pass one gets.

        The fractional carry mirrors the remainder-carry pattern already used
        for exposures and waning: durable_fraction * corrected is normally not
        an integer, and truncating it on every tick would systematically
        under-count durable skepticism across a long run.
        """
        corrected = max(0, min(corrected, self.believing))
        if corrected <= 0:
            return
        self.believing -= corrected
        self.skeptical += corrected

        # Clamped twice over: never more than the people just corrected, and
        # never more than the skeptical pool actually contains, so the
        # invariant 0 <= durable_skeptical <= skeptical cannot be broken.
        raw_durable = corrected * durable_fraction + self._durable_carry
        durable = min(int(raw_durable), corrected)
        self._durable_carry = raw_durable - int(raw_durable)
        self.durable_skeptical += min(durable, self.skeptical - self.durable_skeptical)

    @property
    def revertible_skeptical(self) -> int:
        """
        Skeptical people who can still wane back to Susceptible.

        Waning immunity draws only from this pool, so the durable fraction
        stays corrected permanently. This is what stops S -> B -> K -> S from
        being a closed cycle that the simulation can never escape.
        """
        return self.skeptical - self.durable_skeptical

    def infection_ratio(self) -> float:
        """Fraction of population currently believing -- used for color-coding the map."""
        return self.believing / self.population if self.population else 0.0

    def exposed_ratio(self) -> float:
        """Fraction of population currently exposed-but-not-yet-believing (SEIR only)."""
        return self.exposed / self.population if self.population else 0.0

    def is_actively_spreading(self) -> bool:
        return self.believing > 0

    def __repr__(self):
        return (f"<{type(self).__name__} {self.name} pop={self.population} "
                f"S={self.susceptible} E={self.exposed} B={self.believing} "
                f"K={self.skeptical} (durable={self.durable_skeptical})>")