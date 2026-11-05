from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from hlagent.models import DatasetManifest, SourceFile

LOCI = ("A", "B", "C", "DPA1", "DPB1", "DQA1", "DQB1", "DRB1")
BUILDS = {"hg18": "GRCh36", "hg19": "GRCh37", "hg38": "GRCh38",
          "36": "GRCh36", "37": "GRCh37", "38": "GRCh38",
          "GRCh36": "GRCh36", "GRCh37": "GRCh37", "GRCh38": "GRCh38"}
MISSING = {"", "0", "NA", "N/A", "NAN", "NONE", ".", "-", "?"}


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def resolve_path(value: str) -> Path:
    if not value or "\x00" in value:
        raise ValueError("A valid local path is required")
    if os.name != "nt" and re.match(r"^[A-Za-z]:[\\/]", value):
        result = subprocess.run(["wslpath", "-u", value], capture_output=True, text=True, check=True)
        value = result.stdout.strip()
    return Path(value).expanduser().resolve()


def source(path: Path, role: str = "input") -> SourceFile:
    if not path.is_file():
        raise ValueError(f"Missing file: {path.name}")
    return SourceFile(path=str(path), sha256=sha256(path), size=path.stat().st_size, role=role)


def verify_files(files: list[SourceFile]):
    for entry in files:
        path = Path(entry.path)
        if not path.is_file() or path.stat().st_size != entry.size or sha256(path) != entry.sha256:
            raise ValueError(f"Input changed after registration/approval: {path.name}. Register it again.")


def read_table(path: Path, **kwargs) -> pd.DataFrame:
    return pd.read_csv(path, sep=None, engine="python", dtype=str, keep_default_na=False, **kwargs)


def ids(frame: pd.DataFrame) -> pd.DataFrame:
    if "IID" not in frame:
        raise ValueError("An explicit IID sample identifier column is required")
    frame = frame.copy()
    if "FID" not in frame:
        frame.insert(0, "FID", frame["IID"])
    for col in ("FID", "IID"):
        frame[col] = frame[col].astype(str)
        if frame[col].str.contains(r"\s", regex=True).any() or frame[col].eq("").any():
            raise ValueError("FID and IID must be non-empty and contain no whitespace")
    return frame


def unique_samples(frame: pd.DataFrame):
    if frame.duplicated(["FID", "IID"]).any():
        raise ValueError("Duplicate FID/IID sample identifiers")


def normalize_allele(value: str, locus: str) -> str | None:
    value = str(value).strip().upper().replace("HLA-", "")
    locus = locus.upper().replace("HLA-", "")
    if value in MISSING:
        return None
    if any(c in value for c in ("/", ";", ",")):
        raise ValueError(f"Ambiguous HLA allele at {locus}; resolve ambiguity explicitly")
    if "*" not in value:
        if re.fullmatch(r"\d{4,8}[NLSCAQGP]?", value) and ":" not in value:
            suffix = value[-1] if value[-1].isalpha() else ""
            digits = value[:-1] if suffix else value
            if len(digits) % 2:
                raise ValueError("Legacy allele code needs an explicit nomenclature mapping")
            value = ":".join(digits[i:i + 2] for i in range(0, len(digits), 2)) + suffix
        value = f"{locus}*{value}"
    if not re.fullmatch(r"[A-Z0-9]+\*\d{2,3}(?::\d{2,3}){0,3}[NLSCAQGP]?", value):
        raise ValueError(f"Invalid HLA allele notation at {locus}")
    if value.split("*")[0] != locus:
        raise ValueError("HLA allele and locus disagree")
    return value


def load_hla(path: Path, mapping: dict | None = None, tool: str | None = None) -> pd.DataFrame:
    """Return diploid calls, retaining confidence as a distinct, uninterpreted field."""
    mapping = mapping or {}
    if path.suffix.lower() in (".hped", ".chped", ".hped2"):
        raw = pd.read_csv(path, sep=r"\s+", header=None, dtype=str, keep_default_na=False)
        if raw.shape[1] != 22:
            raise ValueError("HPED/CHPED requires 6 pedigree columns and 16 HLA allele columns")
        rows = []
        for _, r in raw.iterrows():
            for i, locus in enumerate(LOCI):
                rows.append({"FID": r[0], "IID": r[1], "locus": locus,
                             "allele1": r[6 + 2 * i], "allele2": r[7 + 2 * i]})
        result = pd.DataFrame(rows)
    elif tool == "xhla" or path.suffix.lower() == ".json":
        data = json.loads(path.read_text())
        alleles = data.get("hla", {}).get("alleles", [])
        sample = data.get("sample") or data.get("sample_id") or mapping.get("sample_id")
        if not sample or not alleles:
            raise ValueError("xHLA JSON requires sample_id/sample and hla.alleles")
        rows = []
        for locus in LOCI:
            calls = [a for a in alleles if a.replace("HLA-", "").startswith(locus + "*")]
            if calls:
                if len(calls) != 2:
                    raise ValueError("Exactly two calls per locus are required; homozygosity is not guessed")
                rows.append({"FID": str(sample), "IID": str(sample), "locus": locus,
                             "allele1": calls[0], "allele2": calls[1]})
        result = pd.DataFrame(rows)
    elif tool == "hlahd":
        raw = pd.read_csv(path, sep=r"\s+", header=None, dtype=str, keep_default_na=False)
        sample = mapping.get("sample_id")
        if not sample or raw.shape[1] < 3:
            raise ValueError("HLA-HD result requires locus/call1/call2 and explicit sample_id")
        result = raw.iloc[:, :3].copy()
        result.columns = ["locus", "allele1", "allele2"]
        result["FID"] = result["IID"] = str(sample)
    else:
        raw = read_table(path).rename(columns=mapping.get("columns", {}))
        if tool == "optitype":
            sample = mapping.get("sample_id")
            if len(raw) != 1 or not sample:
                raise ValueError("OptiType top-result file requires one row and explicit sample_id")
            raw["IID"] = str(sample)
        if {"locus", "allele1", "allele2", "IID"}.issubset(raw.columns):
            result = raw
        else:
            raw = ids(raw)
            rows = []
            for locus in LOCI:
                candidates = [(f"{locus}_1", f"{locus}_2"), (f"{locus}1", f"{locus}2")]
                pair = next((p for p in candidates if set(p).issubset(raw.columns)), None)
                if pair:
                    for _, r in raw.iterrows():
                        rows.append({"FID": r.FID, "IID": r.IID, "locus": locus,
                                     "allele1": r[pair[0]], "allele2": r[pair[1]]})
            if not rows:
                raise ValueError("Provide a column mapping to IID/locus/allele1/allele2 or locus_1/locus_2")
            result = pd.DataFrame(rows)
    result = ids(result)
    result["locus"] = result["locus"].str.upper().str.replace("HLA-", "", regex=False)
    if not set(result.locus).issubset(LOCI):
        raise ValueError("Only the eight classical HLA loci are supported in this release")
    if result.duplicated(["FID", "IID", "locus"]).any():
        raise ValueError("Duplicate sample/locus HLA records")
    for col in ("allele1", "allele2"):
        result[col] = [normalize_allele(a, locus) for a, locus in zip(result[col], result.locus)]
    if "confidence" in result:
        result["confidence"] = pd.to_numeric(result.confidence, errors="raise")
    return result


def inspect_dataset(project_id: str, value: str, label: str = "", kind: str | None = None,
                    genome_build: str | None = None, metadata: dict | None = None,
                    ancestry: str | None = None, resolution: str | None = None,
                    imgt_release: str | None = None) -> DatasetManifest:
    path = resolve_path(value)
    metadata = dict(metadata or {})
    build = BUILDS.get(genome_build) if genome_build else None
    if genome_build and not build:
        raise ValueError("Use GRCh36/hg18, GRCh37/hg19, or GRCh38/hg38")
    base = dict(project_id=project_id, label=label or path.name, genome_build=build,
                ancestry=ancestry, resolution=resolution, imgt_release=imgt_release, metadata=metadata)
    suffix = path.suffix.lower()
    prefix = path.with_suffix("") if suffix in (".bed", ".bim", ".fam", ".pgen", ".pvar", ".psam") else path
    if kind in ("plink_bed", "reference") or suffix in (".bed", ".bim", ".fam") or Path(str(path) + ".bed").is_file():
        files = [source(Path(str(prefix) + ext)) for ext in (".bed", ".bim", ".fam")]
        fam = pd.read_csv(files[2].path, sep=r"\s+", header=None, dtype=str)
        bim = pd.read_csv(files[1].path, sep=r"\s+", header=None, dtype=str)
        if fam.shape[1] != 6 or bim.shape[1] != 6:
            raise ValueError("Invalid PLINK FAM/BIM column counts")
        if fam.duplicated([0, 1]).any() or bim[1].duplicated().any():
            raise ValueError("Duplicate PLINK sample IDs or marker IDs")
        with Path(files[0].path).open("rb") as handle:
            if handle.read(3) != b"\x6c\x1b\x01":
                raise ValueError("Expected SNP-major PLINK BED content")
        if files[0].size != 3 + len(bim) * math.ceil(len(fam) / 4):
            raise ValueError("BED size does not match BIM/FAM")
        metadata.update(prefix=str(prefix), variant_count=len(bim))
        if kind == "reference":
            for extension in (".bgl.phased", ".markers"):
                files.append(source(Path(str(prefix) + extension)))
            for key in ("genetic_map", "error_rate"):
                if metadata.get(key):
                    files.append(source(resolve_path(metadata[key]), key))
        return DatasetManifest(kind=kind or "plink_bed", files=files, sample_count=len(fam), **base)
    if kind == "plink_pgen" or suffix in (".pgen", ".psam", ".pvar") or Path(str(path) + ".pgen").is_file():
        pvar = next((Path(str(prefix) + ext) for ext in (".pvar", ".pvar.zst")
                     if Path(str(prefix) + ext).is_file()), Path(str(prefix) + ".pvar"))
        files = [source(Path(str(prefix) + ".pgen")), source(pvar), source(Path(str(prefix) + ".psam"))]
        sample = pd.read_csv(files[2].path, sep=r"\s+", dtype=str)
        sample = ids(sample.rename(columns={"#FID": "FID", "#IID": "IID"}))
        unique_samples(sample)
        metadata["prefix"] = str(prefix)
        return DatasetManifest(kind="plink_pgen", files=files, sample_count=len(sample), **base)
    if kind in ("vcf", "bcf") or path.name.endswith((".vcf", ".vcf.gz", ".bcf")):
        import pysam
        with pysam.VariantFile(str(path)) as vcf:
            names = list(vcf.header.samples)
            if not names or len(names) != len(set(names)):
                raise ValueError("VCF/BCF needs unique sample identifiers")
            phased, has_ds, n = True, False, 0
            for record in vcf:
                n += 1
                has_ds |= "DS" in record.format
                for call in record.samples.values():
                    gt = call.get("GT")
                    if gt and len(gt) != 2:
                        raise ValueError("This release requires diploid MHC genotypes")
                    if gt and len(set(gt)) > 1 and not call.phased:
                        phased = False
            if n == 0:
                raise ValueError("Empty genotype file")
        metadata["variant_count"] = n
        files = [source(path)]
        if metadata.get("codebook_path"):
            files.append(source(resolve_path(metadata["codebook_path"]), "codebook"))
        return DatasetManifest(kind="bcf" if suffix == ".bcf" else "vcf", files=files,
                               sample_count=len(names), has_dosage=has_ds, has_phase=phased, **base)
    if kind == "hla" or suffix in (".hped", ".chped", ".hped2") or metadata.get("tool"):
        frame = load_hla(path, metadata.get("mapping"), metadata.get("tool"))
        metadata["loci"] = sorted(frame.locus.unique().tolist())
        return DatasetManifest(kind="hla", files=[source(path)],
                               sample_count=len(frame[["FID", "IID"]].drop_duplicates()),
                               columns=frame.columns.tolist(), **base)
    if kind == "hla_dosage":
        frame = load_dosages(path, metadata.get("mapping"))
        if not metadata.get("dosage_source"):
            raise ValueError("Record the validated dosage source; confidence scores are not dosages")
        metadata["loci"] = sorted(frame.locus.unique())
        return DatasetManifest(kind=kind, files=[source(path)], has_dosage=True,
                               sample_count=len(frame[["FID", "IID"]].drop_duplicates()),
                               columns=frame.columns.tolist(), **base)
    frame = load_sequence(path, metadata) if kind == "sequence" else read_table(path)
    if kind is None:
        if {"locus", "allele1", "allele2"}.issubset(frame.columns):
            return inspect_dataset(project_id, value, label, "hla", genome_build, metadata,
                                   ancestry, resolution, imgt_release)
        raise ValueError("Choose phenotype, summary statistics, HLA calls, or sequence dictionary")
    if kind == "phenotype":
        frame = ids(frame.rename(columns=metadata.get("mapping", {}).get("columns", {})))
        unique_samples(frame)
    elif kind == "sequence":
        if not {"allele", "position", "residue"}.issubset(frame.columns) or not imgt_release:
            raise ValueError("Sequence dictionary needs allele, position, residue and an explicit IMGT release")
    elif kind != "summary":
        raise ValueError("Unrecognized dataset kind")
    return DatasetManifest(kind=kind, files=[source(path)], columns=frame.columns.tolist(),
                           sample_count=len(frame) if kind == "phenotype" else None, **base)


def load_sequence(path: Path, metadata: dict | None = None) -> pd.DataFrame:
    metadata = metadata or {}
    if metadata.get("format") == "hatk_dictionary_aa":
        if metadata.get("position_system") != "alignment_column_1based":
            raise ValueError("HATK dictionaries require an explicit alignment_column_1based position system")
        raw = pd.read_csv(path, sep=r"\s+", header=None, names=["allele", "sequence"], dtype=str)
        if raw.allele.duplicated().any():
            raise ValueError("HATK AA dictionary has duplicate alleles")
        rows = [(allele, f"alignment{index}", residue.upper())
                for allele, sequence in raw.itertuples(index=False, name=None)
                for index, residue in enumerate(sequence, 1)]
        frame = pd.DataFrame(rows, columns=["allele", "position", "residue"])
    else:
        frame = read_table(path)
    if not {"allele", "position", "residue"}.issubset(frame):
        raise ValueError("Sequence needs allele, position, residue columns")
    if frame.duplicated(["allele", "position"]).any():
        raise ValueError("Ambiguous allele/position sequence mapping")
    frame["residue"] = frame.residue.str.upper()
    if not frame.residue.str.fullmatch(r"[ACDEFGHIKLMNPQRSTVWYX*?\-.]").all():
        raise ValueError("Invalid amino acid symbol in sequence dictionary")
    frame["allele"] = [normalize_allele(a, a.split("*")[0]) for a in frame.allele]
    return frame


def load_dosages(path: Path, mapping: dict | None = None) -> pd.DataFrame:
    frame = ids(read_table(path).rename(columns=(mapping or {}).get("columns", {})))
    if not {"locus", "allele", "dosage"}.issubset(frame):
        raise ValueError("HLA dosage table needs IID, locus, allele, dosage columns")
    frame["allele"] = [normalize_allele(a, locus) for a, locus in zip(frame.allele, frame.locus)]
    frame["dosage"] = pd.to_numeric(frame.dosage, errors="raise")
    if frame.allele.isna().any() or not np.isfinite(frame.dosage).all() or not frame.dosage.between(0, 2).all():
        raise ValueError("HLA dosages must be finite expected diploid copies between 0 and 2")
    if frame.duplicated(["FID", "IID", "locus", "allele"]).any():
        raise ValueError("Duplicate sample/locus/allele dosage records")
    sums = frame.groupby(["FID", "IID", "locus"]).dosage.sum()
    if not np.allclose(sums, 2, atol=1e-4, rtol=0):
        raise ValueError("All allele dosages at a called locus must sum to two; omit an entirely missing sample/locus")
    return frame


def dosage_markers(frame: pd.DataFrame, sequence: pd.DataFrame | None = None):
    samples = frame[["FID", "IID"]].drop_duplicates().sort_values(["FID", "IID"]).set_index(["FID", "IID"])
    markers, metadata = samples.copy(), []
    for locus, group in frame.groupby("locus"):
        wide = group.pivot(index=["FID", "IID"], columns="allele", values="dosage").fillna(0).reindex(samples.index)
        for allele in wide:
            marker = "HLA_" + allele
            markers[marker] = wide[allele]
            metadata.append(dict(marker=marker, kind="HLA", locus=locus, position="", effect_allele=allele,
                                 other_allele="NOT_" + allele))
        if sequence is None:
            continue
        for position, rows in sequence[sequence.allele.isin(wide.columns)].groupby("position"):
            mapping = rows.set_index("allele").residue
            known = mapping.index[mapping.isin(list("ACDEFGHIKLMNPQRSTVWY"))]
            unmapped = [a for a in wide if a not in known]
            valid = wide.notna().all(axis=1) & wide[unmapped].sum(axis=1).le(1e-12)
            for residue in sorted(set(mapping.loc[known])):
                marker = f"AA_{locus}_{position}_{residue}"
                markers[marker] = wide[mapping.index[mapping == residue]].sum(axis=1).where(valid)
                metadata.append(dict(marker=marker, kind="AA", locus=locus, position=str(position),
                                     effect_allele=residue, other_allele="NOT_" + residue))
    return markers.reset_index(), pd.DataFrame(metadata)


def stage_dataset(manifest: DatasetManifest, directory: Path) -> dict[str, Path]:
    verify_files(manifest.files)
    directory.mkdir(parents=True, exist_ok=True)
    out = {}
    for entry in manifest.files:
        dest = directory / Path(entry.path).name
        if not dest.is_file() or sha256(dest) != entry.sha256:
            tmp = dest.with_name(dest.name + ".partial")
            shutil.copyfile(entry.path, tmp)
            if sha256(tmp) != entry.sha256:
                raise ValueError("Source changed during staging")
            tmp.replace(dest)
        out[entry.path] = dest
    return out


def dataset_samples(dataset: DatasetManifest) -> pd.DataFrame:
    first = Path(dataset.files[0].path)
    if dataset.kind == "hla":
        frame = load_hla(first, dataset.metadata.get("mapping"), dataset.metadata.get("tool"))
    elif dataset.kind == "hla_dosage":
        frame = load_dosages(first, dataset.metadata.get("mapping"))
    elif dataset.kind == "plink_bed":
        frame = pd.read_csv(first.with_suffix(".fam"), sep=r"\s+", header=None, dtype=str).rename(columns={0: "FID", 1: "IID"})
    elif dataset.kind == "plink_pgen":
        frame = pd.read_csv(first.with_suffix(".psam"), sep=r"\s+", dtype=str).rename(columns={"#FID": "FID", "#IID": "IID"})
        frame = ids(frame)
    elif dataset.kind in ("vcf", "bcf"):
        import pysam
        with pysam.VariantFile(str(first)) as vcf:
            frame = ids(pd.DataFrame({"IID": list(vcf.header.samples)}))
    else:
        raise ValueError("Dataset has no individual-level sample definition")
    return frame[["FID", "IID"]].drop_duplicates()


def hla_markers(calls: pd.DataFrame, sequence: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    samples = calls[["FID", "IID"]].drop_duplicates().sort_values(["FID", "IID"])
    markers = samples.set_index(["FID", "IID"])
    metadata = []
    for locus, group in calls.groupby("locus", sort=True):
        g = group.set_index(["FID", "IID"]).reindex(markers.index)
        valid = g.allele1.notna() & g.allele2.notna()
        alleles = sorted(set(group.allele1.dropna()) | set(group.allele2.dropna()))
        for allele in alleles:
            marker = "HLA_" + allele
            markers[marker] = ((g.allele1 == allele).astype(float) + (g.allele2 == allele).astype(float)).where(valid)
            metadata.append(dict(marker=marker, kind="HLA", locus=locus, position="", effect_allele=allele,
                                 other_allele="NOT_" + allele))
        if sequence is not None:
            s = sequence[sequence.allele.str.startswith(locus + "*")].copy()
            if s.duplicated(["allele", "position"]).any():
                raise ValueError("Sequence dictionary has duplicate or ambiguous allele/position entries")
            for position, rows in s.groupby("position", sort=True):
                lookup = rows.set_index("allele").residue.to_dict()
                a, b = g.allele1.map(lookup), g.allele2.map(lookup)
                known = a.isin(list("ACDEFGHIKLMNPQRSTVWY")) & b.isin(list("ACDEFGHIKLMNPQRSTVWY"))
                residues = sorted((set(a[known]) | set(b[known])))
                for residue in residues:
                    marker = f"AA_{locus}_{position}_{residue}"
                    markers[marker] = ((a == residue).astype(float) + (b == residue).astype(float)).where(known)
                    metadata.append(dict(marker=marker, kind="AA", locus=locus, position=str(position),
                                         effect_allele=residue, other_allele="NOT_" + residue))
    return markers.reset_index(), pd.DataFrame(metadata)


def write_hla_vcf(calls: pd.DataFrame, path: Path, loci: list[str] | None = None,
                  reference_book: dict | None = None) -> dict:
    """A private synthetic coordinate system, never a genomic VCF or liftover input."""
    loci = loci or sorted(calls.locus.unique())
    if len(loci) < 2:
        raise ValueError("Multilocus phasing requires at least two loci")
    samples = sorted(set(zip(calls.FID, calls.IID)))
    lookup = calls.set_index(["FID", "IID", "locus"])
    codebook = {"coordinate_system": "synthetic-HLA-v1", "samples": samples, "markers": {}, "constant_loci": {}}
    with path.open("w") as handle:
        handle.write('##fileformat=VCFv4.3\n##contig=<ID=6>\n')
        handle.write('##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">\n')
        handle.write("#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\t" +
                     "\t".join(f"S{i}" for i in range(len(samples))) + "\n")
        for index, locus in enumerate(loci):
            group = calls[calls.locus == locus]
            alleles = sorted(set(group.allele1.dropna()) | set(group.allele2.dropna()))
            if reference_book:
                ref = reference_book["markers"].get("HLASYN_" + locus)
                if not ref or not set(alleles).issubset(ref["alleles"]):
                    raise ValueError("Reference codebook does not cover all target HLA alleles")
                alleles = ref["alleles"]
            if len(alleles) < 2:
                if alleles:
                    codebook["constant_loci"][locus] = alleles[0]
                continue
            marker = "HLASYN_" + locus
            # Non-overlapping, equal-length A/C/G/T strings preserve multiallelic identity.
            width = max(2, math.ceil(math.log(len(alleles), 4)))
            codes = ["A" + "".join("ACGT"[(i // 4 ** j) % 4] for j in reversed(range(width)))
                     for i in range(len(alleles))]
            if reference_book and codes != reference_book["markers"][marker]["codes"]:
                raise ValueError("Reference and target use different HLA encodings")
            codebook["markers"][marker] = {"locus": locus, "alleles": alleles, "codes": codes,
                                          "position": (index + 1) * 100000}
            genotypes = []
            for fid, iid in samples:
                if (fid, iid, locus) not in lookup.index:
                    genotypes.append("./.")
                    continue
                row = lookup.loc[(fid, iid, locus)]
                genotypes.append("/".join(str(alleles.index(a)) if a in alleles else "."
                                           for a in (row.allele1, row.allele2)))
            handle.write(f"6\t{(index + 1) * 100000}\t{marker}\t{codes[0]}\t{','.join(codes[1:])}\t.\tPASS\t.\tGT\t" +
                         "\t".join(genotypes) + "\n")
    if len(codebook["markers"]) < 2:
        raise ValueError("At least two polymorphic HLA loci are needed for phasing")
    path.with_suffix(".codebook.json").write_text(json.dumps(codebook, indent=2))
    return codebook


def decode_hla_vcf(path: Path, codebook: dict, original: pd.DataFrame) -> pd.DataFrame:
    import pysam
    lookup = original.set_index(["FID", "IID", "locus"])
    rows = []
    seen = set()
    with pysam.VariantFile(str(path)) as vcf:
        if list(vcf.header.samples) != [f"S{i}" for i in range(len(codebook["samples"]))]:
            raise ValueError("Phasing output changed sample identities/order")
        for record in vcf:
            if record.id not in codebook["markers"]:
                if codebook.get("coordinate_system") == "genomic-scaffold-private-HLA-v1" and not (record.id or "").startswith("HLASYN_"):
                    continue
                raise ValueError("Unknown synthetic HLA marker")
            item = codebook["markers"][record.id]
            if list(record.alleles) != item["codes"]:
                raise ValueError("Phasing output changed the allele dictionary")
            seen.add(record.id)
            for index, (fid, iid) in enumerate(codebook["samples"]):
                call = record.samples[f"S{index}"]
                gt = call["GT"]
                if not call.phased or len(gt) != 2 or None in gt:
                    raise ValueError("Incomplete or unphased HLA output")
                a, b = [item["alleles"][g] for g in gt]
                observed = lookup.loc[(fid, iid, item["locus"])] if (fid, iid, item["locus"]) in lookup.index else None
                if observed is not None and pd.notna(observed.allele1) and pd.notna(observed.allele2):
                    if sorted([a, b]) != sorted([observed.allele1, observed.allele2]):
                        raise ValueError("Phasing changed a non-missing diploid HLA genotype")
                rows.append(dict(FID=fid, IID=iid, locus=item["locus"], haplotype1=a, haplotype2=b,
                                 validation_level="exploratory_statistical_phase"))
    if seen != set(codebook["markers"]):
        raise ValueError("Phasing output lost HLA loci")
    for locus, allele in codebook.get("constant_loci", {}).items():
        for fid, iid in codebook["samples"]:
            if (fid, iid, locus) in lookup.index:
                row = lookup.loc[(fid, iid, locus)]
                if pd.notna(row.allele1) and pd.notna(row.allele2):
                    rows.append(dict(FID=fid, IID=iid, locus=locus, haplotype1=allele, haplotype2=allele,
                                     validation_level="observed_homozygous_constant_locus"))
    return pd.DataFrame(rows)


def scaffold_hla_vcf(calls: pd.DataFrame, snp_vcf: Path, path: Path, positions: dict,
                      build: str, loci: list[str] | None = None, reference_book: dict | None = None) -> dict:
    """Merge verified SNP GTs and private multiallelic HLA codes at explicit anchor coordinates."""
    import pysam
    temporary = path.with_name("hla-only.vcf")
    book = write_hla_vcf(calls, temporary, loci, reference_book)
    samples = book["samples"]
    iids = [s[1] for s in samples]
    if len(set(iids)) != len(iids):
        raise ValueError("Scaffold VCF requires globally unique IIDs or a prior explicit ID mapping")
    if not {m["locus"] for m in book["markers"].values()}.issubset(positions):
        raise ValueError("Supply one explicit same-build anchor position for every phased HLA locus")
    if len(set(positions.values())) != len(positions) or any(not isinstance(x, int) or x < 1 for x in positions.values()):
        raise ValueError("HLA anchors must be distinct positive genomic coordinates")
    with pysam.VariantFile(str(snp_vcf)) as snps:
        if set(snps.header.samples) != set(iids):
            raise ValueError("HLA and SNP scaffold samples must match exactly")
        rows = []
        seen = set()
        for record in snps:
            if record.contig not in ("6", "chr6") or not (20_000_000 <= record.pos <= 40_000_000):
                raise ValueError("Provide a chromosome-6 MHC SNP scaffold within 20-40 Mb")
            if record.pos in positions.values() or record.pos in seen:
                raise ValueError("SNP positions collide with one another or HLA anchors")
            if any(len(a) != 1 or a not in "ACGT" for a in record.alleles):
                raise ValueError("The initial scaffold adapter accepts normalized single-nucleotide variants")
            seen.add(record.pos)
            genotypes = []
            for iid in iids:
                call = record.samples[iid]
                gt = call.get("GT")
                if not gt or len(gt) != 2:
                    raise ValueError("Scaffold must contain diploid GT calls")
                genotypes.append("/".join(str(v) if v is not None else "." for v in gt))
            rows.append((record.pos, f"6\t{record.pos}\tSCF_{record.pos}\t{record.ref}\t{','.join(record.alts)}\t.\tPASS\t.\tGT\t" + "\t".join(genotypes)))
        if len(rows) < 2:
            raise ValueError("At least two informative scaffold SNPs are required")
    for line in temporary.read_text().splitlines():
        if line.startswith("#"):
            continue
        fields = line.split("\t")
        item = book["markers"][fields[2]]
        item["position"] = positions[item["locus"]]
        fields[1] = str(item["position"])
        rows.append((item["position"], "\t".join(fields)))
    book.update(coordinate_system="genomic-scaffold-private-HLA-v1", genome_build=build,
                snp_source_sha256=sha256(snp_vcf), interpretation="HLA allele codes are not DNA variants")
    if reference_book:
        if reference_book.get("genome_build") != build or reference_book["markers"] != book["markers"]:
            raise ValueError("Phasing reference build, positions and allele mapping must match exactly")
    headers = [line for line in temporary.read_text().splitlines() if line.startswith("#")]
    path.write_text("\n".join(headers + [line for _, line in sorted(rows)]) + "\n")
    path.with_suffix(".codebook.json").write_text(json.dumps(book, indent=2))
    return book


def validate_phase_reference(path: Path, codebook: dict, target_ids: set[str]):
    import pysam
    observed = set()
    with pysam.VariantFile(str(path)) as vcf:
        if target_ids & set(vcf.header.samples):
            raise ValueError("Target/reference phasing samples overlap")
        for record in vcf:
            if any(not c.phased or None in c.get("GT", ()) for c in record.samples.values()):
                raise ValueError("Phasing reference contains unphased or missing calls")
            if (record.id or "").startswith("HLASYN_"):
                item = codebook["markers"].get(record.id)
                if item is None or item["position"] != record.pos or item["codes"] != list(record.alleles):
                    raise ValueError("Reference VCF does not match its supplied codebook")
                observed.add(record.id)
    if observed != set(codebook["markers"]):
        raise ValueError("Reference VCF lacks declared HLA markers")


def validate_snp_phasing(input_path: Path, output_path: Path):
    import pysam
    with pysam.VariantFile(str(input_path)) as original, pysam.VariantFile(str(output_path)) as output:
        if list(original.header.samples) != list(output.header.samples):
            raise ValueError("Phasing changed sample identities or order")
        expected = {}
        for record in original:
            key = (record.contig, record.pos, record.alleles)
            if key in expected:
                raise ValueError("Duplicate input variant keys")
            expected[key] = [call.get("GT") for call in record.samples.values()]
        seen = set()
        for record in output:
            key = (record.contig, record.pos, record.alleles)
            if key not in expected or key in seen:
                raise ValueError("Phasing output introduced or duplicated variant records")
            seen.add(key)
            for before, after in zip(expected[key], record.samples.values()):
                gt = after.get("GT")
                if not gt or None in gt or not after.phased:
                    raise ValueError("Incomplete or unphased output genotypes")
                if before and None not in before and sorted(before) != sorted(gt):
                    raise ValueError("Phasing changed an observed diploid genotype")
        if seen != set(expected):
            raise ValueError("Phasing lost input variants")
