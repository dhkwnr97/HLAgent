"""Ready-made plans for the acceptance scenarios (plan section 8)."""

from __future__ import annotations

from hlagent import paths
from hlagent.pipeline.contracts import StudySpec, SyntheticPhenotype
from hlagent.pipeline.dag import AnalysisPlan


def _ex():
    return paths.examples_dir()


def bmexample(synthetic: str = "spike_in") -> StudySpec:
    e = _ex() / "BMExample"
    return StudySpec(
        study_id="BMExample",
        genotype_prefix=e / "HAPMAP_CEU",
        hla_file=e / "HAPMAP_CEU_HLA.imgt3320.4field.chped",
        synthetic_phenotype=SyntheticPhenotype(mode=synthetic),
    )  # type: ignore[arg-type]


def genotype_example() -> StudySpec:
    e = _ex() / "GenotypeExample"
    return StudySpec(
        study_id="GenotypeExample",
        genotype_prefix=e / "1958BC.hg19",
        synthetic_phenotype=SyntheticPhenotype(mode="null", name="SYNTHETIC"),
    )


def wtccc_ra() -> StudySpec:
    e = _ex() / "hatk_wtccc"
    return StudySpec(
        study_id="WTCCC_RA",
        genotype_prefix=e / "wtccc_filtered_58C_RA.hatk.300+300.hg18.chr6.29-34mb",
        hla_file=e / "wtccc_filtered_58C_RA.hatk.300+300.imgt3320.2field.chped",
        pheno_file=e / "wtccc_filtered_58C_RA.hatk.300+300.phe",
        pheno_name="RA",
        hg="18",
    )


def nbs_cd_summary() -> StudySpec:
    e = _ex() / "hatk_wtccc" / "MetaAnalysis"
    return StudySpec(
        study_id="NBS_CD",
        pheno_name="CD",
        external_assoc=e / "RESULT_EXAMPLE_wtccc_filtered_NBS_CD.hatk.300+300.chr6.hg18.assoc.logistic",
        external_bim=e / "RESULT_EXAMPLE_wtccc_filtered_NBS_CD.hatk.300+300.chr6.hg18.bim",
    )


def scenario(name: str) -> AnalysisPlan:
    if name == "S2":
        return AnalysisPlan(
            goal="BMExample HLA association (synthetic spike-in phenotype)",
            studies=[bmexample()],
            nodes=["Node1", "Node2", "Node3", "Node4"],
        )
    if name == "S3":
        return AnalysisPlan(
            goal="GenotypeExample CookHLA imputation and regression",
            studies=[genotype_example()],
            nodes=["Node1", "Node2"],
        )
    if name == "S4":
        return AnalysisPlan(
            goal="BMExample + GenotypeExample meta-analysis",
            studies=[bmexample(), genotype_example()],
            nodes=["Node1", "Node2", "Node5"],
        )
    if name == "S5":
        return AnalysisPlan(
            goal="WTCCC RA fine-mapping and RA-CD meta-analysis",
            studies=[wtccc_ra(), nbs_cd_summary()],
            nodes=["Node1", "Node2", "Node3", "Node4", "Node5"],
        )
    raise KeyError(name)
