"""
Temporary, tick-counted modifiers for tactical abilities.

Kept deliberately separate from the permanent trait system. Traits mutate
InfoStrain's base rates additively and are never reverted -- that is the
intended design, since a trait is a permanent upgrade the player paid for.
Abilities are the opposite: they must expire. Mixing the two is exactly what
previously made Bot Amplification Surge permanent and compounding, because it
multiplied the already-trait-boosted transmission rate and nothing ever
divided it back out.

Modifiers are stored as signed ADDITIVE deltas rather than multipliers. A
delta computed once at cast time is exactly reversible -- removing it restores
the prior value with no floating-point drift -- and it cannot run away if
durations or cooldowns are ever retuned. With the shipped numbers (Bot Surge
cooldown 8, duration 3) two surges can never overlap, so compounding is
impossible by construction rather than merely unobserved.
"""


class ActiveEffect:
    """A single temporary modifier with a per-tick countdown."""

    def __init__(self, source: str, attr: str, delta: float, duration: int,
                 target: str | None = None, label: str = ""):
        self.source = source      # ability key, e.g. "bot_surge" -- read by the UI
        self.attr = attr          # which attribute this modifies
        self.delta = delta        # signed additive modifier, not a multiplier
        self.duration = duration  # total ticks this effect was granted for
        self.remaining = duration
        self.target = target      # region name for region-scoped effects, else None
        self.label = label        # human-readable name, e.g. "Echo Chamber Silo"

    def tick(self) -> bool:
        """Advance one tick. Returns True if this effect has now expired."""
        self.remaining -= 1
        return self.remaining <= 0

    @property
    def expired(self) -> bool:
        return self.remaining <= 0

    def describe(self) -> str:
        scope = f" on {self.target}" if self.target else " globally"
        return f"{self.label or self.source}{scope} ({self.remaining} turns left)"

    def __repr__(self):
        scope = self.target or "global"
        return (f"<ActiveEffect {self.source} {self.attr} {self.delta:+.3f} "
                f"{scope} {self.remaining}/{self.duration}t>")


class EffectHost:
    """
    Mixin for anything that can carry temporary modifiers (InfoStrain for
    global ability effects, Region for region-scoped ones).

    Subclasses must call `self._init_effects()` from their constructor.
    """

    def _init_effects(self) -> None:
        self.active_effects: list[ActiveEffect] = []

    def add_effect(self, effect: ActiveEffect) -> None:
        self.active_effects.append(effect)

    def tick_effects(self) -> list[ActiveEffect]:
        """Advance every active effect one tick; return the ones that expired."""
        expired = [e for e in self.active_effects if e.tick()]
        if expired:
            self.active_effects = [e for e in self.active_effects if not e.expired]
        return expired

    def temp_delta(self, attr: str) -> float:
        """Summed additive modifier currently applied to `attr` (0.0 if none)."""
        return sum(e.delta for e in self.active_effects if e.attr == attr)

    def has_effect(self, source: str) -> bool:
        return any(e.source == source for e in self.active_effects)

    def active_effect_descriptions(self) -> list[str]:
        """Human-readable list of what is currently in force, for the UI."""
        return [e.describe() for e in self.active_effects]
