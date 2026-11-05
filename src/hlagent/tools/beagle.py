"""Stage P phasing chain for HATK binary-marker panels (HATK Phasing module, re-implemented with proc.run).

Why this chain: HATK marker panels contain many markers sharing one bp position and non-ACGT
alleles ('p'/'a'). BEAGLE 4/5 reject both, so HATK recommends BEAGLE 3.3.2 and uses BEAGLE
utilities plus a "GC trick":

P1 markers   bim -> "ID BP A2 A1" (4th column = effect allele A1)
P2 LINKAGE   plink --recode --keep-allele-order --alleleACGT; .dat ("M id"); ped without phenotype column
P3 Beagle v3 java -jar linkage2beagle.jar <dat> <nopheno.ped> > <bgl>
P4 GC trick  recode every marker's alleles to G (3rd col) / C (4th col)
P5 redefineBP  give markers sharing a position unique positions (order preserved)
P6 phase     java -jar beagle.jar unphased= markers= out= missing=0 seed=
P7 unGCtrick restore original alleles with the P1 markers
P8 .aa       AllCC_Get_Phased_AA_Calls.R (see hlagent.tools.omnibus.make_aa)
"""

from __future__ import annotations

import gzip
import re
import shutil
from pathlib import Path

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from hlagent import paths
from hlagent.io.formats import read_bim, read_fam
from hlagent.tools import proc


class PhasingParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    java_mem_gb: int = Field(default=4, ge=1, le=64)
    seed: int = -99999
    niterations: int = Field(default=10, ge=1, le=100)
    nsamples: int = Field(default=4, ge=1, le=50)
    keep_intermediates: bool = False


def _jar(name: str) -> Path:
    p = paths.beagle_dir() / name
    if not p.exists():
        raise FileNotFoundError(f"{p} missing (third_party/beagle)")
    return p


def java_mem_arg(gb: int) -> str:
    """HATK convention for BEAGLE 3 and the utilities: decimal MB (4 GB -> -Xmx4000m)."""
    return f"-Xmx{gb * 1000}m"


def write_markers(bim: Path, out: Path) -> Path:
    b = read_bim(bim)
    b[["SNP", "BP", "A2", "A1"]].to_csv(out, sep=" ", header=False, index=False)
    return out


def plink_to_beagle(
    bfile: Path,
    out_prefix: Path,
    *,
    plink: str = "plink",
    java: str = "java",
    java_mem_gb: int = 4,
    log_path: Path,
) -> tuple[Path, Path, list[str]]:
    cmds: list[str] = []
    markers = write_markers(Path(f"{bfile}.bim"), Path(f"{out_prefix}.markers"))
    r = proc.run(
        [
            plink,
            "--recode",
            "--bfile",
            str(bfile),
            "--keep-allele-order",
            "--alleleACGT",
            "--allow-no-sex",
            "--out",
            str(out_prefix),
        ],
        log_path=log_path,
    )
    cmds.append(r.command)
    ped, mp = Path(f"{out_prefix}.ped"), Path(f"{out_prefix}.map")
    dat = Path(f"{out_prefix}.dat")
    ids = pd.read_csv(mp, sep=r"\s+", header=None, usecols=[1], dtype=str)[1]
    dat.write_text("".join(f"M {i}\n" for i in ids))
    nopheno = Path(f"{out_prefix}.nopheno.ped")
    with open(ped, encoding="utf-8") as fin, open(nopheno, "w", encoding="utf-8") as fout:
        for line in fin:
            f = line.rstrip("\n").split(" ")
            fout.write(" ".join(f[:5] + f[6:]) + "\n")
    bgl = Path(f"{out_prefix}.bgl")
    r = proc.run(
        [java, java_mem_arg(java_mem_gb), "-jar", str(_jar("linkage2beagle.jar")), str(dat), str(nopheno)],
        log_path=log_path,
        stdout_path=bgl,
    )
    cmds.append(r.command)
    for f in (ped, mp, nopheno, dat, Path(f"{out_prefix}.nosex"), Path(f"{out_prefix}.log")):
        f.unlink(missing_ok=True)
    return bgl, markers, cmds


def gc_trick(bgl: Path, markers: Path, out_bgl: Path, out_markers: Path) -> None:
    alleles: dict[str, tuple[str, str]] = {}
    with open(markers) as mk, open(out_markers, "w") as mo:
        for line in mk:
            mid, pos, a1, a2 = line.split()
            alleles[mid] = (a1, a2)
            mo.write(f"{mid} {pos} G C\n")
    with open(bgl) as fin, open(out_bgl, "w") as fout:
        for line in fin:
            c = line.split()
            if c[0] != "M":
                fout.write(line)
                continue
            a1, a2 = alleles[c[1]]
            data = ["G" if x == a1 else ("C" if x == a2 else "0") for x in c[2:]]
            fout.write(" ".join(c[:2] + data) + "\n")


def redefine_bp(markers: Path, out: Path) -> Path:
    occupied: dict[int, str] = {}
    with open(markers) as fin:
        for line in fin:
            mid, bp_s, a1, a2 = line.split()
            bp = int(bp_s)
            while bp in occupied:
                bp += 1
            occupied[bp] = f"{mid} {bp} {a1} {a2}\n"
    with open(out, "w") as fout:
        for k in sorted(occupied):
            fout.write(occupied[k])
    return out


def un_gc_trick(phased_gz: Path, markers: Path, out: Path) -> Path:
    alleles: dict[str, tuple[str, str]] = {}
    with open(markers) as mk:
        for line in mk:
            mid, _pos, a1, a2 = line.split()
            alleles[mid] = (a1, a2)
    opener = gzip.open if str(phased_gz).endswith(".gz") else open
    with opener(phased_gz, "rt") as fin, open(out, "w") as fout:
        for line in fin:
            c = line.split()
            if c[0] != "M":
                fout.write(line)
                continue
            a1, a2 = alleles[c[1]]
            data = [a1 if x == "G" else (a2 if x == "C" else "0") for x in c[2:]]
            fout.write(" ".join(c[:2] + data) + "\n")
    return out


def phase_bmarker_panel(
    bfile: Path, out_prefix: Path, params: PhasingParams, *, plink: str = "plink", java: str = "java"
) -> tuple[Path, Path, list[str]]:
    """Run P1-P7. Returns (bgl.phased, markers, commands)."""
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    log = Path(f"{out_prefix}.phasing.log")
    p2b = Path(f"{out_prefix}.P2B")
    bgl, markers, cmds = plink_to_beagle(
        bfile, p2b, plink=plink, java=java, java_mem_gb=params.java_mem_gb, log_path=log
    )
    bgl_gc, mk_gc = Path(f"{bgl}.GCtrick"), Path(f"{markers}.GCtrick")
    gc_trick(bgl, markers, bgl_gc, mk_gc)
    mk_ref = redefine_bp(mk_gc, Path(f"{mk_gc}.refined"))
    beagle_out = Path(f"{out_prefix}.phased")
    r = proc.run(
        [
            java,
            java_mem_arg(params.java_mem_gb),
            "-jar",
            str(_jar("beagle.jar")),
            f"unphased={bgl_gc}",
            f"markers={mk_ref}",
            f"out={beagle_out}",
            "missing=0",
            f"seed={params.seed}",
            f"niterations={params.niterations}",
            f"nsamples={params.nsamples}",
        ],
        log_path=log,
        timeout=24 * 3600,
    )
    cmds.append(r.command)
    phased_gz = Path(f"{beagle_out}.{bgl_gc.name}.phased.gz")
    if not phased_gz.exists():
        raise proc.ToolError("BEAGLE produced no phased output", r.command, proc._tail(log))  # noqa: SLF001
    bgl_phased = un_gc_trick(phased_gz, markers, Path(f"{out_prefix}.bgl.phased"))
    final_markers = Path(f"{out_prefix}.markers")
    shutil.copy(markers, final_markers)
    if not params.keep_intermediates:
        for f in (bgl, markers, bgl_gc, mk_gc, mk_ref, phased_gz):
            f.unlink(missing_ok=True)
        for ext in ("dose.gz", "gprobs.gz", "r2"):
            Path(str(phased_gz).replace(".phased.gz", f".{ext}")).unlink(missing_ok=True)
        for f in out_prefix.parent.glob(f"{beagle_out.name}.*.log"):
            f.unlink(missing_ok=True)
    return bgl_phased, final_markers, cmds


def check_phasing_consistency(
    bfile: Path, bgl_phased: Path, max_markers: int | None = None
) -> dict[str, int]:
    """Invariant: for every sample and marker, the unordered phased pair equals the input genotype.

    BEAGLE 3 imputes missing genotypes, so input-missing calls are skipped. Returns counts.
    """
    fam = read_fam(Path(f"{bfile}.fam"))
    n = len(fam)
    tmp = Path(f"{bgl_phased}.check")
    proc.run(
        [
            "plink",
            "--bfile",
            str(bfile),
            "--recode",
            "--transpose",
            "--keep-allele-order",
            "--alleleACGT",
            "--allow-no-sex",
            "--out",
            str(tmp),
        ],
        log_path=Path(f"{tmp}.log"),
    )
    geno: dict[str, list[tuple[str, str]]] = {}
    with open(f"{tmp}.tped") as fh:
        for i, line in enumerate(fh):
            if max_markers is not None and i >= max_markers:
                break
            f = line.split()
            calls = f[4:]
            geno[f[1]] = [(calls[2 * k], calls[2 * k + 1]) for k in range(n)]
    checked = mismatched = skipped_missing = 0
    with open(bgl_phased) as fh:
        for line in fh:
            c = line.split()
            if c[0] != "M" or c[1] not in geno:
                continue
            hap = c[2:]
            for k, (g1, g2) in enumerate(geno[c[1]]):
                if g1 == "0" or g2 == "0":
                    skipped_missing += 1
                    continue
                checked += 1
                if sorted((hap[2 * k], hap[2 * k + 1])) != sorted((g1, g2)):
                    mismatched += 1
    for ext in ("tped", "tfam", "map", "log", "nosex"):
        Path(f"{tmp}.{ext}").unlink(missing_ok=True)
    return {
        "checked": checked,
        "mismatched": mismatched,
        "skipped_missing": skipped_missing,
        "markers": len(geno),
    }


def beagle_version(java: str = "java") -> str:
    try:
        r = proc.run(
            [java, "-jar", str(_jar("beagle.jar"))],
            check=False,
            log_path=paths.project_root() / "runs" / ".beagle_version.log",
        )
        text = r.log_path.read_text() if r.log_path else ""
        m = re.search(r"Beagle version ([\d.]+)", text)
        return m.group(1) if m else "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"
