"""Node4: HATK omnibus test per amino-acid position (likelihood ratio test, binary traits)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from hlagent.io.formats import read_fam
from hlagent.pipeline.contracts import ArtifactRef, NodeResult, StudySpec
from hlagent.stats import plots
from hlagent.tools.omnibus import run_omnibus


def _fam_ordered(table: Path, fam: Path, out: Path, missing: str = "-9") -> Path:
    """The omnibus R script reads phenotype/covariate rows in order (no ID matching): reorder to the fam."""
    f = read_fam(fam)[["FID", "IID"]]
    t = pd.read_csv(table, sep=r"\s+", dtype=str)
    t = t.rename(columns={t.columns[0]: "FID", t.columns[1]: "IID"})
    m = f.merge(t, on=["FID", "IID"], how="left").fillna(missing)
    m.to_csv(out, sep="\t", index=False)
    return out


def run(ctx, study: StudySpec) -> NodeResult:
    p = ctx.params.node4
    d = ctx.require("StageD", study.study_id)
    n1 = ctx.require("Node1", study.study_id)
    sp = ctx.require("StageP", study.study_id)
    out = ctx.step_dir("Node4", study.study_id)
    res = NodeResult(node="Node4", study_id=study.study_id, status="ok", cache_key="")
    if d.metrics.get("pheno_type") != "binary":
        res.status, res.error_kind = "failed", "input_error"
        res.error_message = "The HATK omnibus test supports binary phenotypes only."
        return res
    fam = Path(f"{n1.art('panel')}.fam")
    phe = _fam_ordered(d.art("pheno"), fam, out / "pheno.famorder.tsv")
    covar = (
        _fam_ordered(study.covar_file, fam, out / "covar.famorder.tsv", "NA") if study.covar_file else None
    )
    name = str(d.metrics["pheno_name"])
    runs = [None, p.conditions] if p.conditions else [None]
    tops = []
    for cond in runs:
        om, cmd = run_omnibus(
            fam,
            sp.art("aa"),
            phe,
            name,
            out / "omnibus",
            covar=covar,
            covar_names=study.covar_names or None,
            conditions=cond,
            rscript=ctx.rscript,
        )
        res.commands.append(cmd)
        df = pd.read_csv(om, sep="\t")
        tag = "NA" if not cond else ",".join(cond)
        key = "omnibus" if not cond else "omnibus_conditional"
        res.artifacts[key] = ArtifactRef.of("omnibus", om, description=f"omnibus, conditions={tag}")
        ok = df.dropna(subset=["log10_P"])
        if len(ok):
            best = ok.nsmallest(1, "log10_P").iloc[0]
            tops.append((tag, best["Variant"], float(best["log10_P"])))
            res.metrics[f"top_position[{tag}]"] = best["Variant"]
            res.metrics[f"top_log10_p[{tag}]"] = float(best["log10_P"])
            res.metrics[f"n_positions_tested[{tag}]"] = int(len(ok))
        png = plots.omnibus_plot(
            df,
            out / f"omnibus.{tag.replace(',', '+')}.png",
            f"{study.study_id} omnibus (conditions: {tag})"
            + (" [SYNTHETIC]" if study.synthetic_phenotype else ""),
        )
        res.artifacts[f"plot_{key}"] = ArtifactRef.of("plot", png)
    if study.synthetic_phenotype:
        res.warnings.append("Phenotype is SYNTHETIC: omnibus results are for demonstration only.")
        res.status = "warning"
    return res
