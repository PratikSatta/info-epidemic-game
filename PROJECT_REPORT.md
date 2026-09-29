# InfoSpread Simulator

## A Compartmental Epidemic Model of Misinformation Spread Across a Geographic Network

**A Project Report Submitted in Partial Fulfilment of the Requirements for the Degree of**

**Bachelor of Computer Application (BCA)**

**Submitted by:** \<Student Name\>
**Exam Roll No.:** \<Roll No.\>
**TU Registration No.:** \<Reg. No.\>

**Submitted to:**
Department of Computer Application
\<College Name\>, \<Campus\>
Tribhuvan University, Kathmandu, Nepal

**Date of Submission:** \<Month\>, 2026

---

## Declaration

I hereby declare that this project report entitled **"InfoSpread Simulator: A Compartmental Epidemic Model of Misinformation Spread Across a Geographic Network"** is my own original work, carried out in partial fulfilment of the requirements for the Bachelor of Computer Application degree at Tribhuvan University. All sources of information, code libraries and published research used in this work have been duly acknowledged and cited. This report has not been submitted elsewhere for the award of any other degree or diploma.

\
\
**\<Student Name\>**
Date: \<Date\>

---

## Certificate

This is to certify that this project report entitled **"InfoSpread Simulator"** has been carried out by **\<Student Name\>** under my supervision and guidance, in partial fulfilment of the requirements for the Bachelor of Computer Application degree of Tribhuvan University. The work embodied in this report is original and has been completed satisfactorily.

\
\
**\<Supervisor Name\>**
Department of Computer Application
\<College Name\>

\
\
**\<Head of Department\>**
Department of Computer Application
\<College Name\>

---

## Acknowledgement

I would like to express my sincere gratitude to my project supervisor, **\<Supervisor Name\>**, for continuous guidance throughout the development of this project. I am also thankful to the Department of Computer Application, \<College Name\>, and to Tribhuvan University for providing the academic environment in which this work was carried out. Finally, I thank my family and friends for their encouragement and support.

**\<Student Name\>**

---

## Abstract

Misinformation spreads through populations in a manner that is mathematically similar to the spread of an infectious disease: a person encounters a claim, may become convinced by it, then attempts to convince others, while corrections circulate alongside the claim and compete for the same attention. This project, **InfoSpread Simulator**, applies compartmental epidemic modelling — the SIR and SEIR families of models originating with Kermack and McKendrick (1927) — to the spread of a false belief across a weighted geographical network, and presents the result as an interactive desktop application in which the user plays the role of the misinformation itself.

The system implements two interchangeable spread models (SIR and a latency-added SEIR variant), two map modes (the seven provinces of Nepal with real population and internet-access data, and a 202-country world map generated from GeoJSON outlines with RSF-derived per-country transmission modifiers, plus four non-geographic platform nodes), a countermeasure layer with telegraph strikes, a permanent trait-catalogue upgrade system, and three tactical abilities. The effective reproduction number R_t is **estimated from the realised incidence curve** using the renewal equation of Cori et al. (2013), rather than derived from the analytic β/γ form, because the model has no single constant removal rate. All model parameters are documented against peer-reviewed literature, and turn-by-turn telemetry can be exported as CSV, JSON and a formatted summary.

Correctness is established by a single executable verification script comprising **92 checks** that run against the real simulation engine and the real pygame application in headless mode. The current state is **85 passed, 0 failed, 7 warnings**, the warnings being five window sizes too short to render every panel line in full and two world-map data-quality items rather than anything affecting correctness. Several substantive modelling defects were found and corrected through this process, the most significant being that the original compartment structure formed a closed cycle `S → B → K → S` with an interior fixed point, causing simulations to park at a stable mixture and never conclude. The report's Results chapter presents these findings with the measured evidence behind each one, and Chapter 5 documents the items that remain open, including the fact that player skill currently does not determine the outcome of a game.

**Keywords:** compartmental model, SIR, SEIR, misinformation, belief dynamics, reproduction number, renewal equation, pygame, simulation.

---

## Table of Contents

| Chapter | Title | Page |
|---|---|---|
| 1 | Introduction | 1 |
| 2 | Literature Review | 8 |
| 3 | System Analysis and Design | 14 |
| 4 | Implementation | 26 |
| 5 | Testing | 38 |
| 6 | Results and Discussion | 47 |
| 7 | Conclusion and Future Work | 58 |
| | References | 62 |
| | Appendices | 64 |

## List of Figures

| # | Caption |
|---|---|
| 3.1 | Four-layer system architecture |
| 3.2 | Class diagram — model layer |
| 3.3 | Entity relationship of a Region |
| 3.4 | Context-level data flow diagram (Level 0) |
| 3.5 | Level-1 data flow diagram of the simulation tick |
| 3.6 | State machine of the game state |
| 3.7 | Screen layout of the main playing view |
| 6.1 | Compartmental trajectories, default SIR |
| 6.2 | R_t against the epidemic threshold |
| 6.3 | Effect of the durable-skepticism fraction on run length |

## List of Tables

| # | Caption |
|---|---|
| 3.1 | Functional requirements |
| 3.2 | Non-functional requirements |
| 3.3 | Model parameters and their literature sources |
| 4.1 | Source file inventory and line counts |
| 5.1 | Verification suite sections and check counts |
| 5.2 | Defects discovered and corrected |
| 6.1 | Terminal outcome by scenario and model |
| 6.2 | R_t estimates across scenarios |
| 6.3 | Durable-skepticism parameter sweep |
| 6.4 | Panel sizing across window resolutions |
| 7.1 | Objectives against achievements |

## List of Abbreviations

| Abbreviation | Expansion |
|---|---|
| SIR | Susceptible–Infectious–Recovered |
| SIRS | Susceptible–Infectious–Recovered–Susceptible |
| SEIR | Susceptible–Exposed–Infectious–Recovered |
| R_t | Effective reproduction number at time t |
| RSF | Reporters Without Borders (press-freedom index) |
| GeoJSON | Geographic JSON, RFC 7946 |
| SDL_ttf | The TrueType font library used by pygame |
| CSV | Comma-Separated Values |
| JSON | JavaScript Object Notation |
| FR / NFR | Functional / Non-functional requirement |

---

# CHAPTER 1: INTRODUCTION

## 1.1 Introduction

The circulation of false information is one of the defining problems of the contemporary information environment. A claim that is false can travel through a population faster than the correction to it, and the mechanisms by which it travels — repeated exposure, social reinforcement, emotional salience, and the structure of the network it moves through — bear a close formal resemblance to the mechanisms by which an infectious disease propagates.

That resemblance is not merely a metaphor. Compartmental epidemic models, introduced by Kermack and McKendrick in 1927, divide a population into a small number of states and describe the rate at which people move between them. A population faced with a claim divides in exactly this way: some have not encountered it (**Susceptible**), some have encountered it and believe it (**Believing**), and some have encountered it and have been corrected (**Skeptical**). The transition rates are governed by contact — how many believers a person is exposed to — just as they are in a disease model.

**InfoSpread Simulator** is a desktop application that takes this correspondence seriously and builds a working, inspectable model out of it. The user does not play the fact-checker; the user plays *the misinformation itself*. They choose a claim, choose where it starts, and then spend points on traits and tactical abilities that make it spread faster, while a countermeasure layer representing fact-checking organisations grows in strength and eventually begins to strike back.

The project is submitted in partial fulfilment of the requirements for the Bachelor of Computer Application degree at Tribhuvan University. It is intended as a demonstration of applied software engineering — layered architecture, object-oriented design, algorithmic thinking, and verification — built on a problem domain with genuine academic literature behind it.

## 1.2 Problem Statement

Misinformation research produces a great deal of empirical knowledge: that false news propagates further and faster than true news (Vosoughi, Roy and Aral, 2018), that fact-checking reduces belief but that the reduction decays (Porter, Wood and Kirby, 2021; Guess et al., 2023), and that corrections are less effective when a claim is congruent with a person's prior attitudes (Flynn, Nyhan and Reifler, 2017).

What the literature does not readily provide is an *interactive, inspectable model* in which these individual findings can be combined and their interaction observed over time. Existing epidemic simulators are either specialised research tools — EpiSim, GLEAM, FRED — that model disease rather than belief and are not designed for experimentation by a student, or entertainment products such as *Plague Inc.* that model contagion but make no claim to academic grounding and expose no telemetry.

The specific problem this project addresses is therefore:

> **Can a compartmental epidemic model be adapted to represent the spread of a belief, calibrated against the published misinformation literature, implemented as a self-contained interactive application, and verified to a standard where its outputs can be trusted as an analysis tool rather than merely a game?**

A secondary problem follows from the first. Once such a model exists, the modelling assumptions themselves become visible and questionable. During development this project repeatedly found that a plausible-looking parameter or rule produced results that did not correspond to anything in the literature, and that diagnosing those discrepancies required instrumenting and measuring the running system rather than reasoning about the source code. A substantial part of the work reported here is that measurement.

## 1.3 Objectives

The specific objectives of this project are:

1. **To design and implement a compartmental model of belief spread** using the SIR family of models, extended with a latency stage (SEIR) and with waning immunity (SIRS), such that a false belief propagates across a network of connected populations.
2. **To ground every model parameter in published research**, and to document the source and the derivation of each parameter in the source code itself, so that a reader can trace any number back to the finding it came from or identify it as an unsupported modelling choice.
3. **To build a weighted geographic network** supporting at least two distinct map modes, one of which uses real Nepali population and internet-access data and the other a global dataset of 202 countries, connected by geographic, linguistic and migration ties, and augmented with non-geographic platform nodes representing social media and messaging spaces.
4. **To implement an opposing countermeasure layer** that models fact-checking as a resource-limited, time-varying intervention, including telegraph strikes that give the player an advance-warned threat to respond to.
5. **To implement a player decision layer** of permanent traits and timed tactical abilities, with genuine trade-offs, so that the simulation is interactive rather than a passive animation.
6. **To estimate the effective reproduction number R_t** from the simulation's own incidence curve using the renewal equation, so that the model's behaviour can be validated against epidemiological theory without relying on an analytic form the model does not satisfy.
7. **To build a verification suite that executes the real system** — not mocks — and asserts on simulated outcomes, UI invariants and data integrity, so that claims about the software's correctness are reproducible by running one command.
8. **To document honestly what does and does not work**, including defects that were found and corrected during an internal audit and issues that remain open.

## 1.4 Scope and Limitations

### 1.4.1 Scope

The system covers:

- Two spread models — SIR (`S → B → K`) and SEIR (`S → E → B → K`) — selectable at launch and interchangeable behind a common abstract interface.
- Waning immunity (SIRS), with a durable component, so that the compartment cycle is not closed.
- Two map modes: **Nepal**, comprising 7 provinces with real population and internet-access data and a hand-specified adjacency graph; and the **World**, comprising 202 countries generated from GeoJSON outlines with press-freedom-derived transmission modifiers, connected by a pre-computed connection list, plus 4 platform nodes.
- Two scenario presets: `default_unverified_rumor` and `earthquake_2015`.
- Four purchasable traits with multiple levels each, and three tactical abilities with point costs and cooldowns.
- An ambient countermeasure with a growth ramp and a cap, plus a telegraph-strike escalation system with a two-front "crackdown" phase.
- A countermeasure AI that selects which region to focus correction on.
- Real-time analytics: a compartmental-trajectory chart and an R_t chart against the epidemic threshold of 1.0.
- Turn-by-turn telemetry export as CSV, JSON and a formatted summary text, plus a pair of publication-quality PNG figures rendered from the same run.
- A headless-capable verification suite of 92 checks.

### 1.4.2 Limitations

The following limitations are inherent to the modelling approach and are stated here rather than deferred:

- **Compartmental, not agent-based.** Individuals are not represented. The model tracks counts, so phenomena that depend on individual network position — super-spreaders, echo chambers as subgraphs, the effect of a specific influencer — cannot be represented.
- **No real-world belief data.** The simulation is calibrated against published *effect sizes* (for example, the 39% durability of a correction), not against a measured time series of belief in any real population. It should be read as a structural model of how the mechanisms interact, not as a forecast.
- **Schematic populations on the world map.** Country populations are approximate values derived from internet penetration (~250–500k per country) rather than real census figures, so geographic position carries little population signal in world mode. Platform-node reach values are calibration inputs, not sourced statistics.
- **Player skill does not currently decide the outcome.** This is a known open issue, measured and documented in Section 6.4. At present the terminal state is determined by the scenario and model chosen rather than by the player's decisions.
- **A simplification in the scenario calibration.** The earthquake scenario applies the Vosoughi et al. six-times multiplier to a transmission rate. The original study measured retweet cascade depth on Twitter, not a generic SIR-style rate parameter, so the multiplier is an analogy rather than a derivation.

## 1.5 Report Organization

**Chapter 2** reviews the epidemiological and misinformation literature on which the model is built. **Chapter 3** presents the system analysis and design, including requirements, architecture, class design, data flow and algorithm design. **Chapter 4** describes the implementation, module by module, and the specific engineering techniques used. **Chapter 5** describes the testing strategy, the verification suite, the defects it found and those that remain open. **Chapter 6** presents the measured results of running the system and discusses what they mean. **Chapter 7** concludes and outlines future work. References and appendices follow.

---

# CHAPTER 2: LITERATURE REVIEW

## 2.1 Compartmental Epidemic Models

The mathematical foundation of this project is the compartmental model of Kermack and McKendrick (1927), which introduced the division of a population into compartments and the use of differential equations to describe movement between them. In the canonical SIR formulation, a susceptible individual becomes infectious upon contact with an infectious individual at a rate proportional to the product of the two group sizes, and recovers into a removed state at a constant per-capita rate.

Two extensions are directly relevant. The **SIRS** model returns recovered individuals to the susceptible state when immunity wanes, which is the appropriate structure for belief: a corrected person does not remain corrected forever. The **SEIR** model inserts an exposed but not-yet-infectious stage, which is the appropriate structure for belief formation: a person who has encountered a claim has not necessarily been convinced by it, and requiring them to pass through a latency stage produces a more realistic, delayed growth curve than assuming instant conversion on contact.

Both extensions are implemented in this project, with the countermeasure playing the role of the removal process.

## 2.2 Misinformation as Contagion

The application of contagion models to the spread of ideas has an established history, and the analogy from rumour to disease is itself old. The modern empirical foundation for treating *misinformation* specifically as a fast-spreading contagion is Vosoughi, Roy and Aral (2018), whose analysis of approximately 126,000 rumour cascades on Twitter found that false news propagated significantly further, faster and more broadly than true news, and that this was driven primarily by novelty and emotional response rather than by automated accounts. The finding that false news reaches more people than the truth is used in this project in two ways: it motivates the win condition being set below universal saturation (a strong majority rather than 95% represents realistic capture), and it supplies the six-times speed multiplier used to calibrate the earthquake scenario.

It is important to note precisely what that multiplier is and is not. The original study measured cascade depth and breadth in retweets. Applying a factor of six to a SIR-style transmission probability is an analogy, and the source code says so explicitly at the point of use. This is documented in the report as a modelling assumption rather than a precise constant.

## 2.3 Correction, and the Durability Problem

The literature on correcting false beliefs establishes two findings that stand in tension, and the resolution of that tension turned out to be the single most important modelling decision in this project.

**Corrections work, but are limited.** Porter, Wood and Kirby (2021) conducted a meta-analysis of fact-checking across multiple countries and found that fact-checks reduced false belief substantially, with an effect corresponding to roughly an 11.8% reduction per direct exposure. Pennycook and Rand (2022) review accuracy prompts as a replicable and generalisable intervention, while also documenting the *continued influence effect* — the tendency of a corrected belief to keep influencing reasoning — which places a ceiling on how effective any correction can be.

**Corrections decay.** Guess et al. (2023) conducted a correction experiment across ten countries and recontacted participants two weeks later. Only 39% of the initial accuracy gain persisted. In other words, 61% of the correction effect decayed within approximately fourteen days. Nyhan (2021) frames the related question of why political misperceptions prove so durable, and argues that the persistence is better explained by the absence of a strong corrective signal than by a backfire effect. Flynn, Nyhan and Reifler (2017) survey the origins of misperceptions and the conditions under which corrections are resisted.

**The modelling consequence.** The decay half of the Guess et al. finding is a statement that corrected people revert. If *all* of them revert, then the compartment structure `S → B → K → S` is a **closed cycle**. This project initially implemented exactly that: waning immunity with no durable component. The result, measured on the running engine, was that the simulation settled at a stable interior mixture — 31% susceptible, 21% believing, 48% skeptical — from tick 75 onward, and never moved again. Neither the win nor the loss condition was ever reached. The fix, described in detail in Section 6.3, is to implement the *other* half of the same finding: 39% of each correction persists permanently. This drains the cycle by that fraction on every lap, and belief eventually goes extinct.

This is presented prominently in this report because it is an example of a modelling decision that looks like a minor parameter choice but is structurally decisive, and because the method by which it was found — measuring the engine rather than reading the code — is a theme of the whole project.

## 2.4 Estimating the Reproduction Number

The effective reproduction number R_t is the average number of secondary cases generated by one case at time t. Above 1.0 an epidemic grows; below 1.0 it decays. It is the standard quantity for judging whether an intervention is winning.

The analytic form familiar from textbook SIR treatments, `R_t = (β/γ)·(S(t)/N)`, requires a single constant removal rate γ. As documented in `algorithm/reproduction_number.py`, this simulation satisfies that condition nowhere:

1. The countermeasure is the only process that removes anyone from Believing. Before it activates, γ is exactly zero and the analytic form is a division by zero — the epidemic at that stage is a pure SI process whose reproduction number is genuinely unbounded, not merely large.
2. Once active, γ is time-varying (it ramps toward its cap each tick) and region-dependent (it is scaled by local media literacy and divided by each node's correction-resistance multiplier).
3. Spread is a metapopulation process over a weighted graph, for which the rigorous analytic threshold is the spectral radius of a next-generation matrix rather than a scalar ratio.

The project therefore follows the approach used in real-time epidemic analytics — Cori, Ferguson, Fraser and Cauchemez (2013) — and **estimates** R_t from the realised incidence curve using the renewal equation,

```
R_t = inc(t) / Σ_{s≥1} w(s) · inc(t−s)
```

where `w` is the generation-time distribution supplied by the active spread model. Because the estimator is parameterised from the model itself, a single implementation serves both: for SIR, where a susceptible becomes believing and infectious within the same tick, `w` is a point mass at lag 1 and the renewal equation collapses *exactly* to the one-tick ratio `inc(t)/inc(t−1)` — a useful closed-form check on the implementation. For SEIR, the latency stage makes `w` geometric with rate equal to the incubation rate, giving a mean generation time of about 2.9 ticks at the default parameters; applying the naive one-tick ratio there understates R_t by roughly a third.

## 2.5 Related Simulators and the Gap

Existing systems fall into two groups. **Research simulators** model disease rather than belief, are typically batch rather than interactive, and are not intended for experimentation by students. **Entertainment products** such as *Plague Inc.* model contagion interactively and are effective at communicating the feel of an epidemic, but expose no telemetry, cite no literature, and make no claim that their parameters correspond to anything measured.

The gap this project occupies is between them: an interactive application whose parameters are individually traceable to published findings, whose internal state is fully observable through a telemetry export, and whose correctness is established by an executable test suite rather than asserted.

## 2.6 Summary of the Literature Review

The literature establishes that (a) compartmental models are a valid formalism for contagion processes generally; (b) false information spreads measurably faster than true information; (c) corrections reduce belief but decay substantially over time, with a minority persisting; and (d) R_t must be estimated from incidence data when the analytic conditions for β/γ do not hold. Every one of these four findings has a direct implementation consequence in the system described in the following chapters.

---

# CHAPTER 3: SYSTEM ANALYSIS AND DESIGN

## 3.1 Requirement Analysis

### 3.1.1 Functional Requirements

**Table 3.1 — Functional requirements**

| ID | Requirement | Verified by |
|---|---|---|
| FR-01 | The system shall simulate belief spread using a compartmental model with at least the compartments Susceptible, Believing and Skeptical. | Section 3 checks |
| FR-02 | The system shall support at least two interchangeable spread models, selectable before play. | Sections 2, 3 |
| FR-03 | The system shall support a latency (Exposed) compartment in at least one model. | Section 3 |
| FR-04 | Population shall be conserved across every tick under all transitions, including corrections, waning and ability use. | Section 3, both models |
| FR-05 | The system shall model waning immunity, with a durable component so that the compartment cycle is not closed. | Section 3 |
| FR-06 | The system shall render at least two geographic map modes, one using real Nepali data and one global. | Section 2 |
| FR-07 | The system shall model non-geographic platform nodes with elevated resistance to correction. | Section 2 |
| FR-08 | The system shall provide at least four purchasable traits with multiple levels and real trade-offs. | Section 6 |
| FR-09 | The system shall provide at least three tactical abilities with point costs and cooldowns. | Section 4 |
| FR-10 | Temporary ability effects shall expire, and shall not leak into permanent base values. | Section 4 |
| FR-11 | The system shall activate a countermeasure automatically once belief crosses a threshold. | Section 3 |
| FR-12 | The countermeasure shall telegraph strikes in advance, showing the player the target and the countdown. | Section 6 |
| FR-13 | The system shall estimate and display R_t against the threshold of 1.0 in a live chart. | Sections 3, 6 |
| FR-14 | The system shall export turn-by-turn telemetry as CSV, JSON and a formatted summary. | Section 5 |
| FR-15 | The system shall detect and report win and loss conditions, and shall track the run's peak belief. | Sections 3, 6 |
| FR-16 | The system shall render correctly at resolutions from 640×480 to 1920×1080 without any panel painting outside its own box. | Section 6 |
| FR-17 | The user interface shall render every character it uses as a real glyph, never as a missing-glyph box. | Section 6 |

### 3.1.2 Non-Functional Requirements

**Table 3.2 — Non-functional requirements**

| ID | Requirement |
|---|---|
| NFR-01 | **Performance** — the main loop shall sustain 60 FPS while simulating a 206-node world. |
| NFR-02 | **Portability** — the application shall run on any platform providing Python 3.14+ and pygame-ce, with no absolute paths in the code. |
| NFR-03 | **Maintainability** — model parameters shall be named constants with their literature source documented at the point of definition. |
| NFR-04 | **Testability** — the system shall be verifiable by a single command that executes the real engine and the real application in headless mode and exits non-zero on failure. |
| NFR-05 | **Reproducibility** — dependencies shall be declared in a manifest such that a fresh clone reproduces the environment. |
| NFR-06 | **Observability** — every quantity that a game rule depends on shall also appear in the exported telemetry. |
| NFR-07 | **Graceful degradation** — a component given less space than it requires shall shed its lowest-priority content rather than painting over its neighbour. |
| NFR-08 | **Honest documentation** — the documentation shall record what does not work, not only what does. |

NFR-06 deserves a note, since it drove a specific change. The loss condition is evaluated against the corrected *mindshare* `K/(K+B)`. Initially the telemetry recorded only the raw compartment counts, leaving an analyst to recompute the ratio — and inviting the mistake of recomputing it as `K/N` instead, which is what the rule used to be. The telemetry now carries `corrected_mindshare` directly, so the defining variable of a run is present in the exported data rather than being re-derived.

## 3.2 Feasibility Study

**Technical feasibility.** The project requires no specialised hardware or services. Python with the pygame-ce library provides rendering, input and font handling; GeoJSON map outlines are parsed at build time into a compact JSON form so that no geographic library is needed at runtime. The compartmental mathematics is elementary arithmetic over dictionaries. The computationally heaviest operation is the R_t estimator, which is bounded by a 15-lag window and a 3-tick smoothing window per tick. Technical feasibility is established by the existence of the working system.

**Economic feasibility.** The entire stack is free and open source: Python, pygame-ce, and NumPy. Map geometry is derived from publicly available GeoJSON outlines. There is no licensing cost, no hosting cost and no third-party service dependency.

**Operational feasibility.** The application runs as a single desktop process launched by one command. It requires no installation beyond `pip install -r requirements.txt`, no network access, and no administrative privileges. The verification suite runs headless and can therefore be executed in an automated or CI context.

**Schedule feasibility.** The project was developed incrementally across nineteen recorded commits, beginning with a file-structure skeleton and proceeding through map data generation, the spread model, the strike system, the countermeasure AI, the UI, and finally a verification-and-audit pass. Each stage produced a runnable artifact.

## 3.3 System Architecture

The system is organised into four layers, with dependencies flowing in one direction only: `view` depends on `controller`, `controller` depends on `model` and `algorithm`, and `model` and `algorithm` depend on nothing above them.

```
┌──────────────────────────────────────────────────────────────────┐
│  VIEW LAYER                                    view/             │
│  main.py (App, event loop, layout)   ui_panels.py                │
│  geo_map_view.py  map_view.py  analytics_modal.py                │
│  tactical_abilities_panel.py  scrollable_panel_base.py           │
│  theme.py  fonts.py                                              │
│  Responsibilities: rendering, input handling, layout,            │
│  presentation state. Holds no simulation rules.                  │
└────────────────────────────┬─────────────────────────────────────┘
                             │ reads state, sends player actions
┌────────────────────────────▼─────────────────────────────────────┐
│  CONTROLLER LAYER                          controller/           │
│  game_engine.py — GameEngine, GameState                          │
│  Responsibilities: the tick sequence, countermeasure activation, │
│  ability execution, telemetry recording, win/loss evaluation,    │
│  points award, effect expiry.                                    │
└────────────────────────────┬─────────────────────────────────────┘
                             │ drives
┌────────────────────────────▼─────────────────────────────────────┐
│  MODEL LAYER                                 model/              │
│  world_graph  region  platform_node  info_strain  trait          │
│  countermeasure  effect  scenarios  world_map_data               │
│  real_world_data  csv_loader  geo_data                           │
│  Responsibilities: domain state and rules. No rendering, no I/O  │
│  beyond data loading.                                            │
├──────────────────────────────────────────────────────────────────┤
│  ALGORITHM LAYER                          algorithm/             │
│  spread_model (SIR, SEIR)   reproduction_number (renewal R_t)    │
│  counter_ai   strike_manager   export_report_figures             │
│  graph_traversal                                                 │
│  Responsibilities: the interchangeable computational strategies. │
│  Each has an abstract base class and concrete implementations.   │
└──────────────────────────────────────────────────────────────────┘
```

**Figure 3.1 — Four-layer system architecture**

The separation is not cosmetic. The `algorithm` layer exists because the spread model, the counter-AI and the R_t estimator each have a natural abstract interface with more than one implementation: `SpreadAlgorithm` has `SIRSpreadModel` and `SEIRSpreadModel`, `CounterAI` has `GreedyCounterAI` and `MinimaxCounterAI`. The engine holds a reference to the abstract type and never branches on which concrete model is running.

## 3.4 Class Design

```
                    ┌────────────────────┐
                    │    WorldGraph      │
                    ├────────────────────┤
                    │ regions: list      │
                    ├────────────────────┤
                    │ add_region()       │
                    │ total_believing()  │
                    │ total_skeptical()  │
                    │ global_infection_  │
                    │   ratio()          │
                    │ corrected_         │
                    │   mindshare()      │
                    │ is_world_          │
                    │   saturated()      │
                    │ is_world_corrected()│
                    └─────────┬──────────┘
                              │ 1..*
                    ┌─────────▼──────────┐          ┌──────────────────┐
                    │      Region        │          │   EffectHost     │
                    ├────────────────────┤          │   (mixin)        │
                    │ name, population   │─────────▷├──────────────────┤
                    │ x, y               │ inherits │ active_effects   │
                    │ base_resistance    │          │ add_effect()     │
                    │ ── compartments ── │          │ tick_effects()   │
                    │ susceptible        │          │ temp_delta()     │
                    │ exposed            │          └────────┬─────────┘
                    │ believing          │                   │
                    │ skeptical          │                   │
                    │ durable_skeptical  │  ◁── sub-count    │
                    │ ── graph ──        │                   │
                    │ connections{}      │                   │
                    ├────────────────────┤                   │
                    │ seed_outbreak()    │                   │
                    │ expose()           │                   │
                    │ move_to_exposed()  │                   │
                    │ convert_exposed_   │                   │
                    │   to_believing()   │                   │
                    │ correct(frac)      │                   │
                    │ revertible_        │                   │
                    │   skeptical        │                   │
                    └─────────┬──────────┘                   │
                              │ extends                      │
                    ┌─────────▼──────────┐                   │
                    │   PlatformNode     │                   │
                    ├────────────────────┤                   │
                    │ category           │                   │
                    │ correction_        │                   │
                    │  resistance_       │                   │
                    │  multiplier        │                   │
                    └────────────────────┘                   │
                                                             │
   ┌──────────────────┐      ┌──────────────────┐           │
   │   InfoStrain     │─────▷│   EffectHost     │◁──────────┘
   ├──────────────────┤ uses ├──────────────────┤
   │ transmission_rate│      └──────────────────┘
   │ believability_   │
   │   rate           │      ┌──────────────────┐
   │ incubation_rate  │      │  ActiveEffect    │
   │ resistance_to_   │      ├──────────────────┤
   │   correction     │      │ source, attr     │
   │ edge_weight_     │      │ delta (additive) │
   │   bonus          │      │ duration         │
   │ detection_risk   │      │ remaining        │
   │ points_available │      │ target, label    │
   │ trait_levels{}   │      │ tick() → expired │
   ├──────────────────┤      └──────────────────┘
   │ effective_       │
   │   transmission_  │      ┌──────────────────┐
   │   rate           │      │      Trait       │ <<abstract>>
   │ effective_       │      ├──────────────────┤
   │   believability_ │      │ name, cost       │
   │   rate           │      │ next_cost(level) │
   │ acquire_trait()  │      │ apply_effect()   │ <<abstract>>
   │ award_points()   │      └────────┬─────────┘
   └──────────────────┘               │ extends
                    ┌────────────┬────┴───────┬────────────────┐
                    │            │            │                │
              VisualTrait  EmotionalTrait  PlatformTrait  ResistanceTrait
              (+transmit,  (+believab,    (+edge weight,  (–correction
               +detect)     +detect)       no downside)    eff, –transmit)
```

**Figure 3.2 — Class diagram, model layer**

Three design decisions in this diagram are worth stating explicitly.

**`durable_skeptical` is a sub-count, not a fifth compartment.** It is a count of people who are *also* counted in `skeptical`. This preserves the invariant that `population` is exactly the sum of the compartments, keeps `total_skeptical()` reporting everyone skeptical, and leaves every existing reader of `skeptical` — the win/loss rules, telemetry, map colouring, side panels — unaffected. Adding a fifth compartment would have required auditing every one of those.

**`ActiveEffect` stores additive deltas, not multipliers.** A delta computed once at cast time is exactly reversible: removing it restores the prior value with no floating-point drift, and it cannot run away if durations or cooldowns are later retuned.

**`InfoStrain` exposes both permanent and effective rates.** `transmission_rate` is the permanent, trait-driven value and is what the trait UI reports; `effective_transmission_rate` folds in temporary ability modifiers and is what the spread model and telemetry read. This separation matters: if the getter folded temporary bonuses in, then buying a trait *during* an ability would permanently bake the bonus into the base value.

## 3.5 Data Design

**Table 3.3 — Model parameters and their sources**

| Parameter | Value | Source / rationale |
|---|---|---|
| `transmission_rate` | 0.15 (default) | Base cross-edge spread probability |
| `believability_rate` | 0.20 (default) | Within-region conversion rate |
| `incubation_rate` | 0.35 (default) | SEIR only; mean latency ≈ 2.9 ticks |
| `resistance_to_correction` | 0.10 (default) | Baseline correction resistance |
| `CounterMeasure.base_strength` | 0.011 | ~1.1% correction/tick at activation |
| `CounterMeasure.growth_rate` | 0.003 | 0.3%/tick ramp |
| `CounterMeasure.cap` | 0.120 | Porter et al. (2021): ~11.8% per exposure |
| `CounterMeasure.DURABLE_FRACTION` | 0.39 | Guess et al. (2023): 39% of correction persists |
| Waning immunity rate | 0.05 / tick | Guess et al. (2023): 61% decays over ~14 ticks; `1 − 0.39^(1/14) ≈ 0.067`, reduced to a conservative 0.05 |
| `StrikeManager.strike_strength` | 0.12 | Porter et al. (2021) upper range |
| `StrikeManager.warning_turns` | 3 | Gives the player a meaningful reaction window |
| `StrikeManager.cooldown_turns` | 6 | Weekly news-cycle rhythm at one tick per day |
| `StrikeManager.crackdown_belief_threshold` | 0.60 | Coordinated national responses deploy after majority penetration |
| Strike population ceiling | 8% of region population | Prevents one strike from swinging global belief |
| `WIN_BELIEF_SHARE` | 0.70 | Calibrated against measured peak belief |
| `LOSS_MINDSHARE` | 0.90 | Share of *engaged* population skeptical |
| `MISINFO_SPEED_MULTIPLIER` | 6.0 | Vosoughi et al. (2018); analogy, not derivation |
| Platform correction multipliers | 1.0 / 1.6 / 2.2 | Public / private / close-group resistance |

**Data files.** Six data files are loaded at runtime: `nepal_districts.json` (75 districts across 7 provinces), `nepal_province_centroids.json` (7 entries), `world_countries.json` (202 countries with parameters and a connection list), and `world_country_centroids.json` (202 entries). All are validated as UTF-8 and checked for internal consistency by the verification suite: 202 countries, 202 parameter entries, 202 centroids, no duplicates, no malformed entries, and exactly 7 provinces containing exactly 75 districts.

**Entity relationship.** A `WorldGraph` contains one or more `Region` objects. A `Region` is connected to zero or more other regions by a weighted, bidirectional edge, stored as a dictionary of neighbour to weight in the range 0–1. A `Region` has exactly one set of compartment counts, which always sum to its population. A `Region` may carry zero or more `ActiveEffect` objects, which are region-scoped temporary modifiers. A `PlatformNode` *is a* `Region` with a category, and overrides the correction-resistance multiplier.

## 3.6 Data Flow

```
   ┌─────────────┐                                    ┌──────────────┐
   │   PLAYER    │──── key / mouse events ───────────▷│     App      │
   │             │◁─── rendered frame ────────────────│  (view)      │
   └─────────────┘                                    └──────┬───────┘
                                                             │
                            advance tick / buy trait / cast ability
                                                             │
                                                      ┌──────▼───────┐
                                                      │ GameEngine   │
                                                      │ (controller) │
                                                      └──────┬───────┘
                                                             │
              ┌──────────────┬───────────────┬───────────────┼──────────────┐
              │              │               │               │              │
     ┌────────▼──────┐ ┌─────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐ ┌────▼──────┐
     │ SpreadAlgorithm│ │CounterMeasure│ │StrikeManager│ │CounterAI   │ │RenewalR_t │
     │ SIR or SEIR   │ │ strength ramp│ │ telegraph   │ │ choose      │ │ estimator │
     └────────┬──────┘ └─────┬──────┘ └──────┬──────┘ │ target      │ └────┬──────┘
              │              │               │        └──────┬──────┘      │
              └──────────────┴───────────────┴───────────────┘             │
                                                             │              │
                                                      ┌──────▼──────────────▼──┐
                                                      │     WorldGraph         │
                                                      │  (compartments change) │
                                                      └──────────┬─────────────┘
                                                                 │
                                                    telemetry_history.append()
                                                                 │
                                              ┌──────────────────┴──────────────┐
                                              │                                 │
                                     ┌────────▼────────┐              ┌─────────▼────────┐
                                     │ Analytics modal │              │ Export (CSV/JSON │
                                     │ (live charts)   │              │  /TXT)           │
                                     └─────────────────┘              └──────────────────┘
```

**Figure 3.5 — Level-1 data flow of a simulation tick**

The tick sequence implemented in `GameEngine.tick()` is:

1. If the countermeasure is not active, compare the global infection ratio against the effective activation threshold (`activation_threshold − strain.detection_risk`, floored at 0.02) and activate it if crossed.
2. Run the spread algorithm for one tick.
3. If active, advance the strike manager: count down pending strikes, execute those reaching zero, and schedule new ones subject to cooldown and the concurrency cap.
4. Ask the counter-AI to choose its informational focus region.
5. Award points to the player, respecting the cap.
6. Count down ability cooldowns.
7. Expire timed ability effects, recording which expired this tick.
8. Increment the tick counter, update peak belief, record the telemetry snapshot.
9. Re-check win and loss conditions.

The win condition is evaluated **before** the loss condition. Both can be true on the same tick, so the ordering is a real decision: a world whose belief has already crossed the win line should not be reclassified as lost merely because the skeptic share has also climbed.

## 3.7 State Machine

```
                    ┌──────────────┐
     launch ───────▷│    MENU      │
                    └──────┬───────┘
                           │ Play (scenario, model, map, seed region)
                    ┌──────▼───────┐
                    │   RUNNING    │◁──────────┐
                    └──┬────────┬──┘           │
        B/N ≥ 0.70     │        │   K/(K+B) ≥ 0.90
                       │        │              │
              ┌────────▼──┐  ┌──▼────────┐     │
              │   WON     │  │   LOST    │     │
              └────────┬──┘  └─────┬─────┘     │
                       │           │           │
                       └─────┬─────┘           │
                             │ Play Again      │
                             └─────────────────┘
```

**Figure 3.6 — Game state machine**

The `WON` and `LOST` states are terminal: `GameEngine.tick()` returns immediately when the state is not `RUNNING`, so no further simulation occurs once the game is decided.

## 3.8 Algorithm Design

### 3.8.1 Spread tick (SIR)

```
function SIR.tick(world, strain, counter):
    counter.tick_growth()
    exposure_deltas ← {}
    correction_deltas ← {}

    for each region in world.regions:
        # within-region exposure
        if region.believing > 0 and region.susceptible > 0:
            rate ← strain.effective_believability_rate
                    × region.believability_multiplier
                    × (region.believing / region.population)
            internal ← region.susceptible × rate
        else:
            internal ← 0

        # cross-edge exposure
        cumulative ← 0
        for (neighbour, weight) in region.connections:
            if neighbour.believing == 0: continue
            w ← min(1.0, weight + strain.edge_weight_bonus)
            cumulative ← cumulative
                        + region.susceptible
                        × strain.effective_transmission_rate × w
                        × (neighbour.believing / neighbour.population)
        external ← cumulative

        # fractional carry
        raw ← internal + external + carry[region]
        new ← min(region.susceptible, int(raw))
        carry[region] ← raw − new
        exposure_deltas[region] ← new

        # correction
        if region.believing > 0 and counter.active:
            strength ← counter.effective_strength_against(strain)
            corrected ← int(region.believing × strength
                          × (1 + region.base_resistance)
                          / region.correction_resistance_multiplier)
            correction_deltas[region] ← min(region.believing, corrected)
        else:
            correction_deltas[region] ← 0

    incidence ← sum(exposure_deltas.values())

    # apply simultaneously
    for each region:
        if exposure_deltas[region] > 0: region.expose(...)
        if correction_deltas[region] > 0:
            region.correct(..., counter.durable_fraction)
        wane(region)
```

The two-pass structure — compute all deltas from a snapshot, then apply them together — prevents updates from cascading unrealistically within a single tick. Nobody infected this tick can infect someone else until the next one.

### 3.8.2 Fractional carry

A subtler issue than it first appears. Every compartment transition computes a real-valued quantity and then truncates to an integer. At low seed counts — a handful of believers in a region of thousands — both the internal and the cross-edge terms routinely compute to fractions just under 1.0. Truncation discards that every single tick, so the simulation **stalls permanently at the seed amount**: the transmission rate climbs each tick, but believing never moves.

The fix is to keep the discarded remainder and add it back on the next tick, so genuine sub-integer growth accumulates into a real new believer rather than being thrown away. The pattern appears three times in SIR (exposure, waning, durable) and four times in SEIR, which has two independent exposure accumulations. It is verified by a dedicated check in the test suite.

### 3.8.3 Renewal-equation R_t estimation

```
class RenewalRTEstimator:
    MAX_LAG ← 15                  # 0.65^15 ≈ 0.16% of geometric mass
    MIN_WEIGHT_COVERAGE ← 0.90
    SMOOTHING_WINDOW ← 3

    function update(new_infections, weights):
        incidence.append(new_infections)
        t ← len(incidence) − 1
        if t < 1: return None                      # no history yet

        current ← mean(incidence[max(0,t−2) .. t])
        if current <= 0: return None

        available ← min(MAX_LAG, len(weights), t)
        mass ← Σ weights[1..available]
        if mass < MIN_WEIGHT_COVERAGE: return None  # too little history

        denominator ← Σ_{s=1..available} (weights[s]/mass) × smoothed(t−s)
        if denominator <= 0: return None

        return current / denominator
```

Three design choices in this algorithm are worth defending.

The estimator **returns `None` rather than a placeholder** when it cannot produce a meaningful value. Early in a run the estimator has seen too little history, and a denominator built from a truncated tail would be an artefact of the truncation rather than a property of the epidemic. Reporting `None` until the coverage threshold is met is preferable to reporting a wrong number. These `None` values propagate as `null` in JSON, an empty cell in CSV, and "warming up" in the modal — never as zero, which would drag every average and the reported reduction toward zero.

The incidence curve is **smoothed** over a trailing three-tick window before estimation, because raw tick-to-tick counts are noisy at low case numbers — a run seeded with 8 people briefly produces ratios like 2/1. Cori et al. likewise smooth the incidence curve prior to estimation.

The incidence series **excludes ability-forced exposures**. R_t measures how many new believers the existing believers generate, and a Sensationalist Blitz is an external shock rather than transmission. Its downstream effect still enters the series normally, through the new believers it creates spreading on subsequent ticks.

### 3.8.4 Countermeasure targeting AI

```
GreedyCounterAI.choose_target(world):
    candidates ← [r for r in world.regions if r.believing > 0]
    if candidates is empty: return None
    return argmax(candidates, key = r.believing)      # O(n)

MinimaxCounterAI.choose_target(world):
    candidates ← [r for r in world.regions if r.believing > 0]
    if candidates is empty: return None
    best ← None; best_score ← +∞
    for candidate in candidates:
        # MIN step: simulate the strain's (MAX player's) remaining potential
        # if this candidate were neutralised now.
        remaining ← Σ estimate_future_spread(r) for r in candidates if r ≠ candidate
        if remaining < best_score:
            best_score ← remaining; best ← candidate
    return best
```

`GreedyCounterAI` implements a "biggest fire first" strategy in O(n). `MinimaxCounterAI` evaluates one ply of an adversarial game in which the strain is the maximising player and the countermeasure is the minimising player. The one-ply restriction keeps it tractable for a real-time game loop; it is a genuine minimax-style evaluation but not a full game-tree search, and the source says so.

### 3.8.5 Strike scheduling

```
StrikeManager.update(world, durable_fraction):
    last_strike_results ← []
    is_crackdown ← world.global_infection_ratio() ≥ 0.60

    # count down and execute
    for strike in pending:
        strike.turns_remaining ← strike.turns_remaining − 1
        if strike.turns_remaining ≤ 0: execute(strike)
        else: keep

    if cooldown_remaining > 0:
        cooldown_remaining ← cooldown_remaining − 1
        return

    # fill open slots up to the concurrency cap (1 normally, 2 in Crackdown)
    cap ← 2 if is_crackdown else 1
    while len(pending) < cap:
        target ← choose_target_excluding(world, already_targeted)
        if target is None: break
        pending.append(PendingStrike(target, warning_turns = 3))

execute(strike):
    removed ← int(target.believing × 0.12)
    removed ← min(removed, target.believing, int(target.population × 0.08))
    if removed > 0: target.correct(removed, durable_fraction)
    cooldown_remaining ← 6
```

The population-relative ceiling of 8% exists because a strike on a populous region could otherwise swing global belief by a large amount in a single tick. The second strike in a Crackdown is selected by querying the counter-AI repeatedly against a **throwaway `WorldGraph`** containing only the eligible candidates, rather than requiring every `CounterAI` subclass to support an exclusion parameter. The real AI logic runs unmodified against a smaller view; no real `Region` state is ever mutated by the selection.

### 3.8.6 Graph traversal

`algorithm/graph_traversal.py` implements breadth-first search, depth-first search, and Dijkstra's algorithm over the region graph. Dijkstra is parameterised with edge cost `1 − connection_weight`, so the resulting distances represent how easily the strain can reach a region — a "fastest spread" path. These are present as algorithmic coursework and are not on the critical path of the simulation; see Appendix B.

## 3.9 User Interface Design

```
┌────────────────────────────────────────────────────────────────────────────┐
│  InfoSpread Simulator        [Map: Nepal ▾]      Turn 24   Points 17       │
├──────────────┬──────────────────────────────────────────┬──────────────────┤
│              │                                          │  📊 ANALYTICS    │
│  ABILITIES   │                                          │  ───────────────  │
│  ──────────  │                                          │  Territory       │
│  Bot Amp.    │              GEOGRAPHIC MAP              │  Telemetry       │
│    15 pts    │                                          │  Population      │
│  Echo Cham.  │        (provinces / countries            │  Believing  222  │
│    20 pts    │         coloured by infection           │  Skeptical   41  │
│  Sens. Blitz │         ratio; edges drawn;              │  Media Lit. 0.07 │
│    12 pts    │         platform nodes in column)        │                  │
│              │                                          │  ──────────────  │
│  ──────────  │                                          │  TRAITS          │
│  TRAITS      │                                          │  Viral Visuals   │
│  Viral Vis.  │                                          │  Emotional Hook  │
│  Emotional   │                                          │  Platform Opt.   │
│  Platform    │                                          │  Corr. Resist.   │
│  Corr. Res.  │                                          │                  │
├──────────────┴──────────────────────────────────────────┴──────────────────┤
│  RACE BAR   Belief ███████████░░░░░░░  Fact-checking ███░░░░░░░░░░░         │
├────────────────────────────────────────────────────────────────────────────┤
│  NEWS FEED                                                                 │
│  • Countermeasure activated                                             │
│  • Strike incoming: Bagmati (3 turns)                                   │
├────────────────────────────────────────────────────────────────────────────┤
│                        [ ADVANCE SIMULATION ]                              │
└────────────────────────────────────────────────────────────────────────────┘
```

**Figure 3.7 — Screen layout of the main playing view**

The layout is computed at runtime from the actual content height each panel declares, not from fixed percentages of the window. Each panel exposes a `required_height()` class method derived from the same constants its `draw()` uses, and `_rebuild_layout()` allocates from those requirements. When the window is too short to hold every panel's requirement, the shortfall is distributed proportionally rather than dumped on whichever panel is least convenient. Section 6.5 presents the measured behaviour of this scheme across seven resolutions.

---

# CHAPTER 4: IMPLEMENTATION

## 4.1 Development Environment

**Table 4.1 — Development environment**

| Component | Version / specification |
|---|---|
| Operating system | Windows 11 (primary); the codebase contains no absolute paths and is portable |
| Language | Python 3.14.4 |
| Graphics / input | pygame-ce 2.5.7 |
| Numerics | NumPy 2.5.1 (declared; used only by non-runtime tooling) |
| Geometry (build-time only) | Shapely 2.1.2 |
| Version control | Git, 19 commits on the development history |
| Editor | Visual Studio Code |
| Headless testing | `SDL_VIDEODRIVER=dummy`, `SDL_AUDIODRIVER=dummy` |

The application is launched with a single command:

```bash
pip install -r requirements.txt
python view/main.py
```

Both `python view/main.py` and `python -m view.main` are supported. Running the file as a script puts `view/` rather than the repository root at `sys.path[0]`, which would make the `model`, `algorithm` and `controller` packages unimportable; `view/main.py` therefore inserts the repository root onto `sys.path` at import time.

## 4.2 Source Inventory

**Table 4.1 (cont.) — Source file inventory**

| Layer | Files | Lines |
|---|---|---|
| `view/` | main.py (861), ui_panels.py (714), geo_map_view.py (600), analytics_modal.py (286), tactical_abilities_panel.py (223), map_view.py (135), theme.py (86), scrollable_panel_base.py (54), fonts.py (216), plus `__init__.py` | ≈ 3,175 |
| `model/` | csv_loader (282), region (145), info_strain (137), trait (131), world_graph (119), effect (83), world_map_data (75), real_world_data (73), countermeasure (70), scenarios (60), geo_data (42), platform_node (39), plus `__init__.py` | ≈ 1,256 |
| `algorithm/` | spread_model (357), export_report_figures (395), strike_manager (226), reproduction_number (150), counter_ai (79), graph_traversal (53), plus `__init__.py` | ≈ 1,260 |
| `controller/` | game_engine (299), plus `__init__.py` | ≈ 299 |
| `tests/` | verify_simulation (681) | 681 |
| Data tooling | data/geo/prepare_nepal_geo.py (161) | 161 |
| **Total** | **33 Python modules** | **≈ 6,832** |

## 4.3 Implemented Modules

### 4.3.1 `model/region.py`

The fundamental unit of the simulation. A `Region` holds a name, a population, screen coordinates, an innate media-literacy proxy (`base_resistance`), the four compartment counts, and a dictionary of weighted connections to neighbouring regions.

All state mutation is encapsulated in methods that clamp their arguments: `expose(amount)` clamps to the available susceptible population, `correct(corrected, durable_fraction)` clamps to the available believing population and then clamps the durable sub-count twice more — never more than the people just corrected, and never more than the skeptical pool actually contains — so the invariant `0 ≤ durable_skeptical ≤ skeptical` cannot be broken regardless of caller behaviour.

`Region` inherits from `EffectHost`, giving it the capacity to carry region-scoped temporary modifiers, and exposes `believability_multiplier`, which is `1.0` unless an Echo Chamber ability is active on that region.

### 4.3.2 `model/platform_node.py`

A `PlatformNode` *is a* `Region` with a category — public, private, or close-group — that overrides `correction_resistance_multiplier` to 1.0, 1.6 or 2.2 respectively. These values model the documented difficulty of moderating private and encrypted spaces relative to public feeds. The constructor validates the category against the multiplier table and raises a `ValueError` naming the valid options if it is not found. Four platform nodes are instantiated: Public Social Media, Short-Video Platforms, Encrypted Messaging, and Close Group Chats.

Their `population` value represents a modelled reach pool rather than a literal headcount. There is no authoritative figure for how many people are reachable through close family group chats; the source code states that this is a calibration input rather than a sourced statistic.

### 4.3.3 `model/info_strain.py`

`InfoStrain` is the claim itself, carrying the rates that govern how it spreads. It exposes permanent properties with validating setters — every rate setter clamps to `[0.0, 1.0]` — and separate `effective_*` properties that add the summed temporary modifiers on top.

Its `acquire_trait` method demonstrates polymorphic dispatch: it calls `trait.apply_effect(self)` without knowing which subclass it holds. Because `apply_effect` adds a delta rather than assigning an absolute value, repeated acquisition of the same trait stacks correctly.

Two mechanics in this class give the upgrade system its shape. First, `next_cost(current_level) = cost × (current_level + 1)²` scales quadratically, so the fourth level of a trait costs sixteen times the base while the first level of a new trait costs one times the base — making diversification genuinely cheaper than depth past level two or three. Second, a **diversification synergy bonus** awards an edge-weight bonus each time the player crosses a new distinct-trait-type threshold: 0.03 for two types, 0.06 for three, and 0.10 for all four. Both mechanics exist to reward spreading investment rather than spamming a single trait.

### 4.3.4 `model/trait.py`

Four concrete traits, each a subclass of the abstract `Trait`, with genuine trade-offs:

| Trait | Base cost | Effect | Trade-off |
|---|---|---|---|
| Viral Visuals | 2 | +0.08 transmission rate per level | +0.015 detection risk |
| Emotional Hook | 3 | +0.10 believability rate per level | +0.02 detection risk |
| Platform Optimized | 2 | +0.05 edge-weight bonus per level | none — deliberately the safe option |
| Correction Resistance | 4 | +0.07 correction resistance per level | −0.02 transmission rate |

`detection_risk` is not a cosmetic number. `GameEngine` reads it to lower the countermeasure's effective activation threshold, so a louder, more attention-grabbing strain brings fact-checkers in **sooner**. This is what makes the trade-off real rather than a dilemma on paper. `PlatformTrait` is deliberately left as the one clean option, both for game-feel reasons — not every choice should be a dilemma — and so that a risk-averse playstyle remains viable.

### 4.3.5 `model/effect.py`

The temporary-modifier system, and the fix for a substantive defect. Previously the tactical abilities mutated the strain's base rates directly, which meant that Bot Amplification Surge's documented three-turn duration was never enforced and the boost compounded permanently.

`ActiveEffect` stores a signed **additive** delta, a duration, a remaining count, an optional target region and a human-readable label. `EffectHost` is a mixin that both `InfoStrain` and `Region` inherit, providing `add_effect`, `tick_effects` (which returns the effects that expired this tick), `temp_delta(attr)` and `has_effect(source)`.

The module docstring records why deltas rather than multipliers: a delta computed once at cast time is exactly reversible, so removing it restores the prior value with no floating-point drift, and it cannot run away if durations are retuned. With the shipped numbers — Bot Surge has a cooldown of 8 and a duration of 3 — two surges can never overlap, so compounding is impossible by construction rather than merely unobserved.

### 4.3.6 `algorithm/spread_model.py`

`SpreadAlgorithm` is an abstract base class declaring three abstract methods — `tick`, `inject_exposure` and `generation_time_weights` — plus a `last_incidence` property.

`inject_exposure` exists specifically to route ability-forced encounters through whichever compartment the *active model* uses for a fresh encounter. Hardcoding the Believing compartment, as an earlier version did, silently bypassed the latency stage that the SEIR model exists to represent.

`generation_time_weights` is abstract for the same reason: the two models have genuinely different generation times, so this cannot be a shared constant.

`SIRSpreadModel` implements the two-pass tick described in Section 3.8.1, with carries for exposure and waning. `SEIRSpreadModel` implements the same structure with an additional Exposed stage, and requires careful ordering: the `Exposed → Believing` conversion must use the **pre-tick** exposed count, captured before this tick's `S → E` arrivals are added, so that nobody skips the latency period entirely within a single tick.

### 4.3.7 `algorithm/reproduction_number.py`

`RenewalRTEstimator`, described in Section 3.8.3. The module docstring is unusually long — roughly forty lines — and deliberately so: it records *why* R_t is estimated rather than derived, with the three specific reasons the model fails the analytic preconditions, and it cites Cori et al. (2013) at the point of use. This is the pattern followed throughout the codebase for any non-obvious modelling decision.

### 4.3.8 `algorithm/strike_manager.py`

`StrikeManager` and `PendingStrike`, described in Section 3.8.5. Every constructor parameter carries a documented source and, where applicable, records the previous value and why it changed — `strike_strength` was 0.35 and is now 0.12, grounded in Porter et al. (2021). Each parameter's docstring explains the real-world behaviour it models: fact-checking organisations have finite staff, so strikes are sporadic rather than continuous; coordinated multi-front campaigns only become institutionally viable at high misinformation penetration.

### 4.3.9 `controller/game_engine.py`

`GameEngine` owns the tick sequence. It holds references to the abstract `SpreadAlgorithm` and `CounterAI` types and never branches on which concrete implementation is running. `GameState` is a simple namespace of string constants.

`use_tactical_ability` validates the target region **before** charging any points, so a missing or unknown region costs the player nothing. Each ability registers an `ActiveEffect` rather than mutating the strain directly.

`_record_telemetry` records nine fields per tick — `tick`, `susceptible`, `exposed`, `believing`, `skeptical`, `population`, `incidence`, `r_t`, `counter_active` — plus `corrected_mindshare`, the quantity the loss condition is actually evaluated against.

### 4.3.10 `view/fonts.py`

A per-character font fallback layer, and the fix for a defect that affected nearly every icon in the interface.

SDL_ttf renders an entire string with exactly one font face and performs no fallback. Any character that face lacks is drawn as a tofu box — silently, without raising. The interface labels itself with symbol and emoji glyphs: the close button is a multiplication sign, the turn counter a stopwatch, a selected territory a pushpin. Those live in Segoe UI Symbol and Segoe UI Emoji, not in Segoe UI. Measured against the face the application was actually rendering with, **34 of the 38 distinct non-ASCII characters in its string literals were tofu**.

`FallbackFont` composites runs of text from whichever installed face has the glyph, the way a browser does. It groups consecutive characters by their rendering face, renders each run, and blits them baseline-aligned onto a composite surface. Three details are load-bearing:

- The composite is sized and baselined exactly like a plain render — to `primary.get_height()`, baselined at `primary.get_ascent()` — so a string containing an icon has the same box as one that does not. Sizing to the tallest run would make them differ (Segoe UI Emoji is 14px tall at this size against Segoe UI's 20px), and every label pairing an icon with a value would draw its two halves on different baselines.
- Text the primary face already covers takes the **untouched** pygame path. Only strings that actually contain a glyph the primary lacks are composited, so nothing about the existing ASCII labels changes.
- Glyph coverage is detected by rendering a private-use sentinel codepoint and comparing bitmaps. `Font.metrics()` cannot do this: it returns notdef *metrics* for an unsupported character rather than reporting that it is unsupported, and every missing glyph in a face returns the same tuple.

### 4.3.11 `view/ui_panels.py` and `view/main.py`

The panel library and the application shell. The most substantive implementation work in the view layer during the audit pass was making panels size themselves from their content rather than from a percentage of the window, and making each panel clip to its own rectangle.

`clip_to` is a context manager that sets the surface clip to a panel's rectangle and restores the previous clip on exit, so anything a panel draws past its own bottom edge cannot land on the panel beneath it. Each telemetry panel declares a `required_height()` class method computed from the same constants its `draw()` uses — `PAD_TOP`, `HEADER_STEP`, `ROW_STEP`, `PAD_BOTTOM` — so the requirement and the drawing cannot drift apart.

`RegionDetailPanel` additionally implements a degradation policy. When given less space than its content requires, it drops lines by priority rank rather than truncating: Believing and Skeptical — the two numbers the win and loss conditions read — are dropped last, and display order is preserved so the panel never appears to shuffle. `NewsTicker` stops before a message it cannot fit rather than drawing half of one.

## 4.4 Object-Oriented Principles Applied

**Abstraction.** `SpreadAlgorithm`, `CounterAI` and `Trait` are abstract base classes that define an interface and forbid direct instantiation. The engine depends on the abstractions.

**Inheritance.** `SEIRSpreadModel` and `SIRSpreadModel` share the `SpreadAlgorithm` contract; `PlatformNode` extends `Region`; the four traits extend `Trait`; `EffectHost` is a mixin shared by `InfoStrain` and `Region`.

**Polymorphism.** `trait.apply_effect(strain)` dispatches to the correct subclass without the caller knowing which. `spread_algo.generation_time_weights(...)` returns the correct generation-time distribution for whichever model is running. `counter_ai.choose_target(world)` returns a target regardless of strategy.

**Encapsulation.** Compartment counts are mutated only through clamped methods. Rate properties have validating setters. `durable_skeptical` cannot exceed `skeptical` even if a caller passes nonsense.

**Composition over inheritance where appropriate.** `GameEngine` *has a* `StrikeManager`, a `RenewalRTEstimator`, a `CounterAI` and a `SpreadAlgorithm`, rather than inheriting from any of them.

## 4.5 Engineering Techniques Worth Recording

**Instrumentation rather than layout arithmetic.** To establish whether a panel was painting outside its box, the audit did not re-derive the layout mathematics. It subclassed `pygame.Surface` with a recording `blit()` that applies `get_clip()` before recording, wrapped each panel's `draw()` call, and unioned the rectangles its blits actually landed on. This measures the pixels that reach the screen rather than a model of them — and it caught an overflow that the previous rectangle-comparison check could not see, because that check compared panel rectangles against the window and each other and was therefore blind to content spilling out of a panel.

**Negative controls.** A test that passes proves nothing unless it can fail. The glyph-coverage check was validated by disabling font fallback entirely, which reproduced the original defect exactly: 34 of 37 characters unrenderable. The durable-skepticism change was validated by setting the durable fraction to 0.0 and confirming it reproduced the previous behaviour exactly (`finalB = 21.4%`, `finalK = 47.6%`) — which is how the closed-cycle diagnosis was confirmed rather than assumed.

**Encoding discipline.** The test suite runs on a Windows console using the cp1252 code page, so any probe that prints non-ASCII must reconfigure stdout. The suite also runs headless under dummy SDL video and audio drivers.

---

# CHAPTER 5: TESTING

## 5.1 Testing Approach

The project's testing strategy is deliberately narrow and strict: **one executable script that runs the real system and exits non-zero if any check fails**.

```bash
python tests/verify_simulation.py
```

The script is not a unit-test framework. No test framework is installed or configured, and rather than add a dependency the project uses a plain script with an explicit `check(name, condition, detail)` helper that accumulates pass, fail and warn counts and sets the process exit code.

Two principles govern what is checked:

**Assert on the real system, not on mocks.** Every simulation check constructs an actual `WorldGraph`, an actual `InfoStrain`, an actual `SpreadAlgorithm` and a real `GameEngine`, and runs real ticks. Every UI check constructs the actual `App` under dummy SDL drivers. Nothing is stubbed.

**A claim in the documentation is a claim under test.** Section 7 of the suite re-measures the checkable rows of the Known-gaps table — that the example CSVs load, that the centroids and the RSF modifiers are still where the documentation says they are, and that two exports in the same second produce distinct files. A row therefore cannot quietly stay documented as open once it has been fixed, nor as fixed once it has regressed: the check and the prose are read in the same place.

## 5.2 Test Sections

**Table 5.1 — Verification suite structure**

| Section | Subject | Representative checks |
|---|---|---|
| 1 | Module imports | Every module imports cleanly; the package structure resolves from any working directory |
| 2 | World construction | Nepal has 7 provinces and 75 districts across exactly 7; the world has 202 countries; every country has a centroid; no duplicates; all data files parse as UTF-8 |
| 3 | Simulation invariants | Population conserved every tick in both models; compartment counts never negative; `durable_skeptical` never exceeds `skeptical` across 7 regions × 400 ticks; fractional carry works; the SIR renewal estimator reduces exactly to `inc(t)/inc(t−1)`; a durable fraction of 0.0 reproduces prior behaviour |
| 4 | Tactical abilities | Every ability's effect is visible immediately and **expires** without leaking into the permanent base value; costs are charged; cooldowns are set; a missing target region costs nothing |
| 5 | Report export | CSV and JSON are written with the documented schema; peak and final statistics cross-check against the CSV; undefined R_t values appear as empty cells, not zero |
| 6 | Headless application | Both map modes launch, simulate and render end-to-end; every documented key binding responds; every glyph is drawable; no panel paints outside its box at any of seven resolutions; panel clicks land only inside their own panel; the analytics overlay cannot consume a click while not drawn |
| 7 | Documented open gaps | The checkable rows of the Known-gaps table are re-measured — that the example CSVs load, that the centroids and the RSF modifiers are still as documented, and that two exports in the same second produce distinct files — so a row cannot stay documented as open once it is fixed, or as fixed once it has regressed |

Total: **92 checks**.

## 5.3 Results

Current state of the suite:

```
85 passed, 0 failed, 7 warnings
    WARN:   1366x768: window too small for full telemetry
    WARN:   1024x768: window too small for full telemetry
    WARN:   1000x600: window too small for full telemetry
    WARN:   800x500: window too small for full telemetry
    WARN:   640x480: window too small for full telemetry
    WARN:   15 of 202 country centroids fall outside their own outline
    WARN:   126 of 202 RSF modifiers exceed the clamp ceiling of 1.0
```

The suite exits zero. Earlier revisions of this report recorded one failure, and it was the two example CSVs the custom-data mode depends on, which had never been committed and made that mode unreachable. That gap is now closed — the examples exist, and the suite loads them rather than merely asserting they are present, so a malformed example could not leave the mode advertised but broken.

All seven warnings are reports of measured behaviour rather than breakage. Five are the window sizes too short to give every panel its full content height, which is the documented degradation policy working as intended. The other two are world-map data-quality items: the centroids that fall outside their own outline, and the RSF modifiers lost to the clamp.

## 5.4 Defects Discovered and Corrected

The audit pass found and corrected a substantial number of defects, several of them structural. They are listed here because the process of finding them is a result in its own right.

**Table 5.2 — Defects discovered and corrected**

| # | Area | Defect | How it was found | Correction |
|---|---|---|---|---|
| D-01 | Abilities | `echo_chamber` had **no effect at all** — it built a description dictionary and never mutated any state, while still charging 20 points and setting a 10-turn cooldown | Reading the ability against its documentation | Implemented as a region-scoped `ActiveEffect` |
| D-02 | Abilities | `bot_surge` multiplied transmission permanently and compounding; the documented 3-turn duration was never enforced | Same | Timed additive delta with expiry |
| D-03 | Abilities | `sensationalist_blitz` injected straight into Believing in SEIR mode, skipping the latency stage | Same | Routed through `SpreadAlgorithm.inject_exposure()` |
| D-04 | Architecture | No timed-effect system existed at all, which was the root cause of D-01 to D-03 | Follow-on from the above | `model/effect.py` |
| D-05 | R_t | R_t was inflated to ~150 against a true value near 1. When the countermeasure is inactive a placeholder `gamma = 0.001` divides into it. This squashed the in-game chart — the threshold line rendered at about 0.7% height — always reported "GROWTH", and made the reported R_t reduction an artefact | Plotting the value and noticing the threshold line was invisible | Replaced with the renewal-equation estimator; measured band is now 0.4–2.1 |
| D-06 | Balance | The simulation never terminated. Measured on the real engine, the default scenario sat at 31% S / 21% B / 48% K from tick 75 onward and never moved again | Running it and watching | Caused by the closed `S → B → K → S` cycle; fixed by the durable fraction |
| D-07 | Balance | The 90% loss condition was unreachable: corrections cap at 12%/tick against 5%/tick waning, so the corrected population plateaus near 50% | Parameter sweep | The plateau was a symptom of D-06, not of the threshold |
| D-08 | Balance | The loss trigger was formulated against total population (`K/N ≥ 0.90`), but the outcome is decided far earlier. At `durable = 0.39` the mindshare `K/(K+B)` passes 90% at tick 75 — yet `K/N` does not reach 90% until tick 2742, so ~2,500 ticks of a decided game ran on | Instrumenting both ratios over a full run | Loss redefined as the mindshare test `K/(K+B) ≥ 0.90` |
| D-09 | Balance | The win line was unreachable: measured peak belief is 72.9–74.7% under SIR and 60.7–62.5% under SEIR under *every* play policy, so a 75% line could never be crossed and the loss was the only reachable ending | Running all four scenario/model combinations | Lowered to 0.70 |
| D-10 | UI | The game-over screen labelled the *final* belief ratio "Peak Belief", reporting ~0.2% for a run whose belief had peaked at 73% | Playing a game to completion | The engine now tracks `peak_belief` across the whole run |
| D-11 | UI layout | The Advance Simulation button rendered off the bottom of the window at the default 1440×900, and was entirely invisible at 1024×768 fullscreen — mouse-advancing turns was impossible | Opening the application at each size | Content-driven layout |
| D-12 | UI input | Panel click handlers were not bounded by their panel rectangle — clicking the trait panel's header fired Sensationalist Blitz, and clicking the news feed's header bought a trait | Clicking each panel's header | Hitboxes bounded to their panel |
| D-13 | UI state | A window resize or fullscreen toggle rebuilt every panel, clearing the news ticker and closing the analytics modal | Resizing the window | Presentation state preserved across rebuilds |
| D-14 | UI state | The analytics modal's `visible` flag was not reset between games, so after Play Again an invisible overlay swallowed clicks across most of the screen | Playing a second game | Flag reset on new game |
| D-15 | UI input | Map zoom buttons were computed once from a placeholder rectangle, so they were drawn over the race bar while their hitboxes stayed live at the wrong coordinates | Comparing drawn position against hitbox | Recomputed on layout change |
| D-16 | UI layout | Scrollable panels did not clip their content — cards scrolled past the top painted over the fixed header | Sampling pixels at the header edge | Clipping added |
| D-17 | UI layout | The Territory Telemetry panel drew out of its own box at **every** window size including the default. Its height was a percentage of the window while its content is a fixed number of pixels. Measured, it needs 162px with an Exposed compartment against boxes of 122px at 1440×900, 100px at 1366×768 and 55px at 640×480 | Instrumented `blit` recording described in Section 4.5 | `required_height()` per panel, layout sizes from it, every panel clips |
| D-18 | UI layout | Sizing the telemetry panels correctly then starved the panels the player interacts with — the first attempt reserved the full telemetry height unconditionally and left the abilities panel 83px at 1366×768, with 39px of clickable area | Dumping the computed column heights | Shortfall shared proportionally |
| D-19 | UI layout | A panel given less than its content height had no degradation policy: it either overflowed or, once clipped, was cut off mid-line | Reviewing D-17's fix | Priority-ranked line dropping |
| D-20 | UI font | Nearly every icon rendered as a tofu box, including the modal's close button. Measured: **34 of 38** distinct non-ASCII characters unrenderable in the face actually used | Rendering each character and comparing against the font's notdef bitmap | `view/fonts.py` |
| D-21 | UI font | After the fallback was added, emoji were drawn from Segoe UI Symbol, which has them only as thin monochrome outlines — at 15px its bar chart and world map are indistinguishable from empty rectangles, so the Analytics button *looked* like it still had a box on it | Comparing Symbol against Emoji at 4× magnification | Emoji preferred; Symbol for the Arrows block and as last resort |
| D-22 | Repo | No `.gitignore` existed and 24 compiled `.pyc` files were tracked | Inspecting the repository | `.gitignore` added |
| D-23 | Repo | The documented launch command crashed with `ModuleNotFoundError` | Running the documented command | `sys.path` insertion restored |
| D-24 | Repo | No dependency manifest, so a fresh clone could not reproduce the environment | Reviewing the repo | `requirements.txt` added |
| D-25 | Export | PNG figures were never generated: `generate_matplotlib_figures()` was defined and called from nowhere, so every export produced the data with no plots while the module's own docstring advertised publication-ready figures | Reading the export module against its docstring | `export_academic_report()` renders them itself, sharing the run name of the CSV they plot so the two are obviously one dataset |
| D-26 | Export | Filenames used second granularity, so pressing `E` twice within one second silently overwrote the first dataset. Measured: 3 files after two exports, where 6 were expected | Pressing `E` twice in succession | `_unique_run_name()` adds a suffix only when the plain name is taken; measured 10 files after two exports, five per run |
| D-27 | Custom data | `data/regions_example.csv` and `data/strain_config_example.csv` were never committed, so the custom-CSV map mode was unreachable and this was the suite's single failing check | Reviewing the repository against the advertised feature | Both examples committed, and the suite now loads them and plays a game on the result rather than only asserting they exist |

One methodological point deserves emphasis. Two of these defects — D-05 and D-17 — were invisible to the test suite that existed at the time, and in both cases the reason was the same: the check was a *model* of the thing rather than a measurement of it. The old R_t check asserted that the value was "plausible" without comparing it against anything external; the old layout check compared rectangles rather than pixels. Both were replaced with checks that observe the real output. Defect D-21 is a subtler instance: the first fix for D-20 was correct by its own logic and still looked wrong, because the check tested that a glyph was present rather than that it was legible.

Two corrections to the project's own documentation are also recorded. Earlier revisions of the implementation summary listed unit tests and an integration test as passing. Those tests had never been written; the claim was removed rather than restated, and the current summary states plainly that the test suite is a single script and why. Separately, the in-game help text advertised a 95% win line that no version of the rules ever used — the constants are now interpolated into the help text, so the rules and the documentation of them cannot drift apart again.

## 5.5 Items Remaining Open

The following are known and documented, and are not addressed by this project:

Three items previously listed here — the unreachable custom-CSV mode, the figures that were never generated, and the same-second export overwrite — were closed in the audit pass that produced this revision and are recorded as D-25 to D-27 in Table 5.2. What remains open is below.

| Area | Issue |
|---|---|
| World map | Country populations are schematic (~250–500k each), so geography carries little population signal. Platform nodes are 0.011% of the total and their mechanic is effectively invisible. |
| World map | The RSF transmission modifier is clamped to a ceiling of 1.0, so per-country penalties survive but boosts are unrepresentable. Measured: 126 of 202 modifiers exceed the ceiling; only 114 distinct edge weights survive across 406 connections. |
| World map | For 15 of 202 countries the centroid falls outside the country's own outline (measured; an earlier figure of 55 was based on a stricter test), so labels and strike effects draw in the wrong place. |
| Balance | Player skill does not decide the outcome. See Section 6.4. |
| Balance | `sensationalist_blitz` is actively counterproductive: converting Susceptible → Believing raises the global infection ratio, tripping the countermeasure's activation threshold sooner (tick 11 rather than 23) and ending the run earlier than not casting it. |
| Balance | The earthquake scenario on Nepal reaches the win in about 15 ticks, so the most expensive ability (20 points at 1 point per tick) is unaffordable in a winning run. |

---

# CHAPTER 6: RESULTS AND DISCUSSION

This chapter presents measured results. Every number below was produced by running the system, not by reasoning about the source code. Where a figure comes from a specific instrumented run, that is stated.

## 6.1 Terminal Outcomes

**Table 6.1 — Terminal outcome by scenario and model, Nepal map**

| Scenario | Model | Outcome | Tick | Peak belief |
|---|---|---|---|---|
| default_unverified_rumor | SIR | **WON** | ≈ 30 | 72.9–74.7% |
| default_unverified_rumor | SEIR | **LOST** | ≈ 92 | 60.7–62.5% |
| earthquake_2015 | SIR | **WON** | ≈ 15 | high |
| earthquake_2015 | SEIR | WON | early | high |

The most important observation in this table is that the SIR model and the SEIR model reach **opposite outcomes on identical inputs**. This is the latency stage doing real work rather than decorating the model: requiring a person to pass through an Exposed stage before they can transmit delays the growth curve enough that the countermeasure — which activates on a belief threshold — gains the time it needs to reach its cap and win the argument.

Peak belief across the four combinations was measured under every play policy the game offers, and the spread between the best and worst play was 1–2 percentage points. That is the origin of the win-line calibration and, as Section 6.4 explains, also the project's most significant open problem.

## 6.2 Reproduction Number

**Table 6.2 — R_t estimates**

| Quantity | Value |
|---|---|
| Placeholder implementation (before the fix) | ≈ 150 |
| Correct implementation, observed band across models and scenarios | 0.4 – 2.1 |
| Default scenario, settled value | ≈ 1.0 |
| Earthquake scenario while winning | > 1.0 |
| Naive one-tick ratio under SEIR, earthquake scenario | 1.40 |
| Correct renewal form, same run | 2.14 |

The R_t chart is the clearest validation available that the simulation is behaving as an epidemic model rather than as an arbitrary animation. The default scenario settles at R_t ≈ 1.0, which is exactly what an endless, non-terminating run should look like — the wave neither grows nor decays. Once the durable-skepticism fix causes the default scenario to conclude, R_t decays below 1.0 and stays there, which is the characteristic signature of an epidemic under control. The earthquake scenario, which wins, stays above 1.0 throughout.

The last two rows quantify the cost of getting the generation time wrong. Applying the one-tick ratio to a model whose mean generation time is 2.9 ticks understates R_t by roughly a third — 1.40 against 2.14 on the same run. This matters because the understated value sits much closer to the threshold of 1.0 than the truth does, and a decision rule based on it would draw a materially different conclusion.

The implementation is confirmed against a closed-form case: for SIR the renewal estimator reduces *exactly* to `inc(t)/inc(t−1)`, which is asserted in the suite.

## 6.3 The Durable-Skepticism Parameter

The single most consequential modelling change in the project. The original model implemented only the decay half of the Guess et al. (2023) finding: corrected people waned back to Susceptible at 5% per tick, and nothing was permanent. This made `S → B → K → S` a **closed cycle**, and a closed cycle has an interior fixed point. Measured on the real engine, the default scenario sat at 31% S / 21% B / 48% K from tick 75 onward and never moved again — neither the win nor the loss was ever reached.

Implementing the other half of the same finding — 39% of each correction persists permanently — drains the cycle by that fraction on every lap.

**Table 6.3 — Effect of the durable fraction on run length (default scenario, loss formulated as K/N at the time of measurement)**

| Durable fraction | Tick at which belief goes extinct |
|---|---|
| 0.20 | 5584 |
| **0.39** (the research value) | **2742** |
| 0.70 | 1181 |

Two things are worth drawing out. First, the parameter is a dial on game length, and the value used is the one the research actually supports rather than the one that produces the best game — 0.39 was adopted because that is what Guess et al. measured, and the run length followed. Second, the extinction tick was not by itself the point at which the game was decided: belief went extinct at tick 259, but under the `K/N` loss formulation the game ran until 2742. Which leads to the next finding.

## 6.4 The Decided-Game Crawl, and an Open Problem

The loss condition was originally `K/N ≥ 0.90` — ninety per cent of the **total population** skeptical. This is a much stronger requirement than it appears, because `K/N` is bounded above by the fraction of people who ever pass through Believing. Any mechanism that lowers peak belief also lowers the reachable ceiling on `K`, so the loss becomes unreachable — and where it is reachable, it fires long after the game is over.

Instrumenting both ratios over a full run made the size of the problem concrete. On the default scenario at `durable = 0.39`:

- the corrected mindshare `K/(K+B)` passes 90% at **tick 75**;
- belief goes extinct at **tick 259**;
- but `K/N` does not reach 90% until **tick 2742**.

Roughly 2,500 ticks of a decided game were still accepting input, because `K/N` could only creep upward as the last few stragglers were corrected a handful of people per tick. The loss is now the mindshare test `K/(K+B) ≥ 0.90`, which keeps the rule mechanism-independent: adding waning immunity or durable skepticism moves peak belief around, but the mindshare ratio still crosses at roughly the same moment, because both its numerator and its denominator are driven by the same epidemic.

**The open problem.** Having fixed the termination defect, a second and more fundamental issue became measurable: **the player's decisions do not determine the outcome.** Tactical abilities move peak belief by only 1–2 percentage points, because the countermeasure activates early and reaches full strength within about 37 ticks. At a 70% win line the result is determined by the scenario and model choice — default SIR wins, default SEIR loses — regardless of what the player does.

This is stated plainly because it is the honest finding and because it bounds what the project can claim. There is no value of the win threshold at which play becomes decisive until the countermeasure's activation timing and growth ramp are rebalanced; a threshold that made play decisive on one scenario would merely move the problem to another. The fix is a redesign of the countermeasure schedule — most plausibly, making activation responsive to the strain's *rate of growth* rather than its absolute level, so that a fast-spreading player is punished later rather than earlier — and it is proposed as future work in Section 7.4 rather than attempted here.

A closely related measured finding is that `sensationalist_blitz` is actively counterproductive under the current design: converting Susceptible → Believing raises the global infection ratio, which trips the countermeasure's activation threshold sooner (tick 11 rather than tick 23) and therefore ends the run earlier than not casting it. This is a direct consequence of the same design issue, and it is recorded as an open item.

## 6.5 Interface Measurements

**Table 6.4 — Panel behaviour across window sizes**

| Resolution | Telemetry panels | Notes |
|---|---|---|
| 1920 × 1080 | Full content height, every line rendered | No shortfall |
| 1440 × 900 | Full content height, every line rendered | Default window size |
| 1366 × 768 | Shortfall shared | Lowest-priority lines dropped |
| 1024 × 768 | Shortfall shared | Lowest-priority lines dropped |
| 1000 × 600 | Shortfall shared | Lowest-priority lines dropped |
| 800 × 500 | Scaled | Advance button visible and clickable |
| 640 × 480 | Scaled | Advance button visible and clickable |

Before the layout was reworked, the Territory Telemetry panel painted out of its own box at **every** window size including the default 1440×900 — its last two lines (Skeptical and Media Literacy) were drawn over the panel beneath it. The root cause was that the panel's height was allocated as a percentage of the window while its content is a fixed number of pixels, so the two agreed at exactly one size.

At every size in the table, no panel paints outside its own box, no panel overlaps another, and the advance button is on screen and clickable. These are measured by the instrumented `blit` recording described in Section 4.5.

The responsiveness of this fix is worth noting as a process observation. The first attempt to size the telemetry panels correctly reserved the full telemetry height unconditionally, which fixed the overflow and starved the panels the player actually interacts with — the abilities panel was left 83px tall at 1366×768, with 39px of clickable area. This was caught by dumping the computed column heights rather than by looking at the screen, and corrected by sharing the shortfall proportionally. A fix that resolves the reported symptom can introduce a worse defect elsewhere, and the only reliable way to notice is to measure the whole system rather than the part that was reported.

## 6.6 Font and Glyph Results

| Measurement | Value |
|---|---|
| Distinct non-ASCII characters used in the view layer's string literals | 38 |
| Unrenderable in the primary face before the fix | 34 |
| After the fix | 0 |
| Negative control (fallback disabled), per the suite | 34 of 37 unrenderable |

The glyph check in the suite reads its character set **out of the view layer's source** rather than listing characters in the test, so a new icon added to any label is covered automatically. It is the only check that can catch this class of defect: a tofu box is a perfectly successful `render()` call that raises nothing, so no exception-based test would ever see it.

The negative-control row is what gives the check its credibility. Setting `FALLBACK_FONTS = ()` reproduces the original defect exactly, confirming both that the check has teeth and that 34-of-38 was the real magnitude of the problem.

## 6.7 Discussion

The results support four conclusions about the model, beyond the software engineering outcomes.

**The compartment structure is decisive, not decorative.** The choice between SIR and SEIR flips the terminal outcome on identical inputs. Adding a latency stage delays the growth curve enough that a threshold-triggered intervention arrives in time to win. This is the kind of interaction that is difficult to reason about analytically and straightforward to observe in a running simulation, which is the argument for building one.

**The durability of a correction is structurally load-bearing.** Implementing only the decay half of a published finding made the model non-terminating, and the defect was not a bug in the code — every line did what it said. It was a modelling error with a mathematical consequence: a closed cycle has an interior fixed point. The lesson is that a parameter derived from research must be implemented in both directions when the finding is two-sided, and that a simulation that parks at a stable mixture is a symptom worth tracing rather than a tuning problem to be papered over.

**Analytic forms must be checked against their preconditions.** The original R_t implementation was not merely inaccurate; it was ~150 times the correct value, and it was wrong because the analytic formula it used requires a constant removal rate that the model does not have. Estimating from the incidence curve instead produced values in the 0.4–2.1 band that corroborate the simulation's own outcomes — the endless default run settles at R_t ≈ 1.0, exactly as an endless epidemic should.

**A game model can be mechanically sound and still not be a good game.** The measured finding that player skill moves the outcome by 1–2 percentage points is the clearest example. Every component does what it is documented to do; the balance between them is wrong. This is reported as the project's principal open problem rather than a limitation to be hedged, because it is measurable and because it is the most useful thing the model has told us about itself.

---

# CHAPTER 7: CONCLUSION AND FUTURE WORK

## 7.1 Summary

InfoSpread Simulator is a desktop application that applies compartmental epidemic modelling to the spread of a false belief across a weighted geographic network. It implements two interchangeable spread models, two map modes covering real Nepali and global data, a literature-grounded countermeasure layer with telegraph strikes, a permanent trait system and three timed tactical abilities, a renewal-equation estimator for the effective reproduction number, live analytics, and turn-by-turn telemetry export in three formats.

The system comprises approximately 6,832 lines of Python across 33 modules, organised in four layers with one-directional dependencies, and is verified by a single executable script of 92 checks that runs the real engine and the real application in headless mode.

## 7.2 Objectives Against Achievements

**Table 7.1 — Objectives against achievements**

| # | Objective | Status |
|---|---|---|
| 1 | Compartmental model with SIR, SEIR and SIRS extensions | **Achieved** — both models implemented behind one abstract interface, with waning immunity and a durable component |
| 2 | Every parameter grounded in published research | **Achieved** — each parameter documents its source at the point of definition; parameters without a source are explicitly marked as calibration inputs |
| 3 | Weighted geographic network with two map modes | **Achieved** — Nepal (7 provinces, real population and internet data) and World (202 countries plus 4 platform nodes) |
| 4 | Countermeasure layer with telegraph strikes | **Achieved** — growth ramp, cap, region-dependent effectiveness, telegraph warning, and a crackdown escalation phase |
| 5 | Player decision layer with real trade-offs | **Achieved** — 4 traits × multiple levels with documented trade-offs, and 3 abilities with costs, cooldowns and expiring effects |
| 6 | R_t estimated from the incidence curve | **Achieved** — renewal-equation estimator, validated against the closed-form SIR case, observed band 0.4–2.1 |
| 7 | Verification suite executing the real system | **Achieved** — 92 checks, no failures, seven test sections, negative controls demonstrated |
| 8 | Honest documentation of what does not work | **Achieved** — 6 open items catalogued, the mechanically checkable ones re-verified by the suite; 27 defects recorded with how each was found |

## 7.3 Limitations

The limitations stated in Section 1.4.2 stand. Restated concisely: the model is compartmental rather than agent-based, so individual network position cannot be represented; it is calibrated against published effect sizes rather than any measured time series of belief, so it is a structural model rather than a forecasting tool; world-map populations are schematic; the earthquake scenario's six-times multiplier is an analogy to a retweet-cascade finding rather than a derivation; and — most significantly — **the player's decisions do not currently determine the outcome**, so the system is at present better understood as an interactive model than as a game with a meaningful skill ceiling.

It should also be noted that eight of the model's parameters have no direct empirical backing and are documented as calibration inputs: the transmission and believability base rates, the incubation rate, the default correction resistance, the strike population ceiling, the platform reach values, the diversification bonuses, and the trait potencies. These were tuned for plausible behaviour, not derived from measurement, and the source code says so at each one.

## 7.4 Future Work

**Rebalance the countermeasure schedule.** The highest-priority item. Making activation respond to the strain's *rate* of growth rather than its absolute belief level would mean a fast-spreading player is punished later rather than sooner, which would make the player's decisions consequential. This is the change most likely to convert the system from a model into a game.

**Re-examine `sensationalist_blitz`.** The ability is currently counterproductive for the reason given in Section 6.4. Either its effect on the activation threshold should be decoupled from the global infection ratio, or the ability should be redesigned around a different mechanism.

**Replace schematic world populations.** Real per-country population figures would make geography carry population signal, which would in turn make the world map a more useful analytical surface than it is now. The centroid-inside-outline issue (15 countries) should be resolved at the same time.

**Consider an agent-based extension.** The compartmental approach cannot represent super-spreaders or echo chambers as subgraphs. A hybrid in which compartments are held per network community rather than per geography would allow the model to represent the structures that the misinformation literature identifies as important, at a cost in complexity that a follow-on project could reasonably absorb.

**Add a sensitivity analysis.** No systematic sweep of the parameter space has been performed. A sensitivity analysis over the transmission rate, believability rate and durable fraction would establish which parameters the outcomes are actually sensitive to, and would strengthen every calibration claim in this report.

## 7.5 Concluding Remarks

The project set out to determine whether a compartmental epidemic model could be adapted to represent the spread of a belief, calibrated against the published literature, implemented as a self-contained interactive application, and verified to a standard where its outputs can be trusted as an analysis tool. The first three parts are met. The fourth is met in the specific sense that the system's correctness is established by an executable suite and its defects are catalogued rather than hidden — but the suite's own most useful finding is a negative one, and the project's principal result is arguably that the model is now honest enough to tell its author that its player decisions do not matter yet.

---

# REFERENCES

1. Kermack, W. O., & McKendrick, A. G. (1927). A contribution to the mathematical theory of epidemics. *Proceedings of the Royal Society A*, 115(772), 700–721.
2. Vosoughi, S., Roy, D., & Aral, S. (2018). The spread of true and false news online. *Science*, 359(6380), 1146–1151.
3. Porter, E., Wood, T. J., & Kirby, D. (2021). The global effectiveness of fact-checking. *PNAS*, 118(37).
4. Guess, A. M., et al. (2023). Correcting COVID-19 vaccine misinformation in 10 countries. *Royal Society Open Science*.
5. Nyhan, B. (2021). Why the backfire effect does not explain the durability of political misperceptions. *PNAS*, 118(15).
6. Pennycook, G., & Rand, D. G. (2022). Accuracy prompts are a replicable and generalizable approach for reducing the spread of misinformation. *Nature Communications*.
7. Flynn, D. J., Nyhan, B., & Reifler, J. (2017). The nature and origins of misperceptions. *Political Psychology*, 38(S1).
8. Cori, A., Ferguson, N. M., Fraser, C., & Cauchemez, S. (2013). A new framework and software to estimate time-varying reproduction numbers during epidemics. *American Journal of Epidemiology*, 178(9), 1505–1512.

---

# APPENDICES

## Appendix A: User Manual

### A.1 Installation

```bash
pip install -r requirements.txt
python view/main.py
```

Requires Python 3.14 or later.

### A.2 Keyboard Controls

| Key | Action |
|---|---|
| `SPACE` / `ENTER` | Advance one simulation tick |
| `A` | Toggle the analytics modal |
| `E` | Export an academic report to `report_exports/` |
| `ESC` | Close the analytics modal; then reset map zoom |
| `F` / `F11` | Toggle fullscreen |
| `5` | Switch to the Nepal map |
| `4` | Switch to custom CSV data, loaded from `data/regions_example.csv` and `data/strain_config_example.csv` |

### A.3 Mouse Controls

- Click a region to select it and read its telemetry.
- Scroll over the map to zoom; drag to pan.
- Click a trait to purchase it; click an ability to cast it.
- Click **ADVANCE SIMULATION** to run a tick.

### A.4 How to Play

1. Choose a scenario, a spread model and a map from the menu, and click Play.
2. Seed the outbreak in a region — the largest region is chosen by default.
3. Advance ticks. Watch the R_t chart: above 1.0 the wave is growing.
4. Buy traits with earned points. Note that attention-grabbing traits bring fact-checkers in sooner.
5. When the countermeasure activates, watch for telegraph strikes — they give three turns of warning.
6. Reach 70% belief of the total population to win; avoid skeptics reaching 90% of everyone holding an opinion, or you lose.
7. Press `E` to export the full turn-by-turn dataset.

## Appendix B: File Map

```
view/          main.py (App, event loop, layout)  theme.py  ui_panels.py
               fonts.py (per-character font fallback)
               geo_map_view.py  map_view.py  analytics_modal.py
               tactical_abilities_panel.py  scrollable_panel_base.py
controller/    game_engine.py (tick, telemetry, abilities)
model/         world_graph  region  platform_node  info_strain  trait
               countermeasure  effect  scenarios  world_map_data
               real_world_data  csv_loader  geo_data
algorithm/     spread_model (SIR, SEIR)  reproduction_number (renewal R_t)
               counter_ai  strike_manager  export_report_figures
               graph_traversal
data/          geo/ (map JSON)  something/ (legacy, orphaned)
tests/         verify_simulation.py (92 checks)
```

**Note on `algorithm/graph_traversal.py`.** This module implements breadth-first search, depth-first search and Dijkstra's algorithm over the region graph. It is not called by the running simulation. It is included as algorithmic coursework, and Dijkstra's edge-cost parameterisation (`1 − connection_weight`) is meaningful — it computes how easily the strain can reach a region — so it is retained rather than removed. `MinimaxCounterAI` in `algorithm/counter_ai.py` is likewise implemented and available but not the AI currently wired up, which is `GreedyCounterAI`.

## Appendix C: Running the Verification Suite

```bash
python tests/verify_simulation.py
```

The script prints results grouped by section and exits with code 1 if any check fails. The expected output on a clean checkout is:

```
85 passed, 0 failed, 7 warnings
```

The warnings are the five window sizes too short for the full panel content and the two world-map data-quality items; none of them is a failure. The suite runs headless and requires no display.

## Appendix D: Glossary

| Term | Meaning in this project |
|---|---|
| Susceptible (S) | Has not encountered the claim |
| Exposed (E) | Has encountered the claim but is not yet convinced. SEIR only |
| Believing (B) | Believes the claim and actively spreads it |
| Skeptical (K) | Has been corrected |
| Durable skeptical | The sub-count of skeptical whose correction is permanent and will never wane |
| Generation time | The interval between one person becoming infectious and the people they infect becoming infectious |
| Renewal equation | The method used to estimate R_t from the incidence curve |
| Incidence | The number of new infections in a single tick |
| Mindshare | The share of the *engaged* population (believers plus skeptics) holding a view |
| Countermeasure | The fact-checking layer: an ambient correction process plus telegraph strikes |
| Crackdown | The escalation phase above 60% belief in which two strikes can be pending at once |

---

*End of report.*
