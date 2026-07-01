# (population_estimate, internet_access_pct, is_estimate_interpolated)
# Population figures are approximate, rounded to thousands for simulation
# readability -- not exact census counts.
PROVINCE_DATA = {
    "Koshi":          {"population": 4_900_000, "internet_access_pct": 0.42, "interpolated": True},
    "Madhesh":        {"population": 6_100_000, "internet_access_pct": 0.30, "interpolated": True},
    "Bagmati":        {"population": 6_100_000, "internet_access_pct": 0.60, "interpolated": False},  # [1]
    "Gandaki":        {"population": 2_500_000, "internet_access_pct": 0.51, "interpolated": False},  # [1]
    "Lumbini":        {"population": 5_100_000, "internet_access_pct": 0.38, "interpolated": True},
    "Karnali":        {"population": 1_700_000, "internet_access_pct": 0.13, "interpolated": False},  # [1]
    "Sudurpashchim":  {"population": 2_700_000, "internet_access_pct": 0.18, "interpolated": False},  # [1]
}

NATIONAL_LITERACY_RATE = 0.763   # [2]
NATIONAL_INTERNET_PENETRATION = 0.558   # [3]

# Real comparative finding used to calibrate strain parameters in the
# "2015 Earthquake Rumors" scenario preset (see scenarios.py):
#   "a 2018 MIT study found that on Twitter, bogus news spreads six times
#    faster than real news" -- widely cited statistic from Vosoughi, Roy &
#    Aral, "The spread of true and false news online", Science 359 (2018).
MISINFO_VS_TRUE_NEWS_SPEED_MULTIPLIER = 6.0


def resistance_from_internet_access(internet_access_pct: float) -> float:
    """
    Derive a region's base_resistance (innate media-literacy proxy, used by
    Region/CounterMeasure) from its real internet-access percentage.

    Rationale: higher internet access correlates with greater exposure to
    fact-checking resources, digital literacy campaigns, and diverse news
    sources -- all concentrated in higher-connectivity areas in Nepal
    (e.g. South Asia Check, the country's only IFCN-certified fact-checking
    organization, operates out of Kathmandu/Bagmati). This is a deliberately
    simple linear mapping, scaled to the project's existing base_resistance
    range (~0.02 to 0.12 in the original hardcoded map) so traits and
    countermeasure math calibrated against that range still behave sensibly.

    This function is intentionally simple and documented as a modeling
    choice, not a precise sociological claim -- a good thing to discuss
    critically in your report's Limitations section.
    """
    return 0.02 + (internet_access_pct * 0.12)


def build_province_layout() -> dict:
    """
    Returns a dict of province_name -> {population, base_resistance, x, y}
    ready to be passed into Region() construction. Coordinates are a rough
    schematic layout (not geographically precise lat/long) arranged to
    roughly mirror Nepal's east-west, north-south province arrangement
    within the map panel's drawable area.
    """
    coords = {
        "Sudurpashchim":  (70, 150),
        "Karnali":        (160, 230),
        "Lumbini":        (220, 380),
        "Gandaki":        (300, 280),
        "Bagmati":        (400, 220),
        "Madhesh":        (470, 380),
        "Koshi":          (560, 200),
    }
    layout = {}
    for province, data in PROVINCE_DATA.items():
        x, y = coords[province]
        layout[province] = {
            "population": data["population"] // 1000,  # scale down for simulation tick math
            "base_resistance": resistance_from_internet_access(data["internet_access_pct"]),
            "internet_access_pct": data["internet_access_pct"],
            "interpolated": data["interpolated"],
            "x": x,
            "y": y,
        }
    return layout