from model import geo_data

PLATFORM_DATA = [
    ("Public Social Media",     "public",      3000),
    ("Short-Video Platforms",   "public",      2200),
    ("Encrypted Messaging",     "private",     2500),
    ("Close Group Chats",       "close_group", 1800),
]


def build_global_world():
    """
    Constructs and returns a fully-wired WorldGraph using all 202 simulation
    countries from world_countries.json. Each country is a Region instance
    with RSF-derived base_resistance. Country-to-country connections come
    from the pre-computed connection list (geographic + linguistic + migration
    ties). Platform nodes connect to every country via platform_edge_weight.

    This replaces the old hand-coded 16-country list with a fully data-driven,
    research-grounded global simulation.
    """
    from model.region import Region
    from model.platform_node import PlatformNode
    from model.world_graph import WorldGraph

    world_geo = geo_data.load_world_countries()
    country_params = world_geo.get("country_params", {})
    connections_raw = world_geo.get("connections", [])
    centroids = geo_data.load_world_country_centroids()

    world = WorldGraph()
    countries = {}

    for name in world_geo["countries"]:
        params = country_params.get(name, {})
        cx, cy = centroids.get(name, [0.5, 0.5])

        # Population: approximate from internet penetration as a schematic
        # value (only used for simulation math, not geography)
        # Base 500K, scaled by internet_pct so connected countries have
        # proportionally more "reachable" population
        inet = params.get("internet_pct", 0.5)
        pop = max(10000, int(500_000 * (0.5 + inet * 0.5)))

        region = Region(
            name=name,
            population=pop,
            x=int(cx * 700),   # schematic pixel coords
            y=int(cy * 500),
            base_resistance=params.get("base_resistance", 0.05),
        )
        countries[name] = region
        world.add_region(region)

    # Wire country-to-country edges, applying destination transmission_modifier
    for entry in connections_raw:
        a, b, base_weight = entry[0], entry[1], entry[2]
        if a not in countries or b not in countries:
            continue
        mod_b = country_params.get(b, {}).get("transmission_modifier", 1.0)
        mod_a = country_params.get(a, {}).get("transmission_modifier", 1.0)
        w_ab = round(min(1.0, base_weight * mod_b), 3)
        w_ba = round(min(1.0, base_weight * mod_a), 3)
        countries[a].connect(countries[b], w_ab)
        countries[b].connect(countries[a], w_ba)

    # Platform nodes connect to every country
    for name, category, population in PLATFORM_DATA:
        platform = PlatformNode(name, population=population,
                                x=750, y=250, category=category)
        world.add_region(platform)
        for cname, country in countries.items():
            pw = country_params.get(cname, {}).get("platform_edge_weight", 0.45)
            platform.connect(country, pw)

    return world