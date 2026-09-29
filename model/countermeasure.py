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
    #
    # durable_fraction:  the 39% half of that same Guess et al. (2023)
    #   finding. Participants recontacted two weeks after a correction still
    #   showed 39% of the initial accuracy gain, so 39% of a correction is
    #   durable and 61% decays. The decay half was already modelled (the
    #   5%/tick waning in algorithm/spread_model.py); this is the
    #   persistence half, which was missing.
    #
    #   Without it every corrected person eventually returns to Susceptible,
    #   which makes S -> B -> K -> S a CLOSED cycle. A closed cycle has an
    #   interior fixed point, and the simulation parks there: measured on the
    #   real engine the default scenario sits at 31% S / 21% B / 48% K from
    #   tick 75 onwards and never moves again, so neither win nor loss is
    #   ever reached. Marking 39% of each correction durable drains the cycle
    #   by that fraction on every lap, so belief eventually dies out and the
    #   game reaches a conclusion on its own.
    DURABLE_FRACTION: float = 0.39

    def __init__(self,
                 base_strength: float = 0.011,
                 growth_rate: float = 0.003,
                 cap: float = 0.120,
                 durable_fraction: float = DURABLE_FRACTION):
        self.strength = base_strength
        self.growth_rate = growth_rate
        self.cap = cap
        self.durable_fraction = durable_fraction
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