import shutil
from pathlib import Path

import pandas as pd
import pytest

from hlagent.adapters import beagle
from hlagent.data import decode_hla_vcf, load_hla, scaffold_hla_vcf, validate_snp_phasing
from hlagent.evaluation import phase_accuracy
from hlagent.execution import Runner
from hlagent.fixtures import create_demo
from hlagent.models import AnalysisIntent, AnalysisOptions, Goal, PlanApproval
from hlagent.planning import build_plan
from hlagent.worker import Worker
from hlagent.workflow import Workflow


@pytest.mark.integration
@pytest.mark.parametrize("mode", ["binary", "conditional", "stepwise", "meta", "haplotype"])
def test_supported_pipeline_modes(store, settings, mode):
    if not shutil.which(settings.plink2) or not settings.beagle_jar:
        pytest.skip("Bioinformatics tools not installed")
    demo = create_demo(store, settings.home)
    intent = AnalysisIntent.model_validate(demo["intent"])
    if mode == "binary":
        intent.phenotype_type, intent.phenotype_column = "binary", "case"
        intent.case_value, intent.control_value = "1", "0"
    if mode == "conditional":
        intent.goals = [Goal.conditional]
        intent.conditioning = ["HLA_A*01:01"]
    if mode == "stepwise":
        intent.goals = [Goal.stepwise]
    if mode == "meta":
        intent = AnalysisIntent(goals=[Goal.meta], dataset_ids=demo["summary_ids"], independent_cohorts=True)
    if mode == "haplotype":
        intent.goals = [Goal.haplotype, Goal.association]
        intent.haplotype_loci = ["A", "B", "DRB1"]
    plan = build_plan(demo["project"]["id"], intent, store.datasets(demo["project"]["id"]),
                      AnalysisOptions(threads=1, memory_gb=1, max_steps=3), settings)
    store.put_plan(plan)
    job = store.approve(PlanApproval(plan_id=plan.id, plan_hash=plan.plan_hash, revision=plan.revision))
    Worker(settings).run_once()
    assert store.job(job.id).state == "succeeded", store.job(job.id).error
    assert any(a.label == "report.html" for a in store.artifacts(job.id))
    if mode == "meta":
        artifact = next(a for a in store.artifacts(job.id) if a.label == "meta.tsv")
        assert pd.read_csv(artifact.path, sep="\t").k.eq(3).all()


def test_revised_plan_needs_new_exact_approval(store, settings):
    demo = create_demo(store, settings.home)
    flow = Workflow(settings, store)
    first = flow.start(demo["project"]["id"], AnalysisIntent.model_validate(demo["intent"]), AnalysisOptions())
    old = first["pending"][0]
    revised = flow.resume(demo["project"]["id"], first["conversation_id"],
                          {"action": "revise", "options": {"memory_gb": 2}})
    current = revised["pending"][0]
    assert current["revision"] == 2 and current["plan_hash"] != old["plan_hash"]
    assert revised["state"]["changes"]["options.memory_gb"] == {"before": 4, "after": 2}
    assert not store.jobs()
    flow.close()


@pytest.mark.integration
def test_real_beagle_snp_scaffold_preserves_both_data_types(store, settings, tmp_path):
    if not settings.beagle_jar:
        pytest.skip("Beagle not installed")
    demo = create_demo(store, settings.home, n=100)
    calls_path = Path(store.datasets(demo["project"]["id"])[0].files[0].path)
    calls = load_hla(calls_path)
    samples = sorted(calls.IID.unique())
    snp = tmp_path / "snp.vcf"
    header = ['##fileformat=VCFv4.3', '##contig=<ID=6>',
              '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">',
              '#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\t' + '\t'.join(samples)]
    for i in range(12):
        header.append(f'6\t{29000000 + i * 10000}\trs{i}\tA\tC\t.\tPASS\t.\tGT\t' +
                      '\t'.join(['0/0', '0/1', '1/1'][(j + i) % 3] for j in range(len(samples))))
    snp.write_text('\n'.join(header) + '\n')
    vcf = tmp_path / "combined.vcf"
    book = scaffold_hla_vcf(calls, snp, vcf, {"A": 30000000, "B": 31000000, "DRB1": 32000000}, "GRCh37")
    output = beagle(Runner(tmp_path), settings, vcf, AnalysisOptions(threads=1, memory_gb=1))
    validate_snp_phasing(vcf, output)
    phased = decode_hla_vcf(output, book, calls)
    assert len(phased) == len(calls)
    truth = pd.read_csv(calls_path.with_name("synthetic_phase_truth.tsv"), sep="\t")
    accuracy = phase_accuracy(truth, phased, ["A", "B", "DRB1"])
    assert accuracy["genotype_mismatches"] == 0
    assert accuracy["complete_haplotype_pairs"] == 100


def test_switch_metric_ignores_global_orientation():
    truth = pd.DataFrame({"FID": ["a"] * 3, "IID": ["a"] * 3, "locus": ["A", "B", "C"],
                          "haplotype1": ["a", "b", "c"], "haplotype2": ["d", "e", "f"]})
    flipped = truth.copy()
    flipped[["haplotype1", "haplotype2"]] = truth[["haplotype2", "haplotype1"]].to_numpy()
    result = phase_accuracy(truth, flipped, ["A", "B", "C"])
    assert result["switch_error_rate"] == 0 and result["haplotype_pair_concordance"] == 1
