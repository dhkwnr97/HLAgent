"""Genome build detection and rsID-based harmonisation to hg18 (the coordinate system of the
1000G_REF panels and of the HATK hg18 dictionaries).

Detection compares positions of rsIDs shared with the hg18 reference bim:
- exact matches >= threshold                      -> hg18
- >= threshold of offsets within +/-2 bp of the mode, mode about -107,979 bp (MHC) -> hg19
- otherwise                                       -> unknown (e.g. legacy HapMap/NCBI35 builds)
hg38 is never guessed from offsets here (its MHC offset to hg18 is not constant); pass `hg="38"`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from hlagent.io.formats import read_bim

HG19_MHC_OFFSET = -107_979  # hg19 - hg18 for chr6 29-34 Mb (observed: 1958BC vs 1000G_REF, 1,199/1,199 SNPs)


@dataclass
class BuildReport:
    build: str
    n_input_snps: int
    n_shared_rsids: int
    exact_match_fraction: float
    mode_offset: int | None
    mode_offset_fraction: float
    method: str
    note: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def detect_build(input_bim: Path, reference_bim: Path, threshold: float = 0.95) -> BuildReport:
    inp = read_bim(input_bim)
    ref = read_bim(reference_bim)
    inp6 = inp[inp["CHR"].isin(["6", "chr6"])]
    shared = inp6.merge(ref[["SNP", "BP"]], on="SNP", suffixes=("", "_ref"))
    shared = shared[shared["SNP"].str.startswith("rs")]
    n = len(shared)
    if n < 20:
        return BuildReport(
            "unknown",
            len(inp),
            n,
            0.0,
            None,
            0.0,
            "too_few_shared",
            "Fewer than 20 rsIDs shared with the reference panel; cannot infer the build.",
        )
    diff = shared["BP"] - shared["BP_ref"]
    exact = float((diff == 0).mean())
    mode = int(diff.mode().iloc[0])
    near = float(((diff - mode).abs() <= 2).mean())
    if exact >= threshold:
        return BuildReport("hg18", len(inp), n, exact, 0, exact, "exact_positions")
    if near >= threshold and abs(mode - HG19_MHC_OFFSET) <= 50:
        return BuildReport(
            "hg19",
            len(inp),
            n,
            exact,
            mode,
            near,
            "constant_offset",
            f"{near:.1%} of shared rsIDs sit {mode} bp from hg18 (hg19 MHC offset).",
        )
    top = diff.value_counts().head(3).to_dict()
    return BuildReport(
        "unknown",
        len(inp),
        n,
        exact,
        mode,
        near,
        "inconsistent_offsets",
        f"Positions match hg18 for {exact:.1%} and no single offset explains them "
        f"(most common offsets: {top}); likely an older build such as NCBI35/hg17",
    )


def remap_table(input_bim: Path, reference_bim: Path, out: Path) -> tuple[Path, Path, int]:
    """Write PLINK --update-map (ID newpos) and --extract lists for rsIDs shared with the reference."""
    inp = read_bim(input_bim)
    ref = read_bim(reference_bim)
    shared = inp.merge(ref[["SNP", "BP"]], on="SNP", suffixes=("", "_ref"))
    shared = shared[shared["SNP"].str.startswith("rs")].drop_duplicates("SNP")
    upd = Path(f"{out}.update_map.txt")
    ext = Path(f"{out}.extract.txt")
    shared[["SNP", "BP_ref"]].to_csv(upd, sep="\t", header=False, index=False)
    shared[["SNP"]].to_csv(ext, header=False, index=False)
    return upd, ext, len(shared)


def position_match_fraction(bim: Path, reference_bim: Path) -> float:
    inp, ref = read_bim(bim), read_bim(reference_bim)
    m = inp.merge(ref[["SNP", "BP"]], on="SNP", suffixes=("", "_ref"))
    m = m[m["SNP"].str.startswith("rs")]
    return float((m["BP"] == m["BP_ref"]).mean()) if len(m) else 0.0


def summarize_offsets(input_bim: Path, reference_bim: Path) -> pd.Series:
    inp, ref = read_bim(input_bim), read_bim(reference_bim)
    m = inp.merge(ref[["SNP", "BP"]], on="SNP", suffixes=("", "_ref"))
    return (m["BP"] - m["BP_ref"]).value_counts()
