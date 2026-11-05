"""Datasets the planner may use: bundled examples and folders uploaded under workspace/.

A workspace dataset is one sub-folder of workspace/ holding any of:
  <prefix>.bed/.bim/.fam      SNP genotypes (one PLINK fileset)
  *.chped / *.hped            HLA types
  *.phe / *.pheno / *.pheno.txt  phenotype table with a 'FID IID <name> ...' header
  *.assoc.logistic / *.assoc.linear (+ matching .bim)  external summary statistics (Node5 only)
Only file names and aggregate checks are ever shown to an LLM; never sample-level values.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from hlagent import paths
from hlagent.pipeline.contracts import StudySpec, SyntheticPhenotype

Kind = Literal["example", "workspace"]


class Dataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    kind: Kind
    genotype_prefix: Path | None = None
    hla_file: Path | None = None
    pheno_file: Path | None = None
    pheno_names: list[str] = []
    hg: Literal["18", "19", "38"] | None = None
    external_assoc: Path | None = None
    external_bim: Path | None = None
    note: str = ""

    def summary(self) -> dict:
        """LLM-safe description (file names only)."""
        return {
            "id": self.id,
            "label": self.label,
            "kind": self.kind,
            "genotypes": self.genotype_prefix.name if self.genotype_prefix else None,
            "hla_types": self.hla_file.name if self.hla_file else None,
            "phenotype_file": self.pheno_file.name if self.pheno_file else None,
            "phenotype_columns": self.pheno_names,
            "external_summary_statistics": self.external_assoc.name if self.external_assoc else None,
            "build_declared": f"hg{self.hg}" if self.hg else None,
            "note": self.note,
        }

    def to_study(
        self,
        *,
        pheno_name: str | None = None,
        synthetic: SyntheticPhenotype | None = None,
        reference_population: str = "EUR",
        study_id: str | None = None,
    ) -> StudySpec:
        if self.external_assoc is not None:
            return StudySpec(
                study_id=study_id or self.id,
                pheno_name=pheno_name or (self.pheno_names or [None])[0],
                external_assoc=self.external_assoc,
                external_bim=self.external_bim,
            )
        name = pheno_name or (self.pheno_names[0] if self.pheno_names and self.pheno_file else None)
        return StudySpec(
            study_id=study_id or self.id,
            genotype_prefix=self.genotype_prefix,
            hla_file=self.hla_file,
            pheno_file=self.pheno_file if synthetic is None else None,
            pheno_name=name if synthetic is None else None,
            hg=self.hg,
            reference_population=reference_population,
            synthetic_phenotype=synthetic,
        )  # type: ignore[arg-type]


def _examples() -> list[Dataset]:
    e = paths.examples_dir()
    w = e / "hatk_wtccc"
    out = [
        Dataset(
            id="BMExample",
            label="HapMap CEU trios (180 samples, 4-field HLA types, no phenotype)",
            kind="example",
            genotype_prefix=e / "BMExample" / "HAPMAP_CEU",
            hla_file=e / "BMExample" / "HAPMAP_CEU_HLA.imgt3320.4field.chped",
            note="Phenotype is missing (-9): use a synthetic phenotype for a demo run. Build is unknown (re-mapped by rsID).",
        ),
        Dataset(
            id="GenotypeExample",
            label="1958BC SNP genotypes (10 samples, hg19, no HLA types, no phenotype)",
            kind="example",
            genotype_prefix=e / "GenotypeExample" / "1958BC.hg19",
            note="No HLA types: CookHLA imputation (Stage I) is required. Phenotype is constant: synthetic null only.",
        ),
        Dataset(
            id="WTCCC_RA",
            label="WTCCC 58C vs RA (HATK example; 300 cases + 300 controls, hg18, 2-field HLA)",
            kind="example",
            genotype_prefix=w / "wtccc_filtered_58C_RA.hatk.300+300.hg18.chr6.29-34mb",
            hla_file=w / "wtccc_filtered_58C_RA.hatk.300+300.imgt3320.2field.chped",
            pheno_file=w / "wtccc_filtered_58C_RA.hatk.300+300.phe",
            pheno_names=["RA"],
            hg="18",
            note="Real case-control phenotype (rheumatoid arthritis).",
        ),
        Dataset(
            id="NBS_CD",
            label="WTCCC NBS vs CD summary statistics (HATK example, Node5 only)",
            kind="example",
            external_assoc=w
            / "MetaAnalysis"
            / "RESULT_EXAMPLE_wtccc_filtered_NBS_CD.hatk.300+300.chr6.hg18.assoc.logistic",
            external_bim=w
            / "MetaAnalysis"
            / "RESULT_EXAMPLE_wtccc_filtered_NBS_CD.hatk.300+300.chr6.hg18.bim",
            pheno_names=["CD"],
            hg="18",
            note="Association results only (Crohn's disease); usable in meta-analysis.",
        ),
    ]
    return [
        d
        for d in out
        if (d.genotype_prefix and Path(f"{d.genotype_prefix}.bed").exists())
        or (d.external_assoc and d.external_assoc.exists())
    ]


def _pheno_columns(path: Path) -> list[str]:
    try:
        head = path.read_text(errors="replace").splitlines()[0].split()
    except (OSError, IndexError):
        return []
    return head[2:] if len(head) > 2 and head[0].upper() == "FID" and head[1].upper() == "IID" else []


def _scan(folder: Path) -> Dataset | None:
    beds = sorted(folder.glob("*.bed"))
    geno = None
    for b in beds:
        if b.with_suffix(".bim").exists() and b.with_suffix(".fam").exists():
            geno = b.with_suffix("")
            break
    hla = next(iter(sorted(folder.glob("*.chped")) + sorted(folder.glob("*.hped"))), None)
    pheno = next(
        iter(sorted(p for pat in ("*.phe", "*.pheno", "*.pheno.txt") for p in folder.glob(pat))), None
    )
    assoc = next(
        iter(sorted(p for pat in ("*.assoc.logistic", "*.assoc.linear") for p in folder.glob(pat))), None
    )
    if geno is None and hla is None and assoc is None:
        return None
    ext_bim = None
    if assoc is not None:
        cands = [p for p in folder.glob("*.bim") if p.with_suffix("") != geno]
        ext_bim = cands[0] if cands else (Path(f"{geno}.bim") if geno else None)
    hg = None
    low = folder.name.lower() + " " + (geno.name.lower() if geno else "")
    for b in ("18", "19", "38"):
        if f"hg{b}" in low:
            hg = b
    return Dataset(
        id=folder.name,
        label=f"workspace/{folder.name}",
        kind="workspace",
        genotype_prefix=geno,
        hla_file=hla,
        pheno_file=pheno,
        pheno_names=_pheno_columns(pheno) if pheno else [],
        hg=hg,  # type: ignore[arg-type]
        external_assoc=assoc if geno is None else None,
        external_bim=ext_bim if geno is None else None,
    )


def catalog() -> list[Dataset]:
    out = _examples()
    ws = paths.workspace_dir()
    if ws.exists():
        for d in sorted(p for p in ws.iterdir() if p.is_dir() and not p.name.startswith(".")):
            ds = _scan(d)
            if ds is not None:
                out.append(ds)
    return out


def get(dataset_id: str) -> Dataset:
    for d in catalog():
        if d.id == dataset_id:
            return d
    raise KeyError(f"unknown dataset {dataset_id!r}; available: {[d.id for d in catalog()]}")
