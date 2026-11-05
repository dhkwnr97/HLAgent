"""Build the per-step planning benchmark (tasks.json).

Step categories follow the analysis steps of an HLA study:
(i) HLA imputation; (ii) fine-mapping: logistic regression, stepwise conditional regression, omnibus test,
meta-analysis; (iii) visualization; (iv) phasing. Two further categories test workflow customisation
(the 21 workflow requests used to evaluate HLAgent v1, now bound to a dataset) and clarification
(requests that must not be executed without asking the user).

Each task gives the expected behaviour and, for 'propose' tasks, the expected datasets, nodes, phenotype
handling and parameters. Scoring compares the *resolved* execution graph (what the engine would run),
so equivalent plans (e.g. "Node2" vs "Node1+Node2") count as the same plan.

Tasks with lang="ko" are written in Korean on purpose: they test that requests in Korean are planned
as well as requests in English.
"""

from __future__ import annotations

import json
from pathlib import Path

WTCCC = {"dataset_id": "WTCCC_RA", "phenotype": ["file"]}
NBS = {"dataset_id": "NBS_CD", "phenotype": ["file"]}
BM_DEMO = {"dataset_id": "BMExample", "phenotype": ["synthetic_spike_in", "synthetic_null"]}
GE_DEMO = {"dataset_id": "GenotypeExample", "phenotype": ["synthetic_null"]}
GE_ANY = {"dataset_id": "GenotypeExample", "phenotype": ["file", "synthetic_null", "synthetic_spike_in"]}


def T(tid, step, lang, prompt, behavior="propose", studies=None, nodes=None, accept=None, params=None):
    t = {"id": tid, "step": step, "lang": lang, "prompt": prompt, "behavior": behavior}
    if behavior == "propose":
        t.update(
            {"studies": studies, "nodes": nodes, "accept_nodes": accept or [nodes], "params": params or {}}
        )
    return t


V1_QUERIES = [
    "My workflow starts at node 1 -> then node 2 -> node 3 -> and ends at node 4.",
    "The process goes from node 1 -> node 2 -> node 3 -> and finishes at node 4.",
    "I want the flow to go like this: 1 -> 2 -> 3 -> 4.",
    "Start at 1 -> move to 2 -> then 3 -> and wrap up at 4.",
    "From node 1 -> we pass through node 2 and node 3 -> and land at node 4.",
    "My process begins at 1 -> goes to 2 -> then 3 -> and stops at 4.",
    "The path is node 1 -> node 2 -> node 3 -> node 4.",
    "First node is 1, last node is 4, and in between are 2 and 3.",
    "The last step is node 4, the first step is node 1, and the middle steps are 2 and 3.",
    "In my workflow, 1 kicks things off, 4 is the finish line, and 2 and 3 happen in the middle.",
    "It starts at 1, goes through 2 and 3, and finishes with 4.",
    "The process begins at node 1, passes node 2, continues to node 3, and ends at node 4.",
    "The first node is 1, after that 2 and 3 come in, and finally node 4 wraps it up.",
    "My workflow’s first step is node 1, last step is node 4, and 2 and 3 fill the gap.",
    "The order is: start at 1, then 2, then 3, and end with 4.",
    "My chain runs from 1 -> 2 -> 3 -> 4 without skipping any steps.",
    "The flow kicks off with 1, passes 2 and 3, and lands at 4.",
    "First node is 1, then you go to 2, then 3, and finally 4.",
    "My sequence is 1 -> 2 -> 3 -> 4 in a straight line.",
    "In this workflow, the start point is 1, the end point is 4, and 2 and 3 are right in the middle.",
    "I want node1, then node2, then node3, then node4",
]
N14 = ["Node1", "Node2", "Node3", "Node4"]

tasks = [
    # (i) HLA imputation: GenotypeExample has SNP genotypes only, so Stage I (CookHLA) must be added
    T(
        "imp-en-1",
        "imputation",
        "en",
        "GenotypeExample only has SNP array genotypes. Impute the classical HLA alleles "
        "with CookHLA and build the HLA binary marker panel.",
        studies=[GE_ANY],
        nodes=["Node1"],
    ),
    T(
        "imp-en-2",
        "imputation",
        "en",
        "Please impute HLA types for GenotypeExample using the East Asian (EAS) 1000 "
        "Genomes reference panel, then build the marker panel.",
        studies=[GE_ANY],
        nodes=["Node1"],
        params={"reference_population": "EAS"},
    ),
    T(
        "imp-ko-1",
        "imputation",
        "ko",
        "GenotypeExample은 SNP 데이터만 있어. CookHLA로 HLA imputation 해서 marker panel까지 만들어 줘.",
        studies=[GE_ANY],
        nodes=["Node1"],
    ),
    # (ii-a) logistic regression
    T(
        "assoc-en-1",
        "regression",
        "en",
        "Run a logistic regression of rheumatoid arthritis on all HLA markers in WTCCC_RA.",
        studies=[WTCCC],
        nodes=["Node2"],
        accept=[["Node2"], ["Node1", "Node2"]],
    ),
    T(
        "assoc-en-2",
        "regression",
        "en",
        "Which HLA alleles and amino acids are associated with RA in the WTCCC_RA "
        "cohort? I only need the marker-level association test.",
        studies=[WTCCC],
        nodes=["Node2"],
        accept=[["Node2"], ["Node1", "Node2"]],
    ),
    T(
        "assoc-ko-1",
        "regression",
        "ko",
        "WTCCC_RA에서 RA와 연관된 HLA 마커를 찾는 회귀분석만 돌려줘.",
        studies=[WTCCC],
        nodes=["Node2"],
        accept=[["Node2"], ["Node1", "Node2"]],
    ),
    # (ii-b) stepwise conditional regression
    T(
        "cond-en-1",
        "conditional",
        "en",
        "In WTCCC_RA, identify independent HLA association signals for RA with "
        "stepwise conditional regression.",
        studies=[WTCCC],
        nodes=["Node3"],
        accept=[["Node3"], ["Node1", "Node3"], ["Node2", "Node3"], ["Node1", "Node2", "Node3"]],
    ),
    T(
        "cond-ko-1",
        "conditional",
        "ko",
        "WTCCC_RA에서 조건부 회귀분석으로 독립적인 신호가 몇 개인지 찾아줘.",
        studies=[WTCCC],
        nodes=["Node3"],
        accept=[["Node3"], ["Node1", "Node3"], ["Node2", "Node3"], ["Node1", "Node2", "Node3"]],
    ),
    # (ii-c) omnibus test (phasing is added by the engine)
    T(
        "omni-en-1",
        "omnibus",
        "en",
        "Test every HLA amino-acid position for association with RA in WTCCC_RA using the omnibus test.",
        studies=[WTCCC],
        nodes=["Node4"],
        accept=[["Node4"], ["Node1", "Node4"]],
    ),
    T(
        "omni-en-2",
        "omnibus",
        "en",
        "Run the omnibus test in WTCCC_RA conditioned on HLA-DRB1 amino-acid position 96 (AA_DRB1_96).",
        studies=[WTCCC],
        nodes=["Node4"],
        accept=[["Node4"], ["Node1", "Node4"]],
        params={"omnibus_conditions": ["AA_DRB1_96"]},
    ),
    T(
        "omni-ko-1",
        "omnibus",
        "ko",
        "WTCCC_RA에서 아미노산 위치별 omnibus 검정을 해줘.",
        studies=[WTCCC],
        nodes=["Node4"],
        accept=[["Node4"], ["Node1", "Node4"]],
    ),
    # (ii-d) meta-analysis
    T(
        "meta-en-1",
        "meta-analysis",
        "en",
        "Meta-analyze the RA association in WTCCC_RA together with the Crohn's "
        "disease summary statistics in NBS_CD.",
        studies=[WTCCC, NBS],
        nodes=["Node5"],
        accept=[["Node5"], ["Node2", "Node5"], ["Node1", "Node2", "Node5"]],
    ),
    T(
        "meta-en-2",
        "meta-analysis",
        "en",
        "Combine BMExample and GenotypeExample in a meta-analysis; demo "
        "(synthetic) phenotypes are fine because neither has a real phenotype.",
        studies=[BM_DEMO, GE_DEMO],
        nodes=["Node5"],
        accept=[["Node5"], ["Node2", "Node5"], ["Node1", "Node2", "Node5"]],
    ),
    T(
        "meta-ko-1",
        "meta-analysis",
        "ko",
        "WTCCC_RA 결과랑 NBS_CD 요약통계로 메타분석 해줘.",
        studies=[WTCCC, NBS],
        nodes=["Node5"],
        accept=[["Node5"], ["Node2", "Node5"], ["Node1", "Node2", "Node5"]],
    ),
    # (iii) visualization (Manhattan, QQ and heatmaps are produced by Node2 and the report)
    T(
        "viz-en-1",
        "visualization",
        "en",
        "Show me a Manhattan plot and the HLA-DRB1 amino-acid heatmap for RA in WTCCC_RA.",
        studies=[WTCCC],
        nodes=["Node2"],
        accept=[["Node2"], ["Node1", "Node2"]],
    ),
    T(
        "viz-ko-1",
        "visualization",
        "ko",
        "WTCCC_RA의 연관분석 결과를 맨해튼 플롯과 히트맵으로 보고 싶어.",
        studies=[WTCCC],
        nodes=["Node2"],
        accept=[["Node2"], ["Node1", "Node2"]],
    ),
    # (iv) phasing (BEAGLE haplotypes feed the amino-acid omnibus test)
    T(
        "phase-en-1",
        "phasing",
        "en",
        "I need phased HLA haplotypes for WTCCC_RA so that I can test amino-acid haplotypes for RA.",
        studies=[WTCCC],
        nodes=["Node4"],
        accept=[["Node4"], ["Node1", "Node4"]],
    ),
    T(
        "phase-ko-1",
        "phasing",
        "ko",
        "WTCCC_RA marker panel을 BEAGLE로 phasing 해서 아미노산 단위 분석까지 해줘.",
        studies=[WTCCC],
        nodes=["Node4"],
        accept=[["Node4"], ["Node1", "Node4"]],
    ),
    # parameter extraction
    T(
        "par-en-1",
        "parameters",
        "en",
        "Use 1-field (2-digit) HLA allele resolution for the association test in WTCCC_RA.",
        studies=[WTCCC],
        nodes=["Node2"],
        accept=[["Node2"], ["Node1", "Node2"]],
        params={"hla_resolution": "1field"},
    ),
    T(
        "par-en-2",
        "parameters",
        "en",
        "BMExample has no phenotype. Run Node1 to Node4 as a demonstration with a "
        "synthetic phenotype in which HLA-DRB1*15:01 carries an odds ratio of 3.",
        studies=[BM_DEMO],
        nodes=N14,
        params={"spike_allele": "DRB1*15:01", "spike_odds_ratio": 3.0},
    ),
    # workflow customisation: the 21 queries of the original Supplementary Table 1, bound to a dataset
    *[
        T(f"wf-v1-{i:02d}", "workflow", "en", f"Using WTCCC_RA: {q}", studies=[WTCCC], nodes=N14)
        for i, q in enumerate(V1_QUERIES, 1)
    ],
    T(
        "wf-en-trunc",
        "workflow",
        "en",
        "For WTCCC_RA, stop after node 2.",
        studies=[WTCCC],
        nodes=["Node1", "Node2"],
        accept=[["Node1", "Node2"], ["Node2"]],
    ),
    T(
        "wf-en-all",
        "workflow",
        "en",
        "Run the complete HLA fine-mapping pipeline on WTCCC_RA and then meta-analyze it with NBS_CD.",
        studies=[WTCCC, NBS],
        nodes=["Node1", "Node2", "Node3", "Node4", "Node5"],
    ),
    T(
        "wf-ko-1",
        "workflow",
        "ko",
        "WTCCC_RA로 Node1부터 Node4까지 순서대로 해줘.",
        studies=[WTCCC],
        nodes=N14,
    ),
    # clarification: must not be executed as asked
    T("clar-en-1", "clarification", "en", "Run the HLA fine-mapping on my cohort.", behavior="clarify"),
    T(
        "clar-en-2",
        "clarification",
        "en",
        "Run the association analysis on BMExample using its real phenotype.",
        behavior="clarify",
    ),
    T("clar-ko-1", "clarification", "ko", "내 데이터로 분석해줘.", behavior="clarify"),
]

ROUTING = [
    *[
        {"id": f"route-qa-{i}", "text": t, "intent": "ask_hla"}
        for i, t in enumerate(
            [
                "Please answer briefly: Is HLA-DRB1 associated with RA?",
                "What is the shared epitope hypothesis in rheumatoid arthritis?",
                "How does CookHLA differ from SNP2HLA?",
                "Why are amino-acid omnibus tests used in MHC fine-mapping?",
                "HLA-B27이 강직성 척추염과 연관된 기전이 뭐야?",
                "What does an I-squared of 60% mean in an HLA meta-analysis?",
                "Explain the difference between 2-field and 4-field HLA nomenclature.",
                "Which amino acids of HLA-DQB1 are linked to type 1 diabetes?",
            ],
            1,
        )
    ],
    *[
        {"id": f"route-an-{i}", "text": t, "intent": "request_analysis"}
        for i, t in enumerate(
            [
                "Run a logistic regression on WTCCC_RA.",
                "Impute HLA alleles for GenotypeExample.",
                "WTCCC_RA로 omnibus 검정 해줘.",
                "Meta-analyze WTCCC_RA with NBS_CD.",
                "Build the HLA marker panel for BMExample.",
                "Please run node 1 to node 3 on WTCCC_RA.",
            ],
            1,
        )
    ],
]

out = Path(__file__).with_name("tasks.json")
out.write_text(
    json.dumps({"version": 1, "planning": tasks, "routing": ROUTING}, ensure_ascii=False, indent=1)
)
cats = {}
for t in tasks:
    cats[t["step"]] = cats.get(t["step"], 0) + 1
print(len(tasks), "planning tasks", cats, "|", len(ROUTING), "routing items")
