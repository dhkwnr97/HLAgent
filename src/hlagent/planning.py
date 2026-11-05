from __future__ import annotations

from pathlib import Path

from hlagent.adapters import tool_versions
from hlagent.data import dataset_samples, read_table, verify_files
from hlagent.models import (
    AnalysisIntent,
    AnalysisOptions,
    AnalysisPlan,
    DatasetManifest,
    Goal,
    PlanStep,
    Question,
    digest,
)
from hlagent.settings import Settings

CAPABILITIES = {
    "version": "2.0.0a1",
    "supported": {g.value: {"enabled": True} for g in Goal},
    "unsupported": ["FASTQ/BAM HLA typing", "survival", "repeated measures", "mixed models",
                    "family-based association", "cross-phenotype meta-analysis", "random-effects meta-analysis"],
    "phase_validation": "experimental; independent HLA truth-phase validation pending",
}
ASSOCIATION = {Goal.association, Goal.conditional, Goal.stepwise, Goal.omnibus}
GENOTYPES = {"plink_bed", "plink_pgen", "vcf", "bcf"}
HLA_INPUTS = {"hla", "hla_dosage"}


def assess(intent: AnalysisIntent, datasets: list[DatasetManifest]) -> list[Question]:
    if intent.unsupported_reason:
        return []
    questions = []

    def ask(field, prompt, options, reason):
        questions.append(Question(field=field, prompt=prompt, options=options, reason=reason))

    if not intent.goals:
        ask("goals", "어떤 분석까지 수행할까요?", [g.value for g in Goal], "연구 목적에 필요한 단계만 실행합니다.")
    by_id = {d.id: d for d in datasets}
    if any(i not in by_id for i in intent.dataset_ids):
        raise ValueError("The request references an unregistered dataset")
    if not intent.dataset_ids:
        ask("dataset_ids", "분석에 사용할 자료를 선택해주세요.",
            [d.id for d in datasets if d.kind not in ("phenotype", "sequence", "reference")],
            "파일을 먼저 등록하면 형식과 표본 수를 검사할 수 있습니다.")
    selected = [by_id[i] for i in intent.dataset_ids]
    goals = set(intent.goals)
    for goal in goals:
        if goal.value not in CAPABILITIES["supported"]:
            raise ValueError("Unsupported capability")
    if Goal.meta in goals:
        if any(d.kind != "summary" for d in selected):
            raise ValueError("Meta-analysis takes cohort summaries; generate each cohort's analysis first")
        if len(selected) < 2:
            ask("dataset_ids", "독립 코호트 요약통계를 두 개 이상 선택해주세요.",
                [d.id for d in datasets if d.kind == "summary"], "메타분석에는 코호트별 효과와 표준오차가 필요합니다.")
        if intent.independent_cohorts is not True:
            ask("independent_cohorts", "코호트 사이에 표본 중복이 없음을 확인했나요?", ["true", "false"],
                "기본 역분산 통합은 독립 코호트를 가정합니다.")
        return questions[:3]
    if goals == {Goal.visualize}:
        if any(d.kind != "summary" for d in selected):
            raise ValueError("Visualization-only mode requires registered result tables")
        return questions[:3]
    main = [d for d in selected if d.kind in GENOTYPES | HLA_INPUTS]
    if selected and not main:
        raise ValueError("This analysis needs genotype or HLA-call data")
    if len(main) > 1:
        raise ValueError("Choose one primary genotype/HLA dataset; analyse cohorts separately")
    dataset = main[0] if main else None
    if dataset and dataset.kind == "hla_dosage" and goals & {Goal.phasing, Goal.haplotype, Goal.imputation}:
        raise ValueError("Expected allele copies alone cannot establish diploid genotypes for phasing; provide validated hard calls")
    if dataset and dataset.kind == "hla" and goals == {Goal.imputation}:
        raise ValueError("HLA typing is already available; imputation requires SNP input. Choose association or haplotype analysis.")
    needs_hla = bool(goals & ASSOCIATION or Goal.haplotype in goals or Goal.imputation in goals)
    if dataset and dataset.kind in GENOTYPES:
        if not dataset.genome_build and not intent.genome_build:
            ask("genome_build", "유전형 자료의 genome build는 무엇인가요?", ["GRCh37", "GRCh38", "GRCh36"],
                "좌표를 추측하거나 reference build와 혼동하지 않습니다.")
        if needs_hla:
            if not intent.reference_id or intent.reference_id not in by_id:
                ask("reference_id", "CookHLA 참조 패널을 선택해주세요.",
                    [d.id for d in datasets if d.kind == "reference"], "SNP로 HLA를 추정하려면 phased reference가 필요합니다.")
            if not dataset.ancestry and not intent.ancestry:
                ask("ancestry", "자료의 ancestry와 참조 패널 적합성을 알려주세요.", [],
                    "Ancestry는 이름으로 추정하지 않습니다. 혼합 집단도 명시할 수 있습니다.")
    if goals & ASSOCIATION:
        if not intent.phenotype_id or intent.phenotype_id not in by_id:
            ask("phenotype_id", "표현형·공변량 자료를 선택해주세요.",
                [d.id for d in datasets if d.kind == "phenotype"], "개인별 결과와 유전형을 표본 ID로 연결합니다.")
        else:
            pheno = by_id[intent.phenotype_id]
            if not intent.phenotype_column:
                ask("phenotype_column", "분석할 표현형 열은 무엇인가요?", [c for c in pheno.columns if c not in ("FID", "IID")],
                    "각 실행에서 하나의 표현형을 분석합니다.")
        if not intent.phenotype_type:
            ask("phenotype_type", "표현형이 이분형인가요, 연속형인가요?", ["binary", "continuous"],
                "로지스틱 또는 선형 회귀를 선택합니다.")
        if intent.phenotype_type == "binary":
            if intent.case_value is None:
                ask("case_value", "환자(case)에 해당하는 값은 무엇인가요?", [], "0/1 또는 1/2의 의미를 추측하지 않습니다.")
            if intent.control_value is None:
                ask("control_value", "대조군(control)에 해당하는 값은 무엇인가요?", [], "효과 방향을 정확히 정의합니다.")
        if not intent.covariates_confirmed:
            ask("covariates", "보정할 공변량을 선택해주세요. 없으면 빈 목록을 확인해주세요.",
                by_id[intent.phenotype_id].columns if intent.phenotype_id in by_id else [],
                "Ancestry PC 등 보정 변수를 임의로 추가하지 않습니다.")
        if not intent.unrelated_confirmed:
            ask("unrelated_confirmed", "서로 혈연관계가 없는 표본을 분석하는 것이 맞나요?", ["true", "false"],
                "가족·혼합모형은 이번 버전의 지원 범위 밖입니다.")
    if Goal.omnibus in goals and (not intent.sequence_id or intent.sequence_id not in by_id):
        ask("sequence_id", "아미노산 서열 사전을 선택해주세요.", [d.id for d in datasets if d.kind == "sequence"],
            "IPD-IMGT/HLA release와 allele-to-residue 매핑을 고정합니다.")
    if Goal.conditional in goals and not intent.conditioning:
        ask("conditioning", "어떤 marker 또는 아미노산 위치를 보정할까요?", [],
            "예: HLA_DRB1*04:01 또는 AA_DRB1_11")
    return questions[:3]


def apply_answers(intent: AnalysisIntent, answers: dict) -> AnalysisIntent:
    value = intent.model_dump(mode="json")
    allowed = set(AnalysisIntent.model_fields) - {"unsupported_reason", "question"}
    for key, answer in answers.items():
        if key not in allowed:
            raise ValueError(f"Unknown question field: {key}")
        if answer in (None, "모르겠어요", "unknown"):
            continue
        if key in ("goals", "dataset_ids", "covariates", "conditioning", "haplotype_loci") and isinstance(answer, str):
            answer = [s.strip() for s in answer.split(",") if s.strip()]
        if key in ("independent_cohorts", "unrelated_confirmed", "covariates_confirmed") and isinstance(answer, str):
            if answer not in ("true", "false"):
                raise ValueError("Use true/false for confirmation fields")
            answer = answer == "true"
        value[key] = answer
        if key == "covariates":
            value["covariates_confirmed"] = True
    return AnalysisIntent.model_validate(value)


def build_plan(project_id: str, intent: AnalysisIntent, datasets: list[DatasetManifest],
               options: AnalysisOptions, settings: Settings, revision: int = 1,
               versions: dict | None = None) -> AnalysisPlan:
    if intent.unsupported_reason:
        raise ValueError(intent.unsupported_reason)
    missing = assess(intent, datasets)
    if missing:
        raise ValueError("Complete required questions before building a plan: " + ", ".join(q.field for q in missing))
    selected_ids = set(intent.dataset_ids) | {intent.phenotype_id, intent.reference_id, intent.sequence_id,
                                            intent.scaffold_id, intent.phase_reference_id}
    selected = [d.model_copy(deep=True) for d in datasets if d.id in selected_ids]
    for d in selected:
        verify_files(d.files)
        if d.id in intent.dataset_ids:
            d.genome_build = d.genome_build or intent.genome_build
            d.ancestry = d.ancestry or intent.ancestry
    versions = versions or tool_versions(settings)
    warnings = ["Results are research associations, not evidence of causality or clinical diagnoses."]
    steps = [PlanStep(id="prepare", tool="prepare")]

    def add(name, dependencies):
        steps.append(PlanStep(id=name, tool=name, depends_on=dependencies))

    goals = set(intent.goals)
    if goals & ASSOCIATION:
        from hlagent.statistics import prepare_design
        phenotype = next(d for d in selected if d.id == intent.phenotype_id)
        frame = read_table(Path(phenotype.files[0].path)).rename(columns=phenotype.metadata.get("mapping", {}).get("columns", {}))
        from hlagent.data import ids
        frame = ids(frame)
        # Validate coding, rank and sample sufficiency before any expensive imputation.
        main_data = next(d for d in selected if d.id in intent.dataset_ids and d.kind in GENOTYPES | HLA_INPUTS)
        prepare_design(dataset_samples(main_data), frame, intent)
    if intent.sequence_id:
        sequence = next(d for d in selected if d.id == intent.sequence_id)
        for d in selected:
            if d.kind in HLA_INPUTS and d.imgt_release and sequence.imgt_release != d.imgt_release:
                raise ValueError("HLA naming and sequence releases differ; harmonize with an explicit mapping first")
    if Goal.meta in goals:
        if goals - {Goal.meta, Goal.visualize}:
            raise ValueError("Meta-analysis uses a separate summary-statistics plan")
        add("meta", ["prepare"])
    elif goals == {Goal.visualize}:
        add("visualize", ["prepare"])
    else:
        main = next(d for d in selected if d.id in intent.dataset_ids and d.kind in GENOTYPES | HLA_INPUTS)
        source_step = "prepare"
        needs_hla = bool(goals & ASSOCIATION or Goal.haplotype in goals or Goal.imputation in goals)
        if main.kind in GENOTYPES and needs_hla:
            if options.memory_gb < 2:
                raise ValueError("CookHLA requires at least 2 GB of total reserved memory")
            ref = next(d for d in selected if d.id == intent.reference_id)
            if ref.kind != "reference" or ref.genome_build != "GRCh36":
                raise ValueError("This CookHLA adapter requires an explicitly hg18/GRCh36 SNP2HLA-format reference")
            if not ref.ancestry:
                raise ValueError("Register reference ancestry/coverage metadata before imputation")
            has_map = bool(ref.metadata.get("genetic_map") and ref.metadata.get("error_rate"))
            if not has_map and (ref.sample_count or 0) < (100 if (main.sample_count or 0) >= 100 else 200):
                raise ValueError("Reference/target too small for automatic adaptive genetic map; supply a compatible map")
            if versions.get("cookhla") == "unavailable":
                raise ValueError("CookHLA image is not installed; use Tools setup")
            chain_key = {"GRCh37": "hg19_chain_sha256", "GRCh38": "hg38_chain_sha256"}.get(main.genome_build)
            if chain_key and versions.get(chain_key) == "unavailable":
                raise ValueError("Install the versioned UCSC liftover chain before imputation")
            add("impute", ["prepare"])
            source_step = "impute"
            warnings.append("CookHLA confidence is not genotype probability or dosage; this path uses hard calls.")
        if needs_hla:
            add("markers", [source_step])
        if Goal.phasing in goals or Goal.haplotype in goals:
            if versions.get("beagle_sha256") == "unavailable":
                raise ValueError("Pinned Beagle JAR is not installed; use Tools setup")
            add("phase", [source_step])
            if intent.phase_reference_id and not intent.scaffold_id:
                raise ValueError("Reference-assisted HLA phasing requires a SNP scaffold and shared HLA codebook")
            if intent.scaffold_id:
                scaffold = next((d for d in selected if d.id == intent.scaffold_id), None)
                if scaffold is None or scaffold.kind not in GENOTYPES:
                    raise ValueError("Register the SNP scaffold dataset before planning phasing")
                if not main.metadata.get("phase_positions") or not main.genome_build or scaffold.genome_build != main.genome_build:
                    raise ValueError("SNP-assisted HLA phasing requires explicit same-build HLA anchor positions")
                if intent.phase_reference_id:
                    ref = next((d for d in selected if d.id == intent.phase_reference_id), None)
                    if not ref or ref.kind != "vcf" or not ref.has_phase or not ref.metadata.get("codebook_path"):
                        raise ValueError("Register phased reference VCF with its HLA encoding codebook")
                warnings.append("SNP-assisted HLA haplotypes use a reversible private allele encoding and require independent phase-truth validation.")
            elif not options.hla_only_exploratory and (main.kind in HLA_INPUTS or source_step == "impute"):
                raise ValueError("HLA-only exploratory mode is disabled; select a validated SNP scaffold")
            if main.kind == "hla" or source_step == "impute":
                if not intent.scaffold_id:
                    warnings.append("HLA-only phasing uses an engine-private coordinate encoding; it is exploratory and does not establish parental origin or calibrated phase probabilities.")
            if Goal.haplotype in goals:
                add("haplotypes", ["phase"])
        if goals & ASSOCIATION:
            if versions.get("plink2") == "unavailable":
                raise ValueError("Install PLINK 2 before association analysis")
            add("association", ["haplotypes" if Goal.haplotype in goals else "markers"])
            if Goal.conditional in goals:
                add("conditional", ["association"])
            if Goal.stepwise in goals:
                add("stepwise", ["association"])
            if Goal.omnibus in goals:
                add("omnibus", ["markers"])
            if not any("pc" in c.lower() for c in intent.covariates):
                warnings.append("No ancestry PCs selected. MHC data alone do not establish adequate population-structure adjustment.")
    add("report", [s.id for s in steps])
    references = {d.id: {"build": d.genome_build, "imgt_release": d.imgt_release,
                         "resolution": d.resolution, "ancestry": d.ancestry}
                  for d in selected if d.kind in ("reference", "sequence")}
    key = digest({"project": project_id, "intent": intent.model_dump(mode="json"), "options": options.model_dump(),
                  "datasets": [d.model_dump(mode="json") for d in selected], "tools": versions})
    return AnalysisPlan(id=key[:32], project_id=project_id, revision=revision, intent=intent, options=options,
                        datasets=selected, steps=steps, tools=versions, references=references, warnings=warnings)
