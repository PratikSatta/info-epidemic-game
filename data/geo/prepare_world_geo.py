import json
import sys
from pathlib import Path

try:
    from shapely.geometry import shape
except ImportError:
    print("This script requires shapely: pip install shapely --break-system-packages")
    sys.exit(1)


# The 16 countries used in model/world_map_data.py, mapped to their exact
# name in the geo-countries source dataset where it differs from this
# project's display name.
NAME_ALIASES = {
    "United States": "United States of America",
}

TARGET_COUNTRIES = [
    "China", "India", "Japan", "Nepal", "United Kingdom", "Germany", "Russia",
    "Nigeria", "Egypt", "South Africa", "United States", "Mexico", "Brazil",
    "Argentina", "Australia", "Saudi Arabia",
]

SIMPLIFY_TOLERANCE_DEGREES = 0.3   # countries span much larger areas than
                                      # Nepal's districts, so a coarser
                                      # tolerance keeps point counts
                                      # reasonable while still preserving
                                      # each country's recognizable silhouette

# Some countries' true extent would badly distort a SHARED projection if
# included at full size -- most notably Russia, which genuinely spans from
# ~27 degrees E to 180 degrees E (the antimeridian), more than twice the
# east-west span of any other country in this set. Rather than let Russia's
# real scale compress every other country into a sliver, this script
# (a) uses INDEPENDENT per-country normalization (each country fills its
# own 0-1 box) and (b) for Russia specifically, clips to its more
# recognizable western/central extent so its node position and shape stay
# legible at the schematic scale this map is drawn at. This is a deliberate
# stylization choice, named explicitly: this is not Russia's true
# territorial extent, the same kind of simplification already applied to
# every country by dropping offshore territories.
MANUAL_CLIP_BOUNDS = {
    # (min_lon, min_lat, max_lon, max_lat)
    "Russia": (27.0, 41.0, 105.0, 78.0),
}


def main():
    here = Path(__file__).parent
    countries_path = here / "world_countries_raw.geojson"
    if not countries_path.exists():
        print(
            f"Expected raw country data at {countries_path} -- not found.\n"
            f"This file is intentionally NOT included in the project deliverable "
            f"(it's ~14MB of raw survey-precision data for all 258 world countries, "
            f"only needed to REGENERATE world_countries.json, never needed to run "
            f"the game itself).\n"
            f"To regenerate, download it first:\n"
            f"  curl -sL https://raw.githubusercontent.com/datasets/geo-countries/master/data/countries.geojson "
            f"-o {countries_path}"
        )
        sys.exit(1)

    with open(countries_path) as f:
        raw = json.load(f)

    by_source_name = {f["properties"]["name"]: f for f in raw["features"]}

    simplified_by_country = {}
    min_lon = min_lat = float("inf")
    max_lon = max_lat = float("-inf")
    missing = []

    for display_name in TARGET_COUNTRIES:
        source_name = NAME_ALIASES.get(display_name, display_name)
        feature = by_source_name.get(source_name)
        if feature is None:
            missing.append(display_name)
            continue

        geom = shape(feature["geometry"])
        if geom.geom_type == "MultiPolygon":
            geom = max(geom.geoms, key=lambda g: g.area)  # mainland only, see module docstring

        if display_name in MANUAL_CLIP_BOUNDS:
            from shapely.geometry import box
            clip_lon_min, clip_lat_min, clip_lon_max, clip_lat_max = MANUAL_CLIP_BOUNDS[display_name]
            geom = geom.intersection(box(clip_lon_min, clip_lat_min, clip_lon_max, clip_lat_max))
            if geom.geom_type == "MultiPolygon":
                geom = max(geom.geoms, key=lambda g: g.area)

        simplified = geom.simplify(SIMPLIFY_TOLERANCE_DEGREES, preserve_topology=True)
        if simplified.geom_type == "MultiPolygon":
            simplified = max(simplified.geoms, key=lambda g: g.area)

        coords = list(simplified.exterior.coords)
        simplified_by_country[display_name] = coords

        for lon, lat in coords:
            min_lon, max_lon = min(min_lon, lon), max(max_lon, lon)
            min_lat, max_lat = min(min_lat, lat), max(max_lat, lat)

    if missing:
        print(f"WARNING: could not find source geometry for: {missing}")

    # SHARED projection across all 16 countries (using one common bounding
    # box, not independent per-country boxes) so real relative geographic
    # positions are preserved -- China genuinely renders east of India,
    # Brazil genuinely renders east of Argentina, etc. This is what makes
    # it an actual world map rather than a grid of disconnected shapes.
    output = {
        "bounds_lon": [min_lon, max_lon],
        "bounds_lat": [min_lat, max_lat],
        "countries": {},
    }
    for name, coords in simplified_by_country.items():
        normalized = []
        for lon, lat in coords:
            x = (lon - min_lon) / (max_lon - min_lon)
            y = 1.0 - (lat - min_lat) / (max_lat - min_lat)
            normalized.append([round(x, 4), round(y, 4)])
        output["countries"][name] = normalized

    out_path = here / "world_countries.json"
    with open(out_path, "w") as f:
        json.dump(output, f)

    total_points = sum(len(c) for c in output["countries"].values())
    print(f"Wrote {len(output['countries'])} countries ({total_points} total points) to {out_path}")


if __name__ == "__main__":
    main()