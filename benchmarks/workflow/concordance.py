"""Concordance of HLAgent v3 outputs with the conventional (standalone) tool outputs.

References are the published HATK example results (WTCCC 58C vs RA, 300 + 300; Choi et al. 2021) and the
CookHLA output produced by HLAgent v1 with the stand-alone container. Reads the run directories recorded
by run_benchmark.py (replicate 1) and writes concordance.json.

    python benchmarks/workflow/concordance.py --results benchmarks/workflow/results
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from hlagent import paths
from hlagent.io.formats import read_assoc, read_bim
from hlagent.tools import proc
from hlagent.tools.beagle import check_phasing_consistency
from hlagent.tools.cookhla import read_alleles

EX = paths.examples_dir() / "hatk_wtccc"
PUB_ASSOC = (
    EX / "RESULT_EXAMPLE" / "RESULT_EXAMPLE_wtccc_filtered_58C_RA.hatk.300+300.chr6.hg18.assoc.logistic"
)
PUB_PANEL = EX / "RESULT_EXAMPLE" / "RESULT_EXAMPLE_wtccc_filtered_58C_RA.hatk.300+300.chr6.hg18"
PUB_OMNI = {
    "NA": EX / "OmnibusTest" / "wtccc_filtered_58C_RA.hatk.300+300.chr6.hg18.RA.NA.omnibus",
    "AA_DRB1_96": EX / "OmnibusTest" / "wtccc_filtered_58C_RA.hatk.300+300.chr6.hg18.RA.AA_DRB1_96.omnibus",
}
V1_COOKHLA = (
    paths.examples_dir() / "cookhla_v1_output" / "1958BC+1000G_REF.EUR..MHC.HLA_IMPUTATION_OUT.alleles"
)


def mtype(s: str) -> str:
    return "rs" if s.startswith("rs") else s.split("_", 1)[0]


def run_dir(results: Path, scenario: str, rep: int = 1) -> Path:
    return Path(json.loads((results / f"{scenario}.rep{rep}.json").read_text())["run_dir"])


def regression(rd: Path, out_dir: Path) -> dict:
    """Node2 association statistics vs the published HATK result (same marker IDs)."""
    pub = read_assoc(PUB_ASSOC)
    ours = read_assoc(rd / "WTCCC_RA" / "node2" / "assoc.assoc.logistic")
    m = pub.merge(ours, on="SNP", suffixes=("_pub", "_hla"))
    m = m[m["P_pub"].notna() & m["P_hla"].notna()]
    out: dict = {
        "n_published": int(pub["P"].notna().sum()),
        "n_hlagent": int(ours["P"].notna().sum()),
        "n_shared_tested": len(m),
    }
    rel = lambda a, b: np.abs(a - b) / np.maximum(np.abs(b), 1e-300)  # noqa: E731
    same_a1 = (m["A1_pub"] == m["A1_hla"]).mean()
    # identical at PLINK's printed precision (4 significant digits): relative difference < 5e-4
    for col in ("OR", "SE", "P"):
        out[f"{col}_identical_fraction"] = float((rel(m[f"{col}_hla"], m[f"{col}_pub"]) < 5e-4).mean())
        out[f"{col}_max_rel_diff"] = float(rel(m[f"{col}_hla"], m[f"{col}_pub"]).max())
    lp_pub, lp_hla = -np.log10(m["P_pub"]), -np.log10(m["P_hla"])
    out.update(
        {
            "A1_identical_fraction": float(same_a1),
            "max_abs_diff_minus_log10P": float(np.abs(lp_pub - lp_hla).max()),
            "pearson_minus_log10P": float(np.corrcoef(lp_pub, lp_hla)[0, 1]),
            "top_marker_published": pub.loc[pub["P"].idxmin(), "SNP"],
            "top_marker_hlagent": ours.loc[ours["P"].idxmin(), "SNP"],
            "by_type": {},
        }
    )
    for t, g in m.groupby(m["SNP"].map(mtype)):
        out["by_type"][t] = {
            "n": len(g),
            "P_identical_fraction": float((rel(g["P_hla"], g["P_pub"]) < 5e-4).mean()),
        }
    # Published-only markers: SNPS markers whose minor allele is IMGT's '.' (intron sequence unknown).
    # PLINK 1.9 b7 reads '.' as a missing allele code, so the marker is monomorphic and bMarkerGenerator's
    # --maf 0.0001 drops it; with '.' as the major allele the marker is kept (allele shown as '0').
    pbim = read_bim(Path(f"{PUB_PANEL}.bim")).set_index("SNP")
    only = sorted(set(pub.loc[pub["P"].notna(), "SNP"]) - set(ours["SNP"]))
    out["published_only"] = {
        "n": len(only),
        "by_type": pd.Series([mtype(s) for s in only]).value_counts().to_dict(),
        "n_minor_allele_dot": int((pbim.loc[only, "A1"] == ".").sum()),
        "n_dot_major_allele_markers_kept": int(((pbim["A2"] == ".") & pbim.index.isin(ours["SNP"])).sum()),
    }
    table = out_dir / "B1.node2_vs_published.tsv"
    m[["SNP", "P_pub", "P_hla"]].to_csv(table, sep="\t", index=False)
    out["_table"] = table.name
    return out


def panel(rd: Path) -> dict:
    """Node1 binary marker genotypes vs the published HATK panel (HLA, AA, SNPS, INS markers)."""
    import tempfile

    ours = rd / "WTCCC_RA" / "node1" / "panel"
    ids = sorted(set(read_bim(Path(f"{ours}.bim"))["SNP"]) & set(read_bim(Path(f"{PUB_PANEL}.bim"))["SNP"]))
    ids = [i for i in ids if i.startswith(("HLA_", "AA_", "SNPS_", "INS_"))]
    with tempfile.TemporaryDirectory() as td:
        Path(td, "ids").write_text("\n".join(ids))
        raws = []
        for tag, pre in (("pub", PUB_PANEL), ("ours", ours)):
            cmd = ["plink", "--bfile", str(pre), "--extract", f"{td}/ids", "--recode", "A"]
            cmd += ["--keep-allele-order", "--allow-no-sex", "--out", f"{td}/{tag}"]
            proc.run(cmd, log_path=Path(td, f"{tag}.plink.log"))
            raws.append(pd.read_csv(f"{td}/{tag}.raw", sep=r"\s+").set_index("IID"))
    a, b = raws
    cols = sorted(set(a.columns[5:]) & set(b.columns[5:]))
    a, b = a.loc[b.index, cols], b[cols]
    both = a.notna() & b.notna()
    mism = int(((a != b) & both).sum().sum())
    return {
        "n_markers_compared": len(cols),
        "n_samples": len(b),
        "n_genotypes_compared": int(both.sum().sum()),
        "n_mismatches": mism,
        "by_type": {t: len([c for c in cols if c.startswith(t)]) for t in ("HLA_", "AA_", "SNPS_", "INS_")},
    }


def phasing(rd: Path) -> dict:
    sp = rd / "WTCCC_RA" / "stagep"
    res = check_phasing_consistency(rd / "WTCCC_RA" / "node1" / "panel", sp / "panel.bgl.phased")
    return {k: int(v) for k, v in res.items()}


def omnibus(rd: Path, cond: str) -> dict:
    return compare_omnibus(PUB_OMNI[cond], rd / "WTCCC_RA" / "node4" / f"omnibus.RA.{cond}.omnibus")


def omnibus_on_published_haplotypes(work: Path) -> dict:
    """Node4 code on the published phased haplotypes: separates the omnibus computation from phasing."""
    from hlagent.tools.omnibus import make_aa, run_omnibus

    work.mkdir(parents=True, exist_ok=True)
    fam = Path(f"{PUB_PANEL}.fam")
    aa, _ = make_aa(
        EX / "OmnibusTest" / "wtccc_filtered_58C_RA.hatk.300+300.chr6.hg18.bgl.phased", fam, work / "ra"
    )
    phe = EX / "wtccc_filtered_58C_RA.hatk.300+300.phe"
    out = {}
    for cond in ("NA", "AA_DRB1_96"):
        f, _ = run_omnibus(fam, aa, phe, "RA", work / "ra", conditions=None if cond == "NA" else [cond])
        out[cond] = compare_omnibus(PUB_OMNI[cond], f)
    return out


def own_vs_published_phase(results: Path) -> dict:
    """HLAgent omnibus from its own phasing (B1/B2) vs from the published haplotypes (same code)."""
    pp = results / "omnibus_published_phase"
    pairs = {
        "NA": (
            run_dir(results, "B1_WTCCC_RA_Node1-5") / "WTCCC_RA/node4/omnibus.RA.NA.omnibus",
            pp / "ra.RA.NA.omnibus",
        ),
        "AA_DRB1_96": (
            run_dir(results, "B2_WTCCC_RA_Node4_cond_DRB1_96")
            / "WTCCC_RA/node4/omnibus.RA.AA_DRB1_96.omnibus",
            pp / "ra.RA.AA_DRB1_96.omnibus",
        ),
    }
    out = {}
    for cond, (own, pub_phase) in pairs.items():
        m = pd.read_csv(own, sep="\t").merge(
            pd.read_csv(pub_phase, sep="\t"), on="Variant", suffixes=("_own", "_pp")
        )
        m = m.dropna(subset=["log10_P_own", "log10_P_pp"])
        d = (m["log10_P_own"] - m["log10_P_pp"]).abs()
        out[cond] = {
            "n": len(m),
            "n_identical": int((d < 1e-9).sum()),
            "max_abs_diff_log10P": float(d.max()),
            "spearman": float(stats.spearmanr(m["log10_P_own"], m["log10_P_pp"]).statistic),
            "top3_own": m.sort_values("log10_P_own")["Variant"].head(3).tolist(),
            "top3_published_phase": m.sort_values("log10_P_pp")["Variant"].head(3).tolist(),
        }
    # the distributed amino-acid file cannot be read by the HATK R script: count malformed lines
    with open(EX / "OmnibusTest" / "wtccc_filtered_58C_RA.hatk.300+300.chr6.hg18.aa") as fh:
        widths = [len(ln.split()) for ln in fh]
    out["published_aa_malformed_lines"] = sum(w != max(widths) for w in widths)
    return out


def compare_omnibus(pub_path: Path, ours_path: Path) -> dict:
    pub = pd.read_csv(pub_path, sep="\t")
    ours = pd.read_csv(ours_path, sep="\t")
    m = pub.merge(ours, on="Variant", suffixes=("_pub", "_hla"))
    n_tested = int(m[["log10_P_pub", "log10_P_hla"]].notna().all(axis=1).sum())
    m = m.dropna(subset=["log10_P_pub", "log10_P_hla"]) if n_tested < len(m) else m
    rho = stats.spearmanr(-m["log10_P_pub"], -m["log10_P_hla"]).statistic
    return {
        "n_published": len(pub),
        "n_hlagent": len(ours),
        "n_shared_tested": n_tested,
        "deltaDF_identical_fraction": float((m["deltaDF_pub"] == m["deltaDF_hla"]).mean()),
        "residues_identical_fraction": float((m["Residues_pub"] == m["Residues_hla"]).mean()),
        "spearman_minus_log10P": float(rho),
        "pearson_minus_log10P": float(np.corrcoef(m["log10_P_pub"], m["log10_P_hla"])[0, 1]),
        "max_abs_diff_log10P": float((m["log10_P_pub"] - m["log10_P_hla"]).abs().max()),
        "top_published": pub.loc[pub["log10_P"].idxmin(), "Variant"],
        "top_published_log10P": float(pub["log10_P"].min()),
        "top_hlagent": ours.loc[ours["log10_P"].idxmin(), "Variant"],
        "top_hlagent_log10P": float(ours["log10_P"].min()),
    }


def phasing_inputs(rd: Path) -> dict:
    """Marker counts of the phased panels: the published haplotypes were estimated on a whole-chr6 panel."""

    def n_markers(p: Path) -> int:
        with open(p) as fh:
            return sum(1 for ln in fh if ln.startswith("M "))

    return {
        "published_bgl_phased_markers": n_markers(
            EX / "OmnibusTest" / "wtccc_filtered_58C_RA.hatk.300+300.chr6.hg18.bgl.phased"
        ),
        "hlagent_bgl_phased_markers": n_markers(rd / "WTCCC_RA" / "stagep" / "panel.bgl.phased"),
    }


def cookhla(rd: Path) -> dict:
    """Stage I calls vs the v1 stand-alone CookHLA run on the same 10 samples (unordered allele pairs)."""
    found = sorted((rd / "GenotypeExample" / "stagei").rglob("*.HLA_IMPUTATION_OUT.alleles"))
    if not found:
        raise FileNotFoundError(f"no CookHLA .alleles under {rd}")
    m = read_alleles(found[0]).merge(read_alleles(V1_COOKHLA), on=["IID", "gene"], suffixes=("_hla", "_v1"))
    out: dict = {"file": found[0].name, "n_genotypes": len(m), "by_gene": {}}
    for res in ("alleles_1field", "alleles_2field"):
        same = pd.Series(
            [
                sorted(str(a).split(",")) == sorted(str(b).split(","))
                for a, b in zip(m[f"{res}_hla"], m[f"{res}_v1"], strict=True)
            ],
            index=m.index,
        )
        out[f"{res}_identical_fraction"] = float(same.mean())
        for g, idx in m.groupby("gene").groups.items():
            out["by_gene"].setdefault(str(g), {})[res] = float(same.loc[idx].mean())
    out["max_abs_diff_conf"] = float((m["conf_hla"] - m["conf_v1"]).abs().max())
    m["same"] = [
        sorted(str(a).split(",")) == sorted(str(b).split(","))
        for a, b in zip(m["alleles_2field_hla"], m["alleles_2field_v1"], strict=True)
    ]
    out["discordant_2field"] = m.loc[
        ~m["same"], ["IID", "gene", "alleles_2field_hla", "conf_hla", "alleles_2field_v1", "conf_v1"]
    ].to_dict("records")
    out["inputs"] = cookhla_inputs(rd)
    return out


def cookhla_inputs(rd: Path) -> dict:
    """CookHLA target SNPs: v1 (liftOver hg19->hg18) vs HLAgent Stage D (rsID re-mapping to hg18)."""
    import tempfile

    v1 = V1_COOKHLA.parent / "1958BC.hg19.COPY.LiftDown_hg18.NoAmbig"
    ours = next((rd / "GenotypeExample" / "stagei").rglob("*.COPY.NoAmbig.bim")).with_suffix("")
    a, b = read_bim(Path(f"{v1}.bim")), read_bim(Path(f"{ours}.bim"))
    shared = sorted(set(a["SNP"]) & set(b["SNP"]))
    pos = a.merge(b, on="SNP", suffixes=("_v1", "_hla"))
    with tempfile.TemporaryDirectory() as td:
        Path(td, "ids").write_text("\n".join(shared))
        raws = []
        for tag, pre in (("v1", v1), ("hla", ours)):
            cmd = ["plink", "--bfile", str(pre), "--extract", f"{td}/ids", "--recode", "A", "--allow-no-sex"]
            proc.run([*cmd, "--out", f"{td}/{tag}"], log_path=Path(td, f"{tag}.log"))
            raws.append(pd.read_csv(f"{td}/{tag}.raw", sep=r"\s+").set_index("IID"))
    x, y = raws
    same = 0
    for col in x.columns[5:]:
        snp, allele = col.rsplit("_", 1)
        other = next(c for c in y.columns[5:] if c.rsplit("_", 1)[0] == snp)
        vy = y.loc[x.index, other] if other.rsplit("_", 1)[1] == allele else 2 - y.loc[x.index, other]
        same += bool((x[col].fillna(-1) == vy.fillna(-1)).all())
    return {
        "n_snps_v1": len(a),
        "n_snps_hlagent": len(b),
        "n_shared": len(shared),
        "n_shared_same_bp": int((pos["BP_v1"] == pos["BP_hla"]).sum()),
        "n_shared_genotype_identical": same,
        "hlagent_only": sorted(set(b["SNP"]) - set(a["SNP"])),
    }


def meta(rd: Path) -> dict:
    """Recompute fixed/random effects from the per-study aligned estimates with an independent implementation."""
    t = pd.read_csv(rd / "node5" / "meta.tsv", sep="\t")
    bcols = [c for c in t.columns if c.startswith("BETA_") and c not in ("BETA_FE", "BETA_RE")]
    scols = [c.replace("BETA_", "SE_") for c in bcols]
    B, S = t[bcols].to_numpy(float), t[scols].to_numpy(float)
    ok = np.isfinite(B).all(1) & np.isfinite(S).all(1) & (S > 0).all(1)
    B, S, t = B[ok], S[ok], t[ok]
    w = 1 / S**2
    bfe = (w * B).sum(1) / w.sum(1)
    sefe = 1 / np.sqrt(w.sum(1))
    pfe = 2 * stats.norm.sf(np.abs(bfe / sefe))
    q = (w * (B - bfe[:, None]) ** 2).sum(1)
    k = B.shape[1]
    i2 = np.where(q > 0, np.maximum(0, (q - (k - 1)) / np.where(q > 0, q, 1)), 0)
    c = w.sum(1) - (w**2).sum(1) / w.sum(1)
    tau2 = np.maximum(0, (q - (k - 1)) / c)
    wr = 1 / (S**2 + tau2[:, None])
    bre = (wr * B).sum(1) / wr.sum(1)
    sere = 1 / np.sqrt(wr.sum(1))
    pre = 2 * stats.norm.sf(np.abs(bre / sere))
    d = {
        "BETA_FE": bfe,
        "SE_FE": sefe,
        "P_FE": pfe,
        "Q": q,
        "I2": i2,
        "TAU2": tau2,
        "BETA_RE": bre,
        "P_RE": pre,
    }
    out = {"n_markers": int(ok.sum()), "k": k}
    for col, v in d.items():
        diff = np.abs(t[col].to_numpy(float) - v)
        if col.startswith("P_"):
            diff = np.abs(
                np.log10(np.maximum(t[col].to_numpy(float), 1e-300)) - np.log10(np.maximum(v, 1e-300))
            )
            out[f"max_abs_diff_log10_{col}"] = float(np.nanmax(diff))
        else:
            out[f"max_abs_diff_{col}"] = float(np.nanmax(diff))
    return out


DETERMINISM_FILES = {
    "B1_WTCCC_RA_Node1-5": [
        "WTCCC_RA/node1/panel.bed",
        "WTCCC_RA/node2/assoc.assoc.logistic",
        "WTCCC_RA/node3/conditional_steps.tsv",
        "WTCCC_RA/stagep/panel.bgl.phased",
        "WTCCC_RA/node4/omnibus.RA.NA.omnibus",
        "node5/meta.tsv",
    ],
    "B2_WTCCC_RA_Node4_cond_DRB1_96": ["WTCCC_RA/node4/omnibus.RA.AA_DRB1_96.omnibus"],
    "B3_GenotypeExample_CookHLA_Node1-2": [
        "GenotypeExample/node1/panel.bed",
        "GenotypeExample/node2/assoc.assoc.logistic",
    ],
    "B4_BMExample_Node1-4": [
        "BMExample/node2/assoc.assoc.logistic",
        "BMExample/stagep/panel.bgl.phased",
        "BMExample/node4/omnibus.SYNTHETIC.NA.omnibus",
    ],
}


def determinism(results: Path) -> dict:
    """SHA-256 of key outputs across replicate runs: the analysis layer is deterministic (fixed BEAGLE seed)."""
    import hashlib

    out: dict = {}
    for sc, files in DETERMINISM_FILES.items():
        reps = sorted(results.glob(f"{sc}.rep*.json"))
        dirs = [Path(json.loads(r.read_text())["run_dir"]) for r in reps]
        per_file = {}
        for f in files:
            hashes = [hashlib.sha256((d / f).read_bytes()).hexdigest() for d in dirs if (d / f).exists()]
            per_file[f] = {
                "n_reps": len(hashes),
                "identical": len(hashes) == len(dirs) and len(set(hashes)) == 1,
            }
        out[sc] = per_file
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", type=Path, required=True)
    a = ap.parse_args()
    out: dict = {"determinism": determinism(a.results)}
    b1 = run_dir(a.results, "B1_WTCCC_RA_Node1-5")
    out["node2_regression"] = regression(b1, a.results)
    out["node1_panel"] = panel(b1)
    out["stagep_phasing_invariant"] = phasing(b1)
    out["stagep_phasing_inputs"] = phasing_inputs(b1)
    out["node4_omnibus_unconditioned"] = omnibus(b1, "NA")
    out["node4_on_published_haplotypes"] = omnibus_on_published_haplotypes(
        a.results / "omnibus_published_phase"
    )
    out["node5_meta_recomputed"] = meta(b1)
    try:
        out["node4_omnibus_conditioned_DRB1_96"] = omnibus(
            run_dir(a.results, "B2_WTCCC_RA_Node4_cond_DRB1_96"), "AA_DRB1_96"
        )
    except FileNotFoundError as e:
        out["node4_omnibus_conditioned_DRB1_96"] = {"missing": str(e)}
    out["node4_own_vs_published_phase"] = own_vs_published_phase(a.results)
    try:
        out["stagei_cookhla_vs_v1"] = cookhla(run_dir(a.results, "B3_GenotypeExample_CookHLA_Node1-2"))
    except FileNotFoundError as e:
        out["stagei_cookhla_vs_v1"] = {"missing": str(e)}
    (a.results / "concordance.json").write_text(
        json.dumps(
            out, indent=1, default=lambda x: None if isinstance(x, float) and math.isnan(x) else str(x)
        )
    )
    print(json.dumps(out, indent=1, default=str)[:6000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
