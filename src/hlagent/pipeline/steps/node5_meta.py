"""Node5: meta-analysis across studies (IVW fixed effect, Cochran Q, I^2, DerSimonian-Laird)."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from hlagent.io.formats import read_fam
from hlagent.pipeline.contracts import ArtifactRef, NodeResult
from hlagent.stats import plots
from hlagent.stats.meta import StudyInput, meta_analyze


def run(ctx, _study=None) -> NodeResult:
    p = ctx.params.node5
    out = ctx.step_dir("Node5", None)
    res = NodeResult(node="Node5", study_id=None, status="ok", cache_key="")
    inputs: list[StudyInput] = []
    phenos: dict[str, str] = {}
    sample_sets: dict[str, set[str]] = {}
    for s in ctx.plan.studies:
        if s.external_assoc is not None:
            inputs.append(StudyInput(s.study_id, s.external_assoc, s.external_bim))
            phenos[s.study_id] = s.pheno_name or "external"
            continue
        n2 = ctx.require("Node2", s.study_id)
        n1 = ctx.require("Node1", s.study_id)
        d = ctx.require("StageD", s.study_id)
        inputs.append(StudyInput(s.study_id, n2.art("assoc"), Path(f"{n1.art('panel')}.bim")))
        phenos[s.study_id] = str(d.metrics.get("pheno_name"))
        fam = read_fam(Path(f"{n1.art('panel')}.fam"))
        sample_sets[s.study_id] = set(fam["FID"] + "\t" + fam["IID"])
    table, rep = meta_analyze(inputs, drop_ambiguous_snps=p.drop_ambiguous_snps)
    meta_path = out / "meta.tsv"
    table.to_csv(meta_path, sep="\t", index=False)
    (out / "harmonization.json").write_text(json.dumps(asdict(rep), indent=1))
    res.artifacts["meta"] = ArtifactRef.of(
        "meta", meta_path, build="hg18", description="meta-analysis per marker"
    )
    names = [x.name for x in inputs]
    k = len(inputs)
    top = table.nsmallest(p.top_n, "P_FE")
    top.to_csv(out / "top_meta.tsv", sep="\t", index=False)
    res.artifacts["top_meta"] = ArtifactRef.of("table", out / "top_meta.tsv")
    res.metrics.update(
        {
            "k_studies": k,
            "n_common": rep.n_common,
            "n_analyzed": rep.n_analyzed,
            "n_flipped": sum(rep.n_flipped.values()),
            "n_dropped_missing": rep.n_dropped_missing,
            "n_dropped_mismatch": rep.n_dropped_mismatch,
            "n_ambiguous_kept": rep.n_ambiguous_kept,
            "bonferroni_threshold": 0.05 / rep.n_analyzed if rep.n_analyzed else None,
            "n_sig_fe_bonferroni": int((table["P_FE"] < 0.05 / max(rep.n_analyzed, 1)).sum()),
            "n_I2_gt_0.5": int((table["I2"] > 0.5).sum()),
        }
    )
    if len(top):
        b = top.iloc[0]
        res.metrics.update(
            {
                "top_marker": b["SNP"],
                "top_p_fe": float(b["P_FE"]),
                "top_p_re": float(b["P_RE"]),
                "top_or_fe": float(b["OR_FE"]),
                "top_i2": float(b["I2"]),
            }
        )
        for _, r in top.head(3).iterrows():
            f = plots.forest(
                r, names, out / f"forest.{str(r['SNP']).replace('*', '_').replace(':', '-')}.png"
            )
            res.artifacts[f"forest_{r['SNP']}"] = ArtifactRef.of("plot", f)
    if table["BP"].notna().any():
        f = plots.manhattan(
            table.rename(columns={"P_FE": "P"}),
            out / "meta_manhattan.png",
            f"Meta-analysis (FE), k={k}",
            {"Bonferroni": 0.05 / max(rep.n_analyzed, 1)},
        )
        res.artifacts["manhattan"] = ArtifactRef.of("plot", f)
    if k == 2:
        res.warnings.append("k=2 studies: Cochran Q has 1 df (low power); I^2 and tau^2 are very imprecise.")
    if len(set(phenos.values())) > 1 or any(s.synthetic_phenotype for s in ctx.plan.studies):
        res.warnings.append(
            "Cross-phenotype meta-analysis ("
            + ", ".join(f"{k}:{v}" for k, v in phenos.items())
            + "): the fixed-effect "
            "P tests a shared effect; opposite directions cancel. Read per-study effects and Q/I^2 together."
        )
    overlap = []
    ids = list(sample_sets)
    for a in range(len(ids)):
        for b in range(a + 1, len(ids)):
            n = len(sample_sets[ids[a]] & sample_sets[ids[b]])
            if n:
                overlap.append(f"{ids[a]}/{ids[b]}: {n}")
    if overlap:
        res.warnings.append(
            "Sample overlap between studies (" + "; ".join(overlap) + "): P values are anti-conservative."
        )
    if any(s.synthetic_phenotype for s in ctx.plan.studies):
        res.warnings.append(
            "At least one study uses a SYNTHETIC phenotype: meta-analysis is a pipeline demonstration."
        )
    if res.warnings:
        res.status = "warning"
    return res
