from model.region import Region


class PlatformCategory:
    PUBLIC = "public"
    PRIVATE = "private"
    CLOSE_GROUP = "close_group"


_CORRECTION_MULTIPLIER_BY_CATEGORY = {
    PlatformCategory.PUBLIC: 1.0,
    PlatformCategory.PRIVATE: 1.6,
    PlatformCategory.CLOSE_GROUP: 2.2,
}


class PlatformNode(Region):
    """
    A non-geographic spread point: a social media platform or messaging
    space. `population` here represents a modeled "reach" pool rather than
    a literal headcount -- there is no authoritative real figure for "how
    many people are reachable through close family group chats," so this
    is treated as a calibration input, not a sourced statistic.
    """

    node_type = "platform"

    def __init__(self, name: str, population: int, x: int, y: int,
                 category: str, base_resistance: float = 0.05):
        super().__init__(name, population, x, y, base_resistance)
        if category not in _CORRECTION_MULTIPLIER_BY_CATEGORY:
            raise ValueError(
                f"Unknown platform category '{category}'. "
                f"Expected one of: {list(_CORRECTION_MULTIPLIER_BY_CATEGORY)}"
            )
        self.category = category

    @property
    def correction_resistance_multiplier(self) -> float:
        return _CORRECTION_MULTIPLIER_BY_CATEGORY[self.category]
