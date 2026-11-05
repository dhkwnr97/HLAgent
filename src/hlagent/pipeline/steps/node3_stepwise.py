"""Node3: stepwise conditional regression (plan section 6.2).

Round k conditions on the markers selected in rounds 1..k-1 (PLINK --condition-list) and adds the
most significant remaining marker if P < alpha. alpha = 0.05/M (Bonferroni, M = markers tested in
round 1) by default, or 5e-8.
"""

from __future__ import annotations

import pandas as pd

from hlagent.io.formats import read_assoc
from hlagent.pipeline.contracts import ArtifactRef, NodeResult, StudySpec
from hlagent.pipeline.steps.node2_regression import trait_of
from hlagent.tools.plink import AssocParams, run_assoc


def run(ctx, study: StudySpec) -> NodeResult:
    p = ctx.params.node3
    d = ctx.require("StageD", study.study_id)
    n1 = ctx.require("Node1", study.study_id)
    out = ctx.step_dir("Node3", study.study_id)
    res = NodeResult(node="Node3", study_id=study.study_id, status="ok", cache_key="")
    trait = trait_of(ctx, study.study_id)
    selected: list[str] = []
    rows = []
    alpha = None
    stop_reason = f"reached max_steps={p.max_steps}"
    for k in range(1, p.max_steps + 1):
        cond = None
        if selected:
            cond = out / f"conditions.round{k}.txt"
            cond.write_text("\n".join(selected) + "\n")
        params = AssocParams(
            pheno_name=str(d.metrics["pheno_name"]),
            trait=trait,
            covar_names=study.covar_names,
            condition_list=cond,
        )
        assoc, cmd = run_assoc(
            n1.art("panel"),
            d.art("pheno"),
            out / f"round{k}",
            params,
            covar=study.covar_file,
            plink=ctx.plink,
        )
        res.commands.append(cmd)
        a = read_assoc(assoc)
        a = a[~a["SNP"].isin(selected)].dropna(subset=["P"])
        if alpha is None:
            m = len(a)
            alpha = (
                (0.05 / m if m else 0.0)
                if p.alpha == "bonferroni"
                else (5e-8 if p.alpha == "genome_wide" else float(p.alpha))
            )
            res.metrics.update({"alpha": alpha, "n_markers_round1": m})
        if a.empty:
            stop_reason = "no testable markers left"
            break
        best = a.nsmallest(1, "P").iloc[0]
        effect = float(best["OR"]) if "OR" in a.columns else float(best["BETA"])
        rows.append(
            {
                "round": k,
                "marker": best["SNP"],
                "effect": effect,
                "P": float(best["P"]),
                "conditioned_on": ",".join(selected),
                "significant": bool(best["P"] < alpha),
            }
        )
        if best["P"] >= alpha:
            stop_reason = f"round {k}: best P={best['P']:.3g} >= alpha={alpha:.3g}"
            break
        selected.append(str(best["SNP"]))
    tab = pd.DataFrame(rows)
    tab.to_csv(out / "conditional_steps.tsv", sep="\t", index=False)
    res.artifacts["steps"] = ArtifactRef.of(
        "table", out / "conditional_steps.tsv", description="stepwise conditional analysis"
    )
    res.metrics.update(
        {"n_independent_signals": len(selected), "selected": ",".join(selected), "stop_reason": stop_reason}
    )
    if study.synthetic_phenotype:
        res.warnings.append("Phenotype is SYNTHETIC: conditional signals are for demonstration only.")
        res.status = "warning"
    return res
