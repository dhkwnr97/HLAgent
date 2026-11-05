import numpy as np
import pandas as pd
import pytest
from scipy import stats

from hlagent.statistics import fixed_effect, meta_analysis, omnibus, reference_regression


def designs():
    d = dict(phenotype="trait", phenotype_type="continuous", effect_scale="mean_difference", unit="x",
             genome_build="GRCh37", resolution="2-field", imgt_release="test", conditioning=[], covariates=[], strand="forward")
    return [{**d, "cohort": "a"}, {**d, "cohort": "b"}, {**d, "cohort": "c"}]


def summary(beta=.2, reverse=False):
    return pd.DataFrame([dict(marker="HLA_A*01:01", effect_allele="absent" if reverse else "present",
                              other_allele="present" if reverse else "absent", beta=beta, se=.1)])


def test_meta_analytical_solution_and_direction():
    a = fixed_effect(np.array([.2, .4]), np.array([.1, .1]))
    assert a["beta"] == pytest.approx(.3)
    assert a["se"] == pytest.approx(.1 / np.sqrt(2))
    out, leave = meta_analysis([summary(.2), summary(-.4, True), summary(.3)], designs(), True)
    assert out.iloc[0].beta == pytest.approx(.3)
    assert out.iloc[0].k == 3
    assert len(leave) == 3


@pytest.mark.parametrize("key", ["phenotype", "unit", "effect_scale", "resolution", "conditioning"])
def test_meta_rejects_incompatible_design(key):
    d = designs()[:2]
    d[1][key] = "different"
    with pytest.raises(ValueError, match="Incomparable"):
        meta_analysis([summary(), summary()], d, True)


def test_meta_rejects_overlap_and_bad_se():
    d = designs()[:2]
    d[0]["sample_hashes"] = d[1]["sample_hashes"] = ["same"]
    with pytest.raises(ValueError, match="overlap"):
        meta_analysis([summary(), summary()], d, True)
    f = summary()
    f["se"] = 0
    with pytest.raises(ValueError, match="positive"):
        meta_analysis([f, summary()], designs()[:2], True)


def test_omnibus_equals_nested_ols_f_test():
    rng = np.random.default_rng(7)
    x = rng.binomial(2, .4, 500).astype(float)
    y = .5 * x + rng.normal(size=500)
    markers = pd.DataFrame({"r0": 2 - x, "r1": x})
    metadata = pd.DataFrame([dict(marker="r0", kind="AA", locus="A", position="11", effect_allele="A"),
                             dict(marker="r1", kind="AA", locus="A", position="11", effect_allele="V")])
    out = omnibus(markers, y, pd.DataFrame(index=range(500)), metadata, False, [], 20).iloc[0]
    reference = reference_regression(y, x, np.empty((500, 0)), False)
    assert out.status == "ok"
    assert out["n"] == 500
    assert out.df == 1
    assert out.p == pytest.approx(reference["p"], rel=1e-9)


def test_logistic_omnibus_and_sparse_failure():
    rng = np.random.default_rng(17)
    x = rng.binomial(2, .3, 1000).astype(float)
    y = rng.binomial(1, 1 / (1 + np.exp(-(-1 + .5 * x))))
    metadata = pd.DataFrame([dict(marker="r0", kind="AA", locus="A", position="11", effect_allele="A"),
                             dict(marker="r1", kind="AA", locus="A", position="11", effect_allele="V")])
    markers = pd.DataFrame({"r0": 2 - x, "r1": x})
    out = omnibus(markers, y, pd.DataFrame(index=range(1000)), metadata, True, [], 20).iloc[0]
    import statsmodels.api as sm
    null = sm.GLM(y, np.ones((1000, 1)), family=sm.families.Binomial()).fit()
    full = sm.GLM(y, sm.add_constant(x), family=sm.families.Binomial()).fit()
    assert out.p == pytest.approx(stats.chi2.sf(2 * (full.llf - null.llf), 1), rel=1e-8)
    out = omnibus(markers, y, pd.DataFrame(index=range(1000)), metadata, True, [], 10000).iloc[0]
    assert out.status == "failed"
    assert pd.isna(out.p)
