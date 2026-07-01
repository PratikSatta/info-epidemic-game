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
    that becomes irrelevant once the countermeasure catches up -- see
    Section 10 of the project guide for the balance reasoning.
    """

    def __init__(self, name: str, cost: int, description: str = ""):
        self.name = name
        self.cost = cost              # base cost; actual cost scales with level via next_cost()
        self.description = description

    def next_cost(self, current_level: int) -> int:
        """Cost to acquire the NEXT level, given how many levels are already owned."""
        return self.cost * (current_level + 1)

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
    """

    def __init__(self, name="Viral Visuals", cost=2, potency=0.08):
        super().__init__(name, cost, "Increases transmission rate via shareable visuals")
        self.potency = potency

    def apply_effect(self, strain) -> None:
        strain.transmission_rate = min(1.0, strain.transmission_rate + self.potency)


class EmotionalTrait(Trait):
    """
    Increases believability_rate: content that triggers strong emotional
    response (fear, anger, outrage) converts Susceptible -> Believing faster.
    """

    def __init__(self, name="Emotional Hook", cost=3, potency=0.10):
        super().__init__(name, cost, "Increases conversion rate from Susceptible to Believing")
        self.potency = potency

    def apply_effect(self, strain) -> None:
        strain.believability_rate = min(1.0, strain.believability_rate + self.potency)


class PlatformTrait(Trait):
    """
    Increases cross-region connectivity weight: content optimized for a
    specific platform format spreads more easily along existing edges
    (e.g. designed for re-sharing / virality mechanics of social platforms).
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
    """

    def __init__(self, name="Correction Resistance", cost=4, potency=0.07):
        super().__init__(name, cost, "Reduces effectiveness of countermeasures against this strain")
        self.potency = potency

    def apply_effect(self, strain) -> None:
        strain.resistance_to_correction = min(0.9, strain.resistance_to_correction + self.potency)