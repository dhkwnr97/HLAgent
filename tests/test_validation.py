import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from hlagent.adapters import attach_cookhla_scores, plink_association
from hlagent.data import dosage_markers, hla_markers, load_dosages, load_hla
from hlagent.execution import Runner
from hlagent.fixtures import create_demo
from hlagent.models import AnalysisIntent, AnalysisOptions
from hlagent.statistics import fixed_effect, prepare_design, reference_regression


@pytest.mark.integration
def test_metafor_independent_numerical_agreement(tmp_path):
    if not shutil.which("Rscript"):
        pytest.skip("R/metafor not installed")
    script = tmp_path / "meta.R"
    output = tmp_path / "result.tsv"
    script.write_text("library(metafor)\nm <- rma(yi=c(.2,-.1,.5), sei=c(.1,.2,.15), method='FE')\n"
                      "write.table(data.frame(beta=as.numeric(m$b),se=m$se,p=m$pval,Q=m$QE,I2=m$I2), "
                      "commandArgs(TRUE)[1],sep='\\t',row.names=FALSE)\n")
    subprocess.run(["Rscript", str(script), str(output)], check=True, capture_output=True)
    actual = fixed_effect(np.array([.2, -.1, .5]), np.array([.1, .2, .15]))
    expected = pd.read_csv(output, sep="\t").iloc[0]
    for key in ("beta", "se", "p", "Q", "I2"):
        assert actual[key] == pytest.approx(expected[key], rel=1e-10, abs=1e-12)


@pytest.mark.integration
@pytest.mark.parametrize("binary", [True, False])
def test_real_plink_matches_independent_regression(store, settings, tmp_path, binary):
    if not shutil.which(settings.plink2):
        pytest.skip("PLINK2 not installed")
    demo = create_demo(store, settings.home)
    data = store.datasets(demo["project"]["id"])
    calls = load_hla(Path(data[0].files[0].path))
    markers, metadata = hla_markers(calls)
    intent = AnalysisIntent.model_validate(demo["intent"])
    intent.phenotype_type = "binary" if binary else "continuous"
    intent.phenotype_column = "case" if binary else "trait"
    intent.case_value, intent.control_value = "1", "0"
    phenotype = pd.read_csv(data[1].files[0].path, sep="\t", dtype=str)
    m, y, c, _ = prepare_design(markers, phenotype, intent)
    result = plink_association(Runner(tmp_path / "plink"), settings, m, y, c, metadata, intent, AnalysisOptions())
    actual = result.set_index("marker").loc["HLA_A*01:01"]
    expected = reference_regression(y, m["HLA_A*01:01"].to_numpy(), c.to_numpy(), binary)
    for key in ("beta", "se", "p"):
        assert actual[key] == pytest.approx(expected[key], rel=3e-5, abs=1e-8)


def test_dosage_preservation_and_incomplete_locus_rejection(tmp_path):
    path = tmp_path / "dosage.tsv"
    pd.DataFrame({"IID": ["a", "a", "b", "b"], "locus": ["A"] * 4,
                  "allele": ["A*01:01", "A*02:01"] * 2, "dosage": [.3, 1.7, .9, 1.1]}).to_csv(path, sep="\t", index=False)
    frame = load_dosages(path)
    markers, _ = dosage_markers(frame)
    assert markers["HLA_A*01:01"].tolist() == [.3, .9]
    frame.iloc[:-1].to_csv(path, sep="\t", index=False)
    with pytest.raises(ValueError, match="sum to two"):
        load_dosages(path)


def test_cookhla_confidence_is_preserved_not_normalized(tmp_path):
    calls = pd.DataFrame([dict(FID="a", IID="a", locus="A", allele1="A*01:01", allele2="A*02:01")])
    path = tmp_path / "test.alleles"
    path.write_text("a a A 01,02 0101,0201 0.7 0.8 1.5\n")
    result = attach_cookhla_scores(calls, path)
    assert result.confidence.iloc[0] == 1.5
    assert "dosage" not in result


def test_cookhla_uncalled_unsupported_locus_may_have_no_score(tmp_path):
    calls = pd.DataFrame([dict(FID="a", IID="a", locus="A", allele1="A*01:01", allele2="A*02:01"),
                          dict(FID="a", IID="a", locus="DPB1", allele1=None, allele2=None)])
    path = tmp_path / "test.alleles"
    path.write_text("a a A 01,02 0101,0201 0.4 0.5 0.9\n")
    result = attach_cookhla_scores(calls, path)
    assert pd.isna(result.loc[result.locus.eq("DPB1"), "confidence"].iloc[0])
