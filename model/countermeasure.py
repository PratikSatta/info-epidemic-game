class CounterMeasure:
    def __init__(self, base_strength: float = 0.04, growth_rate: float = 0.008, cap: float = 0.55):
        self.strength = base_strength      # P(Believing -> Skeptical per tick, before region resistance)
        self.growth_rate = growth_rate     # how fast strength increases each tick while active
        self.cap = cap                      # strength plateaus here -- real-world fact-checking
                                              # capacity is finite, it can't approach 100% effectiveness
        self.active = False

    def activate(self) -> None:
        self.active = True

    def tick_growth(self) -> None:
        """Call once per simulation tick while active; strength ramps up over time, then plateaus at cap."""
        if self.active:
            self.strength = min(self.cap, self.strength + self.growth_rate)

    def effective_strength_against(self, strain) -> float:
        """
        Countermeasure strength is reduced by the strain's
        resistance_to_correction trait value.
        """
        return self.strength * (1.0 - strain.resistance_to_correction)

    def __repr__(self):
        return f"<CounterMeasure strength={self.strength:.2f} active={self.active}>"