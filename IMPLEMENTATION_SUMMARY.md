# InfoSpread Simulator

A misinformation-spread simulator that applies compartmental epidemic models
(SIR/SIRS and SEIR) to the spread of a false belief across a weighted
geographic network.

**Academic context:** TU BCA final-year project.
**Stack:** Python 3.14.4, pygame-ce 2.5.7.

> This document supersedes `QUICK_START.md`, `SCROLLABLE_PANELS_COMPLETE.md` and
> `UI_IMPROVEMENTS_STATUS.md`, which have been removed. Those files contained
> claims that did not match the code (including a list of unit tests that were
> never written). Everything below was checked against the running program.

---

## Running it

```bash
pip install -r requirements.txt
python view/main.py
```

`python -m view.main` also works. Both forms are supported: `view/main.py`
inserts the repository root onto `sys.path` at import time, because running the
file as a script otherwise puts `view/` (not the repository root) at
`sys.path[0]` and the `model` / `algorithm` / `controller` packages cannot be
found.

### Keyboard controls

| Key | Action |
|---|---|
| `SPACE` / `ENTER` | Advance one simulation tick |
| `A` | Toggle the analytics modal |
| `E` | Export an academic report (`report_exports/`) |
| `ESC` | Close the analytics modal; then reset map zoom |
| `F` / `F11` | Toggle fullscreen |
| `5` | Switch to the Nepal map |
| `4` | Switch to custom CSV data — **inert**, see Known gaps |

---

## The model

### Compartments

Each region holds a population split across four compartments:

- **Susceptible (S)** — has not encountered the claim
- **Exposed (E)** — has encountered it but is not yet convinced *(SEIR only)*
- **Believing (B)** — believes it and actively spreads it
- **Skeptical (K)** — has been corrected

### Spread

Two interchangeable models, selectable at launch:

- `SIRSpreadModel` — Susceptible → Believing → Skeptical
- `SEIRSpreadModel` — adds an Exposed latency stage between encounter and belief

Within a region, exposure pressure is `believability_rate * (B / population)`.
Across regions, it is `transmission_rate * edge_weight * (B_neighbour / population_neighbour)`,
summed over every connected neighbour. Deltas are computed from a snapshot and
applied simultaneously, so updates do not cascade within a single tick.

Both models carry the fractional remainder of sub-integer growth across ticks.
Without this, `int()` truncation silently discards any tick where the computed
exposure is below 1.0 — at seed counts of a handful of believers in a region of
millions, both the internal and cross-edge terms routinely compute to fractions
just under 1, which would stall the simulation permanently at the seed amount.

### Waning immunity (SIRS)

Corrected people drift back to Susceptible at 5% per tick. The rate is derived
from Guess et al. (2023): only 39% of a correction persisted at two-week
follow-up, i.e. 61% decayed over ~14 ticks, giving `1 - 0.39^(1/14) ≈ 0.067`.
The code deliberately uses a more conservative 0.05. This turns the SIR model
into SIRS, the standard approach when immunity is not permanent.

### Countermeasure

Parameters are documented in `model/countermeasure.py` against the literature:

- `base_strength = 0.011` — ~1.1% correction per tick at activation
- `growth_rate = 0.003` — slow ramp
- `cap = 0.120` — 12% maximum correction per tick

It activates automatically once global belief reaches the activation threshold
(default 0.20), reduced by the strain's `detection_risk` — a louder, more
attention-grabbing strain is noticed sooner. Effectiveness is further scaled by
each region's media literacy (`base_resistance`) and divided by the region's
`correction_resistance_multiplier`, which is higher for platform node types such
as private messaging where moderation is harder.

### Telegraph strikes

Once active, the countermeasure telegraphs strikes in advance, giving the player
a specific upcoming threat to react to. Strike strength is 0.12 with a 6-turn
cooldown, calibrated to Porter et al. (2021).

### Win / loss conditions

- **Won** — believing population reaches 75% of the total
- **Lost** — corrected population reaches 90% of the total

The 75% threshold is deliberate (lowered from 95%): even highly viral
misinformation rarely achieves universal penetration, but a supermajority
represents decisive capture of the information environment.

---

## Game features

### Maps

- **Nepal** — 7 provinces with real population and literacy data, connected by a
  hand-specified adjacency graph
- **World** — 202 countries generated from GeoJSON outlines with RSF-derived
  per-country transmission modifiers, plus 4 platform nodes (public feed, private
  messaging, close groups, etc.)

### Scenarios

- `default_unverified_rumor` — uncalibrated baseline
- `earthquake_2015` — a disaster-context rumor, calibrated at 6× the
  true-information baseline rate and with elevated resistance to correction,
  modelling the documented theme that official channels are themselves disrupted
  after a disaster

### Traits

Four purchasable traits, each with multiple levels: **Viral Visuals**,
**Emotional Hook**, **Platform Optimized**, **Correction Resistance**. Each
carries a real trade-off — for example, attention-grabbing traits raise
`detection_risk`, which lowers the effective countermeasure activation threshold
and so brings fact-checkers in *sooner*.

### Tactical abilities

Three player-activated powers with point costs and cooldowns:

| Ability | Cost | Cooldown | Intended effect |
|---|---|---|---|
| Bot Amplification Surge | 15 | 8 | +30% global transmission for 3 turns |
| Echo Chamber Silo | 20 | 10 | +50% believability in a selected region for 4 turns |
| Sensationalist Blitz | 12 | 6 | Immediate +10% conversion in every region with believers |

**Status: broken.** See Known gaps — two of the three do not do what the table
says.

### Points

Points accrue at 1 per tick, with a cap of 50 and a starting grant of 5.

---

## Academic analytics

### Telemetry

`GameEngine._record_telemetry()` records a snapshot every tick with eight fields:
`tick, susceptible, exposed, believing, skeptical, population, r_t, counter_active`.

### Analytics modal (`A`)

Two live charts: S-E-I-R compartmental trajectories, and R_t tracked against the
R_t = 1.0 epidemic threshold.

### Report export (`E`)

Writes three timestamped files to `report_exports/`:

- `*_telemetry.csv` — tick-by-tick data, Excel-ready
- `*_telemetry.json` — same data with metadata, for programmatic analysis
- `*_summary.txt` — formatted statistics: simulation duration, peak believers and
  peak R_t with tick numbers, final R_t, countermeasure activation tick, average
  R_t before and after activation, final compartment distribution, and the
  research citations

PNG figure export is **not implemented** — see Known gaps.

---

## Verification status

**There is no automated test suite.** The `tests/` directory exists but is empty,
and no test framework is installed or configured. Earlier revisions of this
document listed unit tests and an integration test as passing; those tests were
never written, and that claim has been removed rather than restated.

What has actually been verified, by executing the program:

- Both map modes launch, simulate and render end-to-end
- All documented key bindings respond as described (`4` excepted)
- Population is conserved across every tick in both spread models, including
  under corrections, waning and ability use
- The fractional-carry mechanism works as documented (sub-integer growth
  accumulates instead of stalling)
- All six data files parse as valid UTF-8 and are internally consistent — 202
  countries, 202 parameter entries, 202 centroids, no duplicates or malformed
  entries; Nepal has 75 districts across exactly 7 provinces
- Telemetry keys and the CSV header match the documented schema
- `report_exports/` receives a correct CSV and JSON; peak and final statistics
  cross-check against the CSV

---

## Known gaps

Honest list of what does not work or is not yet built. Items marked **fixed**
were addressed in the audit-fix pass and are recorded here only for the record.

| Area | Issue | Status |
|---|---|---|
| Tactical abilities | `echo_chamber` has no effect at all — it builds a description dict and never mutates any state, but still charges 20 points and sets a 10-turn cooldown | open |
| Tactical abilities | `bot_surge` multiplies transmission permanently and compounding — the documented 3-turn duration is never enforced | open |
| Tactical abilities | `sensationalist_blitz` works, but in SEIR mode injects straight into Believing, skipping the Exposed latency stage | open |
| Tactical abilities | No timed-effect system exists at all, which is the root cause of the first two | open |
| R_t | Inflated to ~150 rather than ~1: when the countermeasure is inactive a placeholder `gamma = 0.001` divides into R_t. This squashes the in-game chart (threshold line renders at ~0.7% height), always reports "GROWTH", and makes the reported "R_t reduction" an artifact | open |
| Balance | The 90% loss condition is unreachable — corrections cap at 12%/tick against 5%/tick waning, so corrected population plateaus near 50% | open |
| Balance | The default scenario on the Nepal map never terminates — it reaches neither condition and runs indefinitely | open |
| Balance | The earthquake scenario on Nepal reaches the 75% win in ~15 ticks, so the most expensive ability is barely affordable in a winning run | open |
| Export | PNG figures are never generated — `generate_matplotlib_figures()` is defined but called from nowhere | open |
| Export | Filenames use second granularity, so pressing `E` twice within one second silently overwrites the first dataset | open |
| Custom data | The CSV path is unreachable — `data/regions_example.csv` and `data/strain_config_example.csv` do not exist and were never committed | open |
| UI layout | The Advance Simulation button renders off the bottom of the window at the default 1440×900, and is entirely invisible at 1024×768 fullscreen | open |
| UI input | Panel click handlers are not bounded by their panel rectangle — clicking a panel header can trigger an ability or buy a trait | open |
| UI state | A window resize or fullscreen toggle rebuilds every panel, clearing the news ticker and closing the analytics modal | open |
| UI state | The analytics modal's `visible` flag is not reset between games, so after Play Again an invisible overlay swallows clicks across most of the screen | open |
| UI input | Map zoom buttons are computed from a placeholder rect, so they are clipped out of sight while their hitboxes remain live | open |
| UI layout | Scrollable panels do not clip their content — cards scrolled past the top paint over the fixed header | open |
| World map | Country populations are schematic (~250–500k each), so geography carries little population signal; platform nodes are 0.011% of the total and their mechanic is invisible | open |
| World map | The RSF transmission modifier is clamped to a ceiling of 1.0, so per-country penalties survive but boosts are unrepresentable | open |
| World map | For 55 of 202 countries the centroid falls outside the country's own outline, so its label and strike effects draw in the wrong place | open |
| Repo | No `.gitignore` existed and 24 compiled `.pyc` files were tracked | **fixed** |
| Repo | The documented launch command crashed with `ModuleNotFoundError` | **fixed** |
| Repo | No dependency manifest, so a fresh clone could not reproduce the environment | **fixed** |

---

## References

1. Porter, E., Wood, T. J., & Kirby, D. (2021). The global effectiveness of fact-checking. *PNAS*, 118(37).
2. Guess, A. M., et al. (2023). Correcting COVID-19 vaccine misinformation in 10 countries. *Royal Society Open Science*.
3. Nyhan, B. (2021). Why the backfire effect does not explain the durability of political misperceptions. *PNAS*, 118(15).
4. Vosoughi, S., Roy, D., & Aral, S. (2018). The spread of true and false news online. *Science*, 359(6380), 1146–1151.
5. Kermack, W. O., & McKendrick, A. G. (1927). A contribution to the mathematical theory of epidemics. *Proceedings of the Royal Society A*, 115(772), 700–721.
6. Pennycook, G., & Rand, D. G. (2022). Accuracy prompts are a replicable and generalizable approach for reducing the spread of misinformation. *Nature Communications*.
7. Flynn, D. J., Nyhan, B., & Reifler, J. (2017). The nature and origins of misperceptions. *Political Psychology*, 38(S1).

---

## File map

```
view/          main.py (App, event loop, layout)  theme.py  ui_panels.py
               geo_map_view.py  map_view.py  analytics_modal.py
               tactical_abilities_panel.py  scrollable_panel_base.py
controller/    game_engine.py (tick, telemetry, abilities)
model/         world_graph  region  platform_node  info_strain  trait
               countermeasure  scenarios  world_map_data  real_world_data
               csv_loader  geo_data
algorithm/     spread_model (SIR, SEIR)  counter_ai  strike_manager
               export_report_figures  graph_traversal
data/          geo/ (map JSON)  something/ (legacy, orphaned)
```
