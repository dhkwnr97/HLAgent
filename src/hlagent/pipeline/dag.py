"""Plan model and dependency resolution.

The user (or the planner agent) chooses analysis nodes (Node1-5). Stages are added automatically:
- Stage D for every study that runs any per-study step
- Stage I (CookHLA) when a study needs Node1 but has no HLA types
- Stage P (BEAGLE) when Node4 is requested
- Node1 when Node2/3/4 is requested; Node2 for every genotype study when Node5 is requested
Every automatic addition is explained in `ResolvedPlan.notes` so the approval card can show it.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from hlagent.pipeline.contracts import STEP_ORDER, StepId, StudySpec, now_utc
from hlagent.pipeline.params import PipelineParams

NodeId = Literal["Node1", "Node2", "Node3", "Node4", "Node5"]


class AnalysisPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    goal: str = ""
    studies: list[StudySpec]
    nodes: list[NodeId]
    include_report: bool = True
    params: PipelineParams = Field(default_factory=PipelineParams)
    created_at: datetime = Field(default_factory=now_utc)


class Task(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    step: StepId
    study_id: str | None = None

    @property
    def key(self) -> str:
        return f"{self.step}:{self.study_id or '-'}"


class ResolvedPlan(BaseModel):
    tasks: list[Task]
    notes: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def resolve(plan: AnalysisPlan) -> ResolvedPlan:
    notes: list[str] = []
    errors: list[str] = []
    wanted = set(plan.nodes)
    if not wanted:
        errors.append("No analysis node selected (choose at least one of Node1-Node5).")
    geno_studies = [s for s in plan.studies if s.external_assoc is None]
    ext_studies = [s for s in plan.studies if s.external_assoc is not None]
    ids = [s.study_id for s in plan.studies]
    if len(ids) != len(set(ids)):
        errors.append("study_id values must be unique.")

    if "Node5" in wanted:
        if len(plan.studies) < 2:
            errors.append("Node5 (meta-analysis) needs at least 2 studies.")
        if geno_studies and "Node2" not in wanted:
            wanted.add("Node2")
            notes.append("Node2 added: Node5 meta-analysis combines each study's Node2 regression results.")
        for s in ext_studies:
            if s.external_bim is None:
                notes.append(
                    f"{s.study_id}: no .bim for external summary statistics; alleles are matched by A1 only."
                )
    if wanted & {"Node2", "Node3", "Node4"} and "Node1" not in wanted:
        wanted.add("Node1")
        notes.append(
            "Node1 added: regression, conditional and omnibus tests run on the HLA binary marker panel."
        )
    need_phasing = "Node4" in wanted

    tasks: list[Task] = []
    per_study_nodes: list[StepId] = [n for n in ("Node1", "Node2", "Node3", "Node4") if n in wanted]
    for s in geno_studies:
        if not per_study_nodes:
            continue
        if s.genotype_prefix is None and s.hla_file is None:
            errors.append(f"{s.study_id}: provide genotypes (PLINK prefix) and/or HLA types (.chped/.hped).")
            continue
        steps: list[StepId] = ["StageD"]
        if s.hla_file is None:
            if s.genotype_prefix is None:
                errors.append(f"{s.study_id}: HLA imputation needs genotypes.")
                continue
            steps.append("StageI")
            notes.append(
                f"{s.study_id}: Stage I (CookHLA imputation, {s.reference_population} panel) added "
                "because no HLA types were given."
            )
        elif s.genotype_prefix is None:
            notes.append(
                f"{s.study_id}: no SNP genotypes; the marker panel will contain HLA/AA/SNPS markers only."
            )
        steps += per_study_nodes
        if need_phasing:
            steps.append("StageP")
            notes.append(f"{s.study_id}: Stage P (BEAGLE 3.3.2 phasing of the Node1 panel) added for Node4.")
        steps.sort(key=STEP_ORDER.index)
        tasks += [Task(step=st, study_id=s.study_id) for st in steps]
    for s in ext_studies:
        if wanted - {"Node5"}:
            notes.append(f"{s.study_id}: external summary statistics are used in Node5 only.")
    if "Node5" in wanted:
        tasks.append(Task(step="Node5"))
    if plan.include_report and tasks:
        tasks.append(Task(step="StageR"))
    return ResolvedPlan(tasks=tasks, notes=notes, errors=errors)
