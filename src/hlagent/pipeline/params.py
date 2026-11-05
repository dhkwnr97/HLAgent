"""Per-step parameters. Every field is read by the step that owns it (no decorative keys, v1 defect D6)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from hlagent.tools.beagle import PhasingParams


class _P(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StageDParams(_P):
    geno: float = Field(default=0.05, gt=0, le=1, description="max per-SNP missingness (plink --geno)")
    mind: float = Field(default=0.05, gt=0, le=1, description="max per-sample missingness (plink --mind)")
    maf: float = Field(default=0.01, ge=0, lt=0.5)
    hwe: float = Field(default=1e-6, gt=0, lt=1)
    min_n_for_maf_hwe: int = Field(default=50, ge=1, description="skip MAF/HWE filters below this n")
    founders_only: bool = True
    region_from_mb: float = 29.0
    region_to_mb: float = 34.0
    build_match_threshold: float = Field(default=0.95, gt=0.5, le=1)
    harmonized_min_match: float = Field(default=0.99, gt=0.5, le=1)


class StageIParams(_P):
    java_mem_gb: int = Field(default=4, ge=1, le=64)
    n_processes: int = Field(default=1, ge=1, le=9)
    nthreads: int = Field(default=1, ge=1, le=32)
    use_bundled_agm: bool = True
    conf_threshold: float = Field(default=0.8, ge=0, le=1)


class Node1Params(_P):
    resolution: Literal["1field", "2field", "3field", "4field", "Ggroup", "Pgroup"] = "2field"
    imgt: str = "3320"
    hg: Literal["18"] = "18"


class Node2Params(_P):
    trait: Literal["auto", "binary", "continuous"] = "auto"
    ci: float = Field(default=0.95, gt=0.5, lt=1)
    manhattan: bool = True
    heatmap: bool = True
    top_n: int = Field(default=20, ge=1, le=200)


class Node3Params(_P):
    alpha: Literal["bonferroni", "genome_wide"] | float = "bonferroni"
    max_steps: int = Field(default=10, ge=1, le=50)


class Node4Params(_P):
    conditions: list[str] = Field(default_factory=list, description="e.g. AA_DRB1_96")


class Node5Params(_P):
    drop_ambiguous_snps: bool = False
    top_n: int = Field(default=20, ge=1, le=200)


class StageRParams(_P):
    use_llm_narrative: bool = True
    formats: list[Literal["md", "html", "pdf"]] = Field(default_factory=lambda: ["md", "html"])


class PipelineParams(_P):
    stage_d: StageDParams = Field(default_factory=StageDParams)
    stage_i: StageIParams = Field(default_factory=StageIParams)
    node1: Node1Params = Field(default_factory=Node1Params)
    node2: Node2Params = Field(default_factory=Node2Params)
    node3: Node3Params = Field(default_factory=Node3Params)
    stage_p: PhasingParams = Field(default_factory=PhasingParams)
    node4: Node4Params = Field(default_factory=Node4Params)
    node5: Node5Params = Field(default_factory=Node5Params)
    stage_r: StageRParams = Field(default_factory=StageRParams)

    def for_step(self, step: str) -> BaseModel:
        key = {
            "StageD": "stage_d",
            "StageI": "stage_i",
            "Node1": "node1",
            "Node2": "node2",
            "Node3": "node3",
            "StageP": "stage_p",
            "Node4": "node4",
            "Node5": "node5",
            "StageR": "stage_r",
        }[step]
        return getattr(self, key)
