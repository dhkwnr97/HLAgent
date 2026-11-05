"""CookHLA (Docker) wrapper.

Image facts (Docker Hub dhkwnr97/cookhla, v1.0.1 == latest):
- ENTRYPOINT `_entrypoint.sh entrypoint.sh` activates micromamba, then runs the given command.
- WORKDIR /opt/CookHLA, default USER mambauser (uid 57439). We run with the host UID:GID so outputs
  on bind mounts belong to the user (v1 used `--user root`, defect D10); a non-root run was checked
  to resolve python/java/plink inside the image.
- CookHLA runs BEAGLE 5 imputation 9 times (exon 2/3/4 x overlap 0.5/1/1.5 cM); `-mem` is the heap
  of each run and `-mp` how many run at once, so peak memory is about mp x mem.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from hlagent.tools import proc

COOKHLA_IMAGE = "dhkwnr97/cookhla@sha256:0b374cef9cc352cfaa7aa5e89ad49d5b6c64274a6eb8100acbb7f6f452f0c5d6"
REFERENCE_POPULATIONS = ("EUR", "EAS", "AFR", "AMR", "SAS", "ALL")
REFERENCE_HLA_GENES = ("A", "B", "C", "DQB1", "DRB1")  # genes present in the bundled 1000G_REF panels
# pyliftover inside the image looks for chain files in ./ , then $HOME/.pyliftover, then downloads them
# from UCSC at run time. We mount pre-downloaded chains and run with --network none (offline, no data egress).
LIFTOVER_CHAINS = {
    "18": (),
    "19": ("hg19ToHg18.over.chain.gz",),
    "38": ("hg38ToHg19.over.chain.gz", "hg19ToHg18.over.chain.gz"),
}
UCSC_CHAIN_URL = "https://hgdownload.soe.ucsc.edu/goldenPath/{src}/liftOver/{name}"
ALLELES_COLUMNS = ["FID", "IID", "gene", "alleles_1field", "alleles_2field", "prob1", "prob2", "conf"]


class CookHLAParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_prefix: Path = Field(description="Host path prefix of the PLINK target (.bed/.bim/.fam)")
    hg: Literal["18", "19", "38"]
    reference_prefix: Path = Field(description="Host path prefix of the SNP2HLA-format reference panel")
    out_dir: Path
    out_name: str = Field(min_length=1, max_length=120)
    genetic_map: Path | None = None
    error_rate: Path | None = None
    java_mem_gb: int = Field(default=4, ge=1, le=64)
    n_processes: int = Field(default=1, ge=1, le=9)
    nthreads: int = Field(default=1, ge=1, le=32)
    beagle4: bool = False
    save_ambiguous_snp: bool = False
    liftover_dir: Path | None = Field(
        default=None, description="Directory holding UCSC *.over.chain.gz files"
    )
    network_none: bool = True
    image: str = COOKHLA_IMAGE

    @field_validator("out_name")
    @classmethod
    def _clean_name(cls, v: str) -> str:
        if v.endswith(".") or re.search(r"[\s/\\]", v):
            raise ValueError("out_name must not end with '.' (v1 defect D11) or contain spaces/slashes")
        return v

    @model_validator(mode="after")
    def _agm_pair(self) -> CookHLAParams:
        if (self.genetic_map is None) != (self.error_rate is None):
            raise ValueError("genetic_map (-gm) and error_rate (-ae) must be given together or not at all")
        return self

    def missing_chains(self) -> list[str]:
        need = LIFTOVER_CHAINS[self.hg]
        if not need:
            return []
        if self.liftover_dir is None:
            return list(need)
        return [n for n in need if not (self.liftover_dir / n).exists()]


def find_agm(directory: Path) -> tuple[Path, Path] | None:
    """Return (mach_step.avg.clpsB, aver.erate) when both exist in `directory`."""
    gms = sorted(directory.glob("AGM.*.mach_step.avg.clpsB"))
    aes = sorted(directory.glob("AGM.*.aver.erate"))
    if len(gms) == 1 and len(aes) == 1:
        return gms[0], aes[0]
    return None


def peak_memory_gb(p: CookHLAParams) -> float:
    return p.n_processes * p.java_mem_gb + 2.0


def container_name(run_id: str, study_id: str) -> str:
    """Deterministic, Docker-safe container name for one run/study (used to clean up on cancel)."""
    import hashlib

    return "hlagent-" + hashlib.sha1(f"{run_id}/{study_id}".encode()).hexdigest()[:16]


def mem_available_gb() -> float:
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) / 1024**2
    except OSError:
        pass
    return float("nan")


def check_memory_budget(p: CookHLAParams, available_gb: float | None = None) -> tuple[bool, float, float]:
    avail = mem_available_gb() if available_gb is None else available_gb
    need = peak_memory_gb(p)
    ok = not (avail == avail) or need <= 0.8 * avail  # NaN (unknown) -> do not block
    return ok, need, avail


def build_command(
    p: CookHLAParams, *, docker: str = "docker", user: str | None = None, container_name: str | None = None
) -> list[str]:
    in_dir = p.input_prefix.parent.resolve()
    ref_dir = p.reference_prefix.parent.resolve()
    out_dir = p.out_dir.resolve()
    if user is None:
        user = f"{os.getuid()}:{os.getgid()}" if hasattr(os, "getuid") else None
    cmd = [docker, "run", "--rm"]
    if container_name:
        cmd += ["--name", container_name]
    if p.network_none:
        cmd += ["--network", "none"]
    if user:
        cmd += ["--user", user]
    cmd += ["-e", "HOME=/tmp"]
    cmd += ["-v", f"{in_dir}:/data/in:ro", "-v", f"{ref_dir}:/data/ref:ro", "-v", f"{out_dir}:/out"]
    if p.liftover_dir is not None and LIFTOVER_CHAINS[p.hg]:
        cmd += ["-v", f"{p.liftover_dir.resolve()}:/tmp/.pyliftover:ro"]
    gm_c = ae_c = None
    if p.genetic_map is not None and p.error_rate is not None:
        agm_dir = p.genetic_map.parent.resolve()
        if p.error_rate.parent.resolve() != agm_dir:
            raise ValueError("genetic_map and error_rate must be in the same directory")
        if agm_dir == in_dir:
            gm_c, ae_c = f"/data/in/{p.genetic_map.name}", f"/data/in/{p.error_rate.name}"
        else:
            cmd += ["-v", f"{agm_dir}:/data/agm:ro"]
            gm_c, ae_c = f"/data/agm/{p.genetic_map.name}", f"/data/agm/{p.error_rate.name}"
    cmd += [
        p.image,
        "CookHLA.py",
        "-i",
        f"/data/in/{p.input_prefix.name}",
        "-hg",
        p.hg,
        "-o",
        f"/out/{p.out_name}",
        "-ref",
        f"/data/ref/{p.reference_prefix.name}",
        "-mem",
        f"{p.java_mem_gb}g",
    ]
    if gm_c and ae_c:
        cmd += ["-gm", gm_c, "-ae", ae_c]
    if p.n_processes > 1:  # argparse choices are 2..9; 1 means "omit"
        cmd += ["-mp", str(p.n_processes)]
    if p.nthreads > 1:
        cmd += ["-nth", str(p.nthreads)]
    if p.beagle4:
        cmd.append("-bgl4")
    if p.save_ambiguous_snp:
        cmd.append("--save-Ambiguous-SNP")
    return cmd


class CookHLAOutputs(BaseModel):
    alleles: Path
    hped: Path
    raw_vcfs: list[Path]
    lifted_bfile: Path | None  # prefix of the hg18 SNP data CookHLA actually used
    agm: tuple[Path, Path] | None


def collect_outputs(p: CookHLAParams) -> CookHLAOutputs:
    out = p.out_dir
    base = out / f"{p.out_name}.MHC.HLA_IMPUTATION_OUT"
    alleles, hped = Path(f"{base}.alleles"), Path(f"{base}.hped")
    if not alleles.exists() or alleles.stat().st_size == 0:
        raise FileNotFoundError(f"CookHLA produced no allele calls: {alleles}")
    vcfs = sorted(out.glob(f"{p.out_name}.MHC.QC.exon*.raw_imputation_out.vcf"))
    stem = p.input_prefix.name
    lifted = sorted(out.glob(f"{stem}.COPY*.bim"))
    lifted_prefix = Path(str(lifted[-1])[:-4]) if lifted else None
    agm = find_agm(out)
    return CookHLAOutputs(alleles=alleles, hped=hped, raw_vcfs=vcfs, lifted_bfile=lifted_prefix, agm=agm)


def run_cookhla(
    p: CookHLAParams,
    *,
    log_path: Path,
    docker: str = "docker",
    container_name: str | None = None,
    timeout: float | None = 6 * 3600,
) -> tuple[CookHLAOutputs, list[str]]:
    """Run CookHLA. Falls back to root + chown when the non-root run cannot write (returns commands run)."""
    missing = p.missing_chains()
    if missing and p.network_none:
        raise FileNotFoundError(
            f"hg{p.hg} input needs liftover chain file(s) {missing} in {p.liftover_dir}. "
            "Run `hlagent setup-resources --liftover-chains` once (downloads from UCSC), or convert the input to hg18."
        )
    p.out_dir.mkdir(parents=True, exist_ok=True)
    commands: list[str] = []
    cmd = build_command(p, docker=docker, container_name=container_name)
    try:
        r = proc.run(cmd, log_path=log_path, timeout=timeout)
        commands.append(r.command)
    except proc.ToolError as e:
        if "Permission denied" not in e.log_tail:
            raise
        root_cmd = build_command(p, docker=docker, user="0:0", container_name=container_name)
        r = proc.run(root_cmd, log_path=log_path, timeout=timeout)
        commands.append(r.command)
        if hasattr(os, "getuid"):
            chown = [
                docker,
                "run",
                "--rm",
                "--user",
                "0:0",
                "-v",
                f"{p.out_dir.resolve()}:/out",
                "--entrypoint",
                "chown",
                p.image,
                "-R",
                f"{os.getuid()}:{os.getgid()}",
                "/out",
            ]
            commands.append(proc.run(chown, log_path=log_path).command)
    return collect_outputs(p), commands


# ---------------------------------------------------------------- output parsing / QC


def read_alleles(path: Path) -> pd.DataFrame:
    """CookHLA `.alleles`: no header, 8 whitespace-separated columns (v1 defect D13)."""
    df = pd.read_csv(path, sep=r"\s+", header=None, names=ALLELES_COLUMNS, dtype=str)
    for c in ("prob1", "prob2", "conf"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def alleles_summary(df: pd.DataFrame, conf_threshold: float = 0.8) -> dict[str, dict[str, float | int]]:
    out: dict[str, dict[str, float | int]] = {}
    for gene, g in df.groupby("gene", sort=True):
        out[str(gene)] = {
            "n_calls": int(len(g)),
            "conf_mean": float(g["conf"].mean()),
            "conf_min": float(g["conf"].min()),
            "frac_conf_below_threshold": float((g["conf"] < conf_threshold).mean()),
            "n_distinct_2field": int(
                pd.concat(
                    [g["alleles_2field"].str.split(",").str[0], g["alleles_2field"].str.split(",").str[1]]
                ).nunique()
            ),
        }
    return out


def vcf_dr2_summary(
    vcfs: list[Path], prefixes: tuple[str, ...] = ("HLA_", "AA_"), min_maf: float = 0.01
) -> dict[str, dict[str, float | int]]:
    """Distribution of Beagle DR2 (dosage R^2) for imputed HLA/AA markers across the raw VCFs.

    Only markers with estimated MAF = min(AF, 1 - AF) >= `min_maf` are summarised: alleles absent
    from the target have DR2 = 0 by construction and would otherwise dominate the median.
    DR2 is itself an estimate and is noisy in small targets (n < ~50)."""
    vals: dict[str, list[float]] = {p: [] for p in prefixes}
    n_all: dict[str, int] = {p: 0 for p in prefixes}
    pat_dr2, pat_af = re.compile(r"DR2=([0-9.]+)"), re.compile(r"AF=([0-9.eE-]+)")
    for v in vcfs:
        with open(v, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.startswith("#"):
                    continue
                parts = line.split("\t", 8)
                vid = parts[2]
                for pre in prefixes:
                    if vid.startswith(pre):
                        n_all[pre] += 1
                        m, a = pat_dr2.search(parts[7]), pat_af.search(parts[7])
                        if m and a and min(float(a.group(1)), 1 - float(a.group(1))) >= min_maf:
                            vals[pre].append(float(m.group(1)))
    out: dict[str, dict[str, float | int]] = {}
    for pre, xs in vals.items():
        if not n_all[pre]:
            continue
        s = pd.Series(xs, dtype=float)
        out[pre.rstrip("_")] = {
            "n_markers": n_all[pre],
            "n_maf_ge_min": int(s.size),
            "min_maf": min_maf,
            "median": float(s.median()) if s.size else float("nan"),
            "frac_ge_0.8": float((s >= 0.8).mean()) if s.size else float("nan"),
            "frac_lt_0.3": float((s < 0.3).mean()) if s.size else float("nan"),
        }
    return out
