"""Deterministic facts sheet: every number the report (and the LLM narrative) may cite."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from hlagent.pipeline.contracts import STEP_TITLES, NodeResult

CITATIONS = {
    "CookHLA": "Cook S, et al. Accurate imputation of human leukocyte antigens with CookHLA. Nat Commun 2021;12:1264.",
    "HATK": "Choi W, Luo Y, Raychaudhuri S, Han B. HATK: HLA analysis toolkit. Bioinformatics 2021;37:416-418.",
    "BEAGLE3": "Browning SR, Browning BL. Am J Hum Genet 2007;81:1084-1097 (BEAGLE 3).",
    "PLINK": "Chang CC, et al. Second-generation PLINK. GigaScience 2015;4:7.",
    "Omnibus": "Raychaudhuri S, et al. Five amino acids in three HLA proteins explain most of the association "
    "between MHC and seropositive rheumatoid arthritis. Nat Genet 2012;44:291-296.",
    "DL": "DerSimonian R, Laird N. Meta-analysis in clinical trials. Control Clin Trials 1986;7:177-188.",
    "I2": "Higgins JPT, Thompson SG. Quantifying heterogeneity in a meta-analysis. Stat Med 2002;21:1539-1558.",
}


def _table(path: Path, n: int = 10) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    df = pd.read_csv(path, sep="\t").head(n)
    return df.where(df.notna(), None).to_dict(orient="records")


def build_facts(ctx) -> dict[str, Any]:
    plan = ctx.plan
    facts: dict[str, Any] = {
        "run_id": ctx.run_dir.name,
        "goal": plan.goal,
        "synthetic": ctx.is_synthetic(),
        "nodes_requested": plan.nodes,
        "tool_versions": ctx.tool_versions,
        "studies": {},
        "warnings": [],
        "citations": [],
    }
    used: set[str] = {"PLINK", "HATK"}
    results: dict[str, NodeResult] = ctx.results
    for s in plan.studies:
        st: dict[str, Any] = {
            "study_id": s.study_id,
            "steps": {},
            "pheno_name": s.pheno_name,
            "external_summary": s.external_assoc is not None,
        }
        if s.synthetic_phenotype:
            st["synthetic_phenotype"] = s.synthetic_phenotype.model_dump()
        for key, r in results.items():
            step, sid = key.split(":")
            if sid != s.study_id:
                continue
            entry: dict[str, Any] = {
                "title": STEP_TITLES[step],
                "status": r.status,
                "metrics": r.metrics,
                "warnings": r.warnings,
            }
            if step == "Node2" and "top_markers" in r.artifacts:
                entry["top_markers"] = _table(r.art("top_markers"))
            if step == "Node3" and "steps" in r.artifacts:
                entry["conditional_steps"] = _table(r.art("steps"), 20)
            if step == "StageI":
                used.add("CookHLA")
            if step == "StageP":
                used.add("BEAGLE3")
            if step == "Node4":
                used.add("Omnibus")
            st["steps"][step] = entry
            facts["warnings"] += [f"{s.study_id} / {STEP_TITLES[step]}: {w}" for w in r.warnings]
        facts["studies"][s.study_id] = st
    m = results.get("Node5:-")
    if m is not None:
        used |= {"DL", "I2"}
        facts["meta"] = {
            "status": m.status,
            "metrics": m.metrics,
            "warnings": m.warnings,
            "top": _table(m.art("top_meta")) if "top_meta" in m.artifacts else [],
        }
        facts["warnings"] += [f"Meta-analysis: {w}" for w in m.warnings]
    facts["steps_run"] = sorted({k.split(":")[0] for k in results}, key=lambda x: list(STEP_TITLES).index(x))
    if facts["synthetic"]:  # the banner at the top already says so; keep one per-study notice only
        facts["warnings"] = [w for w in facts["warnings"] if "Phenotype is SYNTHETIC" not in w]
    facts["warnings"] = list(dict.fromkeys(facts["warnings"]))
    facts["citations"] = [CITATIONS[k] for k in CITATIONS if k in used]
    return facts


def numbers_in(facts: Any) -> list[float]:
    """All numeric values in the facts tree (for the narrative validator)."""
    out: list[float] = []
    if isinstance(facts, dict):
        for v in facts.values():
            out += numbers_in(v)
    elif isinstance(facts, list):
        for v in facts:
            out += numbers_in(v)
    elif isinstance(facts, bool):
        pass
    elif isinstance(facts, (int, float)):
        out.append(float(facts))
    elif isinstance(facts, str):
        import re

        for tok in re.findall(r"-?\d+(?:\.\d+)?(?:[eE]-?\d+)?", facts):
            try:
                out.append(float(tok))
            except ValueError:
                pass
    return out
