"""Node2: marker-level regression + Manhattan, QQ and HATK heatmaps (v1 Node2)."""

from __future__ import annotations

import contextlib
import io
from pathlib import Path

import numpy as np
import pandas as pd

from hlagent import paths
from hlagent.io.formats import read_assoc
from hlagent.pipeline.contracts import ArtifactRef, NodeResult, StudySpec
from hlagent.stats import plots
from hlagent.tools.plink import AssocParams, run_assoc

HEATMAP_GENES = ("A", "B", "C", "DPA1", "DPB1", "DQA1", "DQB1", "DRB1")


def trait_of(ctx, study_id: str) -> str:
    p = ctx.params.node2
    if p.trait != "auto":
        return p.trait
    t = ctx.require("StageD", study_id).metrics.get("pheno_type")
    return "binary" if t == "binary" else "continuous"


def top_table(a: pd.DataFrame, n: int) -> pd.DataFrame:
    cols = [c for c in ("SNP", "BP", "A1", "OR", "BETA", "SE", "L95", "U95", "P", "NMISS") if c in a.columns]
    t = a.dropna(subset=["P"]).nsmallest(n, "P")[cols].copy()
    t["marker_type"] = t["SNP"].map(plots.marker_type)
    return t


def spike_in_recovery(a: pd.DataFrame, d_metrics: dict, resolution: str) -> dict | None:
    """Positive-control check for a spike-in synthetic phenotype: how the planted allele ranks and
    whether its estimated OR covers the generating OR. Returns None when not applicable."""
    if d_metrics.get("synthetic_mode") != "spike_in":
        return None
    allele = str(d_metrics["synthetic_allele"])
    gene, rest = allele.split("*", 1)
    n_fields = {"1field": 1, "2field": 2, "3field": 3, "4field": 4}.get(resolution)
    fields = rest.split(":")
    if n_fields is None or len(fields) < n_fields:
        return {
            "spike_marker": None,
            "spike_note": f"panel resolution {resolution} cannot represent {allele}",
        }
    marker = f"HLA_{gene}*{':'.join(fields[:n_fields])}"
    row = a[a["SNP"] == marker]
    if row.empty or pd.isna(row["P"].iloc[0]):
        return {"spike_marker": marker, "spike_note": "marker not tested (absent or NA)"}
    r = row.iloc[0]
    tested = a.dropna(subset=["P"])
    true_or = float(d_metrics["synthetic_odds_ratio"])
    out = {
        "spike_marker": marker,
        "spike_true_or": true_or,
        "spike_p": float(r["P"]),
        "spike_rank": int((tested["P"] < r["P"]).sum()) + 1,
        "spike_n_tested": len(tested),
    }
    if "OR" in r and pd.notna(r.get("L95")):
        out.update(
            {
                "spike_or": float(r["OR"]),
                "spike_l95": float(r["L95"]),
                "spike_u95": float(r["U95"]),
                "spike_true_or_in_ci": bool(r["L95"] <= true_or <= r["U95"]),
            }
        )
    return out


def run(ctx, study: StudySpec) -> NodeResult:
    p = ctx.params.node2
    d = ctx.require("StageD", study.study_id)
    n1 = ctx.require("Node1", study.study_id)
    out = ctx.step_dir("Node2", study.study_id)
    res = NodeResult(node="Node2", study_id=study.study_id, status="ok", cache_key="")
    trait = trait_of(ctx, study.study_id)
    params = AssocParams(
        pheno_name=str(d.metrics["pheno_name"]), trait=trait, ci=p.ci, covar_names=study.covar_names
    )
    assoc_path, cmd = run_assoc(
        n1.art("panel"), d.art("pheno"), out / "assoc", params, covar=study.covar_file, plink=ctx.plink
    )
    res.commands.append(cmd)
    a = read_assoc(assoc_path)
    n_total, n_na = len(a), int(a["P"].isna().sum())
    m = n_total - n_na
    bonf = 0.05 / m if m else float("nan")
    res.metrics.update(
        {
            "trait": trait,
            "n_markers_tested": n_total,
            "n_markers_na": n_na,
            "bonferroni_threshold": bonf,
            "n_sig_bonferroni": int((a["P"] < bonf).sum()),
            "n_sig_5e-8": int((a["P"] < 5e-8).sum()),
            "lambda_gc": round(plots.lambda_gc(a["P"]), 4),
        }
    )
    if n_na > 0.2 * n_total:
        res.warnings.append(
            f"{n_na}/{n_total} markers returned NA (monomorphic or perfectly separated); "
            "typical for small samples."
        )
    top = top_table(a, p.top_n)
    top.to_csv(out / "top_markers.tsv", sep="\t", index=False)
    if len(top):
        best = top.iloc[0]
        res.metrics.update(
            {
                "top_marker": best["SNP"],
                "top_p": float(best["P"]),
                "top_effect": float(best["OR"] if "OR" in best else best["BETA"]),
            }
        )
    spike = spike_in_recovery(a, d.metrics, ctx.params.node1.resolution)
    if spike:
        res.metrics.update(spike)
        if spike.get("spike_true_or_in_ci") is False:
            res.warnings.append(
                f"Spike-in check: estimated OR {spike['spike_or']:.3g} "
                f"(95% CI {spike['spike_l95']:.3g}-{spike['spike_u95']:.3g}) does not cover the "
                f"generating OR {spike['spike_true_or']:g}; expected in about 5% of draws."
            )
    res.artifacts["assoc"] = ArtifactRef.of(
        "assoc", assoc_path, build="hg18", description=f"{trait} regression"
    )
    res.artifacts["top_markers"] = ArtifactRef.of("table", out / "top_markers.tsv")
    syn = " [SYNTHETIC]" if study.synthetic_phenotype and "SYNTHETIC" not in params.pheno_name.upper() else ""
    if p.manhattan and m:
        f = plots.manhattan(
            a,
            out / "manhattan.png",
            f"{study.study_id}: {params.pheno_name}{syn}",
            {"Bonferroni": bonf, "5e-8": 5e-8},
        )
        res.artifacts["manhattan"] = ArtifactRef.of("plot", f)
        f = plots.qq(a["P"], out / "qq.png", f"{study.study_id}{syn}")
        res.artifacts["qq"] = ArtifactRef.of("plot", f)
    if p.heatmap and m:
        cache = paths.hatk_cache_dir() / f"hg{ctx.params.node1.hg}_imgt{ctx.params.node1.imgt}"
        genes_in_panel = {s.split("_")[1].split("*")[0] for s in a["SNP"] if s.startswith("HLA_")}
        import sys

        sys.path.insert(0, str(paths.project_root() / "vendor"))
        from hatk_port.Visualizer.heatmapPlot import HeatmapGenerator

        for g in HEATMAP_GENES:
            mt = cache / f"HLA_MAPTABLE_{g}.hg{ctx.params.node1.hg}.imgt{ctx.params.node1.imgt}.txt"
            if g not in genes_in_panel or not mt.exists():
                continue
            try:
                # colour scale follows the data (HATK default is a fixed +-15 that washes out small studies)
                gene_p = a.loc[a["SNP"].str.match(rf"^(?:HLA_{g}\*|AA_{g}_)"), "P"].dropna()
                vmax = float(max(3.0, np.ceil(-np.log10(max(gene_p.min(), 1e-300))))) if len(gene_p) else 3.0
                cfg = {"_data_processing": {"max_pvalue_display": vmax}}
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    png = HeatmapGenerator(
                        str(assoc_path),
                        str(mt),
                        g,
                        str(out / f"heatmap.{g}"),
                        use_plotly=False,
                        save_intermediates=False,
                        config=cfg,
                        verbose=False,
                    ).generate()
                if png and Path(png).exists():
                    res.artifacts[f"heatmap_{g}"] = ArtifactRef.of(
                        "plot", Path(png), description=f"HLA-{g} heatmap"
                    )
            except Exception as e:  # noqa: BLE001 - a figure must not fail the analysis
                res.warnings.append(f"heatmap HLA-{g} skipped: {e}")
    if study.synthetic_phenotype:
        res.warnings.append("Phenotype is SYNTHETIC: associations are for pipeline demonstration only.")
    if res.warnings:
        res.status = "warning"
    if not np.isfinite(bonf):
        res.status, res.error_kind, res.error_message = "failed", "input_error", "no marker could be tested"
    return res
