from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


def uid() -> str:
    return uuid4().hex


def now() -> str:
    return datetime.now(UTC).isoformat()


def digest(value: Any) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Goal(StrEnum):
    imputation = "imputation"
    phasing = "phasing"
    association = "association"
    conditional = "conditional"
    stepwise = "stepwise"
    omnibus = "omnibus"
    haplotype = "haplotype"
    meta = "meta"
    visualize = "visualize"


class SourceFile(Contract):
    path: str
    sha256: str
    size: int
    role: str = "input"


class DatasetManifest(Contract):
    id: str = Field(default_factory=uid)
    project_id: str
    label: str
    kind: Literal["plink_bed", "plink_pgen", "vcf", "bcf", "hla", "hla_dosage", "phenotype", "summary", "sequence", "reference"]
    files: list[SourceFile]
    sample_count: int | None = None
    columns: list[str] = Field(default_factory=list)
    genome_build: Literal["GRCh36", "GRCh37", "GRCh38"] | None = None
    ancestry: str | None = None
    resolution: str | None = None
    imgt_release: str | None = None
    has_dosage: bool = False
    has_phase: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=now)


class AnalysisIntent(Contract):
    question: str = ""
    goals: list[Goal] = Field(default_factory=list)
    dataset_ids: list[str] = Field(default_factory=list)
    phenotype_id: str | None = None
    sequence_id: str | None = None
    reference_id: str | None = None
    scaffold_id: str | None = None
    phase_reference_id: str | None = None
    genome_build: Literal["GRCh36", "GRCh37", "GRCh38"] | None = None
    ancestry: str | None = None
    phenotype_column: str | None = None
    phenotype_type: Literal["binary", "continuous"] | None = None
    case_value: str | None = None
    control_value: str | None = None
    covariates: list[str] = Field(default_factory=list)
    covariates_confirmed: bool = False
    unrelated_confirmed: bool = False
    independent_cohorts: bool | None = None
    conditioning: list[str] = Field(default_factory=list)
    haplotype_loci: list[str] = Field(default_factory=list)
    unsupported_reason: str | None = None


class AnalysisOptions(Contract):
    alpha: float = Field(default=0.05, gt=0, lt=1)
    max_steps: int = Field(default=10, ge=1, le=100)
    min_count: int = Field(default=20, ge=1)
    max_missing: float = Field(default=0.02, ge=0, lt=1)
    threads: int = Field(default=4, ge=1, le=256)
    memory_gb: int = Field(default=4, ge=1, le=1024)
    seed: int = 20260906
    cookhla_processes: int = Field(default=1, ge=1, le=9)
    cookhla_confidence_min: float | None = Field(default=None, ge=0, le=2)
    hla_only_exploratory: bool = True
    export_directory: str | None = None
    cookhla_sensitivity_thresholds: list[float] = Field(default_factory=lambda: [0.5, 0.9])

    @model_validator(mode="after")
    def valid_execution_options(self):
        if any(not 0 <= t <= 2 for t in self.cookhla_sensitivity_thresholds):
            raise ValueError("CookHLA native-score thresholds must lie between 0 and 2")
        if len(self.cookhla_sensitivity_thresholds) > 10:
            raise ValueError("At most ten predefined sensitivity thresholds per plan")
        if self.cookhla_processes > 1 and (self.cookhla_processes > self.threads or self.cookhla_processes * 2 > self.memory_gb):
            raise ValueError("CookHLA processes require at least one CPU and two GB total RAM per process")
        return self


class PlanStep(Contract):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    tool: str
    depends_on: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)


class AnalysisPlan(Contract):
    id: str = Field(default_factory=uid, pattern=r"^[a-f0-9]{32}$")
    project_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    revision: int = 1
    intent: AnalysisIntent
    options: AnalysisOptions = Field(default_factory=AnalysisOptions)
    datasets: list[DatasetManifest]
    steps: list[PlanStep]
    tools: dict[str, str] = Field(default_factory=dict)
    references: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=now)

    @property
    def plan_hash(self) -> str:
        return digest(self)

    @model_validator(mode="after")
    def acyclic(self):
        seen = set()
        for step in self.steps:
            if step.id in seen or not set(step.depends_on).issubset(seen):
                raise ValueError("Steps must have unique IDs in dependency order")
            seen.add(step.id)
        return self


class PlanApproval(Contract):
    plan_id: str
    plan_hash: str
    revision: int


class JobRecord(Contract):
    id: str = Field(default_factory=uid)
    project_id: str
    plan_id: str
    plan_hash: str
    state: Literal["queued", "running", "succeeded", "failed", "cancel_requested", "cancelled"] = "queued"
    current_step: str | None = None
    error: str | None = None
    attempt: int = 0
    created_at: str = Field(default_factory=now)
    updated_at: str = Field(default_factory=now)


class ArtifactManifest(Contract):
    id: str = Field(default_factory=uid)
    job_id: str
    step_id: str
    path: str
    sha256: str
    size: int
    media_type: str
    label: str
    validation: dict[str, Any] = Field(default_factory=dict)


class Evidence(Contract):
    id: str
    title: str
    locator: str
    text: str
    url: str | None = None
    source_hash: str | None = None


class EvidenceAnswer(Contract):
    answer: str
    citations: list[Evidence] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class Question(Contract):
    field: str
    prompt: str
    options: list[str] = Field(default_factory=list)
    reason: str


class ProviderConfig(Contract):
    provider: Literal["google", "anthropic", "openai", "ollama"] = "google"
    model: str = "gemini-3.5-flash-lite"
    base_url: str | None = None
    validated: bool = False
    validated_at: str | None = None
