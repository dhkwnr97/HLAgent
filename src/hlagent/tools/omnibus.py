"""HATK omnibus test (R) and phased amino-acid calls.

Both R scripts are the vendored HATK ones; this module only builds the argument lists.
- `AllCC_Get_Phased_AA_Calls.R <bgl.phased> <fam> <out_prefix>` -> `<out_prefix>.aa`
- `OmnibusTest_BHv5.R <outfile> <fam> <aa> <phe> <phe_name> <covar|NA> <covar_names|NA> <conditions|NA>`
"""

from __future__ import annotations

from pathlib import Path

from hlagent import paths
from hlagent.tools import proc


def _r_script(name: str) -> Path:
    base = paths.vendor_dir() / "OmnibusTest"
    p = base / name if (base / name).exists() else base / "src" / name
    if not p.exists():
        raise FileNotFoundError(p)
    return p


def make_aa(bgl_phased: Path, fam: Path, out_prefix: Path, rscript: str = "Rscript") -> tuple[Path, str]:
    cmd = [rscript, str(_r_script("AllCC_Get_Phased_AA_Calls.R")), str(bgl_phased), str(fam), str(out_prefix)]
    r = proc.run(cmd, log_path=Path(f"{out_prefix}.aa.log"))
    out = Path(f"{out_prefix}.aa")
    if not out.exists():
        raise proc.ToolError("AA call script produced no .aa file", r.command)
    return out, r.command


def omnibus_output_path(out_prefix: Path, pheno_name: str, conditions: list[str] | None) -> Path:
    cond = ",".join(conditions) if conditions else "NA"
    return Path(f"{out_prefix}.{pheno_name}.{cond}.omnibus")


def run_omnibus(
    fam: Path,
    aa: Path,
    pheno: Path,
    pheno_name: str,
    out_prefix: Path,
    covar: Path | None = None,
    covar_names: list[str] | None = None,
    conditions: list[str] | None = None,
    rscript: str = "Rscript",
) -> tuple[Path, str]:
    out = omnibus_output_path(out_prefix, pheno_name, conditions)
    cmd = [
        rscript,
        str(_r_script("OmnibusTest_BHv5.R")),
        str(out),
        str(fam),
        str(aa),
        str(pheno),
        pheno_name,
        str(covar) if covar else "NA",
        ",".join(covar_names) if covar_names else "NA",
        ",".join(conditions) if conditions else "NA",
    ]
    r = proc.run(cmd, log_path=Path(f"{out}.log"))
    if not out.exists():
        raise proc.ToolError("omnibus script produced no output", r.command)
    return out, r.command
