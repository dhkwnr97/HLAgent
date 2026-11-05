"""Helpers shared by pipeline steps."""

from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd

from hlagent import paths
from hlagent.io.formats import read_fam

REF_TEMPLATE = "1000G_REF.{pop}.chr6.hg18.29mb-34mb.inT1DGC"


def reference_prefix(pop: str = "EUR") -> Path:
    return paths.reference_panels_dir() / "1000G_REF" / REF_TEMPLATE.format(pop=pop)


def reference_bim() -> Path:
    return Path(f"{reference_prefix('EUR')}.bim")


def copy_bfile(src: Path, dst: Path) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    for ext in ("bed", "bim", "fam"):
        shutil.copy(f"{src}.{ext}", f"{dst}.{ext}")
    return dst


def n_samples(prefix: Path) -> int:
    return len(read_fam(Path(f"{prefix}.fam")))


def n_variants(prefix: Path) -> int:
    with open(f"{prefix}.bim") as fh:
        return sum(1 for _ in fh)


def is_family_data(fam: pd.DataFrame) -> bool:
    return bool(((fam["PID"] != "0") | (fam["MID"] != "0")).any())


def classify_pheno(values: pd.Series) -> dict:
    """Binary if observed values are within {1,2} (PLINK coding), else continuous."""
    v = pd.to_numeric(values, errors="coerce")
    obs = v[(v.notna()) & (v != -9)]
    info: dict = {"n_observed": int(len(obs)), "n_missing": int(len(v) - len(obs))}
    if len(obs) and set(obs.unique()) <= {0, 1, 2}:
        obs = obs[obs != 0]
        info.update(type="binary", n_cases=int((obs == 2).sum()), n_controls=int((obs == 1).sum()))
        info["usable"] = info["n_cases"] > 0 and info["n_controls"] > 0
    elif len(obs):
        info.update(type="continuous", variance=float(obs.var()) if len(obs) > 1 else 0.0)
        info["usable"] = info["variance"] > 0
    else:
        info.update(type="none", usable=False)
    return info
