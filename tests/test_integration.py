import shutil
from pathlib import Path

import pandas as pd
import pytest

from hlagent.adapters import beagle
from hlagent.data import decode_hla_vcf, load_hla, write_hla_vcf
from hlagent.execution import Runner
from hlagent.fixtures import create_demo
from hlagent.models import AnalysisIntent, AnalysisOptions, PlanApproval
from hlagent.planning import build_plan
from hlagent.worker import Worker


@pytest.mark.integration
def test_real_plink_and_report_pipeline(store, settings):
    if not shutil.which(settings.plink2):
        pytest.skip("PLINK 2 not installed")
    demo = create_demo(store, settings.home)
    plan = build_plan(demo["project"]["id"], AnalysisIntent.model_validate(demo["intent"]),
                      store.datasets(demo["project"]["id"]), AnalysisOptions(), settings)
    store.put_plan(plan)
    job = store.approve(PlanApproval(plan_id=plan.id, plan_hash=plan.plan_hash, revision=plan.revision))
    Worker(settings).run_once()
    assert store.job(job.id).state == "succeeded", store.job(job.id).error
    artifacts = store.artifacts(job.id)
    report = next(a for a in artifacts if a.label == "report.html")
    assert "Statistical observation unit: individual" in Path(report.path).read_text()
    result = next(a for a in artifacts if a.label == "association.tsv")
    frame = pd.read_csv(result.path, sep="\t")
    assert frame.p.notna().sum() > 0
    assert frame["n"].dropna().eq(240).all()
    assert frame.loc[frame.marker == "HLA_A*01:01", "beta"].iloc[0] > 0


@pytest.mark.integration
def test_real_beagle_multiallelic_roundtrip(store, settings, tmp_path):
    if not shutil.which(settings.java) or not settings.beagle_jar:
        pytest.skip("Java/Beagle not installed")
    demo = create_demo(store, settings.home, n=100)
    calls = load_hla(Path(store.datasets(demo["project"]["id"])[0].files[0].path))
    directory = tmp_path / "phase"
    directory.mkdir()
    vcf = directory / "hla.vcf"
    book = write_hla_vcf(calls, vcf)
    output = beagle(Runner(directory), settings, vcf, AnalysisOptions(threads=1, memory_gb=1))
    phased = decode_hla_vcf(output, book, calls)
    assert len(phased) == len(calls)
