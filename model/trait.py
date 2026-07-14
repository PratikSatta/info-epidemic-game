from abc import ABC, abstractmethod


class Trait(ABC):
    """
    Abstract base class for all traits an InfoStrain can acquire.

    A trait modifies the strain's spread characteristics when applied.
    Concrete subclasses must implement apply_effect(). Traits can be
    acquired more than once (re-leveled) -- each subsequent level costs
    more (cost * level, via next_cost()) but keeps stacking its effect via
    apply_effect(), since apply_effect() adds a delta rather than setting
    an absolute value. This gives the player an ongoing lever against the
    CounterMeasure's continuous growth instead of a one-time fixed boost
    that becomes irrelevant once the countermeasure catches up
    """

    def __init__(self, name: str, cost: int, description: str = ""):
        self.name = name
        self.cost = cost              # base cost; actual cost scales with level via next_cost()
        self.description = description

    def next_cost(self, current_level: int) -> int:
        """Cost to acquire the NEXT level, given how many levels are already owned.
        Quadratic scaling so single-trait spam becomes self-limiting -- the cost
        of a 4th level of the same trait is 16x base, while the 1st level of a
        new trait is only 1x base, making diversification genuinely cheaper than
        depth past level 2-3.
        """
        return self.cost * (current_level + 1) ** 2

    @abstractmethod
    def apply_effect(self, strain) -> None:
        """
        Apply this trait's effect to the given InfoStrain instance.
        Must be overridden by subclasses. Called once per level acquired,
        so implementations should ADD a delta (not set an absolute value)
        for repeated acquisition to make sense.
        """
        raise NotImplementedError

    def __repr__(self):
        return f"<{self.__class__.__name__} '{self.name}' cost={self.cost}>"


class VisualTrait(Trait):
    """
    Increases transmission_rate: content that is visually engaging
    (images, memes, infographics) spreads faster between regions.

    TRADEOFF: also raises detection_risk -- eye-catching, highly shareable
    content draws attention faster, lowering the countermeasure's effective
    activation threshold (see GameEngine, which reads strain.detection_risk
    to adjust how early fact-checkers start paying attention). This is the
    classic Plague-Inc-style tension: the trait that makes you spread
    fastest is also the one that gets you noticed fastest.
    """

    def __init__(self, name="Viral Visuals", cost=2, potency=0.08, detection_penalty=0.015):
        super().__init__(name, cost, "Increases transmission rate via shareable visuals (but easier to notice)")
        self.potency = potency
        self.detection_penalty = detection_penalty

    def apply_effect(self, strain) -> None:
        strain.transmission_rate = min(1.0, strain.transmission_rate + self.potency)
        strain.detection_risk = min(0.5, strain.detection_risk + self.detection_penalty)


class EmotionalTrait(Trait):
    """
    Increases believability_rate: content that triggers strong emotional
    response (fear, anger, outrage) converts Susceptible -> Believing faster.

    TRADEOFF: also raises detection_risk -- outrage-bait content draws
    scrutiny (and reports) faster than calmer content, same mechanism as
    VisualTrait's tradeoff but modeling a different real cause.
    """

    def __init__(self, name="Emotional Hook", cost=3, potency=0.10, detection_penalty=0.02):
        super().__init__(name, cost, "Increases conversion rate from Susceptible to Believing (but easier to notice)")
        self.potency = potency
        self.detection_penalty = detection_penalty

    def apply_effect(self, strain) -> None:
        strain.believability_rate = min(1.0, strain.believability_rate + self.potency)
        strain.detection_risk = min(0.5, strain.detection_risk + self.detection_penalty)


class PlatformTrait(Trait):
    """
    Increases cross-region connectivity weight: content optimized for a
    specific platform format spreads more easily along existing edges
    (e.g. designed for re-sharing / virality mechanics of social platforms).

    Deliberately left as the one "clean" trait with no downside -- every
    upgrade tree needs at least one safe, no-tradeoff option, both for
    game-feel reasons (not every choice should be a dilemma) and so a
    risk-averse playstyle remains viable.
    """

    def __init__(self, name="Platform Optimized", cost=2, potency=0.05):
        super().__init__(name, cost, "Increases effective edge weight between connected regions")
        self.potency = potency

    def apply_effect(self, strain) -> None:
        strain.edge_weight_bonus = min(0.5, strain.edge_weight_bonus + self.potency)


class ResistanceTrait(Trait):
    """
    Decreases the rate at which fact-checking / countermeasures convert
    Believing -> Skeptical. Models things like distrust-of-media framing,
    or "do your own research" rhetorical patterns that resist correction.

    TRADEOFF: slightly reduces transmission_rate -- going quiet/cautious
    enough to resist scrutiny costs you reach, modeling the real tension
    between staying low-key (resists correction) and being loud (spreads
    fast but draws fire). This is the mirror image of VisualTrait/
    EmotionalTrait's tradeoff: those trade reach for safety risk, this
    trades reach for safety itself.
    """

    def __init__(self, name="Correction Resistance", cost=4, potency=0.07, transmission_penalty=0.02):
        super().__init__(name, cost, "Reduces effectiveness of countermeasures against this strain (but spreads more cautiously)")
        self.potency = potency
        self.transmission_penalty = transmission_penalty

    def apply_effect(self, strain) -> None:
        strain.resistance_to_correction = min(0.9, strain.resistance_to_correction + self.potency)
        strain.transmission_rate = max(0.02, strain.transmission_rate - self.transmission_penalty)