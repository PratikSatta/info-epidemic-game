class Region:
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

        self.connections: dict["Region", float] = {}   # neighbor -> edge weight (0-1)

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

    def correct(self, corrected: int) -> None:
        """Believing -> Skeptical, used identically by both SIR and SEIR models."""
        corrected = max(0, min(corrected, self.believing))
        self.believing -= corrected
        self.skeptical += corrected

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
                f"S={self.susceptible} E={self.exposed} B={self.believing} K={self.skeptical}>")