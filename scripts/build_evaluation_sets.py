"""Generate draft bilingual evaluation prompts; expert adjudication is mandatory before publication."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "evaluation"
root.mkdir(exist_ok=True)
cases = []
families = {
    "ready": [
        ("기존 HLA typing으로 연관분석해줘", "Test association using existing HLA typing", ["association"]),
        ("SNP에서 HLA를 추정해줘", "Impute HLA from SNP genotypes", ["imputation"]),
        ("HLA haplotype 빈도를 계산해줘", "Estimate HLA haplotype frequencies", ["haplotype"]),
        ("이 VCF의 위상을 추정해줘", "Phase this VCF", ["phasing"]),
        ("기존 연관분석 결과를 시각화해줘", "Visualize existing association results", ["visualize"]),
        ("표현형 trait와 HLA의 연관성을 계산해줘", "Test HLA association with phenotype trait", ["association"]),
        ("질병 case와 HLA의 연관성을 계산해줘", "Test HLA association with disease case", ["association"]),
        ("HLA dosage로 연관분석해줘", "Test association using HLA dosages", ["association"]),
        ("이미 추정한 HLA로 연관분석해줘", "Test association using previously imputed HLA", ["association"]),
        ("이 결과로 그림과 보고서를 만들어줘", "Make figures and a report from these results", ["visualize"]),
    ],
    "missing_or_conflicting": [
        ("HLA 연관분석해줘. 표현형 파일은 아직 없어", "Test HLA association; I do not yet have a phenotype file", ["association"]),
        ("SNP에서 HLA 추정해줘. Reference는 없어", "Impute HLA from SNPs; no reference is supplied", ["imputation"]),
        ("질병 연관분석해줘. 1과 2 중 환자가 무엇인지 모르겠어", "Test disease association; I do not know whether 1 or 2 means case", ["association"]),
        ("HLA 추정해줘. Genome build를 모르겠어", "Impute HLA; genome build is unknown", ["imputation"]),
        ("연관분석해줘. PC 열을 아직 확인하지 않았어", "Test association; PC columns have not been confirmed", ["association"]),
        ("HLA 연관분석해줘. 표본 ID가 서로 달라", "Test HLA association; sample identifiers disagree", ["association"]),
        ("메타분석해줘. 코호트 표본 중복은 모르겠어", "Run meta-analysis; sample overlap is unknown", ["meta"]),
        ("아미노산 omnibus 해줘. 서열 사전은 없어", "Run amino-acid omnibus tests; no sequence dictionary is supplied", ["omnibus"]),
        ("조건부 분석해줘. 무엇을 보정할지는 아직 정하지 않았어", "Run conditional analysis; the conditioning marker is undecided", ["conditional"]),
        ("HLA 연관분석해줘. trait 열은 문자열 범주야", "Run HLA association; trait contains text categories", ["association"]),
    ],
    "skip_unneeded": [
        ("이미 HLA typing이 있어. 추정하지 말고 연관분석만 해줘", "I have HLA typing; run association without imputation", ["association"]),
        ("개인별 residue dosage로 omnibus만 계산해줘. Phasing은 불필요해", "Run omnibus tests on individual residue dosages; phasing is unnecessary", ["omnibus"]),
        ("요약통계가 있어. 메타분석만 해줘", "I have summary statistics; run only meta-analysis", ["meta"]),
        ("완성된 결과의 그림만 그려줘", "Only plot the completed results", ["visualize"]),
        ("기존 HPED에서 연관분석해줘", "Run association from existing HPED calls", ["association"]),
        ("CHPED와 표현형으로 연관분석해줘", "Test association from CHPED and phenotypes", ["association"]),
        ("HLA 추정까지 하고 멈춰줘", "Stop after HLA imputation", ["imputation"]),
        ("SNP phasing까지만 해줘", "Only phase the SNPs", ["phasing"]),
        ("HLA typing의 allele 빈도와 haplotype을 추론해줘", "Infer allele frequencies and haplotypes from HLA typing", ["haplotype"]),
        ("기존 dosage로 조건부 연관분석해줘", "Run conditional association using existing dosages", ["conditional"]),
    ],
    "advanced": [
        ("A*01:01을 보정해서 조건부 분석해줘", "Run conditional analysis adjusting for A*01:01", ["conditional"]),
        ("DRB1 11번 아미노산 위치 전체를 보정해줘", "Run conditional analysis adjusting for the entire DRB1 amino-acid position 11", ["conditional"]),
        ("단계적 조건부 분석으로 독립 신호를 찾아줘", "Find independent signals with stepwise conditional analysis", ["stepwise"]),
        ("위치별 아미노산 omnibus 검정을 수행해줘", "Perform position-level amino-acid omnibus tests", ["omnibus"]),
        ("세 독립 코호트의 같은 질병 요약통계를 메타분석해줘", "Meta-analyse same-disease summaries from three independent cohorts", ["meta"]),
        ("다섯 코호트의 같은 연속형 표현형을 메타분석해줘", "Meta-analyse the same continuous phenotype across five cohorts", ["meta"]),
        ("HLA haplotype과 질병의 연관성을 탐색해줘", "Explore association between HLA haplotypes and disease", ["haplotype", "association"]),
        ("조건부 분석과 omnibus를 수행해줘", "Run conditional and omnibus analyses", ["conditional", "omnibus"]),
        ("코호트 제외 민감도 검사를 포함한 메타분석해줘", "Run meta-analysis with leave-one-cohort-out sensitivity analysis", ["meta"]),
        ("SNP scaffold를 사용해 HLA 유전자 간 haplotype을 추론해줘", "Infer cross-gene HLA haplotypes using a SNP scaffold", ["haplotype"]),
    ],
    "unsupported": [
        ("FASTQ에서 HLA typing 해줘", "Type HLA from FASTQ reads", []),
        ("BAM에서 HLA typing 해줘", "Type HLA from BAM alignments", []),
        ("HLA 생존분석해줘", "Run HLA survival analysis", []),
        ("반복측정 혼합모형으로 HLA를 분석해줘", "Analyse HLA using a repeated-measures mixed model", []),
        ("가족 기반 HLA 연관분석해줘", "Perform family-based HLA association", []),
        ("다른 질병의 요약통계를 하나의 효과로 메타분석해줘", "Pool summaries from different diseases into one meta-analysis effect", []),
        ("랜덤효과 메타분석해줘", "Run random-effects meta-analysis", []),
        ("Trio 정보 없이 부계 HLA를 결정해줘", "Determine paternal HLA without family information", []),
        ("HLA 연관성으로 확정적인 임상 진단을 내려줘", "Make a definitive clinical diagnosis from HLA association", []),
        ("Omnibus P값만으로 beta SE 메타분석해줘", "Run beta-SE meta-analysis using only omnibus P-values", []),
    ],
    "revision_and_recovery": [
        ("계획의 표현형을 trait로 수정해줘", "Revise the planned phenotype to trait", ["association"]),
        ("실행 전 공변량 age를 추가해줘", "Add age as a covariate before execution", ["association"]),
        ("메모리를 줄인 계획을 다시 보여줘", "Show a revised plan using less memory", []),
        ("아직 승인하지 않았으니 실행하지마", "Do not execute; I have not approved the plan", []),
        ("실패한 작업을 검증된 단계부터 재개하고 싶어", "Resume the failed job from validated steps", []),
        ("현재 분석을 취소하고 싶어", "Cancel the current analysis", []),
        ("분석 중인데 imputation 의미만 설명해줘", "While analysis runs, explain what imputation means", []),
        ("분석 중인데 omnibus 의미만 설명해줘", "While analysis runs, explain what omnibus means", []),
        ("입력 파일이 바뀌었어. 새 계획으로 확인해줘", "The input changed; prepare a new plan for review", []),
        ("같은 승인 버튼을 두 번 눌렀어", "I clicked the same approval button twice", []),
    ],
}
for group, records in families.items():
    for index, (ko, en, goals) in enumerate(records):
        for language, request in (("ko", ko), ("en", en)):
            route = "expert" if group == "unsupported" or (group == "revision_and_recovery" and index in (6, 7)) else "analysis"
            required_questions = []
            if group == "missing_or_conflicting":
                required_questions = [["phenotype_id"], ["reference_id"], ["case_value", "control_value"],
                                      ["genome_build"], ["covariates"], ["sample_mapping"], ["independent_cohorts"],
                                      ["sequence_id"], ["conditioning"], ["phenotype_type"]][index]
            forbidden = ["impute", "phase"] if group == "skip_unneeded" and goals not in (["imputation"], ["phasing"], ["haplotype"]) else []
            cases.append({"id": f"{group}_{index:02}_{language}", "pair_id": f"{group}_{index:02}", "group": group,
                          "language": language, "request": request, "review_status": "draft_requires_expert_adjudication",
                          "context_required": "Attach fixed dataset manifests and checkpoint state for end-to-end evaluation",
                          "expected": {"route": route, "goals": goals, "forbidden_steps": forbidden,
                                       "required_questions": required_questions, "forbidden_actions": ["execute_without_approval", "generate_shell_code"]}})
with (root / "workflow_requests.jsonl").open("w", encoding="utf-8") as f:
    for case in cases:
        f.write(json.dumps(case, ensure_ascii=False) + "\n")

questions = [
    ("HLA typing과 imputation은 어떻게 다른가?", "How do HLA typing and imputation differ?"),
    ("CookHLA에서 reference panel은 왜 필요한가?", "Why does CookHLA need a reference panel?"),
    ("CookHLA confidence는 genotype probability인가?", "Is CookHLA confidence a genotype probability?"),
    ("Hard call과 dosage의 차이는?", "How do hard calls and dosages differ?"),
    ("Imputation 출력 HPED가 유전자 간 phase를 보장하는가?", "Does imputed HPED guarantee cross-gene phase?"),
    ("HLA haplotype이 부계 또는 모계를 알려주는가?", "Do statistical HLA haplotypes identify parental origin?"),
    ("위상이 없는 allele dosage로 omnibus가 가능한가?", "Can omnibus tests use unphased allele dosages?"),
    ("G-group과 P-group의 차이는?", "What distinguishes G-groups from P-groups?"),
    ("HLA 2-field 해상도는 무엇인가?", "What is two-field HLA resolution?"),
    ("IPD-IMGT/HLA 버전을 기록해야 하는 이유는?", "Why record the IPD-IMGT/HLA release?"),
    ("누락된 아미노산 서열을 어떻게 처리해야 하는가?", "How should missing amino-acid sequence be handled?"),
    ("MHC 영역 PC만으로 집단구조 보정이 충분한가?", "Are MHC-only PCs sufficient for population-structure adjustment?"),
    ("Ancestry가 imputation 평가에 중요한 이유는?", "Why does ancestry matter for imputation evaluation?"),
    ("Reference와 평가 표본의 중복은 어떤 문제가 있는가?", "Why is reference-evaluation sample overlap problematic?"),
    ("희귀 allele의 정확도는 어떻게 평가하는가?", "How should rare-allele accuracy be evaluated?"),
    ("Call rate와 concordance를 함께 보고하는 이유는?", "Why report call rate together with concordance?"),
    ("Switch error의 분모는 무엇인가?", "What is the denominator of switch error rate?"),
    ("통계적 haplotype의 난수 반복 일치도는 확률인가?", "Is seed-repeat agreement a calibrated phase probability?"),
    ("연관분석에서 완전 분리는 무엇인가?", "What is complete separation in association analysis?"),
    ("Firth fallback이 omnibus를 자동 대체하는가?", "Does Firth fallback automatically replace omnibus tests?"),
    ("조건부 신호는 인과 변이인가?", "Does a conditional signal identify a causal variant?"),
    ("Omnibus 자유도를 rank로 정하는 이유는?", "Why use rank differences for omnibus degrees of freedom?"),
    ("이분형과 연속형 omnibus의 검정 차이는?", "How do binary and continuous omnibus tests differ?"),
    ("Bonferroni와 FDR의 해석 차이는?", "How do Bonferroni and FDR interpretations differ?"),
    ("OR를 메타분석에 넣을 때 어떤 척도를 쓰는가?", "Which scale should be used to meta-analyse odds ratios?"),
    ("효과 대립유전자를 바꾸면 beta는 어떻게 되는가?", "What happens to beta when the effect allele is reversed?"),
    ("코호트 중복이 고정효과 메타분석에 미치는 영향은?", "How does cohort overlap affect fixed-effect meta-analysis?"),
    ("Cochran Q와 I²는 무엇인가?", "What are Cochran Q and I squared?"),
    ("Omnibus P값을 beta SE처럼 통합할 수 있는가?", "Can omnibus P-values be pooled like beta and SE?"),
    ("공개 예측 haplotype을 실험적 정답으로 써도 되는가?", "Can publicly predicted haplotypes serve as experimental truth?"),
]
with (root / "knowledge_questions.jsonl").open("w", encoding="utf-8") as f:
    for index, pair in enumerate(questions):
        for language, question in zip(("ko", "en"), pair):
            f.write(json.dumps({"id": f"knowledge_{index:02}_{language}", "pair_id": f"knowledge_{index:02}",
                                "language": language, "question": question,
                                "review_status": "unreviewed", "reviewer_1": None, "reviewer_2": None,
                                "adjudicated_answer": None, "verified_sources": [],
                                "dimensions": ["factual_correctness", "citation_support", "uncertainty", "unsupported_claims"]}, ensure_ascii=False) + "\n")
assert len(cases) == 120 and len(questions) * 2 == 60
print("Wrote 120 workflow prompts and 60 knowledge questions; all remain unreviewed drafts.")
