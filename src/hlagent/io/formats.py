"""Readers and format sniffing for the files HLAgent handles.

PLINK fam/bim, phenotype tables, HATK HPED/CHPED, CookHLA `.alleles`, PLINK association output.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pandas as pd

FAM_COLUMNS = ["FID", "IID", "PID", "MID", "SEX", "PHENO"]
BIM_COLUMNS = ["CHR", "SNP", "CM", "BP", "A1", "A2"]
HPED_GENES = ["A", "B", "C", "DPA1", "DPB1", "DQA1", "DQB1", "DRB1"]
BED_MAGIC = bytes([0x6C, 0x1B, 0x01])

FileKind = Literal["bfile", "vcf", "hped", "chped", "alleles", "pheno", "assoc", "unknown"]


def read_fam(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep=r"\s+", header=None, names=FAM_COLUMNS, dtype=str)
    return df


def read_bim(path: Path) -> pd.DataFrame:
    df = pd.read_csv(
        path, sep=r"\s+", header=None, names=BIM_COLUMNS, dtype={"CHR": str, "SNP": str, "A1": str, "A2": str}
    )
    df["BP"] = df["BP"].astype("int64")
    return df


def bfile_exists(prefix: Path) -> bool:
    return all(Path(f"{prefix}.{ext}").exists() for ext in ("bed", "bim", "fam"))


def is_bed(path: Path) -> bool:
    with open(path, "rb") as fh:
        return fh.read(3) == BED_MAGIC


def read_pheno(path: Path) -> pd.DataFrame:
    """PLINK-style phenotype table. With a `FID IID ...` header the names are kept; otherwise PHENO1.."""
    with open(path, encoding="utf-8") as fh:
        first = fh.readline().split()
    has_header = len(first) >= 2 and first[0].upper() == "FID" and first[1].upper() == "IID"
    if has_header:
        df = pd.read_csv(path, sep=r"\s+", dtype=str)
        df = df.rename(columns={df.columns[0]: "FID", df.columns[1]: "IID"})
    else:
        df = pd.read_csv(path, sep=r"\s+", header=None, dtype=str)
        df.columns = ["FID", "IID"] + [f"PHENO{i}" for i in range(1, df.shape[1] - 1)]
    return df


def write_pheno(df: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, sep="\t", index=False)
    return path


def hped_has_header(path: Path) -> bool:
    with open(path, encoding="utf-8") as fh:
        first = fh.readline().split()
    return bool(first) and first[0].upper() in ("FID", "FAM_ID", "FAMILY_ID")


def read_hped(path: Path) -> pd.DataFrame:
    """HPED/CHPED: 6 PLINK columns + 2 alleles per gene (8 classical genes, possibly more with a header)."""
    header = hped_has_header(path)
    df = pd.read_csv(path, sep=r"\s+", header=0 if header else None, dtype=str)
    if not header:
        n_genes = (df.shape[1] - 6) // 2
        genes = HPED_GENES[:n_genes] if n_genes <= len(HPED_GENES) else [f"G{i}" for i in range(n_genes)]
        df.columns = FAM_COLUMNS + [f"{g}_{k}" for g in genes for k in (1, 2)]
    else:
        df.columns = FAM_COLUMNS + list(df.columns[6:])
    return df


def hped_genes_typed(df: pd.DataFrame) -> dict[str, int]:
    """Number of non-missing allele calls per gene (0 means the gene is absent)."""
    out: dict[str, int] = {}
    for c in df.columns[6:]:
        gene = c.rsplit("_", 1)[0]
        n = int((~df[c].isin(["0", "-9", "NA", ""])).sum())
        out[gene] = out.get(gene, 0) + n
    return out


def read_assoc(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep=r"\s+", dtype={"SNP": str, "A1": str, "TEST": str})
    for c in ("OR", "BETA", "SE", "L95", "U95", "STAT", "P", "NMISS"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def sniff(path: Path) -> FileKind:
    """Best-effort classification of a single file (bfile is recognised from any of its 3 parts)."""
    name = path.name.lower()
    if name.endswith((".bed", ".bim", ".fam")):
        return "bfile"
    if name.endswith((".vcf", ".vcf.gz", ".bcf")):
        return "vcf"
    if name.endswith(".chped"):
        return "chped"
    if name.endswith(".hped"):
        return "hped"
    if name.endswith(".alleles"):
        return "alleles"
    if name.endswith((".assoc.logistic", ".assoc.linear", ".glm.logistic", ".glm.linear")):
        return "assoc"
    if name.endswith((".phe", ".pheno", ".txt", ".tsv")):
        try:
            with open(path, encoding="utf-8") as fh:
                first = fh.readline().split()
            if len(first) >= 3 and first[0].upper() == "FID" and first[1].upper() == "IID":
                return "pheno"
        except (OSError, UnicodeDecodeError):
            return "unknown"
    return "unknown"
