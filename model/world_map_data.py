# (population_millions, internet_penetration_pct, estimated)
COUNTRY_DATA = {
    "China":         {"population_millions": 1410, "internet_pct": 0.80, "estimated": False},
    "India":          {"population_millions": 1430, "internet_pct": 0.62, "estimated": False},
    "Japan":           {"population_millions": 124,  "internet_pct": 0.88, "estimated": False},
    "Nepal":            {"population_millions": 30,   "internet_pct": 0.56, "estimated": False},
    "United Kingdom":    {"population_millions": 68,   "internet_pct": 0.98, "estimated": False},
    "Germany":            {"population_millions": 84,   "internet_pct": 0.94, "estimated": True},
    "Russia":              {"population_millions": 144,  "internet_pct": 0.88, "estimated": False},
    "Nigeria":              {"population_millions": 220,  "internet_pct": 0.38, "estimated": False},
    "Egypt":                 {"population_millions": 113,  "internet_pct": 0.85, "estimated": True},
    "South Africa":            {"population_millions": 60,   "internet_pct": 0.73, "estimated": True},
    "United States":            {"population_millions": 335,  "internet_pct": 0.92, "estimated": False},
    "Mexico":                    {"population_millions": 128,  "internet_pct": 0.78, "estimated": True},
    "Brazil":                     {"population_millions": 216,  "internet_pct": 0.84, "estimated": False},
    "Argentina":                   {"population_millions": 46,   "internet_pct": 0.87, "estimated": True},
    "Australia":                    {"population_millions": 26,   "internet_pct": 0.91, "estimated": True},
    "Saudi Arabia":                  {"population_millions": 36,   "internet_pct": 0.99, "estimated": False},
}

# Rough schematic (x, y) layout within the map panel, arranged by continent
# rather than true geographic projection -- readability over cartographic
# accuracy, consistent with how Plague Inc's own map is stylized rather than
# a precise map projection. Coordinates are scaled to fit comfortably within
# the default 680x560 map panel (leaving margin for node radius up to ~34px
# and below-node name labels).
_COUNTRY_COORDS = {
    "United States": (110, 160), "Mexico": (90, 250), "Brazil": (160, 380), "Argentina": (150, 470),
    "United Kingdom": (260, 90), "Germany": (300, 110), "Russia": (420, 80),
    "Nigeria": (260, 330), "Egypt": (330, 270), "South Africa": (300, 460),
    "Saudi Arabia": (390, 230),
    "China": (480, 170), "India": (400, 280), "Nepal": (450, 250), "Japan": (560, 150),
    "Australia": (520, 460),
}

# Real-ish adjacency / strong-tie pairs (shared borders, major migration or
# trade corridors) -- edge weights are this project's own connectivity
# ESTIMATE (no single sourced "rumor transmission strength between country
# X and Y" statistic exists), same caveat as the Nepal province map.
COUNTRY_CONNECTIONS = [
    ("China", "India", 0.5), ("China", "Russia", 0.5), ("China", "Japan", 0.4),
    ("India", "Nepal", 0.7), ("India", "Saudi Arabia", 0.3),
    ("Russia", "Germany", 0.4), ("Germany", "United Kingdom", 0.7),
    ("United Kingdom", "United States", 0.6), ("United States", "Mexico", 0.7),
    ("Mexico", "Brazil", 0.3), ("Brazil", "Argentina", 0.6),
    ("Nigeria", "Egypt", 0.3), ("Egypt", "Saudi Arabia", 0.5),
    ("Nigeria", "South Africa", 0.3), ("Egypt", "United Kingdom", 0.3),
    ("Australia", "United Kingdom", 0.3), ("Japan", "United States", 0.4),
    ("Germany", "Saudi Arabia", 0.2), ("United States", "Brazil", 0.3),
]

# (name, category, relative reach in millions, estimated correction-resistance category)
PLATFORM_DATA = [
    ("Public Social Media", "public", 3000),
    ("Short-Video Platforms", "public", 2200),
    ("Encrypted Messaging", "private", 2500),
    ("Close Group Chats", "close_group", 1800),
]

_PLATFORM_COORDS = {
    "Public Social Media": (590, 270),
    "Short-Video Platforms": (590, 340),
    "Encrypted Messaging": (590, 410),
    "Close Group Chats": (590, 480),
}


def resistance_from_internet_pct(internet_pct: float) -> float:
    """Same linear mapping pattern as real_world_data.py, reused here for consistency."""
    return 0.02 + (internet_pct * 0.12)


def build_world_map_layout() -> dict:
    """
    Returns {country_name: {population, base_resistance, x, y, internet_pct, estimated}}
    ready for Region() construction -- same shape contract as
    real_world_data.build_province_layout(), so view/main.py can treat both
    built-in maps interchangeably.
    """
    layout = {}
    for name, data in COUNTRY_DATA.items():
        x, y = _COUNTRY_COORDS[name]
        layout[name] = {
            "population": data["population_millions"] * 10,  # scaled down for simulation tick math
            "base_resistance": resistance_from_internet_pct(data["internet_pct"]),
            "internet_pct": data["internet_pct"],
            "estimated": data["estimated"],
            "x": x,
            "y": y,
        }
    return layout


def build_platform_layout() -> list:
    """
    Returns a list of (name, category, population, x, y) tuples for
    PlatformNode construction. Unlike countries, platform "population" is
    an explicit reach-pool modeling choice, not a sourced statistic --
    see model/platform_node.py docstring.
    """
    result = []
    for name, category, reach_millions in PLATFORM_DATA:
        x, y = _PLATFORM_COORDS[name]
        result.append((name, category, reach_millions * 10, x, y))
    return result


def build_global_world():
    """
    Constructs and returns a fully-wired WorldGraph: 16 countries (Region
    instances) connected by real-ish adjacency/trade-tie edges, plus 4
    PlatformNode instances each connected to EVERY country with an edge
    weight scaled by that country's internet penetration (a platform can't
    reach a population it can't get online to in the first place, regardless
    of platform type).

    Local imports avoid a circular dependency (region.py/platform_node.py
    don't import this module).
    """
    from model.region import Region
    from model.platform_node import PlatformNode
    from model.world_graph import WorldGraph

    world = WorldGraph()
    country_layout = build_world_map_layout()
    platform_specs = build_platform_layout()

    countries = {}
    for name, data in country_layout.items():
        countries[name] = Region(
            name,
            population=data["population"],
            x=data["x"],
            y=data["y"],
            base_resistance=data["base_resistance"],
        )
        world.add_region(countries[name])

    for name_a, name_b, weight in COUNTRY_CONNECTIONS:
        countries[name_a].connect(countries[name_b], weight)

    platforms = {}
    for name, category, population, x, y in platform_specs:
        platforms[name] = PlatformNode(name, population=population, x=x, y=y, category=category)
        world.add_region(platforms[name])

    # Connect every platform to every country, weight scaled by that
    # country's internet penetration -- a real-data-driven parameter,
    # consistent with this project's other connectivity estimates.
    for platform in platforms.values():
        for name, country in countries.items():
            internet_pct = country_layout[name]["internet_pct"]
            edge_weight = round(0.2 + internet_pct * 0.5, 3)   # scales roughly 0.2-0.7
            platform.connect(country, edge_weight)

    return world