"""Golden tests G1-G4: reproduce published HATK / v1 CookHLA results.

G1 regression: identical to HATK RESULT_EXAMPLE assoc.logistic (all columns, PLINK precision).
G2 CookHLA: identical .alleles/.hped to the v1 run (hg18 input, offline container).
G3 omnibus: the published .omnibus cannot be reproduced exactly from the inputs shipped with it
    (its .aa has two malformed lines and regenerating from the shipped .bgl.phased changes 210/383
    deviances), so G3 checks what is reproducible: same variants/df/N/residues, rank agreement
    (Spearman >= 0.95), and the same top signal, unconditioned and conditioned on AA_DRB1_96.
G4 meta: identical to the v1/HATK inverse-variance implementation on RA+CD.
"""

from __future__ import annotations

import contextlib
import io
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.stats import spearmanr

from hlagent import paths
from hlagent.io.formats import read_assoc
from hlagent.stats.meta import StudyInput, meta_analyze
from hlagent.tools.plink import AssocParams, run_assoc
from tests.conftest import needs_docker, needs_java, needs_plink, needs_r, needs_resources

pytestmark = [pytest.mark.golden, needs_resources]


@needs_plink
def test_g1_regression_matches_hatk(tmp_path, hatk_ex, ra_bfile):
    out, cmd = run_assoc(
        ra_bfile,
        hatk_ex / "wtccc_filtered_58C_RA.hatk.300+300.phe",
        tmp_path / "ra",
        AssocParams(pheno_name="RA"),
    )
    a, b = read_assoc(out), read_assoc(Path(f"{ra_bfile}.assoc.logistic"))
    assert len(a) == len(b) == 10439
    assert (a["SNP"].values == b["SNP"].values).all()
    assert (a["A1"].values == b["A1"].values).all()
    for c in ("NMISS", "OR", "SE", "L95", "U95", "STAT", "P"):
        x, y = a[c].to_numpy(float), b[c].to_numpy(float)
        assert (np.isnan(x) == np.isnan(y)).all(), c
        ok = ~np.isnan(x)
        # PLINK prints 4 significant digits; allow one unit in the last place
        np.testing.assert_allclose(x[ok], y[ok], rtol=1e-3, err_msg=c)
    assert "--a1-allele" in cmd


@needs_docker
@pytest.mark.slow
def test_g2_cookhla_matches_v1(tmp_path):
    from hlagent.tools.cookhla import CookHLAParams, find_agm, run_cookhla

    v1 = paths.resources_dir() / "examples" / "cookhla_v1_output"
    inp = tmp_path / "in"
    inp.mkdir()
    stem = "1958BC.hg19.COPY.LiftDown_hg18.NoAmbig"
    for ext in ("bed", "bim", "fam"):
        shutil.copy(v1 / f"{stem}.{ext}", inp)
    for f in v1.glob("AGM.*"):
        shutil.copy(f, inp)
    gm, ae = find_agm(inp)
    p = CookHLAParams(
        input_prefix=inp / stem,
        hg="18",
        reference_prefix=paths.reference_panels_dir()
        / "1000G_REF"
        / "1000G_REF.EUR.chr6.hg18.29mb-34mb.inT1DGC",
        out_dir=tmp_path / "out",
        out_name="1958BC+1000G_REF.EUR",
        genetic_map=gm,
        error_rate=ae,
        java_mem_gb=2,
        n_processes=4,
    )
    outs, _ = run_cookhla(p, log_path=tmp_path / "cookhla.log")
    ref_alleles = v1 / "1958BC+1000G_REF.EUR..MHC.HLA_IMPUTATION_OUT.alleles"
    ref_hped = v1 / "1958BC+1000G_REF.EUR..MHC.HLA_IMPUTATION_OUT.hped"
    assert sorted(outs.alleles.read_text().splitlines()) == sorted(ref_alleles.read_text().splitlines())
    assert sorted(outs.hped.read_text().splitlines()) == sorted(ref_hped.read_text().splitlines())


@needs_r
def test_g3_omnibus_reproducible_parts(tmp_path, hatk_ex, ra_bfile):
    from hlagent.tools.omnibus import make_aa, run_omnibus

    fam = Path(f"{ra_bfile}.fam")
    aa, _ = make_aa(
        hatk_ex / "OmnibusTest" / "wtccc_filtered_58C_RA.hatk.300+300.chr6.hg18.bgl.phased",
        fam,
        tmp_path / "ra",
    )
    phe = hatk_ex / "wtccc_filtered_58C_RA.hatk.300+300.phe"
    for cond, tag, top in [(None, "RA.NA", "AA_DRB1_96"), (["AA_DRB1_96"], "RA.AA_DRB1_96", "AA_B_109")]:
        out, _ = run_omnibus(fam, aa, phe, "RA", tmp_path / "ra", conditions=cond)
        a = pd.read_csv(out, sep="\t")
        b = pd.read_csv(
            hatk_ex / "OmnibusTest" / f"wtccc_filtered_58C_RA.hatk.300+300.chr6.hg18.{tag}.omnibus", sep="\t"
        )
        m = a.merge(b, on="Variant", suffixes=("_v3", "_hatk"))
        assert len(a) == len(b) == len(m) == 383
        assert (m["deltaDF_v3"].fillna(-1) == m["deltaDF_hatk"].fillna(-1)).all()
        assert (m["N_v3"] == m["N_hatk"]).all()
        assert (m["Residues_v3"] == m["Residues_hatk"]).all()
        mm = m.dropna(subset=["log10_P_v3", "log10_P_hatk"])
        assert spearmanr(mm["log10_P_v3"], mm["log10_P_hatk"]).statistic >= 0.95
        assert a.sort_values("log10_P").iloc[0]["Variant"] == top
        assert b.sort_values("log10_P").iloc[0]["Variant"] == top


def test_g4_meta_matches_v1(hatk_ex):
    s1 = StudyInput(
        "RA",
        hatk_ex
        / "RESULT_EXAMPLE"
        / "RESULT_EXAMPLE_wtccc_filtered_58C_RA.hatk.300+300.chr6.hg18.assoc.logistic",
        hatk_ex / "RESULT_EXAMPLE" / "RESULT_EXAMPLE_wtccc_filtered_58C_RA.hatk.300+300.chr6.hg18.bim",
    )
    s2 = StudyInput(
        "CD",
        hatk_ex
        / "MetaAnalysis"
        / "RESULT_EXAMPLE_wtccc_filtered_NBS_CD.hatk.300+300.chr6.hg18.assoc.logistic",
        hatk_ex / "MetaAnalysis" / "RESULT_EXAMPLE_wtccc_filtered_NBS_CD.hatk.300+300.chr6.hg18.bim",
    )
    out, rep = meta_analyze([s1, s2])
    sys.path.insert(0, str(paths.project_root() / "vendor"))
    from hatk_port.MetaAnalysis.metaanal_utils import run_meta_analysis

    with contextlib.redirect_stdout(io.StringIO()):
        v1, _ = run_meta_analysis(str(s1.assoc), str(s2.assoc), str(s1.bim), str(s2.bim))
    m = out.merge(v1, on="SNP")
    assert len(out) == len(v1) == len(m)
    assert rep.n_flipped["CD"] == 97
    np.testing.assert_allclose(m["BETA_FE"], m["BETA"], atol=1e-12)
    np.testing.assert_allclose(m["SE_FE"], m["SE"], atol=1e-12)
    np.testing.assert_allclose(m["P_FE"], m["MetaP"], rtol=1e-9)


@needs_plink
def test_g5_node1_panel_hla_aa_markers_match_hatk(tmp_path, hatk_ex, ra_bfile):
    """Rebuild the HATK example panel; HLA/AA/INS genotypes must equal the published panel.

    rs SNPs differ by design: the published panel used whole-chr6 SNPs, the shipped input is 29-34 Mb.
    """
    from hlagent.pipeline.steps.node1_bmarker import build_panel_from_chped
    from hlagent.tools import proc

    cache = paths.hatk_cache_dir() / "hg18_imgt3320"
    prefix, _, _ = build_panel_from_chped(
        hatk_ex / "wtccc_filtered_58C_RA.hatk.300+300.imgt3320.2field.chped",
        hatk_ex / "wtccc_filtered_58C_RA.hatk.300+300.hg18.chr6.29-34mb",
        tmp_path / "panel",
        cache,
        hg="18",
        imgt="3320",
    )
    ids = sorted(
        set(pd.read_csv(f"{prefix}.bim", sep="\t", header=None)[1])
        & set(pd.read_csv(f"{ra_bfile}.bim", sep="\t", header=None)[1])
    )
    ids = [i for i in ids if i.startswith(("HLA_", "AA_", "INS_"))]
    assert len(ids) == 901
    (tmp_path / "ids.txt").write_text("\n".join(ids))
    raws = []
    for name, bf in (("new", prefix), ("pub", ra_bfile)):
        proc.run(
            [
                "plink",
                "--bfile",
                str(bf),
                "--extract",
                str(tmp_path / "ids.txt"),
                "--keep-allele-order",
                "--recode",
                "A",
                "--allow-no-sex",
                "--out",
                str(tmp_path / name),
            ],
            log_path=tmp_path / "p.log",
        )
        raws.append(pd.read_csv(tmp_path / f"{name}.raw", sep=r"\s+").set_index("IID").sort_index(axis=1))
    a, b = raws
    assert list(a.columns) == list(b.columns)
    assert a.loc[b.index].fillna(-1).equals(b.fillna(-1))


@needs_plink
@needs_java
@pytest.mark.slow
def test_stage_p_phasing_invariant(tmp_path, ra_bfile):
    """Phased haplotype pairs must equal the unphased input genotypes (BEAGLE 3.3.2 chain, ~15 min)."""
    from hlagent.tools.beagle import PhasingParams, check_phasing_consistency, phase_bmarker_panel

    ph, _, cmds = phase_bmarker_panel(ra_bfile, tmp_path / "ra", PhasingParams(java_mem_gb=4))
    assert any("seed=-99999" in c for c in cmds)
    res = check_phasing_consistency(ra_bfile, ph)
    assert res["checked"] > 1_000_000 and res["mismatched"] == 0
