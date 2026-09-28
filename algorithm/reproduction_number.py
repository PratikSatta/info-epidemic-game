"""
Time-varying effective reproduction number, estimated from the incidence curve.

WHY THIS IS ESTIMATED RATHER THAN DERIVED
-----------------------------------------
The textbook analytic form for a simple SIR model is

    R_t = (beta / gamma) * (S(t) / N)

and it is only valid when the model has a single, constant removal rate gamma.
This simulation does not satisfy that condition, for three separate reasons:

  1. The countermeasure is the ONLY process that removes anyone from
     Believing. Waning immunity moves Skeptical -> Susceptible, not
     Believing -> Skeptical, and nothing else touches Believing at all. So
     before the countermeasure activates there is no removal term, gamma is
     exactly zero, and beta/gamma is division by zero. The epidemic at that
     stage is a pure SI process whose reproduction number is genuinely
     unbounded -- not a large number, but an undefined one.

  2. Once active, gamma is both time-varying (it ramps toward its cap every
     tick) and region-dependent (it is divided by each region's node
     resistance and scaled by local media literacy).

  3. Spread is a metapopulation process over a weighted graph. The rigorous
     analytic threshold for that is not a scalar ratio at all but the
     spectral radius of a next-generation matrix.

Faced with a system that has no valid closed-form R_t, this module MEASURES
it from the realised incidence curve instead, using the renewal equation --
the standard approach in real-time epidemic analytics:

    R_t = inc(t) / sum_{s >= 1} w(s) * inc(t - s)

where inc(t) is the number of new infections at tick t and w is the
generation-time (serial-interval) distribution of the active spread model.

    Cori, A., Ferguson, N. M., Fraser, C., & Cauchemez, S. (2013). A new
    framework and software to estimate time-varying reproduction numbers
    during epidemics. American Journal of Epidemiology, 178(9), 1505-1512.

WHY THE MODEL'S OWN w(s) MATTERS
--------------------------------
w is not a constant -- it is supplied by whichever spread model is running,
because the two models have genuinely different generation times:

  * SIR: a Susceptible becomes Believing and starts transmitting within a
    single tick, so the generation time is exactly one tick and w is a point
    mass at lag 1. The renewal equation then collapses to the simple ratio
    inc(t)/inc(t-1).
  * SEIR: an exposed person must pass through the latency stage first, at
    incubation_rate, so the generation time is geometric with mean
    1/incubation_rate -- about 3 ticks at the default 0.35. Applying the
    one-tick ratio here understates R_t by roughly a third, because it
    credits each new infection to last tick's cases rather than to the cases
    that actually produced it. Measured on the earthquake scenario, the
    naive ratio gives 1.40 against 2.14 for the correct renewal form.

INTERPRETATION
--------------
R_t is the number of new believers the average existing believer generates
per generation. Above 1.0 the wave is growing, below 1.0 it is decaying, and
1.0 is the epidemic threshold. Because this is measured from the simulation
rather than imposed on it, it corroborates the simulation's own outcomes --
the default scenario settles below 1.0, which is why it runs indefinitely
without ever reaching a win or loss condition.
"""


class RenewalRTEstimator:
    """
    Estimates R_t from a running incidence series via the renewal equation.

    Stateful: feed it one tick's new-infection count at a time. Returns None
    while the estimate is not yet meaningful, which is the honest answer both
    at the very start of a run and whenever incidence has stalled at zero.
    """

    # Lags beyond this contribute negligible mass to the geometric serial
    # interval at the incubation rates used here: at the default rate of 0.35
    # the 15th lag carries 0.65^15 of the mass, about 0.16%.
    MAX_LAG = 15

    # A renewal estimate is only trustworthy once the lags available so far
    # account for most of the generation-time mass. Early in a run the
    # estimator has seen too little history, and a denominator built from a
    # truncated tail would produce a number that is an artefact of the
    # truncation rather than a property of the epidemic. Reporting None until
    # the coverage threshold is met is preferable to reporting a wrong number.
    MIN_WEIGHT_COVERAGE = 0.90

    # Trailing window used to smooth the incidence curve before estimation.
    # Raw tick-to-tick counts are noisy at low case numbers -- a run seeded
    # with 8 people briefly produces ratios like 2/1. Cori et al. likewise
    # smooth the incidence curve prior to estimation.
    SMOOTHING_WINDOW = 3

    def __init__(self, max_lag: int = MAX_LAG,
                 smoothing_window: int = SMOOTHING_WINDOW,
                 min_weight_coverage: float = MIN_WEIGHT_COVERAGE):
        self.max_lag = max_lag
        self.smoothing_window = smoothing_window
        self.min_weight_coverage = min_weight_coverage
        self._incidence: list[float] = []

    def reset(self) -> None:
        """Forget all history, e.g. when a new simulation is seeded."""
        self._incidence.clear()

    def update(self, new_infections: float, weights: list[float]) -> float | None:
        """
        Record one tick's incidence and return R_t for that tick.

        `weights` is the active spread model's generation-time distribution,
        w(1), w(2), ... -- see SpreadAlgorithm.generation_time_weights().
        Returns None when R_t is undefined for this tick.
        """
        self._incidence.append(float(new_infections))
        t = len(self._incidence) - 1

        # Nothing to compare against on the first tick.
        if t < 1:
            return None

        current = self._smoothed(t)
        if current <= 0:
            return None

        # Renormalise over the lags actually available, but only accept the
        # result once that renormalisation is a minor correction (see
        # MIN_WEIGHT_COVERAGE).
        available = min(self.max_lag, len(weights), t)
        mass = sum(weights[s - 1] for s in range(1, available + 1))
        if mass < self.min_weight_coverage:
            return None

        denominator = sum(
            (weights[s - 1] / mass) * self._smoothed(t - s)
            for s in range(1, available + 1)
        )
        if denominator <= 0:
            return None

        return current / denominator

    def _smoothed(self, t: int) -> float:
        """Trailing mean of incidence ending at tick t."""
        start = max(0, t - self.smoothing_window + 1)
        window = self._incidence[start:t + 1]
        return sum(window) / len(window)
