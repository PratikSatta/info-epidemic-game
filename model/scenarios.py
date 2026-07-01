from model.info_strain import InfoStrain


# A hypothetical "verified/true information" strain, used only as a
# comparison baseline -- never actually played by the user, just run
# programmatically alongside the rumor scenario for the report's
# comparison chapter (see tests/test_scenarios.py for a worked example).
TRUE_INFO_BASELINE_TRANSMISSION = 0.05
TRUE_INFO_BASELINE_BELIEVABILITY = 0.08

# Misinformation transmission/believability rates derived by applying the
# Vosoughi/Roy/Aral 6x multiplier to the true-information baseline above.
# This is a simplification (the original study measured retweet cascade
# depth/breadth on Twitter specifically, not a generic SIR-style rate) --
# name this assumption explicitly in your report rather than presenting
# 6x as a precise universal constant.
MISINFO_SPEED_MULTIPLIER = 6.0


def true_info_baseline() -> InfoStrain:
    """A slow-spreading, accurate-information strain for comparison purposes."""
    return InfoStrain(
        "Verified Information",
        base_transmission_rate=TRUE_INFO_BASELINE_TRANSMISSION,
        base_believability_rate=TRUE_INFO_BASELINE_BELIEVABILITY,
    )


def earthquake_rumor_scenario() -> InfoStrain:
    """
    "2015 Earthquake Rumors" preset: a misinformation strain calibrated to
    spread MISINFO_SPEED_MULTIPLIER times faster than the true-info
    baseline, modeling the kind of disaster-context rumor documented in
    post-2015-earthquake research (false aftershock predictions, fake
    relief-fund appeals). Capped at 1.0 since transmission_rate is a
    probability-like parameter.
    """
    strain = InfoStrain(
        "Earthquake Rumor (2015-style)",
        base_transmission_rate=min(1.0, TRUE_INFO_BASELINE_TRANSMISSION * MISINFO_SPEED_MULTIPLIER),
        base_believability_rate=min(1.0, TRUE_INFO_BASELINE_BELIEVABILITY * MISINFO_SPEED_MULTIPLIER),
    )
    # Disaster-context rumors tend to resist correction longer because
    # official channels are themselves disrupted immediately after a
    # disaster (a documented theme in the post-2015-earthquake literature
    # on crisis communication breakdowns) -- modeled here as elevated
    # resistance_to_correction relative to the InfoStrain default of 0.10.
    strain.resistance_to_correction = 0.25
    return strain


def default_unverified_rumor() -> InfoStrain:
    """The original, non-calibrated default used when no scenario is selected."""
    return InfoStrain("Unverified Rumor")


SCENARIOS = {
    "default": default_unverified_rumor,
    "earthquake_2015": earthquake_rumor_scenario,
}