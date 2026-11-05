"""Demo-only synthetic phenotypes (plan section 6.7).

null:     Y ~ Bernoulli(case_fraction), independent of genotype.
spike_in: logit P(Y=1) = b0 + ln(OR) * x, x = dosage (0/1/2) of a chosen HLA allele;
          b0 solved by bisection so that mean P(Y=1) = case_fraction.
Output coding is PLINK binary: 2 = case, 1 = control. Results are SYNTHETIC and carry no biology.
"""

from __future__ import annotations

import math
import re

import numpy as np
import pandas as pd

from hlagent.pipeline.contracts import SyntheticPhenotype

_FIELDS = re.compile(r"^(?:HLA-)?([A-Z0-9]+)\*?(.*)$")


def allele_fields(allele: str) -> tuple[str | None, list[str]]:
    """'DRB1*15:01:01:01' -> ('DRB1', ['15','01','01','01']); '1501' (HPED 4-digit) -> (None, ['15','01'])."""
    a = allele.strip()
    if a in ("", "0", "-9", "NA"):
        return None, []
    if "*" in a:
        gene, rest = a.split("*", 1)
        return gene.upper(), [f for f in re.split(r"[:]", rest) if f]
    if ":" in a:
        return None, a.split(":")
    if a.isdigit() and len(a) in (4, 6, 8):
        return None, [a[i : i + 2] for i in range(0, len(a), 2)]
    return None, [a]


def allele_dosage(hla: pd.DataFrame, allele: str) -> pd.Series:
    """Count copies (0/1/2) of `allele` (e.g. 'DRB1*15:01') per row of an HPED/CHPED frame."""
    gene, fields = allele_fields(allele)
    if gene is None or not fields:
        raise ValueError("allele must look like GENE*XX:YY")
    cols = [c for c in hla.columns[6:] if c.rsplit("_", 1)[0].upper() == gene]
    if len(cols) != 2:
        raise ValueError(f"gene {gene} not found in HLA table columns {list(hla.columns[6:])}")

    def matches(v: str) -> int:
        _, f = allele_fields(str(v))
        return int(len(f) >= len(fields) and f[: len(fields)] == fields)

    return hla[cols[0]].map(matches) + hla[cols[1]].map(matches)


def _expit(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def solve_intercept(x: np.ndarray, beta: float, target: float) -> float:
    lo, hi = -30.0, 30.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if _expit(mid + beta * x).mean() < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def generate(
    ids: pd.DataFrame, spec: SyntheticPhenotype, dosage: pd.Series | None = None
) -> tuple[pd.DataFrame, dict]:
    """Return (FID IID <name> table, metadata)."""
    rng = np.random.default_rng(spec.seed)
    n = len(ids)
    meta: dict = {"mode": spec.mode, "seed": spec.seed, "n": n, "case_fraction_target": spec.case_fraction}
    if spec.mode == "null":
        y = rng.random(n) < spec.case_fraction
    else:
        if dosage is None:
            raise ValueError("spike_in needs HLA types to compute allele dosage")
        x = dosage.to_numpy(dtype=float)
        beta = math.log(spec.odds_ratio)
        b0 = solve_intercept(x, beta, spec.case_fraction)
        p = _expit(b0 + beta * x)
        y = rng.random(n) < p
        meta.update(
            {
                "allele": spec.allele,
                "odds_ratio": spec.odds_ratio,
                "beta": beta,
                "intercept": b0,
                "allele_frequency": float(x.mean() / 2),
                "carriers": int((x > 0).sum()),
            }
        )
    out = ids[["FID", "IID"]].copy()
    out[spec.name] = np.where(y, 2, 1)
    meta["n_cases"] = int(y.sum())
    meta["n_controls"] = int(n - y.sum())
    return out, meta
