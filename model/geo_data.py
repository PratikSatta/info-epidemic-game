import json
from pathlib import Path
from functools import lru_cache

_GEO_DIR = Path(__file__).parent.parent / "data" / "geo"


@lru_cache(maxsize=1)
def load_nepal_districts() -> dict:
    """Returns the full nepal_districts.json content: bounds + per-district outline/province."""
    with open(_GEO_DIR / "nepal_districts.json") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_nepal_province_centroids() -> dict:
    """Returns {province_name: [x, y]} in the same 0-1 space as nepal_districts.json."""
    with open(_GEO_DIR / "nepal_province_centroids.json") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_world_countries() -> dict:
    """Returns the full world_countries.json content: bounds + per-country outline."""
    with open(_GEO_DIR / "world_countries.json") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_world_country_centroids() -> dict:
    """Returns {country_name: [x, y]} in the same 0-1 space as world_countries.json."""
    with open(_GEO_DIR / "world_country_centroids.json") as f:
        return json.load(f)


def districts_for_province(province_name: str) -> dict:
    """Returns {district_name: outline} for every district belonging to the given province."""
    data = load_nepal_districts()
    return {
        name: info["outline"]
        for name, info in data["districts"].items()
        if info["province"] == province_name
    }