
from model.trait import Trait


class InfoStrain:
    # Synergy bonus to edge_weight_bonus awarded each time the player crosses
    # a new distinct-trait-type threshold. Keys are the number of distinct trait
    # types owned; value is the bonus applied at that crossing. Rewards spreading
    # investment across trait types rather than spamming one.
    _DIVERSIFICATION_BONUS_AT_COUNT: dict[int, float] = {
        2: 0.03,   # own 2 distinct types -> small bonus
        3: 0.06,   # own 3 distinct types -> meaningful bonus
        4: 0.10,   # own all 4 types     -> large bonus
    }

    def __init__(self, name: str, base_transmission_rate: float = 0.15,
                 base_believability_rate: float = 0.20,
                 base_incubation_rate: float = 0.35,
                 points_cap: int = 8):
        self.name = name
        self._transmission_rate = base_transmission_rate   # P(spread along an edge per tick)
        self._believability_rate = base_believability_rate  # P(Susceptible -> Exposed/Believing per exposure)
        self._incubation_rate = base_incubation_rate          # SEIR only: P(Exposed -> Believing per tick),
                                                                 # i.e. how fast a doubtful person becomes convinced
        self.resistance_to_correction = 0.10                # P(countermeasure fails to convert back)
        self.edge_weight_bonus = 0.0                          # bonus multiplier on edge weights
        self.detection_risk = 0.0                              # see Trait downsides: raises how visible the
                                                                  # strain is, lowering the countermeasure's
                                                                  # activation threshold (GameEngine reads this)
        self.points_cap = points_cap                            # max points that can be banked at once -- a
                                                                  # deliberate "DNA-point" style cap so the player
                                                                  # can't hoard indefinitely and is nudged to spend
                                                                  # with intent rather than dump everything the
                                                                  # moment they're flush (see Section 10/balance notes)
        self.points_available: int = min(5, points_cap)         # "DNA points" equivalent
        self.acquired_traits: list[Trait] = []                 # full history, in acquisition order (kept for back-compat/UI)
        self.trait_levels: dict[str, int] = {}                  # trait class name -> level count

    # ---- Encapsulated properties with validation ----
    @property
    def transmission_rate(self) -> float:
        return self._transmission_rate

    @transmission_rate.setter
    def transmission_rate(self, value: float) -> None:
        self._transmission_rate = max(0.0, min(1.0, value))

    @property
    def believability_rate(self) -> float:
        return self._believability_rate

    @believability_rate.setter
    def believability_rate(self, value: float) -> None:
        self._believability_rate = max(0.0, min(1.0, value))

    @property
    def incubation_rate(self) -> float:
        return self._incubation_rate

    @incubation_rate.setter
    def incubation_rate(self, value: float) -> None:
        self._incubation_rate = max(0.0, min(1.0, value))

    # ---- Trait management ----
    def acquire_trait(self, trait: Trait) -> bool:
        """
        Attempt to unlock (or re-level) a trait. Returns True if successful
        (enough points for the NEXT level's cost), False otherwise.
        Demonstrates polymorphic dispatch: each trait applies its effect
        differently via apply_effect().

        Traits can be acquired multiple times -- each level's cost is
        trait.next_cost(current_level), which scales up quadratically per
        level (see Trait.next_cost()), making single-trait spam
        self-limiting. A diversification synergy bonus is also applied to
        edge_weight_bonus each time the player crosses a new distinct-trait-
        type threshold, rewarding spreading investment across types.
        """
        type_key = type(trait).__name__
        current_level = self.trait_levels.get(type_key, 0)
        cost = trait.next_cost(current_level)

        if cost > self.points_available:
            return False

        distinct_before = len(self.trait_levels)
        trait.apply_effect(self)          # polymorphic call
        self.points_available -= cost
        self.acquired_traits.append(trait)
        self.trait_levels[type_key] = current_level + 1

        # Award diversification synergy bonus if this acquisition crossed a
        # new distinct-type threshold (i.e. this was the first level of a
        # brand-new trait type).
        distinct_after = len(self.trait_levels)
        if distinct_after > distinct_before:
            bonus = self._DIVERSIFICATION_BONUS_AT_COUNT.get(distinct_after, 0.0)
            if bonus:
                self.edge_weight_bonus = min(0.5, self.edge_weight_bonus + bonus)

        return True

    def trait_level(self, trait: Trait) -> int:
        """Current level of the given trait's type (0 if never acquired)."""
        return self.trait_levels.get(type(trait).__name__, 0)

    def award_points(self, amount: int) -> None:
        """
        Called by the controller when the player earns more upgrade points.
        Capped at points_cap -- points awarded beyond the cap are lost, not
        banked, which is the entire point of the cap: it nudges the player
        to spend deliberately rather than let points pile up indefinitely
        with no cost to waiting.
        """
        self.points_available = min(self.points_cap, self.points_available + amount)

    def __repr__(self):
        return (f"<InfoStrain '{self.name}' "
                f"transmission={self._transmission_rate:.2f} "
                f"believability={self._believability_rate:.2f} "
                f"incubation={self._incubation_rate:.2f} "
                f"traits={[t.name for t in self.acquired_traits]}>")