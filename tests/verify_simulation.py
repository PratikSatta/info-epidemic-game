"""
Full verification pass over the InfoSpread simulator.

Exercises the real engine and the real pygame app headless:
 1. module imports
 2. world construction (both maps)
 3. simulation invariants (both scenarios x both models)
 4. telemetry schema
 5. tactical abilities
 6. report export
 7. headless app: layout, events, both map modes

Run with:

    python tests/verify_simulation.py

Exits non-zero if any check fails, so it is usable as a smoke test in a
pre-demo script or a CI step. This is a plain script rather than a pytest
suite because no test framework is installed in this project; the checks
assert on real simulation runs, not on mocks, and the output is a readable
report rather than a dot stream.
"""
import csv
import json
import os
import shutil
import sys
import tempfile

# Repo root is this file's grandparent directory. Derived rather than
# hardcoded so the script runs from any working directory, on any machine --
# it previously pinned an absolute Windows path and died on anything else.
# os.chdir is kept because several checks below read the data/ tree by
# relative path, and the missing-CSV check deliberately tests whether those
# relative paths resolve from the repo root.
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)
os.chdir(REPO)
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

PASS, FAIL, WARN = [], [], []


def check(label, ok, detail=""):
    (PASS if ok else FAIL).append(label)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  -- {detail}" if detail else ""))


def warn(label, detail=""):
    WARN.append(label)
    print(f"  [WARN] {label}" + (f"  -- {detail}" if detail else ""))


def section(title):
    print()
    print("=" * 84)
    print(f"  {title}")
    print("=" * 84)


# ---------------------------------------------------------------- 1. imports
section("1. MODULE IMPORTS")
MODULES = [
    "model.region", "model.world_graph", "model.platform_node", "model.info_strain",
    "model.trait", "model.countermeasure", "model.scenarios", "model.world_map_data",
    "model.real_world_data", "model.csv_loader", "model.geo_data", "model.effect",
    "algorithm.spread_model", "algorithm.reproduction_number", "algorithm.counter_ai",
    "algorithm.strike_manager", "algorithm.export_report_figures",
    "algorithm.graph_traversal",
    "controller.game_engine",
    "view.theme", "view.map_view", "view.geo_map_view", "view.ui_panels",
    "view.analytics_modal", "view.tactical_abilities_panel",
    "view.scrollable_panel_base", "view.main",
]
failed = []
for _m in MODULES:
    try:
        __import__(_m)
    except Exception as _e:
        failed.append(f"{_m}: {type(_e).__name__}: {_e}")
check(f"all {len(MODULES)} modules import", not failed, "; ".join(failed) or "clean")

from view.main import build_world, build_global_world, App
from model.scenarios import default_unverified_rumor, earthquake_rumor_scenario
from model.countermeasure import CounterMeasure
from algorithm.spread_model import SIRSpreadModel, SEIRSpreadModel
from algorithm.counter_ai import GreedyCounterAI
from controller.game_engine import GameEngine, GameState

# ---------------------------------------------------------------- 2. worlds
section("2. WORLD CONSTRUCTION")


def audit_world(label, world):
    regions = world.regions
    bad_pop = [r.name for r in regions if r.population <= 0]
    asym, badw, isolated = [], [], []
    for r in regions:
        if not r.connections:
            isolated.append(r.name)
        for nb, w in r.connections.items():
            if not (0.0 < w <= 1.0):
                badw.append(f"{r.name}->{nb.name}={w}")
            if r not in nb.connections:
                asym.append(f"{r.name}->{nb.name}")
    check(f"{label}: regions built", len(regions) > 0, f"{len(regions)} regions, "
          f"pop={sum(r.population for r in regions):,}")
    check(f"{label}: all populations positive", not bad_pop, str(bad_pop[:5]))
    check(f"{label}: connections symmetric", not asym, str(asym[:5]))
    check(f"{label}: edge weights in (0,1]", not badw, str(badw[:5]))
    check(f"{label}: no isolated regions", not isolated, str(isolated[:5]))
    return regions


nepal = audit_world("nepal", build_world())
world_map = audit_world("world", build_global_world())
platforms = [r for r in world_map if getattr(r, "node_type", "geographic") != "geographic"]
check("world map has platform nodes", len(platforms) > 0,
      ", ".join(f"{r.name}({r.node_type})" for r in platforms))
check("platform nodes resist correction",
      all(r.correction_resistance_multiplier >= 1.0 for r in platforms),
      str({r.name: r.correction_resistance_multiplier for r in platforms}))

# ------------------------------------------------- 3. simulation invariants
section("3. SIMULATION INVARIANTS (population conservation, compartment bounds)")
SCHEMA = {"tick", "susceptible", "exposed", "believing", "skeptical",
          "population", "incidence", "r_t", "counter_active",
          "corrected_mindshare"}


def run_invariants(factory, model_cls, label, max_ticks=6000):
    counter = CounterMeasure()
    engine = GameEngine(build_world(), factory(), counter, model_cls(),
                        GreedyCounterAI())
    engine.start("Bagmati", seed_amount=8)
    problems, rts, schema_bad = [], [], 0
    for _ in range(max_ticks):
        engine.tick()
        h = engine.telemetry_history[-1]
        if set(h) != SCHEMA:
            schema_bad += 1
        if h["r_t"] is not None:
            rts.append(h["r_t"])
        for r in engine.world.regions:
            total = r.susceptible + r.exposed + r.believing + r.skeptical
            if total != r.population:
                problems.append(f"t{h['tick']} {r.name}: compartments sum {total} "
                                f"!= population {r.population}")
            if min(r.susceptible, r.exposed, r.believing, r.skeptical) < 0:
                problems.append(f"t{h['tick']} {r.name}: negative compartment")
            if not (0 <= r.durable_skeptical <= r.skeptical):
                problems.append(f"t{h['tick']} {r.name}: durable {r.durable_skeptical} "
                                f"outside [0, {r.skeptical}]")
        if engine.state != GameState.RUNNING:
            break
    h = engine.telemetry_history[-1]
    n = h["population"]
    print(f"    {label:<22} {engine.state:>7} end=t{h['tick']:<5} "
          f"peakB={max(x['believing'] for x in engine.telemetry_history)/n:>6.1%} "
          f"finalS={h['susceptible']/n:>6.1%} finalB={h['believing']/n:>6.1%} "
          f"finalK={h['skeptical']/n:>6.1%}")
    return problems, rts, schema_bad, engine


for factory, fname in [(default_unverified_rumor, "default"),
                       (earthquake_rumor_scenario, "earthquake")]:
    for model_cls, mname in [(SIRSpreadModel, "SIR"), (SEIRSpreadModel, "SEIR")]:
        problems, rts, schema_bad, engine = run_invariants(
            factory, model_cls, f"{fname}/{mname}")
        check(f"{fname}/{mname}: compartments and population conserved",
              not problems, "; ".join(problems[:3]) if problems else
              f"{len(engine.telemetry_history)} ticks clean")
        check(f"{fname}/{mname}: telemetry schema stable", schema_bad == 0,
              f"{schema_bad} mismatched ticks")
        check(f"{fname}/{mname}: R_t in a plausible band",
              all(0.1 <= v <= 5.0 for v in rts) if rts else False,
              f"{len(rts)} defined points, range "
              f"{min(rts):.2f}-{max(rts):.2f}" if rts else "no defined values")

# ---------------------------------------------------------------- 4. abilities
section("4. TACTICAL ABILITIES")
# activation_threshold is lowered purely so this fixture outlives the test.
# At the default 0.20 the countermeasure arrives late, belief wins at t=30, and
# every tick() after that is a no-op (the engine returns early once the game is
# over) -- so the expiry assertions below would silently never run. At 0.05 the
# run lasts to t=72, comfortably past the t=52 this test needs.
engine = GameEngine(build_world(), default_unverified_rumor(), CounterMeasure(),
                    SIRSpreadModel(), GreedyCounterAI(), activation_threshold=0.05)
engine.start("Bagmati", seed_amount=8)
for _ in range(40):
    engine.tick()

for name, target in [("bot_surge", None), ("echo_chamber", "Bagmati"),
                     ("sensationalist_blitz", None)]:
    engine.strain.points_available = 99
    engine.active_abilities[name]["cooldown"] = 0
    before_t = engine.strain.effective_transmission_rate
    before_b = sum(r.believing for r in engine.world.regions)
    before_w = engine.world.get_region(target).believability_multiplier if target else None
    res = engine.use_tactical_ability(name, target)
    ok = res["success"]
    # Effect must be visible immediately...
    if name == "bot_surge":
        ok = ok and engine.strain.effective_transmission_rate > before_t
    elif name == "echo_chamber":
        ok = ok and engine.world.get_region(target).believability_multiplier > 1.0
    else:
        ok = ok and sum(r.believing for r in engine.world.regions) > before_b
    check(f"{name}: applies its effect", ok,
          str(res.get("effect", {})) if ok else res.get("message", ""))
    # ...and must expire, not leak into the permanent base value.
    for _ in range(12):
        engine.tick()
    if name == "bot_surge":
        leaked = engine.strain.transmission_rate != 0.15
        check("bot_surge: expires without leaking into base rate", not leaked,
              f"base transmission_rate={engine.strain.transmission_rate}")
    elif name == "echo_chamber":
        check("echo_chamber: expires",
              engine.world.get_region(target).believability_multiplier == 1.0,
              f"multiplier={engine.world.get_region(target).believability_multiplier}")
    else:
        check("sensationalist_blitz: instantaneous, nothing to expire", True)

# cooldown + points
engine.strain.points_available = 0
res = engine.use_tactical_ability("sensationalist_blitz")
check("ability refused without points", not res["success"], res["message"])
engine.strain.points_available = 99
engine.use_tactical_ability("sensationalist_blitz")
res = engine.use_tactical_ability("sensationalist_blitz")
check("ability refused while on cooldown", not res["success"], res["message"])

# ------------------------------------------------------------------ 5. export
section("5. REPORT EXPORT")
import algorithm.export_report_figures as exf

engine = GameEngine(build_world(), default_unverified_rumor(), CounterMeasure(),
                    SIRSpreadModel(), GreedyCounterAI())
engine.start("Bagmati", seed_amount=8)
for _ in range(200):
    engine.tick()
    if engine.state != GameState.RUNNING:
        break

# A system temp dir, not a folder inside the repo: if this script is
# interrupted the exports should not be left behind in the working tree,
# where they would show up in `git status` and possibly get committed.
tmpdir = tempfile.mkdtemp(prefix="infospread_verify_")
try:
    result = exf.export_academic_report(engine.telemetry_history, "Unverified Rumor",
                                        "SIR", output_dir=tmpdir)
    files = sorted(os.listdir(tmpdir)) if os.path.isdir(tmpdir) else []
    check("export writes files", len(files) >= 3, str(files))
    csvs = [f for f in files if f.endswith(".csv")]
    jsons = [f for f in files if f.endswith(".json")]
    txts = [f for f in files if f.endswith(".txt")]
    if csvs:
        with open(os.path.join(tmpdir, csvs[0]), newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        check("exported CSV parses and matches history",
              len(rows) == len(engine.telemetry_history),
              f"{len(rows)} rows vs {len(engine.telemetry_history)} ticks")
        check("exported CSV header matches telemetry schema",
              set(rows[0]) == SCHEMA, str(sorted(set(rows[0]) ^ SCHEMA)) if rows else "")
    if jsons:
        with open(os.path.join(tmpdir, jsons[0]), encoding="utf-8") as fh:
            blob = json.load(fh)
        check("exported JSON parses", isinstance(blob, (dict, list)),
              type(blob).__name__)
    if txts:
        text = open(os.path.join(tmpdir, txts[0]), encoding="utf-8").read()
        check("summary mentions the citations", "Cori" in text or "Guess" in text,
              f"{len(text)} chars")
    # PNG figures
    pngs = [f for f in files if f.endswith(".png")]
    if not pngs:
        warn("no PNG figures produced", "generate_matplotlib_figures() is never called")
except Exception as e:
    import traceback
    check("export runs without raising", False, f"{type(e).__name__}: {e}")
    traceback.print_exc()
shutil.rmtree(tmpdir, ignore_errors=True)

# --------------------------------------------------------------------- 6. GUI
section("6. HEADLESS APP")
import pygame

app = App()
check("App constructs headless", True,
      f"{len(app.world.regions)} regions, map={app.selected_map_name}")

SIZES = [(1440, 900), (1920, 1080), (1024, 768), (1000, 600), (800, 500), (640, 480)]
PANELS = ["race_bar", "strike_panel", "stats_panel", "detail_panel",
          "abilities_panel", "trait_panel", "news_ticker", "advance_button"]
for size in SIZES:
    app.screen = pygame.display.set_mode(size, pygame.RESIZABLE)
    app._rebuild_layout()
    w, h = size
    outside = []
    for pname in PANELS:
        p = getattr(app, pname, None)
        if p is None or not hasattr(p, "rect"):
            continue
        r = p.rect
        if r.left < 0 or r.top < 0 or r.right > w or r.bottom > h:
            outside.append(f"{pname}{tuple(r)}")
    over = []
    rects = [(pn, getattr(app, pn).rect) for pn in PANELS
             if getattr(app, pn, None) and hasattr(getattr(app, pn), "rect")]
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            inter = rects[i][1].clip(rects[j][1])
            if inter.width > 4 and inter.height > 4:
                over.append(f"{rects[i][0]}/{rects[j][0]}")
    check(f"{w}x{h}: panels inside the window", not outside, str(outside))
    check(f"{w}x{h}: no panel overlaps another", not over, str(over))

# events + a full game in each map mode / model
for map_name in ("nepal", "world"):
    for model_name in ("SIR", "SEIR"):
        app.screen = pygame.display.set_mode((1440, 900), pygame.RESIZABLE)
        app.selected_map_name = map_name
        app.selected_model_name = model_name
        app.selected_scenario_name = "default"
        app.use_custom_data = False
        app._build_game()
        app.start_game()
        label = f"{map_name}/{model_name}"
        # Capture the outcome at the moment the game FIRST ends. Reading
        # tick_count after the loop instead is meaningless: game-over + SPACE
        # calls _build_game(), which replaces the engine and resets it to 0,
        # so a finished game silently reports "0 ticks" and looks like a pass.
        outcome, ticks, err = None, 0, None
        try:
            for _ in range(300):
                pygame.event.post(pygame.event.Event(pygame.KEYDOWN,
                                                     key=pygame.K_SPACE))
                app.handle_events()
                app.draw_playing()
                if app.state != "playing":
                    outcome, ticks = app.engine.state, app.engine.tick_count
                    break
            if outcome is None:
                outcome, ticks = "still running", app.engine.tick_count
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
        check(f"{label}: plays, handles input and draws", err is None,
              err or f"{outcome} at t={ticks}")

# menu interactions, including the inert custom-data option
app.state = "menu"
app.screen = pygame.display.set_mode((1440, 900), pygame.RESIZABLE)
app._rebuild_layout()
app.draw_menu()
for key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5):
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key))
    app.handle_events()
check("menu: every option key handled without error", True,
      f"custom_data_available={app.custom_data_available}")

# analytics modal + export key
app.selected_map_name = "nepal"
app._build_game()
app.start_game()
# 15, not 30: the default SIR game now ends at t=30, and past that point the
# modal's key handling sits behind the game-over screen rather than the
# playing screen, so a longer loop tests the wrong branch.
for _ in range(15):
    app._advance_one_tick()
pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a))
app.handle_events()
check("analytics modal opens", app.analytics_modal.visible)
app.draw_playing()
pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a))
app.handle_events()
check("analytics modal closes", not app.analytics_modal.visible)

# ------------------------------------------------- 7. documented open gaps
section("7. DOCUMENTED OPEN GAPS (checking the Known-gaps table)")

# (a) export filenames use second granularity
tmpdir = tempfile.mkdtemp(prefix="infospread_overwrite_")
exf.export_academic_report(engine.telemetry_history, "Unverified Rumor", "SIR",
                           output_dir=tmpdir)
after_first = set(os.listdir(tmpdir))
exf.export_academic_report(engine.telemetry_history, "Unverified Rumor", "SIR",
                           output_dir=tmpdir)
after_second = set(os.listdir(tmpdir))
if after_second == after_first:
    warn("export overwrites itself within the same second",
         f"{len(after_first)} files after two exports, expected {2 * len(after_first)}")
else:
    check("two exports in the same second produce distinct files", True,
          f"{len(after_second)} files")
shutil.rmtree(tmpdir, ignore_errors=True)

# (b) country centroids vs their own outlines
cen = json.load(open("data/geo/world_country_centroids.json", encoding="utf-8"))
poly = json.load(open("data/geo/world_countries.json", encoding="utf-8"))["countries"]


def point_in_ring(x, y, ring):
    inside = False
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xin = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < xin:
                inside = not inside
    return inside


missing = sorted(set(poly) - set(cen))
outside = sorted(name for name, (x, y) in cen.items()
                 if name in poly and not point_in_ring(x, y, poly[name]))
check("every country has a centroid", not missing, str(missing[:5]))
if outside:
    warn(f"{len(outside)} of {len(cen)} country centroids fall outside their own outline",
         ", ".join(outside[:8]) + (" ..." if len(outside) > 8 else ""))
else:
    check("all centroids fall inside their country outline", True, f"{len(cen)} checked")

# (c) RSF transmission modifiers vs the clamp
params = json.load(open("data/geo/world_countries.json", encoding="utf-8"))["country_params"]
mods = [v["transmission_modifier"] for v in params.values()]
above = [m for m in mods if m > 1.0]
conns = json.load(open("data/geo/world_countries.json", encoding="utf-8"))["connections"]
weights = {round(min(1.0, base * params[b]["transmission_modifier"]), 3)
           for _, b, base in conns}
if above:
    warn(f"{len(above)} of {len(mods)} RSF modifiers exceed the clamp ceiling of 1.0",
         f"range {min(mods):.3f}-{max(mods):.3f}; only {len(weights)} distinct "
         f"edge weights survive across {len(conns)} connections")
else:
    check("RSF modifiers survive the clamp", True, f"range {min(mods):.3f}-{max(mods):.3f}")

# (d) custom CSV path
from view.main import CUSTOM_REGIONS_CSV_PATH, CUSTOM_STRAIN_CSV_PATH
check("custom CSV files exist", os.path.exists(CUSTOM_REGIONS_CSV_PATH)
      and os.path.exists(CUSTOM_STRAIN_CSV_PATH),
      f"{CUSTOM_REGIONS_CSV_PATH} exists={os.path.exists(CUSTOM_REGIONS_CSV_PATH)}, "
      f"{CUSTOM_STRAIN_CSV_PATH} exists={os.path.exists(CUSTOM_STRAIN_CSV_PATH)}")

# ------------------------------------------------------------------- summary
print()
print("=" * 84)
print(f"  {len(PASS)} passed, {len(FAIL)} failed, {len(WARN)} warnings")
for f in FAIL:
    print(f"    FAILED: {f}")
for w in WARN:
    print(f"    WARN:   {w}")
print("=" * 84)

# Non-zero on failure so this is usable as a gate before a demo. Note that
# "custom CSV files exist" is an OPEN, already-documented gap (the example
# CSVs were never committed, so the custom-data path is unreachable), which
# means an exit of 1 with that as the only failure is the expected state of
# this repository rather than a regression.
sys.exit(1 if FAIL else 0)
