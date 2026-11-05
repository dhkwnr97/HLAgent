"""Meta-analysis formulas (plan section 6.5) and allele harmonisation."""

from __future__ import annotations

import numpy as np
import pytest

from hlagent.stats.meta import _align, fixed_and_random


def test_reference_values_two_studies():
    r = fixed_and_random(np.array([[0.40, 0.10]]), np.array([[0.10, 0.20]]))
    expected = {
        "BETA_FE": 0.34,
        "SE_FE": 0.0894427191,
        "Z_FE": 3.8013155617,
        "P_FE": 1.4392985650e-4,
        "Q": 1.8,
        "P_Q": 0.1797124949,
        "I2": 0.4444444444,
        "TAU2": 0.02,
        "BETA_RE": 0.30,
        "SE_RE": 0.1414213562,
        "P_RE": 3.3894853525e-2,
    }
    for k, v in expected.items():
        assert r[k][0] == pytest.approx(v, rel=1e-8), k


def test_identical_studies_have_no_heterogeneity():
    r = fixed_and_random(np.array([[0.2, 0.2, 0.2]]), np.array([[0.1, 0.1, 0.1]]))
    assert r["Q"][0] == pytest.approx(0.0)
    assert r["I2"][0] == 0.0
    assert r["TAU2"][0] == 0.0
    assert r["BETA_RE"][0] == pytest.approx(r["BETA_FE"][0])
    assert r["SE_FE"][0] == pytest.approx(0.1 / np.sqrt(3))


@pytest.mark.parametrize(
    ("ref", "study", "expected"),
    [
        (("A", "G"), ("A", "G"), (1, False)),  # same orientation
        (("A", "G"), ("G", "A"), (-1, False)),  # swapped -> flip beta
        (("A", "G"), ("T", "C"), (1, True)),  # strand complement
        (("A", "G"), ("C", "T"), (-1, True)),  # complement + swap
        (("A", "G"), ("A", "C"), None),  # irreconcilable
        (("p", "a"), ("a", "p"), (-1, False)),  # HATK binary marker swapped
        (("p", "a"), ("t", "a"), None),  # binary markers are never complemented
    ],
)
def test_align(ref, study, expected):
    assert _align(ref[0], ref[1], study[0], study[1]) == expected


def test_align_without_other_allele_only_accepts_same_effect_allele():
    assert _align("A", None, "A", None) == (1, False)
    assert _align("A", None, "G", None) is None
