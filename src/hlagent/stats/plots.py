"""Figures for Node2/3/4/5 (matplotlib, Agg backend)."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.stats import chi2  # noqa: E402

MARKER_COLORS = {
    "rs": "#9aa5b1",
    "SNPS": "#4c78a8",
    "AA": "#e45756",
    "HLA": "#54a24b",
    "INS": "#b279a2",
    "other": "#bab0ac",
}
# hg18 approximate gene starts (Mb) for labels
HLA_GENES_HG18 = {
    "HLA-A": 30.018,
    "HLA-C": 31.344,
    "HLA-B": 31.430,
    "HLA-DRB1": 32.655,
    "HLA-DQA1": 32.717,
    "HLA-DQB1": 32.735,
    "HLA-DPA1": 33.140,
    "HLA-DPB1": 33.151,
}


HLA_GENES_HG18_ORDER = [g.replace("HLA-", "") for g in HLA_GENES_HG18]


def marker_type(snp: str) -> str:
    if snp.startswith("rs"):
        return "rs"
    head = snp.split("_", 1)[0]
    return head if head in MARKER_COLORS else "other"


def manhattan(
    assoc: pd.DataFrame,
    out: Path,
    title: str,
    thresholds: dict[str, float] | None = None,
    p_col: str = "P",
    bp_col: str = "BP",
    snp_col: str = "SNP",
    annotate: int = 1,
) -> Path:
    df = assoc.dropna(subset=[p_col]).copy()
    df = df[df[p_col] > 0]
    df["mlog"] = -np.log10(df[p_col].astype(float))
    df["type"] = df[snp_col].map(marker_type)
    fig, ax = plt.subplots(figsize=(11, 4.2), dpi=150)
    for t, g in df.groupby("type"):
        ax.scatter(
            g[bp_col] / 1e6,
            g["mlog"],
            s=7,
            c=MARKER_COLORS.get(t, "#999"),
            label=f"{t} ({len(g)})",
            alpha=0.85,
            linewidths=0,
        )
    data_max = df["mlog"].max() if len(df) else 1.0
    thr = {k: -np.log10(v) for k, v in (thresholds or {}).items()}
    # always show the least stringent threshold (usually Bonferroni) so "nothing passes" is visible
    shown = {k: v for k, v in thr.items() if v <= max(data_max, min(thr.values(), default=0)) * 1.001}
    ymax = max(data_max, *shown.values(), 1.0) * 1.15
    for name, y in shown.items():
        ax.axhline(y, ls="--", lw=0.8, color="#555")
        ax.text(df[bp_col].min() / 1e6, y, f" {name}", va="bottom", fontsize=7, color="#555")
    for i, (_, r) in enumerate(df.nsmallest(annotate, p_col).iterrows()):
        ax.annotate(
            r[snp_col],
            (r[bp_col] / 1e6, r["mlog"]),
            fontsize=6.5,
            xytext=(6, 2 + 9 * i),
            textcoords="offset points",
            arrowprops={"arrowstyle": "-", "lw": 0.4, "color": "#888"},
        )
    last, level = -1.0, 0
    for g, mb in sorted(HLA_GENES_HG18.items(), key=lambda kv: kv[1]):
        level = level + 1 if mb - last < 0.12 else 0  # stagger labels of neighbouring genes
        last = mb
        ax.axvline(mb, color="#ddd", lw=0.6, zorder=0)
        ax.text(
            mb,
            ymax * (0.99 - 0.07 * level),
            g.replace("HLA-", ""),
            fontsize=6,
            va="top",
            ha="center",
            color="#777",
            backgroundcolor="white",
        )
    ax.set_ylim(0, ymax)
    ax.set_xlabel("chr6 position (Mb, hg18)")
    ax.set_ylabel("-log10(P)")
    ax.set_title(title, fontsize=10)
    ax.legend(fontsize=7, markerscale=1.5, frameon=False, ncol=1, loc="upper left", bbox_to_anchor=(1.0, 1.0))
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)
    return out


def lambda_gc(p: pd.Series) -> float:
    p = p.dropna()
    p = p[(p > 0) & (p <= 1)]
    if p.empty:
        return float("nan")
    return float(np.median(chi2.isf(p, 1)) / chi2.ppf(0.5, 1))


def qq(p: pd.Series, out: Path, title: str) -> Path:
    p = p.dropna()
    p = np.sort(p[(p > 0) & (p <= 1)].to_numpy())
    n = len(p)
    exp = -np.log10((np.arange(1, n + 1) - 0.5) / n)
    fig, ax = plt.subplots(figsize=(4, 4), dpi=150)
    ax.scatter(exp, -np.log10(p), s=6, c="#4c78a8", linewidths=0)
    lim = max(exp.max() if n else 1, (-np.log10(p)).max() if n else 1) * 1.05
    ax.plot([0, lim], [0, lim], color="#999", lw=0.8)
    ax.set_xlabel("expected -log10(P)")
    ax.set_ylabel("observed -log10(P)")
    ax.set_title(f"{title}\nlambda_GC = {lambda_gc(pd.Series(p)):.3f}", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)
    return out


def forest(meta_row: pd.Series, studies: list[str], out: Path) -> Path:
    labels, b, lo, hi = [], [], [], []
    for s in studies:
        be, se = meta_row[f"BETA_{s}"], meta_row[f"SE_{s}"]
        labels.append(s)
        b.append(be)
        lo.append(be - 1.96 * se)
        hi.append(be + 1.96 * se)
    for tag in ("FE", "RE"):
        be, se = meta_row[f"BETA_{tag}"], meta_row[f"SE_{tag}"]
        labels.append(f"Meta ({tag})")
        b.append(be)
        lo.append(be - 1.96 * se)
        hi.append(be + 1.96 * se)
    y = np.arange(len(labels))[::-1]
    fig, ax = plt.subplots(figsize=(5.5, 0.45 * len(labels) + 1.2), dpi=150)
    or_, olo, ohi = np.exp(b), np.exp(lo), np.exp(hi)
    ax.errorbar(or_, y, xerr=[or_ - olo, ohi - or_], fmt="o", color="#333", ecolor="#333", capsize=3)
    for i in range(len(studies), len(labels)):
        ax.plot(or_[i], y[i], "D", color="#e45756")
    ax.axvline(1, color="#999", lw=0.8, ls="--")
    ax.set_xscale("log")
    ax.set_yticks(y, labels)
    ax.set_xlabel("Odds ratio (95% CI)")
    ax.set_title(f"{meta_row['SNP']}  (I2 = {meta_row['I2']:.2f}, P_Q = {meta_row['P_Q']:.2g})", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)
    return out


def omnibus_plot(om: pd.DataFrame, out: Path, title: str) -> Path:
    df = om.dropna(subset=["log10_P"]).copy()
    # AA_DRB1_96 / INS_AA_C_300x301_31345772 -> gene, position (indels plotted at their left position)
    core = df["Variant"].str.replace(r"^INS_", "", regex=True).str.split("_")
    df["gene"] = core.str[1]
    df["pos"] = pd.to_numeric(core.str[2].str.split("x").str[0], errors="coerce")
    genes = [g for g in HLA_GENES_HG18_ORDER if g in set(df["gene"])] + sorted(
        set(df["gene"]) - set(HLA_GENES_HG18_ORDER)
    )
    if not genes:
        genes = ["(none)"]
    fig, axes = plt.subplots(1, len(genes), figsize=(max(6, 1.6 * len(genes)), 3.2), dpi=150, sharey=True)
    axes = np.atleast_1d(axes)
    ymax = (-df["log10_P"]).max() * 1.1 if len(df) else 1
    for ax, g in zip(axes, genes, strict=True):
        d = df[df["gene"] == g]
        ax.scatter(d["pos"], -d["log10_P"], s=8, c="#e45756", linewidths=0)
        top = d.nsmallest(1, "log10_P")
        for _, r in top.iterrows():
            ax.annotate(
                str(int(r["pos"])) if r["pos"] == r["pos"] else "", (r["pos"], -r["log10_P"]), fontsize=7
            )
        ax.set_title(g, fontsize=8)
        ax.set_ylim(0, ymax)
        ax.tick_params(labelsize=6)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("-log10(P), omnibus")
    fig.suptitle(title, fontsize=9)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)
    return out
