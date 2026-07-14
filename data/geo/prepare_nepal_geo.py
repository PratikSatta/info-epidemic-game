import json
import sys
from pathlib import Path

try:
    from shapely.geometry import shape
except ImportError:
    print("This script requires shapely: pip install shapely --break-system-packages")
    sys.exit(1)


# Authoritative district -> province mapping, Constitution of Nepal 2015
# Schedule 4, using pre-2017 district names (matching the 75-feature source
# dataset, before Nawalparasi/Rukum were split).
DISTRICT_TO_PROVINCE = {
    # Koshi (14)
    "BHOJPUR": "Koshi", "DHANKUTA": "Koshi", "ILAM": "Koshi", "JHAPA": "Koshi",
    "KHOTANG": "Koshi", "MORANG": "Koshi", "OKHALDHUNGA": "Koshi", "PANCHTHAR": "Koshi",
    "SANKHUWASABHA": "Koshi", "SOLUKHUMBU": "Koshi", "SUNSARI": "Koshi", "TAPLEJUNG": "Koshi",
    "TEHRATHUM": "Koshi", "UDAYAPUR": "Koshi",
    # Madhesh (8)
    "PARSA": "Madhesh", "BARA": "Madhesh", "RAUTAHAT": "Madhesh", "SARLAHI": "Madhesh",
    "DHANUSA": "Madhesh", "SIRAHA": "Madhesh", "MAHOTTARI": "Madhesh", "SAPTARI": "Madhesh",
    # Bagmati (13)
    "SINDHULI": "Bagmati", "RAMECHHAP": "Bagmati", "DOLAKHA": "Bagmati", "BHAKTAPUR": "Bagmati",
    "DHADING": "Bagmati", "KATHMANDU": "Bagmati", "KAVRE": "Bagmati", "LALITPUR": "Bagmati",
    "NUWAKOT": "Bagmati", "RASUWA": "Bagmati", "SINDHUPALCHOK": "Bagmati", "CHITWAN": "Bagmati",
    "MAKWANPUR": "Bagmati",
    # Gandaki (10 -- pre-split; Nawalparasi listed once under Lumbini below
    # per the old undivided district, consistent with this 75-district dataset)
    "BAGLUNG": "Gandaki", "GORKHA": "Gandaki", "KASKI": "Gandaki", "LAMJUNG": "Gandaki",
    "MANANG": "Gandaki", "MUSTANG": "Gandaki", "MYAGDI": "Gandaki", "PARBAT": "Gandaki",
    "SYANGJA": "Gandaki", "TANAHU": "Gandaki",
    # Lumbini (12, including the still-undivided Nawalparasi and Rukum)
    "KAPILBASTU": "Lumbini", "NAWALPARASI": "Lumbini", "RUPANDEHI": "Lumbini",
    "ARGHAKHANCHI": "Lumbini", "GULMI": "Lumbini", "PALPA": "Lumbini", "DANG": "Lumbini",
    "PYUTHAN": "Lumbini", "ROLPA": "Lumbini", "RUKUM": "Lumbini", "BANKE": "Lumbini", "BARDIYA": "Lumbini",
    # Karnali (9)
    "SALYAN": "Karnali", "DOLPA": "Karnali", "HUMLA": "Karnali", "JUMLA": "Karnali",
    "KALIKOT": "Karnali", "MUGU": "Karnali", "SURKHET": "Karnali", "DAILEKH": "Karnali",
    "JAJARKOT": "Karnali",
    # Sudurpashchim (9)
    "KAILALI": "Sudurpashchim", "ACHHAM": "Sudurpashchim", "DOTI": "Sudurpashchim",
    "BAJHANG": "Sudurpashchim", "BAJURA": "Sudurpashchim", "KANCHANPUR": "Sudurpashchim",
    "DADELDHURA": "Sudurpashchim", "BAITADI": "Sudurpashchim", "DARCHULA": "Sudurpashchim",
}

SIMPLIFY_TOLERANCE_DEGREES = 0.025   # tuned by inspection -- low enough to keep
                                       # each district's distinctive shape
                                       # recognizable, high enough to keep
                                       # point counts small for fast rendering


def main():
    here = Path(__file__).parent
    districts_path = here / "nepal_districts_raw.geojson"
    if not districts_path.exists():
        print(
            f"Expected raw district data at {districts_path} -- not found.\n"
            f"This file is intentionally NOT included in the project deliverable "
            f"(it's ~2MB of raw survey-precision data only needed to REGENERATE "
            f"nepal_districts.json, never needed to run the game itself).\n"
            f"To regenerate, download it first:\n"
            f"  curl -sL https://raw.githubusercontent.com/mesaugat/geojson-nepal/master/nepal-districts.geojson "
            f"-o {districts_path}"
        )
        sys.exit(1)

    with open(districts_path) as f:
        raw = json.load(f)

    # First pass: collect every district's simplified polygon and the
    # overall bounding box across ALL of Nepal, so normalization is
    # consistent across districts rather than each one being normalized
    # to its own bounds (which would destroy relative positioning).
    simplified_by_district = {}
    min_lon = min_lat = float("inf")
    max_lon = max_lat = float("-inf")

    skipped = []
    for feature in raw["features"]:
        district_name = feature["properties"]["DISTRICT"]
        province = DISTRICT_TO_PROVINCE.get(district_name)
        if province is None:
            skipped.append(district_name)
            continue

        geom = shape(feature["geometry"])
        simplified = geom.simplify(SIMPLIFY_TOLERANCE_DEGREES, preserve_topology=True)

        # A handful of districts may simplify to a MultiPolygon (e.g. if
        # they have small detached parts) -- take the largest piece by
        # area for a clean single-outline render, since sub-islands are
        # not meaningful at this stylization level.
        if simplified.geom_type == "MultiPolygon":
            simplified = max(simplified.geoms, key=lambda g: g.area)

        coords = list(simplified.exterior.coords)
        simplified_by_district[district_name] = {"province": province, "coords": coords}

        for lon, lat in coords:
            min_lon, max_lon = min(min_lon, lon), max(max_lon, lon)
            min_lat, max_lat = min(min_lat, lat), max(max_lat, lat)

    if skipped:
        print(f"WARNING: {len(skipped)} districts had no province mapping and were skipped: {skipped}")

    # Second pass: normalize every coordinate into 0-1 space using the
    # SAME bounds for every district, and flip Y (screen coordinates grow
    # downward, latitude grows upward).
    output = {
        "bounds_lon": [min_lon, max_lon],
        "bounds_lat": [min_lat, max_lat],
        "districts": {},
    }
    for district_name, info in simplified_by_district.items():
        normalized = []
        for lon, lat in info["coords"]:
            x = (lon - min_lon) / (max_lon - min_lon)
            y = 1.0 - (lat - min_lat) / (max_lat - min_lat)
            normalized.append([round(x, 4), round(y, 4)])
        output["districts"][district_name] = {
            "province": info["province"],
            "outline": normalized,
        }

    out_path = here / "nepal_districts.json"
    with open(out_path, "w") as f:
        json.dump(output, f)

    total_points = sum(len(d["outline"]) for d in output["districts"].values())
    print(f"Wrote {len(output['districts'])} districts ({total_points} total points) to {out_path}")


if __name__ == "__main__":
    main()