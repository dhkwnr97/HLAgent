"""Typed contracts shared by the planner, the DAG resolver, the runner and every step.

Naming follows HLAgent v1: "Node1-5" are the HATK analysis nodes (binary marker panel, regression,
stepwise conditional, omnibus, meta-analysis). Imputation (CookHLA) and phasing (BEAGLE) are stages.
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

StepId = Literal["StageD", "StageI", "Node1", "Node2", "Node3", "StageP", "Node4", "Node5", "StageR"]
STEP_ORDER: tuple[StepId, ...] = (
    "StageD",
    "StageI",
    "Node1",
    "Node2",
    "Node3",
    "StageP",
    "Node4",
    "Node5",
    "StageR",
)
PER_STUDY_STEPS: tuple[StepId, ...] = ("StageD", "StageI", "Node1", "Node2", "Node3", "StageP", "Node4")
STEP_TITLES: dict[str, str] = {
    "StageD": "Data intake & QC",
    "StageI": "HLA imputation (CookHLA)",
    "Node1": "Node1: HLA binary marker panel",
    "Node2": "Node2: Regression + Manhattan/heatmap",
    "Node3": "Node3: Stepwise conditional regression",
    "StageP": "Phasing (BEAGLE 3.3.2)",
    "Node4": "Node4: Omnibus test",
    "Node5": "Node5: Meta-analysis",
    "StageR": "Report",
}

ArtifactKind = Literal[
    "bfile",
    "hped",
    "chped",
    "alleles",
    "vcf",
    "bgl_phased",
    "markers",
    "aa",
    "assoc",
    "omnibus",
    "meta",
    "table",
    "plot",
    "report",
    "json",
    "log",
]
Build = Literal["hg18", "hg19", "hg38", "unknown"]


def fingerprint(path: Path, limit: int = 1 << 20) -> str:
    """sha256 over the first MiB plus size and, for PLINK prefixes, all three files."""
    h = hashlib.sha256()
    files = [path]
    if not path.exists() and all(Path(f"{path}.{e}").exists() for e in ("bed", "bim", "fam")):
        files = [Path(f"{path}.{e}") for e in ("bed", "bim", "fam")]
    for f in files:
        if f.is_dir():
            for sub in sorted(f.rglob("*")):
                if sub.is_file():
                    h.update(sub.name.encode())
                    h.update(str(sub.stat().st_size).encode())
            continue
        with open(f, "rb") as fh:
            h.update(fh.read(limit))
        h.update(str(f.stat().st_size).encode())
    return h.hexdigest()


class ArtifactRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: ArtifactKind
    path: Path
    sha256: str
    build: Build | None = None
    description: str = ""

    @classmethod
    def of(
        cls, kind: ArtifactKind, path: Path, build: Build | None = None, description: str = ""
    ) -> ArtifactRef:
        return cls(kind=kind, path=path, sha256=fingerprint(path), build=build, description=description)


class NodeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node: StepId
    study_id: str | None
    status: Literal["ok", "skipped_cached", "warning", "blocked", "failed"]
    cache_key: str
    artifacts: dict[str, ArtifactRef] = Field(default_factory=dict)
    metrics: dict[str, float | int | str | bool | None] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    commands: list[str] = Field(default_factory=list)
    tool_versions: dict[str, str] = Field(default_factory=dict)
    error_kind: Literal["input_error", "tool_error", "resource_error", "blocked"] | None = None
    error_message: str | None = None
    user_action: str | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None

    def art(self, key: str) -> Path:
        return self.artifacts[key].path


class SyntheticPhenotype(BaseModel):
    """Demo-only phenotype (plan section 6.7). Every artifact of a run using it is marked SYNTHETIC."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["null", "spike_in"] = "null"
    seed: int = 20261023
    allele: str = Field(default="DRB1*15:01", description="spike_in: allele whose dosage drives risk")
    odds_ratio: float = Field(default=5.0, gt=1.0, le=50.0)
    case_fraction: float = Field(default=0.5, gt=0.05, lt=0.95)
    name: str = "SYNTHETIC"


_STUDY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.+-]{0,63}$")


class StudySpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    study_id: str
    genotype_prefix: Path | None = Field(default=None, description="PLINK prefix (.bed/.bim/.fam)")
    hla_file: Path | None = Field(default=None, description="HLA types: .chped/.hped (skip imputation)")
    pheno_file: Path | None = None
    pheno_name: str | None = None
    covar_file: Path | None = None
    covar_names: list[str] = Field(default_factory=list)
    hg: Literal["18", "19", "38"] | None = Field(default=None, description="override build detection")
    reference_population: Literal["EUR", "EAS", "AFR", "AMR", "SAS", "ALL"] = "EUR"
    synthetic_phenotype: SyntheticPhenotype | None = None
    external_assoc: Path | None = Field(default=None, description="summary statistics only (Node5 input)")
    external_bim: Path | None = None

    @field_validator("study_id")
    @classmethod
    def _sid(cls, v: str) -> str:
        if not _STUDY_ID.match(v):
            raise ValueError("study_id: letters, digits, _ . + - only (max 64)")
        return v


def now_utc() -> datetime:
    return datetime.now(UTC)
