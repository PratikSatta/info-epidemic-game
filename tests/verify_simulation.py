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
import glob
import json
import os
import re
import shutil
import sys
import tempfile
import unicodedata

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
from view.ui_panels import StatsPanel, RegionDetailPanel, NewsTicker
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
    # PNG figures. export_academic_report() renders these itself now, sharing
    # the run name of the CSV they were plotted from, so an export and its
    # plots are obviously one dataset.
    pngs = [f for f in files if f.endswith(".png")]
    try:
        import matplotlib  # noqa: F401
        have_mpl = True
    except ImportError:
        have_mpl = False
    if have_mpl:
        check("export produces the PNG figures", len(pngs) == 2, str(pngs))
        csv_stem = csvs[0][: -len("_telemetry.csv")] if csvs else None
        check("figures share the run name of the CSV they plot",
              csv_stem is not None and all(p.startswith(csv_stem) for p in pngs),
              f"{csv_stem} vs {pngs}")
    else:
        warn("no PNG figures produced", "matplotlib not installed")
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

# --- every glyph the UI asks for must actually be drawable ----------------
#
# SDL_ttf performs no font fallback: a character the face does not have is
# painted as a tofu box, silently and without raising. The UI labels itself
# with emoji -- a pushpin on the territory header, a shield on the defence
# bar, a multiplication X on the modal's close button -- and none of those
# live in the primary face, so before view/fonts.py existed every one of them
# was a box, including the close button. Measured at the time: 34 of the 38
# distinct non-ASCII characters in the view layer's string literals.
#
# This is the only check that can see that failure, because a box is a
# perfectly successful render call. Any new icon added to a label is covered
# automatically: the character set is read out of the source, not listed here.
_icons = set()
for _path in glob.glob(os.path.join(REPO, "view", "*.py")):
    # fonts.py is excluded because it deliberately renders a character no face
    # has, to capture each face's missing-glyph bitmap.
    if os.path.basename(_path) == "fonts.py":
        continue
    with open(_path, encoding="utf-8") as _fh:
        for _lit in re.findall(r'"([^"\n]*)"|\'([^\'\n]*)\'', _fh.read()):
            for _text in _lit:
                _icons.update(
                    c for c in _text
                    if ord(c) > 127
                    # Private use: no standard glyph exists by definition.
                    and not 0xE000 <= ord(c) <= 0xF8FF
                    # Non-spacing marks and format characters have no glyph of
                    # their own -- U+FE0F is the variation selector that
                    # follows most emoji and only modifies the character
                    # before it, so it is not an icon and cannot be "missing".
                    and unicodedata.category(c) not in ("Mn", "Cf"))

_app_fonts = {"body": app.font_body, "header": app.font_header,
              "small": app.font_small, "title": app.font_title}
check("app fonts load with fallback faces available",
      all(f._fallbacks for f in _app_fonts.values()),
      f"{[len(f._fallbacks) for f in _app_fonts.values()]} fallback faces per font")
tofu = [f"U+{ord(c):04X} {unicodedata.name(c, '?')} in {label}"
        for label, font in _app_fonts.items()
        for c in sorted(_icons) if not font.has_glyph(c)]
check(f"all {len(_icons)} icon characters the UI uses are drawable",
      not tofu, "; ".join(tofu))

# The close button specifically, because it is the one icon that is the only
# visible affordance for its control: if ✕ renders as a box, the modal has no
# readable way out.
check("close button glyph renders", app.font_header.has_glyph("✕"),
      "U+2715 MULTIPLICATION X")

# 1366x768 is the most common laptop resolution and the one the layout rework
# was tuned against, so it is checked rather than assumed.
SIZES = [(1440, 900), (1920, 1080), (1366, 768), (1024, 768), (1000, 600),
         (800, 500), (640, 480)]
PANELS = ["race_bar", "strike_panel", "stats_panel", "detail_panel",
          "abilities_panel", "trait_panel", "news_ticker", "advance_button"]


class Spy(pygame.Surface):
    """Surface that records where blits actually LAND, honouring the clip.

    Applying the surface clip before recording is the whole point: it makes the
    recorded boxes the pixels that really reach the screen. A panel that draws
    without clipping to its own rect therefore shows up here as an escape.
    """

    def __init__(self, size):
        super().__init__(size)
        self.boxes = []

    def blit(self, src, dest, *args, **kwargs):
        r = dest if isinstance(dest, pygame.Rect) else pygame.Rect(dest, src.get_size())
        landed = r.clip(self.get_clip())
        if landed.width > 0 and landed.height > 0:
            self.boxes.append(landed)
        return super().blit(src, dest, *args, **kwargs)


class _FakeRegion:
    """A region with the fields RegionDetailPanel reads, so the layout checks
    below can exercise the five-line SEIR case without mutating the live world."""

    def __init__(self, exposed):
        self.name, self.node_type = "Madhesh", "geographic"
        self.population, self.believing = 6_000_000, 1_200_000
        self.skeptical, self.exposed = 300_000, exposed
        self.base_resistance = 0.35

    def infection_ratio(self):
        return self.believing / self.population


def painted_bounds(draw_fn) -> pygame.Rect | None:
    """Union of everything `draw_fn` actually paints, or None if it paints nothing."""
    spy = Spy(app.screen.get_size())
    draw_fn(spy)
    if not spy.boxes:
        return None
    bounds = spy.boxes[0].copy()
    for box in spy.boxes[1:]:
        bounds.union_ip(box)
    return bounds


# The content-height requirement each telemetry panel declares, and a draw call
# that exercises its full-height case (SEIR, exposed > 0, a full news backlog).
STATS_SUMMARY = {"global_infection_ratio": 0.42, "ticks": 37, "total_believing": 1_200_000,
                 "total_skeptical": 300_000, "total_exposed": 400_000}
TELEMETRY = {
    "stats_panel": (StatsPanel.required_height(app.font_body),
                    lambda s: app.stats_panel.draw(s, STATS_SUMMARY, "Nepal SIR", "SEIR")),
    "detail_panel": (RegionDetailPanel.required_height(app.font_body),
                     lambda s: app.detail_panel.draw(s, _FakeRegion(346))),
    "news_ticker": (NewsTicker.required_height(app.font_small),
                    lambda s: _draw_full_news(s)),
}


def _draw_full_news(surface):
    for i in range(5):
        app.news_ticker.push(f"[DATA] Event {i} in a region")
    app.news_ticker.draw(surface)


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

    # The two checks above compare panel RECTANGLES against the window and each
    # other, which is why they never caught the defect that was actually on
    # screen: the detail panel was 122px tall at 1440x900 while painting 158px
    # of telemetry, so its last two lines were drawn over the panel beneath it
    # at every size below 1080p. Nothing compared a panel's content to its own
    # box. These do -- see Spy and painted_bounds above.
    escapes, drops = [], []
    for pname, (needs, draw_it) in TELEMETRY.items():
        panel = getattr(app, pname)
        bounds = painted_bounds(draw_it)
        # No panel may paint outside its own rect, at any size. This is what
        # clip_to guarantees; if it is ever removed, or a new panel forgets it,
        # the overflow reappears and this fails instead of reaching the screen.
        if bounds is not None and not panel.rect.contains(bounds):
            escapes.append(f"{pname} paints {tuple(bounds)} outside {tuple(panel.rect)}")
        # A panel given less than it declares must have dropped lines rather
        # than be silently cut off mid-line, so record what was lost.
        if panel.rect.height < needs:
            drops.append(f"{pname} {panel.rect.height}<{needs}")
    check(f"{w}x{h}: no panel paints outside its box", not escapes, "; ".join(escapes))

    # Where the layout has room, the panels must get their full declared height.
    # The signal that it does not is the two scrollable panels being squeezed
    # below their own floors, which is the intended failure mode on a window too
    # small for the layout as a whole.
    layout_squeezed = (app.abilities_panel.rect.height < 120
                       or app.trait_panel.rect.height < 130)
    if not layout_squeezed:
        check(f"{w}x{h}: telemetry panels get their full content height",
              not drops, "; ".join(drops))
    elif drops:
        warn(f"{w}x{h}: window too small for full telemetry",
             f"dropped content: {', '.join(drops)}")

# A squeezed detail panel must drop its least important lines rather than have
# its bottom sliced off, and must never drop the two numbers that decide the
# game. Exercised directly on the fitting helper so the expectation is stated
# once, independent of whatever window sizes happen to be tested above.
# Heights are derived from the panel's own constants rather than written as
# literal pixel counts, so this cannot drift when the layout constants change.
_FULL = RegionDetailPanel.required_height(app.font_body)
_STEP = RegionDetailPanel.LINE_STEP
_ENTRIES = [("Population", RegionDetailPanel.KEEP_CONTEXT),
            ("Latent Exposed", RegionDetailPanel.KEEP_EXTRA),
            ("Believing", RegionDetailPanel.KEEP_CORE),
            ("Skeptical", RegionDetailPanel.KEEP_CORE),
            ("Media Literacy", RegionDetailPanel.KEEP_EXTRA)]
_kept = {lines: RegionDetailPanel(pygame.Rect(0, 0, 320, _FULL - n * _STEP),
                                  app.font_body, app.font_header)._fitted_lines(_ENTRIES)
         for n, lines in ((0, 5), (1, 4), (2, 3), (3, 2), (4, 1))}
check("detail panel: full box keeps every line",
      _kept[5] == ["Population", "Latent Exposed", "Believing", "Skeptical", "Media Literacy"],
      str(_kept[5]))
check("detail panel: one line short drops Media Literacy",
      _kept[4] == ["Population", "Latent Exposed", "Believing", "Skeptical"], str(_kept[4]))
check("detail panel: squeezed box keeps the decision numbers last",
      _kept[3] == ["Population", "Believing", "Skeptical"], str(_kept[3]))
check("detail panel: heavily squeezed box keeps Believing",
      _kept[1] == ["Believing"], str(_kept[1]))
check("detail panel: kept lines stay in display order",
      all(lines == sorted(lines, key=["Population", "Latent Exposed", "Believing",
                                      "Skeptical", "Media Literacy"].index)
          for lines in _kept.values()),
      str(_kept))

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

# (d) custom CSV path -- now closed: the example files are committed and the
# mode is reachable. Load them for real rather than merely asserting the files
# are present, because a malformed example would leave the mode advertised but
# broken, which is worse than the gap it replaced.
from view.main import CUSTOM_REGIONS_CSV_PATH, CUSTOM_STRAIN_CSV_PATH
from model.csv_loader import build_world_from_csv, build_strain_from_csv
try:
    custom_world, custom_world_warns = build_world_from_csv(CUSTOM_REGIONS_CSV_PATH)
    custom_strain, custom_strain_warns = build_strain_from_csv(CUSTOM_STRAIN_CSV_PATH)
    custom_warnings = custom_world_warns + custom_strain_warns
    check("custom CSV example loads", True,
          f"{len(custom_world.regions)} regions, strain '{custom_strain.name}'")
    check("custom CSV example loads without warnings", not custom_warnings,
          str(custom_warnings))
    isolated = [r.name for r in custom_world.regions if not r.connections]
    check("custom CSV example leaves no region isolated", not isolated, str(isolated))
    check("custom CSV data is selectable in the menu", app.custom_data_available,
          f"custom_data_available={app.custom_data_available}")
except Exception as e:
    check("custom CSV example loads", False, f"{type(e).__name__}: {e}")

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
