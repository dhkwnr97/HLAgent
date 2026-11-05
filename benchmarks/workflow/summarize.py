"""Summarise the workflow benchmark (timings over replicates) and draw the benchmark figure.

Reads results/<scenario>.rep<n>.json (run_benchmark.py), concordance.json (concordance.py) and
effort.json (conventional.py); writes timing_summary.json, timing_summary.md and
figure_benchmark.{png,pdf} (300 dpi).

    python benchmarks/workflow/summarize.py --results benchmarks/workflow/results
"""

from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from hlagent import paths

SCENARIOS = {
    "B1_WTCCC_RA_Node1-5": "B1  WTCCC RA: Node1-5 + meta",
    "B2_WTCCC_RA_Node4_cond_DRB1_96": "B2  WTCCC RA: conditional omnibus",
    "B3_GenotypeExample_CookHLA_Node1-2": "B3  SNP-only (hg19): CookHLA + Node1-2",
    "B4_BMExample_Node1-4": "B4  BMExample (unknown build, family): Node1-4",
}
# step groups for the figure (7 categories; validated categorical palette, fixed order)
GROUPS = [
    ("Stage D + R (QC, report)", ("StageD", "StageR"), "#2a78d6"),
    ("Stage I (CookHLA)", ("StageI",), "#eb6834"),
    ("Node1 (marker panel)", ("Node1",), "#1baf7a"),
    ("Node2-3 (regression)", ("Node2", "Node3"), "#eda100"),
    ("Stage P (BEAGLE phasing)", ("StageP",), "#e87ba4"),
    ("Node4 (omnibus)", ("Node4",), "#008300"),
    ("Node5 (meta-analysis)", ("Node5",), "#6250d6"),
]
STEP_ORDER = ["StageD", "StageI", "Node1", "Node2", "Node3", "StageP", "Node4", "Node5", "StageR"]
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def _ts(s: str) -> float:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def exclusive_tool_seconds(rep: dict) -> dict[str, float]:
    """Attribute each external command once: to the step whose window contains the command start."""
    ledger_f = Path(rep["run_dir"]) / "logs" / "commands.jsonl"
    cmds = (
        [json.loads(x) for x in ledger_f.read_text().splitlines() if x.strip()] if ledger_f.exists() else []
    )
    wins = [
        (s["step"], _ts(s["started_at"]), _ts(s["finished_at"])) for s in rep["steps"] if s["finished_at"]
    ]
    out: dict[str, float] = {}
    for c in cmds:
        start = c["ts"] - c["seconds"]
        inside = [w for w in wins if w[1] - 0.05 <= start <= w[2] + 0.05]
        step = (
            min(inside, key=lambda w: abs(start - w[1]))[0]
            if inside
            else min(wins, key=lambda w: abs(start - w[1]))[0]
        )
        out[step] = out.get(step, 0.0) + c["seconds"]
    return out


def summarise(results: Path) -> dict:
    summary: dict = {}
    for sc in SCENARIOS:
        reps = [json.loads(f.read_text()) for f in sorted(results.glob(f"{sc}.rep*.json"))]
        reps = [r for r in reps if r.get("state") == "done"]
        if not reps:
            continue
        per_step: dict[str, list[float]] = {}
        tool: dict[str, list[float]] = {}
        for r in reps:
            secs: dict[str, float] = {}
            for s in r["steps"]:
                secs[s["step"]] = secs.get(s["step"], 0.0) + (s["seconds"] or 0.0)
            for k, v in secs.items():
                per_step.setdefault(k, []).append(v)
            t = exclusive_tool_seconds(r)
            for k in secs:
                tool.setdefault(k, []).append(t.get(k, 0.0))
        totals = [r["total_seconds"] for r in reps]
        step_sum = [sum(s["seconds"] or 0.0 for s in r["steps"]) for r in reps]

        def stats(v: list[float]) -> dict:
            return {
                "n": len(v),
                "mean": statistics.fmean(v),
                "sd": statistics.stdev(v) if len(v) > 1 else 0.0,
                "min": min(v),
                "max": max(v),
            }

        summary[sc] = {
            "label": SCENARIOS[sc],
            "n_reps": len(reps),
            "total": stats(totals),
            "engine_gaps": stats([t - s for t, s in zip(totals, step_sum, strict=True)]),
            "steps": {
                k: {**stats(per_step[k]), "tool_mean": statistics.fmean(tool[k])}
                for k in STEP_ORDER
                if k in per_step
            },
        }
    return summary


def write_markdown(summary: dict, path: Path) -> None:
    lines = [
        "| Scenario | Step | Wall-clock, s (mean ± SD, n) | Range, s | External tools, s (mean) |",
        "|---|---|---|---|---|",
    ]
    for s in summary.values():
        for k, v in s["steps"].items():
            lines.append(
                f"| {s['label']} | {k} | {v['mean']:.1f} ± {v['sd']:.1f} ({v['n']}) | {v['min']:.1f}-{v['max']:.1f} "
                f"| {v['tool_mean']:.1f} |"
            )
        t = s["total"]
        lines.append(
            f"| {s['label']} | **Total** | **{t['mean']:.1f} ± {t['sd']:.1f}** ({t['n']}) | {t['min']:.1f}-{t['max']:.1f} | |"
        )
    path.write_text("\n".join(lines) + "\n")


def figure(summary: dict, results: Path, out: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from scipy import stats

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 7.5,
            "axes.edgecolor": MUTED,
            "axes.labelcolor": INK,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "axes.linewidth": 0.6,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    fig = plt.figure(figsize=(7.2, 6.4))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 1.1], hspace=0.55, wspace=0.32)

    # (a) where the time goes
    ax = fig.add_subplot(gs[0, :])
    names = [sc for sc in SCENARIOS if sc in summary]
    y = np.arange(len(names))[::-1]
    for label, members, color in GROUPS:
        left = np.zeros(len(names))
        for i, sc in enumerate(names):
            steps = summary[sc]["steps"]
            # cumulative left edge: all earlier groups
            prev = [m for g in GROUPS[: [g[0] for g in GROUPS].index(label)] for m in g[1]]
            left[i] = sum(steps[m]["mean"] for m in prev if m in steps)
        widths = [
            sum(summary[sc]["steps"][m]["mean"] for m in members if m in summary[sc]["steps"]) for sc in names
        ]
        ax.barh(
            y, widths, left=left, height=0.5, color=color, edgecolor="#fcfcfb", linewidth=1.0, label=label
        )
    for i, sc in enumerate(names):
        t = summary[sc]["total"]
        ax.text(t["mean"] + 4, y[i], f"{t['mean']:.0f} ± {t['sd']:.0f} s", va="center", color=INK, fontsize=7)
    ax.set_yticks(y, [summary[sc]["label"] for sc in names])
    ax.set_xlabel("Wall-clock time per run, s (mean of 3 runs; label: total mean ± SD)")
    ax.xaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.set_xlim(0, max(summary[sc]["total"]["mean"] for sc in names) * 1.18)
    ax.legend(ncol=4, frameon=False, fontsize=6.5, loc="upper center", bbox_to_anchor=(0.45, -0.22))
    ax.set_title(
        "a  Where the time goes (4 vCPU, 16 GB RAM; fresh run directory, no cache)", loc="left", fontsize=8
    )

    # (b) Node2 vs published HATK
    ax = fig.add_subplot(gs[1, 0])
    t = pd.read_csv(results / "B1.node2_vs_published.tsv", sep="\t")
    ax.scatter(-np.log10(t["P_pub"]), -np.log10(t["P_hla"]), s=5, color="#2a78d6", alpha=0.6, linewidths=0)
    lim = max((-np.log10(t["P_pub"])).max(), (-np.log10(t["P_hla"])).max()) * 1.05
    ax.plot([0, lim], [0, lim], color=MUTED, linewidth=0.7, zorder=0)
    ax.set_xlim(0, lim)
    ax.set_ylim(0, lim)
    ax.set_xlabel("−log10 P, published HATK result")
    ax.set_ylabel("−log10 P, HLAgent v3 (Node2)")
    conc = json.loads((results / "concordance.json").read_text())["node2_regression"]
    ax.text(
        0.04,
        0.96,
        f"{conc['n_shared_tested']:,} markers\nOR, SE, P identical: {conc['P_identical_fraction'] * 100:.0f}%",
        transform=ax.transAxes,
        va="top",
        color=INK,
        fontsize=7,
    )
    ax.set_title("b  Logistic regression vs HATK (WTCCC RA)", loc="left", fontsize=8)

    # (c) omnibus vs published, unconditioned (B1) and conditioned on AA_DRB1_96 (B2)
    ax = fig.add_subplot(gs[1, 1])
    ex = paths.examples_dir() / "hatk_wtccc" / "OmnibusTest"
    series = [
        ("No condition (B1)", "B1_WTCCC_RA_Node1-5", "NA", "#2a78d6", "o"),
        ("Conditioned on DRB1 96 (B2)", "B2_WTCCC_RA_Node4_cond_DRB1_96", "AA_DRB1_96", "#1baf7a", "^"),
    ]
    lim = 0.0
    for label, sc, cond, color, marker in series:
        rep = results / f"{sc}.rep1.json"
        if not rep.exists():
            continue
        rd = Path(json.loads(rep.read_text())["run_dir"])
        pub = pd.read_csv(ex / f"wtccc_filtered_58C_RA.hatk.300+300.chr6.hg18.RA.{cond}.omnibus", sep="\t")
        ours = pd.read_csv(rd / "WTCCC_RA" / "node4" / f"omnibus.RA.{cond}.omnibus", sep="\t")
        m = pub.merge(ours, on="Variant", suffixes=("_pub", "_hla")).dropna(
            subset=["log10_P_pub", "log10_P_hla"]
        )
        rho = stats.spearmanr(m["log10_P_pub"], m["log10_P_hla"]).statistic
        ax.scatter(
            -m["log10_P_pub"],
            -m["log10_P_hla"],
            s=14,
            color=color,
            marker=marker,
            alpha=0.75,
            edgecolors="#fcfcfb",
            linewidths=0.4,
            label=f"{label}: {rho:.3f}",
        )
        top = m.loc[m["log10_P_hla"].idxmin()]
        if cond != "NA":  # near-null after conditioning: the top label carries no information
            lim = max(lim, -m["log10_P_pub"].min(), -m["log10_P_hla"].min())
            continue
        ax.annotate(
            top["Variant"],
            (-top["log10_P_pub"], -top["log10_P_hla"]),
            xytext=(-58, -3),
            textcoords="offset points",
            fontsize=6.5,
            color=INK,
        )
        lim = max(lim, -m["log10_P_pub"].min(), -m["log10_P_hla"].min())
    lim *= 1.08
    ax.plot([0, lim], [0, lim], color=MUTED, linewidth=0.7, zorder=0)
    ax.set_xlim(0, lim)
    ax.set_ylim(0, lim)
    ax.set_xlabel("−log10 P, published HATK omnibus")
    ax.set_ylabel("−log10 P, HLAgent v3 (Node4)")
    ax.legend(
        frameon=False, fontsize=6.5, loc="lower right", title="Spearman ρ vs published", title_fontsize=6.5
    )
    ax.set_title("c  Amino-acid omnibus test vs HATK", loc="left", fontsize=8)

    fig.savefig(out.with_suffix(".png"), dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(out.with_suffix(".pdf"), bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", type=Path, required=True)
    a = ap.parse_args()
    s = summarise(a.results)
    (a.results / "timing_summary.json").write_text(json.dumps(s, indent=1))
    write_markdown(s, a.results / "timing_summary.md")
    figure(s, a.results, a.results / "figure_benchmark")
    print((a.results / "timing_summary.md").read_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
