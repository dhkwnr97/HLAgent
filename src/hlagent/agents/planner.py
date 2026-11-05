"""Mode 2 planner: turn the user's goal into an analysis plan and ask for approval.

Flow: list_datasets / inspect_dataset -> preview_plan(draft) -> execute_plan(draft).
`execute_plan` requires approval (Pydantic AI deferred tool), so the run ends with DeferredToolRequests
and the UI shows an approval card that lists the steps and asks the user to approve or change them.
The card text is rendered here from the validated draft, not written by the LLM. The LLM only sees
file names and aggregate checks (sample counts, build, phenotype case/control counts), never genotypes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai import Agent, DeferredToolRequests, ModelRetry, RunContext

from hlagent import datasets
from hlagent.pipeline.contracts import STEP_TITLES, SyntheticPhenotype
from hlagent.pipeline.dag import AnalysisPlan, NodeId, resolve
from hlagent.pipeline.params import Node1Params, Node4Params, PipelineParams
from hlagent.pipeline.steps.stage_d_data import ASSOCIATION_NODES, preflight

NODE_DESC = {
    "Node1": "HLA binary marker panel (alleles, amino acids, intragenic SNPs; HATK bMarkerGenerator)",
    "Node2": "marker-level association (logistic/linear regression) + Manhattan, QQ, HLA heatmaps",
    "Node3": "stepwise conditional regression (independent signals)",
    "Node4": "omnibus likelihood-ratio test per amino-acid position (needs BEAGLE phasing, added automatically)",
    "Node5": "meta-analysis across >= 2 studies (fixed + random effects, Cochran Q, I2)",
}
NODE_NAMES = {
    "Node1": "HLA marker panel",
    "Node2": "association test",
    "Node3": "conditional analysis",
    "Node4": "omnibus test",
    "Node5": "meta-analysis",
}


class StudyDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str = Field(description="dataset id returned by list_datasets")
    phenotype: Literal["file", "synthetic_null", "synthetic_spike_in"] = Field(
        default="file",
        description="'file' uses the dataset's phenotype; synthetic_* are demo-only phenotypes for data without one "
        "(spike_in needs HLA types in the dataset)",
    )
    pheno_name: str | None = Field(default=None, description="phenotype column when the file has several")
    spike_allele: str = Field(
        default="DRB1*15:01", description="spike_in only: allele that drives the synthetic risk"
    )
    spike_odds_ratio: float = Field(default=5.0, gt=1.0, le=50.0)
    reference_population: Literal["EUR", "EAS", "AFR", "AMR", "SAS", "ALL"] = "EUR"


class PlanDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(description="one-line analysis goal in the user's language")
    studies: list[StudyDraft] = Field(min_length=1, max_length=8)
    nodes: list[NodeId] = Field(
        min_length=1, description="requested nodes; required stages are added automatically"
    )
    hla_resolution: Literal["1field", "2field", "3field", "4field"] = "2field"
    omnibus_conditions: list[str] = Field(
        default_factory=list, description="Node4 conditioning, e.g. AA_DRB1_96"
    )


def build_plan(draft: PlanDraft) -> AnalysisPlan:
    studies = []
    for sd in draft.studies:
        ds = datasets.get(sd.dataset_id)
        syn = None
        if sd.phenotype != "file":
            syn = SyntheticPhenotype(
                mode="spike_in" if sd.phenotype == "synthetic_spike_in" else "null",
                allele=sd.spike_allele,
                odds_ratio=sd.spike_odds_ratio,
            )
        studies.append(
            ds.to_study(pheno_name=sd.pheno_name, synthetic=syn, reference_population=sd.reference_population)
        )
    params = PipelineParams(
        node1=Node1Params(resolution=draft.hla_resolution),
        node4=Node4Params(conditions=draft.omnibus_conditions),
    )
    return AnalysisPlan(goal=draft.goal, studies=studies, nodes=sorted(set(draft.nodes)), params=params)


def _preflight_summary(pre: dict) -> dict:
    keep = (
        "n_samples",
        "n_snps",
        "family_data",
        "n_founders",
        "hla_genes_typed",
        "hla_genes_missing",
        "n_samples_with_hla",
        "errors",
        "warnings",
        "needs_user_choice",
    )
    out = {k: pre[k] for k in keep if k in pre}
    if "build" in pre:
        out["build"] = pre["build"].get("user_override") or pre["build"].get("build")
    if "phenotype" in pre:
        ph = pre["phenotype"]
        out["phenotype"] = {k: ph.get(k) for k in ("type", "n_cases", "n_controls", "n_observed", "usable")}
    return out


def preview(draft: PlanDraft) -> dict[str, Any]:
    """Validated plan + resolved steps + per-study checks (aggregates only)."""
    try:
        plan = build_plan(draft)
    except (KeyError, ValueError) as e:
        return {"ok": False, "errors": [str(e)]}
    r = resolve(plan)
    pre = {}
    for s in plan.studies:
        if s.external_assoc is not None:
            pre[s.study_id] = {
                "external_summary_statistics": True,
                "errors": [] if s.external_assoc.exists() else [f"file not found: {s.external_assoc.name}"],
            }
        else:
            needs_ph = bool(set(plan.nodes) & ASSOCIATION_NODES)
            pre[s.study_id] = _preflight_summary(preflight(s, plan.params.stage_d, needs_ph))
    errors = list(r.errors) + [f"{sid}: {e}" for sid, p in pre.items() for e in p.get("errors", [])]
    choices = [f"{sid}: {c}" for sid, p in pre.items() for c in p.get("needs_user_choice", [])]
    return {
        "ok": not errors and not choices,
        "errors": errors,
        "needs_user_choice": choices,
        "steps": [{"step": t.step, "study": t.study_id, "title": STEP_TITLES[t.step]} for t in r.tasks],
        "notes": r.notes,
        "studies": pre,
        "nodes": plan.nodes,
    }


def render_proposal(draft: PlanDraft, pv: dict[str, Any]) -> str:
    """Deterministic approval-card text, rendered from the validated draft."""
    nodes = sorted(set(draft.nodes))
    last = nodes[-1]
    span = f"{nodes[0]} → {last}" if len(nodes) > 1 else last
    lines = [
        f"**Goal**: {draft.goal}",
        "",
        f"Proposed analysis: **{span}** ({', '.join(f'{n} {NODE_NAMES[n]}' for n in nodes)})",
        "",
    ]
    lines.append("| Dataset | Samples | Build | HLA | Phenotype |")
    lines.append("|---|---|---|---|---|")
    for sd in draft.studies:
        p = pv.get("studies", {}).get(sd.dataset_id, {})
        if p.get("external_summary_statistics"):
            lines.append(f"| {sd.dataset_id} | summary statistics | - | - | external results (Node5 only) |")
            continue
        n = p.get("n_founders") if p.get("family_data") else p.get("n_samples")
        hla = "typed" if p.get("hla_genes_typed") else "CookHLA imputation"
        ph = p.get("phenotype") or {}
        if sd.phenotype == "synthetic_spike_in":
            phs = f"synthetic spike-in ({sd.spike_allele}, OR {sd.spike_odds_ratio:g}), demonstration only"
        elif sd.phenotype == "synthetic_null":
            phs = "synthetic null, demonstration only"
        else:
            phs = f"{ph.get('type')}: case {ph.get('n_cases')} / control {ph.get('n_controls')}"
        lines.append(f"| {sd.dataset_id} | {n} | {p.get('build', '?')} | {hla} | {phs} |")
    lines += [
        "",
        "**Steps to run**: "
        + " → ".join(f"{s['step']}" + (f"({s['study']})" if s["study"] else "") for s in pv.get("steps", [])),
    ]
    if pv.get("notes"):
        lines += ["", "Steps added automatically:"] + [f"- {n}" for n in pv["notes"]]
    warns = [w for sp in pv.get("studies", {}).values() for w in sp.get("warnings", [])]
    if warns:
        lines += ["", "Warnings:"] + [f"- {w}" for w in dict.fromkeys(warns)]
    lines += ["", "Shall I proceed? You can also tell me which nodes (1–5) to run."]
    return "\n".join(lines)


@dataclass
class PlannerDeps:
    start_job: Callable[[AnalysisPlan], str]
    previews: dict[str, dict[str, Any]] = field(default_factory=dict)
    started: list[str] = field(default_factory=list)


INSTRUCTIONS = f"""\
You are the analysis planner of HLAgent, an HLA fine-mapping assistant. The pipeline nodes are:
{chr(10).join(f"- {k}: {v}" for k, v in NODE_DESC.items())}
Stage D (data QC), Stage I (CookHLA imputation when no HLA types exist), Stage P (phasing) and Stage R (report)
are added automatically by the engine; never ask the user to choose them.

Rules:
1. If the user did not name a dataset, call list_datasets and pick or ask. Use inspect_dataset to check data.
2. Choose the smallest node set that answers the goal. A single study with a usable phenotype: Node1-Node4.
   Node5 needs at least two studies (genotype studies and/or external summary statistics).
3. If a phenotype has no usable variation, use phenotype='synthetic_spike_in' (if HLA types exist) or
   'synthetic_null' and say clearly that results are a demo with no biological meaning. Never invent data.
4. Always call preview_plan before execute_plan. If preview_plan reports errors or needs_user_choice, explain
   them briefly and ask the user; do not call execute_plan.
5. When the preview is clean, call execute_plan with the same draft in the same turn. The user then sees an
   approval card; do not say the analysis has started until execute_plan returns a run_id.
6. If the user denies or edits the plan, adjust the draft (e.g. the nodes they name) and repeat 4-5.
7. Never ask for, print or reason about individual genotype or phenotype values.
8. Answer in the user's language (Korean if the user writes Korean). Be brief.
"""

planner_agent: Agent[PlannerDeps, str | DeferredToolRequests] = Agent(
    deps_type=PlannerDeps,
    output_type=[str, DeferredToolRequests],
    instructions=INSTRUCTIONS,
    name="planner",
    retries=2,
)


@planner_agent.tool_plain
def list_datasets() -> list[dict]:
    """Datasets available to analyse (bundled examples and folders uploaded to workspace/)."""
    return [d.summary() for d in datasets.catalog()]


@planner_agent.tool_plain
def inspect_dataset(dataset_id: str) -> dict:
    """Aggregate checks for one dataset: sample/SNP counts, genome build, family structure, HLA genes, phenotype."""
    try:
        ds = datasets.get(dataset_id)
    except KeyError as e:
        raise ModelRetry(str(e)) from e
    if ds.external_assoc is not None:
        return {
            "id": ds.id,
            "external_summary_statistics": ds.external_assoc.name,
            "phenotype": ds.pheno_names,
        }
    # phenotype usability is reported but not enforced here: it depends on the nodes requested later
    return {"id": ds.id, **_preflight_summary(preflight(ds.to_study(), needs_phenotype=False))}


@planner_agent.tool
def preview_plan(ctx: RunContext[PlannerDeps], draft: PlanDraft) -> dict:
    """Validate a draft plan and return the steps the engine will run plus per-study checks."""
    pv = preview(draft)
    ctx.deps.previews[draft.model_dump_json()] = pv
    return pv


@planner_agent.tool(requires_approval=True)
def execute_plan(ctx: RunContext[PlannerDeps], draft: PlanDraft) -> dict:
    """Start the analysis. Needs the user's approval; call only after a clean preview_plan."""
    pv = ctx.deps.previews.get(draft.model_dump_json()) or preview(draft)
    if not pv.get("ok"):
        return {"started": False, "errors": pv.get("errors", []) + pv.get("needs_user_choice", [])}
    run_id = ctx.deps.start_job(build_plan(draft))
    ctx.deps.started.append(run_id)
    return {"started": True, "run_id": run_id}
