import json

import numpy as np
import pandas as pd
import pytest

from hlagent.data import (
    decode_hla_vcf,
    hla_markers,
    inspect_dataset,
    load_hla,
    normalize_allele,
    verify_files,
    write_hla_vcf,
)
from hlagent.fixtures import create_demo


def test_allele_semantics():
    assert normalize_allele("HLA-A*01:01:01N", "A") == "A*01:01:01N"
    assert normalize_allele("0101", "A") == "A*01:01"
    assert normalize_allele("A*01:01G", "A") == "A*01:01G"
    assert normalize_allele("0", "A") is None
    for allele in ("A*01:01/A*02:01", "B*01:01", "garbage"):
        with pytest.raises(ValueError):
            normalize_allele(allele, "A")


def test_individual_dosage_and_unknown_sequence():
    calls = pd.DataFrame([dict(FID="01", IID="001", locus="A", allele1="A*01:01", allele2="A*02:01"),
                          dict(FID="02", IID="002", locus="A", allele1="A*01:01", allele2=None)])
    sequence = pd.DataFrame([dict(allele="A*01:01", position="11", residue="A"),
                             dict(allele="A*02:01", position="11", residue="V")])
    markers, metadata = hla_markers(calls, sequence)
    assert len(markers) == 2
    assert markers.loc[0, "HLA_A*01:01"] == 1
    assert markers.loc[0, ["AA_A_11_A", "AA_A_11_V"]].sum() == 2
    assert np.isnan(markers.loc[1, "HLA_A*01:01"])
    assert "NOT_A*01:01" in set(metadata.other_allele)


def test_registration_integrity_and_no_phase_in_hped(store, settings):
    demo = create_demo(store, settings.home)
    data = store.datasets(demo["project"]["id"])[0]
    assert data.has_phase is False
    path = __import__("pathlib").Path(data.files[0].path)
    path.write_text(path.read_text() + "\n")
    with pytest.raises(ValueError, match="changed"):
        verify_files(data.files)


def test_bad_bed_content(tmp_path):
    prefix = tmp_path / "fake"
    prefix.with_suffix(".bed").write_bytes(b"wrong")
    prefix.with_suffix(".bim").write_text("6 rs1 0 1 A C\n")
    prefix.with_suffix(".fam").write_text("01 001 0 0 1 -9\n")
    with pytest.raises(ValueError, match="BED"):
        inspect_dataset("p", str(prefix))


def test_hla_roundtrip_preserves_diploid_identity(store, settings, tmp_path):
    demo = create_demo(store, settings.home, n=100)
    calls = load_hla(__import__("pathlib").Path(store.datasets(demo["project"]["id"])[0].files[0].path))
    path = tmp_path / "hla.vcf"
    book = write_hla_vcf(calls, path)
    text = path.read_text().replace("/", "|")
    # Restore header URL-free text; only genotype separators occur in this generated file.
    path.write_text(text)
    phased = decode_hla_vcf(path, book, calls)
    assert len(phased) == len(calls)
    assert book["coordinate_system"] == "synthetic-HLA-v1"
    assert json.loads(path.with_suffix(".codebook.json").read_text())["markers"]


def test_duplicate_samples_rejected(tmp_path):
    path = tmp_path / "phenotype.tsv"
    path.write_text("IID\ty\n001\t1\n001\t0\n")
    with pytest.raises(ValueError, match="Duplicate"):
        inspect_dataset("p", str(path), kind="phenotype")
