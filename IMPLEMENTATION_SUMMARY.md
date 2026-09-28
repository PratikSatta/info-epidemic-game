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

### Waning immunity (SIRS) and durable skepticism

Corrected people drift back to Susceptible at 5% per tick. The rate is derived
from Guess et al. (2023): only 39% of a correction persisted at two-week
follow-up, i.e. 61% decayed over ~14 ticks, giving `1 - 0.39^(1/14) ≈ 0.067`.
The code deliberately uses a more conservative 0.05. This turns the SIR model
into SIRS, the standard approach when immunity is not permanent.

**The other half of that same finding is that 39% persisted** — and until
recently the code implemented only the decay, letting 0% persist. That made
`S → B → K → S` a *closed* cycle: every corrected person eventually returned to
Susceptible and could believe again, so no one ever left the loop. A closed
cycle has an interior fixed point, and the simulation parked there — measured
on the real engine the default scenario sat at 31% S / 21% B / 48% K from tick
75 onwards and never moved again, reaching neither win nor loss.

`CounterMeasure.DURABLE_FRACTION = 0.39` now marks 39% of each correction as
permanent. It is stored as `Region.durable_skeptical`, a **sub-count** of
`skeptical` rather than a fifth compartment, so `population` remains exactly the
sum of the compartments, `total_skeptical()` still reports everyone skeptical,
and every existing reader of `skeptical` (win/loss, telemetry, map colouring,
side panels) is unaffected. Waning draws only from `revertible_skeptical`
(`skeptical - durable_skeptical`); strikes apply the same fraction, threaded
through `StrikeManager.update()` from the active countermeasure.

With the fraction at the research value the default scenario now concludes:
belief goes extinct at tick 259. The fraction is a dial on game length —
0.20 ends at 5584, 0.39 at 2742, 0.70 at 1181.

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

Three player-activated powers with point costs and cooldowns. All three are
implemented and verified working:

| Ability | Cost | Cooldown | Effect |
|---|---|---|---|
| Bot Amplification Surge | 15 | 8 | +30% global transmission for 3 turns |
| Echo Chamber Silo | 20 | 10 | +50% internal believability in a selected region for 4 turns |
| Sensationalist Blitz | 12 | 6 | Immediate conversion of 10% of Susceptible in every region that has believers |

Temporary effects live in `model/effect.py`, deliberately separate from the
permanent trait system. Traits mutate the strain's base rates additively and
never revert — correct for a permanent upgrade the player has paid for.
Abilities are the opposite: they must expire, so they are stored as tick-counted
`ActiveEffect` modifiers. `effective_transmission_rate` and
`effective_believability_rate` on the strain (and `believability_multiplier` on
a region) fold the active modifiers on top of the permanent value. The spread
model and telemetry read the **effective** values; the trait UI reads the
permanent ones.

That separation matters more than it looks. If the getter folded temporary
bonuses in, then buying a trait *during* an ability would permanently bake the
bonus into the base value — which is exactly how Bot Amplification Surge
previously became a permanent, compounding +30%. Modifiers are stored as fixed
additive deltas computed once at cast time, so expiry restores the exact prior
value with no floating-point drift, and a second cast cannot compound on the
first.

Sensationalist Blitz routes through `SpreadAlgorithm.inject_exposure()`, so a
forced encounter lands in whichever compartment the active model uses for one:
Believing under SIR, Exposed under SEIR — where those people still face the
normal incubation delay rather than bypassing it.

Expired effects are collected on `GameEngine.last_expired_effects` each tick so
the UI can announce when a boost has lapsed.

### Points

Points accrue at 1 per tick, with a cap of 50 and a starting grant of 5.

---

## Academic analytics

### Telemetry

`GameEngine._record_telemetry()` records a snapshot every tick with nine fields:
`tick, susceptible, exposed, believing, skeptical, population, incidence, r_t,
counter_active`.

`incidence` is new infections during that tick (Susceptible → Believing under
SIR, Susceptible → Exposed under SEIR) from natural transmission only. Exposures
forced by a Sensationalist Blitz are excluded — R_t measures how many new
believers the existing believers generate, and an ability is an external shock
rather than transmission.

`r_t` is `null` on ticks where the estimator lacks the history to produce a
meaningful value, rather than a placeholder number.

### Analytics modal (`A`)

Two live charts: S-E-I-R compartmental trajectories, and R_t tracked against the
R_t = 1.0 epidemic threshold. Ticks with an undefined R_t break the curve rather
than plotting as zero.

### How R_t is computed

R_t is **estimated from the incidence curve** using the renewal equation,

```
R_t = inc(t) / Σ_{s≥1} w(s) · inc(t−s)
```

where `w` is the generation-time distribution of the *active* spread model — a
point mass at lag 1 for SIR, geometric with rate `incubation_rate` for SEIR
(Cori et al. 2013). It is deliberately **not** derived from `β/γ`: that analytic
form requires a single constant removal rate, and this model has none. The
countermeasure is the only process that removes anyone from Believing, so before
it activates the removal rate is exactly zero and `β/γ` is undefined — the
epidemic is a pure SI process at that point — and once active the rate is
time-varying, region-dependent, and metapopulation-wide, with no scalar
threshold. See `algorithm/reproduction_number.py` for the full reasoning.

Because the estimator is parameterised from the model itself, one implementation
serves both models: for SIR it reduces *exactly* to `inc(t)/inc(t−1)`, and for
SEIR it accounts for the latency stage, which the one-tick ratio understates by
roughly a third.

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
- R_t stays in a plausible band across both models and both scenarios (0.4–2.1,
  against the old placeholder's 150); the default scenario settles at R_t ≈ 1.0
  which matches its endless outcome, and the earthquake scenario stays above 1.0
  while it wins
- Undefined R_t ticks are reported as `null` in JSON, as an empty cell in CSV and
  as "warming up" in the modal — never as zero, which would drag every average
  and the reported reduction toward zero
- The renewal estimator reduces exactly to `inc(t)/inc(t−1)` for SIR, confirming
  the implementation against the closed-form case
- `durable_skeptical` never exceeds `skeptical` and never goes negative, at every
  tick of runs in both models (checked across 7 regions × 400 ticks)
- A durable fraction of 0.0 reproduces the previous behaviour exactly
  (`finalB = 21.4%`, `finalK = 47.6%`), which is how the closed-cycle diagnosis
  was confirmed rather than assumed
- `report_exports/` receives a correct CSV and JSON; peak and final statistics
  cross-check against the CSV
- The right-hand column fits inside the window at 1440×900, 1024×768, 1000×600,
  1920×1080, 800×500 and 640×480, with no panel overlapping another and the
  advance button on screen and clickable at every one of those sizes
- Panel clicks land only inside the panel they belong to; clicks on a panel
  header no longer reach the cards of the panel above it
- Scrolled cards are clipped at the header edge (checked by sampling pixels)
- The analytics overlay cannot consume a click while it is not drawn

---

## Known gaps

Honest list of what does not work or is not yet built. Items marked **fixed**
were addressed in the audit-fix pass and are recorded here only for the record.

| Area | Issue | Status |
|---|---|---|
| Tactical abilities | `echo_chamber` had no effect at all — it built a description dict and never mutated any state, while still charging 20 points and setting a 10-turn cooldown | **fixed** |
| Tactical abilities | `bot_surge` multiplied transmission permanently and compounding; the documented 3-turn duration was never enforced | **fixed** |
| Tactical abilities | `sensationalist_blitz` injected straight into Believing in SEIR mode, skipping the Exposed latency stage | **fixed** |
| Tactical abilities | No timed-effect system existed at all, which was the root cause of the above | **fixed** |
| R_t | Inflated to ~150 rather than ~1: when the countermeasure is inactive a placeholder `gamma = 0.001` divides into R_t. This squashed the in-game chart (threshold line rendered at ~0.7% height), always reported "GROWTH", and made the reported "R_t reduction" an artifact | **fixed** |
| Balance | The 90% loss condition is unreachable — corrections cap at 12%/tick against 5%/tick waning, so corrected population plateaus near 50% | **fixed** — the plateau was a symptom of the closed cycle, not of the threshold. With the durable fraction in place the loss condition is reached; see the two rows below for the remaining timing question |
| Balance | The default scenario on the Nepal map never terminates — it reaches neither condition and runs indefinitely | **fixed** — caused by the missing durable fraction (see *Waning immunity*); the default scenario now resolves and reaches the loss condition, though the trigger fires later than it should (next row) |
| Balance | The loss trigger is formulated against total population (`K/N ≥ 0.90`), but the outcome is decided far earlier. At `durable = 0.39` the default scenario's corrected-to-believing mindshare `K/(K+B)` passes 90% at tick 75 and belief goes extinct at tick 259 — yet `K/N` does not reach 90% until tick 2742, so ~2,500 ticks of a decided game run on | open |
| Balance | The earthquake scenario on Nepal reaches the 75% win in ~15 ticks, so the most expensive ability is barely affordable in a winning run | open |
| Export | PNG figures are never generated — `generate_matplotlib_figures()` is defined but called from nowhere | open |
| Export | Filenames use second granularity, so pressing `E` twice within one second silently overwrites the first dataset | open |
| Custom data | The CSV path is unreachable — `data/regions_example.csv` and `data/strain_config_example.csv` do not exist and were never committed | open |
| UI layout | The Advance Simulation button rendered off the bottom of the window at the default 1440×900, and was entirely invisible at 1024×768 fullscreen — mouse-advancing turns was impossible | **fixed** |
| UI input | Panel click handlers were not bounded by their panel rectangle — clicking the trait panel's header fired Sensationalist Blitz, and clicking the news feed's header bought a trait | **fixed** |
| UI state | A window resize or fullscreen toggle rebuilt every panel, clearing the news ticker and closing the analytics modal | **fixed** |
| UI state | The analytics modal's `visible` flag was not reset between games, so after Play Again an invisible overlay swallowed clicks across most of the screen | **fixed** |
| UI input | Map zoom buttons were computed once from a placeholder rect, so they were drawn over the race bar while their hitboxes stayed live at the wrong coordinates | **fixed** |
| UI layout | Scrollable panels did not clip their content — cards scrolled past the top painted over the fixed header | **fixed** |
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
8. Cori, A., Ferguson, N. M., Fraser, C., & Cauchemez, S. (2013). A new framework and software to estimate time-varying reproduction numbers during epidemics. *American Journal of Epidemiology*, 178(9), 1505–1512.

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
algorithm/     spread_model (SIR, SEIR)  reproduction_number (renewal R_t)
               counter_ai  strike_manager  export_report_figures  graph_traversal
data/          geo/ (map JSON)  something/ (legacy, orphaned)
```
