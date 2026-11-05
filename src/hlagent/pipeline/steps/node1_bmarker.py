"""Node1: HLA binary marker panel (v1 Node1 = IMGT2Seq -> NomenCleaner -> bMarkerGenerator)."""

from __future__ import annotations

import contextlib
import io
import re
import sys
from pathlib import Path

import pandas as pd

from hlagent import paths
from hlagent.io.formats import HPED_GENES, read_bim, read_hped
from hlagent.pipeline.contracts import ArtifactRef, NodeResult, StudySpec

RESOLUTION_CODE = {"1field": 1, "2field": 2, "3field": 3, "4field": 4, "Ggroup": 5, "Pgroup": 6}


def _vendor():
    v = str(paths.project_root() / "vendor")
    if v not in sys.path:
        sys.path.insert(0, v)


def dictionaries(cache_dir: Path, hg: str, imgt: str) -> dict[str, Path]:
    return {
        "aa_seq": cache_dir / f"HLA_DICTIONARY_AA.hg{hg}.imgt{imgt}.txt",
        "aa_map": cache_dir / f"HLA_DICTIONARY_AA.hg{hg}.imgt{imgt}.map",
        "snps_seq": cache_dir / f"HLA_DICTIONARY_SNPS.hg{hg}.imgt{imgt}.txt",
        "snps_map": cache_dir / f"HLA_DICTIONARY_SNPS.hg{hg}.imgt{imgt}.map",
        "hat": cache_dir / f"HLA_ALLELE_TABLE.imgt{imgt}.hat",
    }


def ensure_dictionaries(hg: str, imgt: str, log: io.StringIO) -> tuple[Path, dict[str, Path]]:
    cache = paths.hatk_cache_dir() / f"hg{hg}_imgt{imgt}"
    d = dictionaries(cache, hg, imgt)
    if all(p.exists() for p in d.values()):
        return cache, d
    _vendor()
    from hatk_port.IMGT2Seq.IMGT2Seq import IMGT2Seq

    cache.mkdir(parents=True, exist_ok=True)
    imgt_dir = paths.imgt_dir() / f"IMGTHLA-{imgt[0]}.{imgt[1:-1]}.{imgt[-1]}-alpha"
    with contextlib.redirect_stdout(log):
        IMGT2Seq(imgt, hg, str(cache), _imgt_dir=str(imgt_dir) if imgt_dir.exists() else None)
    missing = [k for k, p in d.items() if not p.exists()]
    if missing:
        raise FileNotFoundError(f"IMGT2Seq did not produce {missing} in {cache}")
    return cache, d


_FIELD_SEP = re.compile(r":")


def truncate_chped(src: Path, dst: Path, n_fields: int | None) -> tuple[Path, list[str]]:
    """Cut CHPED alleles ('A*25:01:01:01') to `n_fields` fields (None keeps them) and drop untyped genes.

    HATK reads gene columns by position, infers each gene from its alleles and lays out the
    dictionary maps in HPED_GENES order. So: a gene whose two columns are all '0' (e.g. DPA1/DPB1
    in BMExample) is removed, genes without a HATK dictionary are removed, and the remaining
    column pairs are written in HPED_GENES order. Returns (dst, dropped genes)."""
    df = read_hped(src)

    def cut(a: str) -> str:
        if n_fields is None or not isinstance(a, str) or "*" not in a:
            return a
        gene, rest = a.split("*", 1)
        return f"{gene}*{':'.join(_FIELD_SEP.split(rest)[:n_fields])}"

    for c in df.columns[6:]:
        df[c] = df[c].map(cut)
    pairs: dict[str, list[str]] = {}
    dropped: list[str] = []
    cols = list(df.columns[6:])
    for k in range(0, len(cols), 2):
        pair = cols[k : k + 2]
        called = [a for c in pair for a in df[c] if isinstance(a, str) and "*" in a]
        if not called:
            dropped.append(pair[0].rsplit("_", 1)[0])
            continue
        gene = called[0].split("*", 1)[0]
        if gene not in HPED_GENES:
            dropped.append(gene)
            continue
        pairs[gene] = pair
    order = [c for g in HPED_GENES if g in pairs for c in pairs[g]]
    df[list(df.columns[:6]) + order].to_csv(dst, sep="\t", header=False, index=False)
    return dst, dropped


def build_panel_from_chped(
    hla_file: Path,
    variants: Path | None,
    out_prefix: Path,
    cache_dir: Path,
    *,
    hg: str = "18",
    imgt: str = "3320",
    resolution: str = "2field",
    plink: str = "plink",
) -> tuple[Path, str, list[str]]:
    """Return (panel prefix, captured HATK log, dropped untyped genes).

    Accepts .chped (cut to resolution) or .hped (NomenCleaner)."""
    _vendor()
    from hatk_port.bMarkerGenerator.bMarkerGenerator import bMarkerGenerator
    from hatk_port.NomenCleaner.NomenCleaner import NomenCleaner
    from hatk_port.NomenCleaner.src.CHPED import CHPED

    d = dictionaries(cache_dir, hg, imgt)
    log = io.StringIO()
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    chped = Path(f"{out_prefix}.{resolution}.chped")
    with contextlib.redirect_stdout(log):
        if hla_file.suffix.lower() == ".chped":
            if resolution in ("Ggroup", "Pgroup"):
                raise ValueError(
                    "G/P-group output needs uncleaned HPED input (NomenCleaner); got a CHPED file"
                )
            _, dropped = truncate_chped(hla_file, chped, RESOLUTION_CODE[resolution])
        else:
            chped_s, _ = NomenCleaner(
                str(hla_file), str(d["hat"]), str(out_prefix) + ".nomencleaner", RESOLUTION_CODE[resolution]
            )
            _, dropped = truncate_chped(Path(chped_s), chped, None)
        bm = bMarkerGenerator(
            CHPED(str(chped)),
            str(out_prefix),
            hg,
            str(d["aa_seq"]),
            str(d["aa_map"]),
            str(d["snps_seq"]),
            str(d["snps_map"]),
            _variants=str(variants) if variants else None,
            _plink=plink,
        )
    prefix = Path(str(bm.bed)[:-4]) if hasattr(bm, "bed") and bm.bed else out_prefix
    return prefix, log.getvalue(), dropped


def marker_counts(bim: Path) -> dict[str, int]:
    b = read_bim(bim)
    t = b["SNP"].map(lambda s: "rs" if s.startswith("rs") else s.split("_", 1)[0])
    return {f"n_{k}": int(v) for k, v in t.value_counts().items()}


def run(ctx, study: StudySpec) -> NodeResult:
    p = ctx.params.node1
    d = ctx.require("StageD", study.study_id)
    i = ctx.result("StageI", study.study_id)
    out = ctx.step_dir("Node1", study.study_id)
    res = NodeResult(node="Node1", study_id=study.study_id, status="ok", cache_key="")
    hla = (i.art("hla") if i is not None else None) or (d.art("hla") if "hla" in d.artifacts else None)
    if hla is None:
        raise RuntimeError("Node1 needs HLA types (Stage D hla or Stage I imputation)")
    variants = None
    if i is not None and "snps_hg18" in i.artifacts:
        variants = i.art("snps_hg18")
    elif "snps_hg18" in d.artifacts:
        variants = d.art("snps_hg18")
    if variants is not None and pd.read_csv(f"{variants}.bim", sep=r"\s+", header=None).empty:
        variants = None
    hlog = io.StringIO()
    cache, _ = ensure_dictionaries(p.hg, p.imgt, hlog)
    prefix, log, dropped = build_panel_from_chped(
        hla, variants, out / "panel", cache, hg=p.hg, imgt=p.imgt, resolution=p.resolution, plink=ctx.plink
    )
    (out / "hatk.log").write_text(hlog.getvalue() + log)
    if dropped:
        res.warnings.append(f"Untyped HLA genes left out of the panel: {', '.join(dropped)}.")
        res.metrics["genes_untyped"] = ",".join(dropped)
    res.artifacts["panel"] = ArtifactRef.of(
        "bfile", prefix, build="hg18", description=f"HATK binary marker panel ({p.resolution}, IMGT {p.imgt})"
    )
    res.metrics.update(marker_counts(Path(f"{prefix}.bim")))
    res.metrics.update(
        {
            "resolution": p.resolution,
            "imgt": p.imgt,
            "n_samples": int(sum(1 for _ in open(f"{prefix}.fam"))),
            "snps_included": variants is not None,
        }
    )
    res.commands.append(
        f"hatk_port.bMarkerGenerator(chped={hla.name}, variants={variants}, hg={p.hg}, imgt={p.imgt})"
    )
    if variants is None:
        res.warnings.append("No SNP genotypes merged: the panel holds HLA/AA/SNPS markers only.")
    if res.warnings:
        res.status = "warning"
    return res
