import csv
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from model.world_graph import WorldGraph
    from model.info_strain import InfoStrain


class CSVLoadError(Exception):
    """Raised for problems severe enough that no usable data could be loaded at all."""
    pass


def load_regions_csv(filepath: str) -> tuple[dict, list[str]]:
    """
    Parse a regions CSV into a layout dict compatible with the same shape
    build_province_layout() returns: {region_name: {population, base_resistance,
    x, y, connects_to: [...], edge_weights: [...]}}.

    Returns (layout, warnings) -- warnings is a list of human-readable
    strings describing any rows that were skipped or auto-corrected, even
    if the overall load succeeded. Callers should display these to the
    user (e.g. in the news ticker or a console message) rather than
    discarding them silently.

    Raises CSVLoadError if the file doesn't exist, is empty, is missing
    required columns entirely, or every row failed validation (i.e.
    nothing usable could be loaded).
    """
    path = Path(filepath)
    if not path.exists():
        raise CSVLoadError(f"Regions CSV not found: {filepath}")

    warnings: list[str] = []
    layout: dict = {}

    required_columns = {"name", "population", "base_resistance", "x", "y"}

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise CSVLoadError(f"Regions CSV is empty: {filepath}")

        missing_columns = required_columns - set(reader.fieldnames)
        if missing_columns:
            raise CSVLoadError(
                f"Regions CSV is missing required column(s): {sorted(missing_columns)}. "
                f"Found columns: {reader.fieldnames}"
            )

        rows = list(reader)

    for i, row in enumerate(rows, start=2):  # start=2: row 1 is the header
        name = (row.get("name") or "").strip()
        if not name:
            warnings.append(f"Row {i}: skipped — empty or missing 'name'")
            continue
        if name in layout:
            warnings.append(f"Row {i}: skipped — duplicate region name '{name}'")
            continue

        try:
            population = int(float(row["population"]))
            if population <= 0:
                raise ValueError("population must be > 0")
        except (ValueError, KeyError):
            warnings.append(f"Row {i} ('{name}'): skipped — invalid population '{row.get('population')}'")
            continue

        try:
            base_resistance = float(row["base_resistance"])
            if not (0.0 <= base_resistance <= 1.0):
                raise ValueError("base_resistance must be between 0.0 and 1.0")
        except (ValueError, KeyError):
            warnings.append(f"Row {i} ('{name}'): skipped — invalid base_resistance '{row.get('base_resistance')}'")
            continue

        try:
            x = int(float(row["x"]))
            y = int(float(row["y"]))
        except (ValueError, KeyError):
            warnings.append(f"Row {i} ('{name}'): skipped — invalid x/y coordinates")
            continue

        connects_to_raw = (row.get("connects_to") or "").strip()
        edge_weights_raw = (row.get("edge_weights") or "").strip()
        connects_to = [c.strip() for c in connects_to_raw.split(";") if c.strip()] if connects_to_raw else []
        edge_weights_str = [w.strip() for w in edge_weights_raw.split(";") if w.strip()] if edge_weights_raw else []

        edge_weights: list[float] = []
        if connects_to and len(edge_weights_str) != len(connects_to):
            warnings.append(
                f"Row {i} ('{name}'): connects_to has {len(connects_to)} entries but "
                f"edge_weights has {len(edge_weights_str)} — using default weight 0.5 for all edges from this region"
            )
            edge_weights = [0.5] * len(connects_to)
        else:
            for w in edge_weights_str:
                try:
                    weight = float(w)
                    edge_weights.append(max(0.0, min(1.0, weight)))
                except ValueError:
                    edge_weights.append(0.5)
                    warnings.append(f"Row {i} ('{name}'): invalid edge weight '{w}' — defaulted to 0.5")

        layout[name] = {
            "population": population,
            "base_resistance": base_resistance,
            "x": x,
            "y": y,
            "connects_to": connects_to,
            "edge_weights": edge_weights,
        }

    if not layout:
        raise CSVLoadError(f"No valid regions could be loaded from {filepath} — check warnings: {warnings}")

    # Second pass: drop connections that reference a region not present in
    # the file at all (typo'd name, or intentionally partial data) rather
    # than crashing when the caller tries to wire up the graph.
    valid_names = set(layout.keys())
    for name, data in layout.items():
        kept_connects = []
        kept_weights = []
        for target, weight in zip(data["connects_to"], data["edge_weights"]):
            if target in valid_names:
                kept_connects.append(target)
                kept_weights.append(weight)
            else:
                warnings.append(f"Region '{name}': connection to unknown region '{target}' ignored")
        data["connects_to"] = kept_connects
        data["edge_weights"] = kept_weights

    return layout, warnings


# Recognized strain parameters and their valid ranges, used to validate
# strain_config.csv contents. Keeping this as an explicit allow-list (rather
# than just passing through arbitrary column names) catches typos like
# "transmision_rate" instead of silently ignoring the intended override.
_STRAIN_NUMERIC_FIELDS = {
    "transmission_rate": (0.0, 1.0),
    "believability_rate": (0.0, 1.0),
    "incubation_rate": (0.0, 1.0),
    "resistance_to_correction": (0.0, 1.0),
}


def load_strain_config_csv(filepath: str) -> tuple[dict, list[str]]:
    """
    Parse a strain-config CSV (parameter,value rows) into a plain dict of
    {parameter_name: value}, suitable for passing as keyword overrides when
    constructing an InfoStrain. Returns (config, warnings).

    Raises CSVLoadError if the file doesn't exist or has no usable rows.
    """
    path = Path(filepath)
    if not path.exists():
        raise CSVLoadError(f"Strain config CSV not found: {filepath}")

    warnings: list[str] = []
    config: dict = {}

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or "parameter" not in reader.fieldnames or "value" not in reader.fieldnames:
            raise CSVLoadError(
                f"Strain config CSV must have 'parameter' and 'value' columns. Found: {reader.fieldnames}"
            )
        rows = list(reader)

    for i, row in enumerate(rows, start=2):
        key = (row.get("parameter") or "").strip()
        value = (row.get("value") or "").strip()
        if not key:
            continue

        if key == "name":
            config["name"] = value
            continue

        if key not in _STRAIN_NUMERIC_FIELDS:
            warnings.append(f"Row {i}: unrecognized parameter '{key}' — ignored (check for typos)")
            continue

        try:
            numeric_value = float(value)
        except ValueError:
            warnings.append(f"Row {i}: parameter '{key}' has non-numeric value '{value}' — ignored")
            continue

        low, high = _STRAIN_NUMERIC_FIELDS[key]
        if not (low <= numeric_value <= high):
            warnings.append(
                f"Row {i}: parameter '{key}' value {numeric_value} outside [{low}, {high}] — clamped"
            )
            numeric_value = max(low, min(high, numeric_value))

        config[key] = numeric_value

    if not config:
        raise CSVLoadError(f"No usable parameters could be loaded from {filepath} — check warnings: {warnings}")

    return config, warnings


def build_world_from_csv(filepath: str) -> tuple["WorldGraph", list[str]]:
    """
    Convenience wrapper: load_regions_csv() + construct actual Region and
    WorldGraph objects, including wiring up connections. Returns
    (world_graph, warnings).

    This is the function view/main.py calls when the player chooses to
    load a custom map -- everything downstream (the spread algorithm, the
    map renderer, the game engine) is completely unaware that the data
    came from a CSV instead of build_province_layout(), since both produce
    the same Region/WorldGraph objects.
    """
    # Local import to avoid a circular import at module load time
    # (region.py and world_graph.py don't import csv_loader.py).
    from model.region import Region
    from model.world_graph import WorldGraph

    layout, warnings = load_regions_csv(filepath)

    world = WorldGraph()
    regions = {}
    for name, data in layout.items():
        regions[name] = Region(
            name,
            population=data["population"],
            x=data["x"],
            y=data["y"],
            base_resistance=data["base_resistance"],
        )
        world.add_region(regions[name])

    connected_pairs = set()
    for name, data in layout.items():
        for target, weight in zip(data["connects_to"], data["edge_weights"]):
            pair = frozenset((name, target))
            if pair in connected_pairs:
                continue  # already connected from the other direction
            regions[name].connect(regions[target], weight)
            connected_pairs.add(pair)

    isolated = [name for name, r in regions.items() if not r.connections]
    if isolated:
        warnings.append(
            f"Region(s) with no connections at all (isolated, rumor can never reach them "
            f"from elsewhere): {isolated}"
        )

    return world, warnings


def build_strain_from_csv(filepath: str) -> tuple["InfoStrain", list[str]]:
    """
    Convenience wrapper: load_strain_config_csv() + construct an actual
    InfoStrain with those parameters applied, falling back to InfoStrain's
    own defaults for any field not present in the file. Returns
    (strain, warnings).
    """
    from model.info_strain import InfoStrain

    config, warnings = load_strain_config_csv(filepath)

    kwargs = {}
    if "transmission_rate" in config:
        kwargs["base_transmission_rate"] = config["transmission_rate"]
    if "believability_rate" in config:
        kwargs["base_believability_rate"] = config["believability_rate"]
    if "incubation_rate" in config:
        kwargs["base_incubation_rate"] = config["incubation_rate"]

    name = config.get("name", "Custom Strain (CSV)")
    strain = InfoStrain(name, **kwargs)

    if "resistance_to_correction" in config:
        strain.resistance_to_correction = config["resistance_to_correction"]

    return strain, warnings