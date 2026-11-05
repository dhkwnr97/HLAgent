"""Marker-level meta-analysis across k studies (plan section 6.5).

Fixed effect (inverse variance):
    w_s = 1/SE_s^2,  b_F = sum(w b)/sum(w),  SE_F = sum(w)^-1/2,  p_F = 2(1 - Phi(|b_F/SE_F|))
Heterogeneity:
    Q = sum w (b - b_F)^2 ~ chi2_{k-1},  I^2 = max(0, (Q-(k-1))/Q)
Random effects (DerSimonian-Laird):
    tau^2 = max(0, (Q-(k-1)) / (sum w - sum w^2/sum w)),  w* = 1/(SE^2 + tau^2)

Allele harmonisation uses study 1 as reference. The effect allele is the A1 column of each
association file; the other allele comes from the matching bim. Allele pairs that only agree
after a strand flip are complemented; HATK binary markers (p/a) are never complemented.
A/T and C/G SNPs are matched by allele label (as HATK, METAL and PLINK do), which is correct when
all studies were aligned to the same reference panel (CookHLA aligns targets to it). For external
summary statistics on unknown strand, set `drop_ambiguous_snps=True` to drop ambiguous rs SNPs.
HATK-generated markers (HLA_, AA_, SNPS_, INS_) come from IMGT sequence and are never dropped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import chi2, norm

from hlagent.io.formats import read_assoc, read_bim

_COMPLEMENT = {"A": "T", "T": "A", "C": "G", "G": "C"}
_AMBIGUOUS = {frozenset("AT"), frozenset("CG")}


@dataclass
class StudyInput:
    name: str
    assoc: Path
    bim: Path | None = None


@dataclass
class HarmonizationReport:
    n_markers_per_study: dict[str, int] = field(default_factory=dict)
    n_common: int = 0
    n_flipped: dict[str, int] = field(default_factory=dict)
    n_strand_complemented: dict[str, int] = field(default_factory=dict)
    n_ambiguous_kept: int = 0
    n_dropped_ambiguous: int = 0
    n_dropped_mismatch: int = 0
    n_dropped_missing: int = 0
    n_analyzed: int = 0


def _load_study(s: StudyInput) -> pd.DataFrame:
    a = read_assoc(s.assoc)
    if "TEST" in a.columns:
        a = a[a["TEST"].isin(["ADD"])]
    if "BETA" in a.columns and a["BETA"].notna().any():
        beta = a["BETA"]
    elif "OR" in a.columns:
        with np.errstate(divide="ignore", invalid="ignore"):
            beta = np.log(a["OR"].where(a["OR"] > 0))
    else:
        raise ValueError(f"{s.assoc}: needs BETA or OR")
    if "SE" not in a.columns:
        raise ValueError(f"{s.assoc}: needs SE (run PLINK with --ci)")
    df = pd.DataFrame(
        {
            "SNP": a["SNP"],
            "CHR": a.get("CHR"),
            "BP": a.get("BP"),
            "EA": a["A1"].astype(str),
            "BETA": beta.astype(float),
            "SE": a["SE"].astype(float),
            "P": a.get("P"),
        }
    )
    if s.bim is not None:
        bim = read_bim(s.bim)[["SNP", "A1", "A2"]]
        df = df.merge(bim, on="SNP", how="left")
        df["OA"] = np.where(df["EA"] == df["A1"], df["A2"], np.where(df["EA"] == df["A2"], df["A1"], None))
        df = df.drop(columns=["A1", "A2"])
    else:
        df["OA"] = None
    return df.drop_duplicates("SNP")


def _align(ea_ref: str, oa_ref: str | None, ea: str, oa: str | None) -> tuple[int, bool] | None:
    """Return (sign, complemented) to express study effect on reference effect allele, or None (drop)."""
    if oa_ref is None or oa is None:
        # without the other allele we can only match the effect allele itself
        if ea == ea_ref:
            return 1, False
        return None
    ref = (ea_ref, oa_ref)
    binary = {ea_ref.lower(), oa_ref.lower()} <= {"p", "a"}
    if (ea, oa) == ref:
        return 1, False
    if (oa, ea) == ref:
        return -1, False
    if binary:
        return None
    comp = (_COMPLEMENT.get(ea, "?"), _COMPLEMENT.get(oa, "?"))
    if comp == ref:
        return 1, True
    if (comp[1], comp[0]) == ref:
        return -1, True
    return None


_HATK_PREFIXES = ("HLA_", "AA_", "SNPS_", "INS_")


def _is_ambiguous(a: str, b: str | None) -> bool:
    return b is not None and frozenset((a.upper(), b.upper())) in _AMBIGUOUS


def fixed_and_random(beta: np.ndarray, se: np.ndarray) -> dict[str, np.ndarray]:
    """Vectorised IVW-FE, Cochran Q, I^2 and DL random effects. beta/se: shape (m, k)."""
    w = 1.0 / se**2
    sw = w.sum(axis=1)
    b_f = (w * beta).sum(axis=1) / sw
    se_f = np.sqrt(1.0 / sw)
    z_f = b_f / se_f
    p_f = 2.0 * norm.sf(np.abs(z_f))
    k = beta.shape[1]
    q = (w * (beta - b_f[:, None]) ** 2).sum(axis=1)
    df = k - 1
    p_q = chi2.sf(q, df) if df > 0 else np.full_like(q, np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        i2 = np.where(q > 0, np.maximum(0.0, (q - df) / q), 0.0)
    c = sw - (w**2).sum(axis=1) / sw
    with np.errstate(divide="ignore", invalid="ignore"):
        tau2 = np.where(c > 0, np.maximum(0.0, (q - df) / c), 0.0)
    w_r = 1.0 / (se**2 + tau2[:, None])
    sw_r = w_r.sum(axis=1)
    b_r = (w_r * beta).sum(axis=1) / sw_r
    se_r = np.sqrt(1.0 / sw_r)
    p_r = 2.0 * norm.sf(np.abs(b_r / se_r))
    return {
        "BETA_FE": b_f,
        "SE_FE": se_f,
        "Z_FE": z_f,
        "P_FE": p_f,
        "Q": q,
        "P_Q": p_q,
        "I2": i2,
        "TAU2": tau2,
        "BETA_RE": b_r,
        "SE_RE": se_r,
        "P_RE": p_r,
    }


def meta_analyze(
    studies: list[StudyInput], drop_ambiguous_snps: bool = False
) -> tuple[pd.DataFrame, HarmonizationReport]:
    if len(studies) < 2:
        raise ValueError("meta-analysis needs at least 2 studies")
    rep = HarmonizationReport()
    frames = [_load_study(s) for s in studies]
    for s, f in zip(studies, frames, strict=True):
        rep.n_markers_per_study[s.name] = len(f)
    ref = frames[0].set_index("SNP")
    common = set(ref.index)
    for f in frames[1:]:
        common &= set(f["SNP"])
    rep.n_common = len(common)
    snps = [s for s in frames[0]["SNP"] if s in common]  # keep reference order
    k = len(frames)
    betas = np.full((len(snps), k), np.nan)
    ses = np.full((len(snps), k), np.nan)
    keep = np.ones(len(snps), dtype=bool)
    idx = [f.set_index("SNP") for f in frames]
    for s in studies:
        rep.n_flipped[s.name] = 0
        rep.n_strand_complemented[s.name] = 0
    for i, snp in enumerate(snps):
        ea0, oa0 = ref.at[snp, "EA"], ref.at[snp, "OA"]
        oa0 = None if pd.isna(oa0) else oa0
        if _is_ambiguous(ea0, oa0) and not str(snp).startswith(_HATK_PREFIXES):
            if drop_ambiguous_snps:
                keep[i] = False
                rep.n_dropped_ambiguous += 1
                continue
            rep.n_ambiguous_kept += 1
        for j, f in enumerate(idx):
            row = f.loc[snp]
            if pd.isna(row["BETA"]) or pd.isna(row["SE"]) or row["SE"] <= 0:
                keep[i] = False
                break
            oa = None if pd.isna(row["OA"]) else row["OA"]
            al = _align(ea0, oa0, row["EA"], oa) if j > 0 else (1, False)
            if al is None:
                keep[i] = False
                break
            sign, comp = al
            betas[i, j] = sign * row["BETA"]
            ses[i, j] = row["SE"]
            if j > 0:
                rep.n_flipped[studies[j].name] += int(sign < 0)
                rep.n_strand_complemented[studies[j].name] += int(comp)
        else:
            continue
        # broke out of the study loop: classify reason
        if np.isnan(betas[i]).any():
            if any(pd.isna(f.loc[snp, "BETA"]) or pd.isna(f.loc[snp, "SE"]) for f in idx):
                rep.n_dropped_missing += 1
            else:
                rep.n_dropped_mismatch += 1
    snps_k = [s for s, kk in zip(snps, keep, strict=True) if kk]
    b, se = betas[keep], ses[keep]
    stats = fixed_and_random(b, se) if len(snps_k) else {}
    out = pd.DataFrame({"SNP": snps_k})
    out["CHR"] = [ref.at[s, "CHR"] for s in snps_k]
    out["BP"] = [ref.at[s, "BP"] for s in snps_k]
    out["EA"] = [ref.at[s, "EA"] for s in snps_k]
    out["OA"] = [ref.at[s, "OA"] for s in snps_k]
    out["K"] = k
    for key, val in stats.items():
        out[key] = val
    out["OR_FE"] = np.exp(out.get("BETA_FE", pd.Series(dtype=float)))
    for j, s in enumerate(studies):
        out[f"BETA_{s.name}"] = b[:, j]
        out[f"SE_{s.name}"] = se[:, j]
    rep.n_analyzed = len(out)
    return out, rep
