"""
Academic Report Figure Exporter for TU BCA 8th Semester Final Project

Generates publication-quality PNG figures and CSV telemetry exports from
simulation telemetry history for inclusion in academic defense presentations
and written reports.

Output:
- SEIR_trajectories.png: S-E-I-R compartmental model time series
- Rt_tracking.png: Effective reproduction number evolution
- telemetry_data.csv: Raw simulation data for further analysis
- simulation_summary.txt: Formatted summary statistics

Academic Standards:
All figures follow IFCN (International Fact-Checking Network) research
standards and WHO epidemic modeling guidelines for mathematical rigor
and visual clarity.
"""

import json
from pathlib import Path
from datetime import datetime

# Imported rather than hardcoded so the report states the threshold the engine
# actually evaluates. Hardcoding it here is how the in-game help text ended up
# advertising a 95% win line that no version of the rules ever used.
from model.world_graph import LOSS_MINDSHARE


def _unique_run_name(output_path: Path, strain_name: str,
                     model_name: str) -> str:
    """A run name that no export already in `output_path` is using.

    The timestamp alone has second granularity, and the documented way to
    export is to press `E` -- twice in quick succession is entirely normal, so
    two exports inside the same second used to collide and the second silently
    overwrote the first dataset. Measured: three files after two exports, where
    six were expected.

    The suffix is only added when the plain name is already taken, so the
    ordinary case still reads as `Unverified_Rumor_SIR_20260929_143012`.
    """
    base = (f"{strain_name.replace(' ', '_')}_{model_name}_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    name = base
    suffix = 2
    while any(output_path.glob(f"{name}_*")):
        name = f"{base}_{suffix}"
        suffix += 1
    return name


def export_academic_report(telemetry_history: list[dict],
                          strain_name: str,
                          model_name: str,
                          output_dir: str = "report_exports",
                          with_figures: bool = True) -> dict:
    """
    Export complete academic report package from telemetry history.

    Args:
        telemetry_history: List of tick-by-tick simulation snapshots
        strain_name: Name of the misinformation strain simulated
        model_name: Epidemic model used (SIR or SEIR)
        output_dir: Directory to save exports (created if missing)
        with_figures: Also render the PNG figures, sharing this export's run
            name so the figures and the CSV they were plotted from are
            obviously a matching pair. Degrades to "no figures" if matplotlib
            is not installed -- the CSV/JSON/summary export is unaffected, and
            the reason is reported in `figures_error`.

    Returns:
        dict with paths to generated files and export summary
    """
    if not telemetry_history:
        return {"success": False, "message": "No telemetry data to export"}

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    run_name = _unique_run_name(output_path, strain_name, model_name)

    result = {
        "success": True,
        "run_name": run_name,
        "output_dir": str(output_path.absolute()),
        "files": {},
        "summary": {}
    }

    # Export CSV telemetry
    csv_path = output_path / f"{run_name}_telemetry.csv"
    _export_csv(telemetry_history, csv_path)
    result["files"]["csv"] = str(csv_path.absolute())

    # Export summary statistics
    summary_path = output_path / f"{run_name}_summary.txt"
    summary_stats = _export_summary(telemetry_history, strain_name, model_name, summary_path)
    result["files"]["summary"] = str(summary_path.absolute())
    result["summary"] = summary_stats

    # Export JSON (for programmatic access)
    json_path = output_path / f"{run_name}_telemetry.json"
    _export_json(telemetry_history, strain_name, model_name, json_path)
    result["files"]["json"] = str(json_path.absolute())

    # Figures last, reusing this export's run name so the plots and the CSV
    # they were drawn from share a prefix and are obviously one dataset.
    if with_figures:
        figures = generate_matplotlib_figures(
            telemetry_history, strain_name, model_name,
            output_dir=output_dir, run_name=run_name)
        if figures.get("success"):
            result["files"].update(figures["figures"])
        else:
            result["figures_error"] = figures.get("message")

    return result


def _export_csv(history: list[dict], output_path: Path) -> None:
    """Export telemetry as CSV for spreadsheet analysis."""
    with open(output_path, "w", encoding="utf-8") as f:
        # Header
        f.write("tick,susceptible,exposed,believing,skeptical,population,incidence,"
                "r_t,counter_active,corrected_mindshare\n")

        # Data rows. r_t is written as an empty cell when the estimator has too
        # little history for a meaningful value, rather than as 0, so the
        # column cannot be misread as "R_t was zero here".
        #
        # corrected_mindshare rides along because it is the quantity the LOSS
        # CONDITION is evaluated against (K/(K+B), see
        # WorldGraph.is_world_corrected). Without it in the export the defining
        # variable of the run is missing from the data, and an analyst is left
        # dividing skeptical by population -- which is a different number and
        # not the one that ended the game. Read with .get so a history built by
        # hand elsewhere cannot crash the export.
        for h in history:
            r_t = "" if h["r_t"] is None else h["r_t"]
            mindshare = h.get("corrected_mindshare", "")
            f.write(f"{h['tick']},{h['susceptible']},{h['exposed']},{h['believing']},"
                   f"{h['skeptical']},{h['population']},{h['incidence']},{r_t},"
                   f"{int(h['counter_active'])},{mindshare}\n")


def _export_json(history: list[dict], strain_name: str, model_name: str, output_path: Path) -> None:
    """Export full telemetry with metadata as JSON."""
    export_data = {
        "metadata": {
            "strain_name": strain_name,
            "model": model_name,
            "export_timestamp": datetime.now().isoformat(),
            "total_ticks": len(history),
        },
        "telemetry": history
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2)


def _export_summary(history: list[dict], strain_name: str, model_name: str, output_path: Path) -> dict:
    """Generate formatted summary statistics for academic writeup."""
    if not history:
        return {}

    final_state = history[-1]
    peak_believing = max(h["believing"] for h in history)
    peak_believing_tick = next(h["tick"] for h in history if h["believing"] == peak_believing)

    # R_t is None on ticks where the estimator had too little history to
    # produce a meaningful value, so every statistic below is computed over the
    # defined entries only. Treating None as 0 would drag the averages and the
    # reported reduction toward zero.
    rt_series = [(h["tick"], h["r_t"]) for h in history if h["r_t"] is not None]

    if rt_series:
        peak_rt_tick, peak_rt = max(rt_series, key=lambda pair: pair[1])
    else:
        peak_rt = peak_rt_tick = None

    final_rt = final_state["r_t"]

    countermeasure_activation = next((h["tick"] for h in history if h["counter_active"]), None)

    # Calculate average R_t before and after countermeasure
    if countermeasure_activation:
        pre_counter_rt = [rt for tick, rt in rt_series if tick < countermeasure_activation]
        post_counter_rt = [rt for tick, rt in rt_series if tick >= countermeasure_activation]
        avg_rt_pre = sum(pre_counter_rt) / len(pre_counter_rt) if pre_counter_rt else None
        avg_rt_post = sum(post_counter_rt) / len(post_counter_rt) if post_counter_rt else None
    else:
        all_rt = [rt for _, rt in rt_series]
        avg_rt_pre = sum(all_rt) / len(all_rt) if all_rt else None
        avg_rt_post = None

    summary = {
        "total_ticks": final_state["tick"],
        "peak_believing": peak_believing,
        "peak_believing_tick": peak_believing_tick,
        "peak_rt": round(peak_rt, 3) if peak_rt is not None else None,
        "peak_rt_tick": peak_rt_tick,
        "final_rt": round(final_rt, 3) if final_rt is not None else None,
        "countermeasure_activation_tick": countermeasure_activation,
        "avg_rt_pre_countermeasure": round(avg_rt_pre, 3) if avg_rt_pre is not None else None,
        "avg_rt_post_countermeasure": round(avg_rt_post, 3) if avg_rt_post is not None else None,
        "final_believing": final_state["believing"],
        "final_skeptical": final_state["skeptical"],
        "final_susceptible": final_state["susceptible"],
        # The quantity the loss condition is evaluated against, so the report
        # states the number that actually decided the run rather than only the
        # raw compartment counts it is computed from.
        "final_corrected_mindshare": final_state.get("corrected_mindshare"),
    }

    # Write formatted summary
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"EPIDEMIC SIMULATION SUMMARY REPORT\n")
        f.write(f"{'=' * 60}\n\n")
        f.write(f"Strain: {strain_name}\n")
        f.write(f"Model: {model_name}\n")
        f.write(f"Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        f.write(f"SIMULATION DURATION\n")
        f.write(f"{'-' * 60}\n")
        f.write(f"Total Ticks: {summary['total_ticks']}\n\n")

        f.write(f"EPIDEMIC PEAK METRICS\n")
        f.write(f"{'-' * 60}\n")
        f.write(f"Peak Believers: {summary['peak_believing']:,} (Tick {summary['peak_believing_tick']})\n")
        if summary['peak_rt'] is not None:
            f.write(f"Peak R_t: {summary['peak_rt']} (Tick {summary['peak_rt_tick']})\n\n")
        else:
            f.write(f"Peak R_t: not estimated (run too short)\n\n")

        f.write(f"EFFECTIVE REPRODUCTION NUMBER (R_t) ANALYSIS\n")
        f.write(f"{'-' * 60}\n")
        f.write(f"Final R_t: {summary['final_rt'] if summary['final_rt'] is not None else 'not estimated'}\n")
        if countermeasure_activation:
            f.write(f"Countermeasure Activated: Tick {countermeasure_activation}\n")
            f.write(f"Average R_t (Pre-Countermeasure): {summary['avg_rt_pre_countermeasure']}\n")
            f.write(f"Average R_t (Post-Countermeasure): {summary['avg_rt_post_countermeasure']}\n")
            if summary['avg_rt_pre_countermeasure'] and summary['avg_rt_post_countermeasure'] is not None:
                rt_reduction = summary['avg_rt_pre_countermeasure'] - summary['avg_rt_post_countermeasure']
                rt_reduction_pct = (rt_reduction / summary['avg_rt_pre_countermeasure']) * 100
                f.write(f"R_t Reduction: {rt_reduction:.3f} ({rt_reduction_pct:.1f}%)\n")
                f.write(f"Below threshold after activation: "
                        f"{'yes' if summary['avg_rt_post_countermeasure'] < 1.0 else 'no'}\n")
            else:
                f.write(f"R_t Reduction: not estimable (insufficient R_t history)\n")
        else:
            f.write(f"Countermeasure: Never Activated\n")
            f.write(f"Average R_t: {summary['avg_rt_pre_countermeasure']}\n")
        f.write(f"\nEpidemic Threshold: R_t = 1.0\n")
        final_rt = summary['final_rt']
        verdict = "indeterminate" if final_rt is None else ("GROWTH" if final_rt > 1.0 else "DECAY")
        f.write(f"Final State: {verdict}\n\n")

        f.write(f"FINAL COMPARTMENTAL DISTRIBUTION\n")
        f.write(f"{'-' * 60}\n")
        total_pop = final_state["population"]
        f.write(f"Susceptible: {summary['final_susceptible']:,} ({summary['final_susceptible']/total_pop*100:.1f}%)\n")
        f.write(f"Believing: {summary['final_believing']:,} ({summary['final_believing']/total_pop*100:.1f}%)\n")
        f.write(f"Skeptical: {summary['final_skeptical']:,} ({summary['final_skeptical']/total_pop*100:.1f}%)\n")
        # Reported separately from the population shares above because the
        # loss condition is a MINDSHARE, not a share of total population: the
        # fact-checkers win once they hold LOSS_MINDSHARE of everyone who has
        # an opinion, which is why this number can differ sharply from the
        # Skeptical percentage on the line above it.
        final_mindshare = summary.get("final_corrected_mindshare")
        if final_mindshare is not None:
            f.write(f"Corrected mindshare K/(K+B): {final_mindshare*100:.1f}% "
                    f"(loss condition: {LOSS_MINDSHARE*100:.0f}%)\n\n")
        else:
            f.write("\n")

        f.write(f"RESEARCH FOUNDATIONS\n")
        f.write(f"{'-' * 60}\n")
        f.write(f"This simulation implements a {model_name} compartmental epidemic model\n")
        f.write(f"adapted for misinformation spread dynamics, grounded in:\n\n")
        f.write(f"1. Porter et al. (2021) - Global fact-checking effectiveness (PNAS)\n")
        f.write(f"2. Guess et al. (2023) - Correction persistence in 10 countries\n")
        f.write(f"3. Nyhan (2021) - Durability of political misperceptions (PNAS)\n")
        f.write(f"4. Bode & Vraga (2015) - Social media correction mechanisms\n")
        f.write(f"5. Cori et al. (2013) - Time-varying reproduction numbers (Am. J. Epidemiol.)\n\n")
        f.write(f"R_t is ESTIMATED from the incidence curve using the renewal equation:\n")
        f.write(f"  R_t = inc(t) / sum_s w(s) * inc(t - s)\n")
        f.write(f"where inc(t) = new infections at tick t and w(s) is the generation-time\n")
        f.write(f"distribution of the active spread model -- a point mass at lag 1 for SIR\n")
        f.write(f"(where S -> B takes one tick) and geometric with rate incubation_rate for\n")
        f.write(f"SEIR (which inserts a latency stage).\n\n")
        f.write(f"It is not derived from beta/gamma, because that analytic form requires a\n")
        f.write(f"single constant removal rate and this model has none: the countermeasure is\n")
        f.write(f"the only process that removes anyone from Believing, so before it activates\n")
        f.write(f"the removal rate is exactly zero and the ratio is undefined. Once active,\n")
        f.write(f"the rate is time-varying and region-dependent, and spread across the region\n")
        f.write(f"graph is a metapopulation process with no scalar threshold. Estimating R_t\n")
        f.write(f"from the realised incidence curve is the standard approach in real-time\n")
        f.write(f"epidemic analytics and remains valid under all of the above.\n\n")

    return summary


def generate_matplotlib_figures(telemetry_history: list[dict],
                                strain_name: str,
                                model_name: str,
                                output_dir: str = "report_exports",
                                run_name: str | None = None) -> dict:
    """
    Generate high-resolution PNG figures using matplotlib (if available).
    Falls back to basic export if matplotlib is not installed.

    `run_name` is normally supplied by export_academic_report() so the figures
    and the CSV they were plotted from share a prefix. Called on its own it
    derives its own unique name, so two standalone calls cannot collide.

    Returns dict with figure paths or installation instructions.
    """
    try:
        import matplotlib
        matplotlib.use('Agg')  # Non-interactive backend
        import matplotlib.pyplot as plt
    except ImportError:
        return {
            "success": False,
            "message": "matplotlib not installed. Install with: pip install matplotlib",
            "fallback": "Use CSV export for manual graphing in Excel/Google Sheets"
        }

    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    if run_name is None:
        run_name = _unique_run_name(output_path, strain_name, model_name)

    result = {"success": True, "figures": {}}

    # Extract time series
    ticks = [h["tick"] for h in telemetry_history]
    susceptible = [h["susceptible"] for h in telemetry_history]
    exposed = [h["exposed"] for h in telemetry_history]
    believing = [h["believing"] for h in telemetry_history]
    skeptical = [h["skeptical"] for h in telemetry_history]
    # R_t is None on ticks where the estimator lacked the history to produce a
    # meaningful value, so only the defined points are plotted rather than
    # letting a None become a zero on the axis.
    rt_points = [(h["tick"], h["r_t"]) for h in telemetry_history if h["r_t"] is not None]

    # Figure 1: SEIR Trajectories
    fig1, ax1 = plt.subplots(figsize=(12, 7), dpi=300)
    ax1.plot(ticks, susceptible, 'b-', linewidth=2, label='S - Susceptible')
    if any(e > 0 for e in exposed):
        ax1.plot(ticks, exposed, 'm-', linewidth=2, label='E - Exposed')
    ax1.plot(ticks, believing, 'r-', linewidth=2, label='I - Believing')
    ax1.plot(ticks, skeptical, 'g-', linewidth=2, label='R - Skeptical')

    ax1.set_xlabel('Simulation Tick', fontsize=12)
    ax1.set_ylabel('Population', fontsize=12)
    ax1.set_title(f'{model_name} Compartmental Model Trajectories - {strain_name}', fontsize=14, fontweight='bold')
    ax1.legend(loc='best', fontsize=10)
    ax1.grid(True, alpha=0.3)

    fig1_path = output_path / f"{run_name}_SEIR_trajectories.png"
    fig1.savefig(fig1_path, bbox_inches='tight', dpi=300)
    plt.close(fig1)
    result["figures"]["seir"] = str(fig1_path.absolute())

    # Figure 2: R_t Tracking
    fig2, ax2 = plt.subplots(figsize=(12, 7), dpi=300)
    if rt_points:
        ax2.plot([p[0] for p in rt_points], [p[1] for p in rt_points], 'c-', linewidth=3,
                 label='R_t (Effective Reproduction Number, renewal estimate)')
    ax2.axhline(y=1.0, color='orange', linestyle='--', linewidth=2, label='Epidemic Threshold (R_t = 1.0)')
    ax2.set_ylim(bottom=0, top=max(3.0, max((p[1] for p in rt_points), default=0.0)) * 1.05)

    # Shade regions
    countermeasure_tick = next((h["tick"] for h in telemetry_history if h["counter_active"]), None)
    if countermeasure_tick:
        ax2.axvspan(0, countermeasure_tick, alpha=0.1, color='red', label='Pre-Countermeasure')
        ax2.axvspan(countermeasure_tick, max(ticks), alpha=0.1, color='green', label='Active Response')

    ax2.set_xlabel('Simulation Tick', fontsize=12)
    ax2.set_ylabel('R_t Value', fontsize=12)
    ax2.set_title(f'Effective Reproduction Number (R_t) Evolution - {strain_name}', fontsize=14, fontweight='bold')
    ax2.legend(loc='best', fontsize=10)
    ax2.grid(True, alpha=0.3)

    fig2_path = output_path / f"{run_name}_Rt_tracking.png"
    fig2.savefig(fig2_path, bbox_inches='tight', dpi=300)
    plt.close(fig2)
    result["figures"]["rt"] = str(fig2_path.absolute())

    return result
