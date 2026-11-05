"""PLINK 1.9 / PLINK 2 commands used by HLAgent.

Association tests reproduce the HATK command exactly (HATK `HLA_Analysis.py`):
`--logistic hide-covar --ci 0.95 --a1-allele <bfile>.ref --chr 6 --from-mb 29 --to-mb 34 --allow-no-sex`.
The `.ref` file follows HATK `MakeDefaultReferenceAllele`: bim A1, except binary markers coded
A1='a', A2='p' get A1='p', so the effect allele of HLA/AA/SNPS markers is always "present".
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from hlagent.io.formats import read_bim
from hlagent.tools import proc


def plink_version(plink: str = "plink") -> str:
    import subprocess

    try:
        out = subprocess.run([plink, "--version"], capture_output=True, text=True, timeout=30, check=False)  # noqa: S603
        return out.stdout.strip().splitlines()[0] if out.stdout else "unknown"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return "not found"


def make_default_reference_allele(bfile: Path, out: Path) -> Path:
    bim = read_bim(Path(f"{bfile}.bim"))
    a1 = bim["A1"].where(~((bim["A1"] == "a") & (bim["A2"] == "p")), "p")
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"SNP": bim["SNP"], "A1": a1}).to_csv(out, sep="\t", header=False, index=False)
    return out


class AssocParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pheno_name: str
    trait: Literal["binary", "continuous"] = "binary"
    covar_names: list[str] = Field(default_factory=list)
    ci: float = Field(default=0.95, gt=0.5, lt=1.0)
    chrom: str = "6"
    from_mb: float = 29.0
    to_mb: float = 34.0
    condition_list: Path | None = None


def assoc_command(
    bfile: Path,
    pheno: Path,
    out_prefix: Path,
    params: AssocParams,
    ref_allele: Path,
    covar: Path | None = None,
    plink: str = "plink",
) -> list[str]:
    cmd = [
        plink,
        "--bfile",
        str(bfile),
        "--pheno",
        str(pheno),
        "--pheno-name",
        params.pheno_name,
        "--logistic" if params.trait == "binary" else "--linear",
        "hide-covar",
        "--ci",
        f"{params.ci:g}",
        "--a1-allele",
        str(ref_allele),
        "--chr",
        params.chrom,
        "--from-mb",
        f"{params.from_mb:g}",
        "--to-mb",
        f"{params.to_mb:g}",
        "--allow-no-sex",
        "--out",
        str(out_prefix),
    ]
    if covar is not None:
        cmd += ["--covar", str(covar)]
        if params.covar_names:
            cmd += ["--covar-name", ",".join(params.covar_names)]
    if params.condition_list is not None:
        cmd += ["--condition-list", str(params.condition_list)]
    return cmd


def run_assoc(
    bfile: Path,
    pheno: Path,
    out_prefix: Path,
    params: AssocParams,
    covar: Path | None = None,
    plink: str = "plink",
    ref_allele: Path | None = None,
) -> tuple[Path, str]:
    """Run the HATK association test; returns (assoc file, command)."""
    ref = ref_allele or make_default_reference_allele(bfile, Path(f"{out_prefix}.ref"))
    cmd = assoc_command(bfile, pheno, out_prefix, params, ref, covar, plink)
    r = proc.run(cmd, log_path=Path(f"{out_prefix}.cmd.log"))
    suffix = ".assoc.logistic" if params.trait == "binary" else ".assoc.linear"
    out = Path(f"{out_prefix}{suffix}")
    if not out.exists():
        raise proc.ToolError("PLINK finished but produced no association file", r.command)
    return out, r.command


def run_plink(args: list[str], out_prefix: Path, plink: str = "plink") -> str:
    """Generic PLINK call writing `<out_prefix>.*`; returns the command."""
    r = proc.run([plink, *args, "--out", str(out_prefix)], log_path=Path(f"{out_prefix}.cmd.log"))
    return r.command
