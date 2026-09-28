class CounterMeasure:
    # ── Research-derived parameter documentation ─────────────────────────
    # base_strength:  ~1.1% correction/tick at game start. Reflects the
    #   early-stage targeting failure described in Nyhan (2021) [C] --
    #   fact-checks are slow to reach the people actually holding the
    #   false belief.
    #
    # growth_rate:  0.3%/tick ramp. Slow-building, reflecting the lag
    #   between misinformation peaks and coordinated correction campaigns
    #   documented in the literature.
    #
    # cap:  12% max correction/tick. Grounded in the ~11.8% per-exposure
    #   reduction from Porter et al. (2021) [A] and the continued-influence
    #   effect ceiling documented by Pennycook & Rand (2022) [D].
    #   Also consistent with Guess et al. (2023) [B] finding that only
    #   39% of corrections persist after 2 weeks -- implying most
    #   "corrected" individuals drift back, so the effective net correction
    #   rate is substantially lower than raw exposure numbers suggest.

    def __init__(self,
                 base_strength: float = 0.011,
                 growth_rate: float = 0.003,
                 cap: float = 0.120):
        self.strength = base_strength
        self.growth_rate = growth_rate
        self.cap = cap
        self.active = False

    def activate(self) -> None:
        self.active = True

    def tick_growth(self) -> None:
        """Call once per simulation tick while active; strength ramps up
        over time, then plateaus at cap. The plateau models finite real-world
        fact-checking capacity -- even at peak mobilisation, corrections
        cannot approach 100% effectiveness (continued influence effect,
        Pennycook & Rand 2022 [D])."""
        if self.active:
            self.strength = min(self.cap, self.strength + self.growth_rate)

    def effective_strength_against(self, strain) -> float:
        """
        Countermeasure strength is reduced by the strain's
        resistance_to_correction trait value, modelling the real-world
        finding that corrections are less effective when the false belief
        is congruent with prior attitudes (Flynn, Nyhan & Reifler 2017;
        Pennycook & Rand 2022 [D]).
        """
        return self.strength * (1.0 - strain.resistance_to_correction)

    def __repr__(self):
        return f"<CounterMeasure strength={self.strength:.3f} cap={self.cap:.3f} active={self.active}>"