"""Stage I: HLA imputation with CookHLA (Docker), plan section 5.3."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from hlagent import paths
from hlagent.io.formats import read_fam, read_hped
from hlagent.pipeline.contracts import ArtifactRef, NodeResult, StudySpec
from hlagent.pipeline.steps.common import reference_prefix
from hlagent.tools.cookhla import (
    REFERENCE_HLA_GENES,
    CookHLAParams,
    alleles_summary,
    check_memory_budget,
    container_name,
    find_agm,
    read_alleles,
    run_cookhla,
    vcf_dr2_summary,
)


def liftover_dir() -> Path:
    return paths.resources_dir() / "liftover"


def run(ctx, study: StudySpec) -> NodeResult:
    p = ctx.params.stage_i
    d = ctx.require("StageD", study.study_id)
    out = ctx.step_dir("StageI", study.study_id)
    res = NodeResult(node="StageI", study_id=study.study_id, status="ok", cache_key="")

    # Prefer the original build with liftover chains (CookHLA's own liftover); otherwise the
    # Stage D hg18 re-mapping, which needs no chains.
    build = d.metrics.get("build_input")
    use_input = "snps_input" in d.artifacts and build in ("hg19", "hg38")
    hg = build[2:] if use_input else "18"
    tentative = CookHLAParams(
        input_prefix=d.art("snps_input") if use_input else d.art("snps_hg18"),
        hg=hg,
        reference_prefix=reference_prefix(study.reference_population),
        out_dir=out / "cookhla",
        out_name=f"{study.study_id}+1000G_REF.{study.reference_population}",
        liftover_dir=liftover_dir(),
    )
    if use_input and tentative.missing_chains():
        res.warnings.append(
            f"Liftover chains {tentative.missing_chains()} not installed; using the Stage D hg18 "
            "re-mapping instead (run `hlagent setup-resources --liftover-chains` to use CookHLA's liftover)."
        )
        use_input, hg = False, "18"
    inp = d.art("snps_input") if use_input else d.art("snps_hg18")

    gm = ae = None
    if p.use_bundled_agm and study.genotype_prefix is not None:
        agm = find_agm(study.genotype_prefix.parent)
        if agm:
            gm, ae = agm
            res.warnings.append(f"Using adaptive genetic map shipped with the input: {gm.name}")
    cp = CookHLAParams(
        input_prefix=inp,
        hg=hg,
        reference_prefix=reference_prefix(study.reference_population),
        out_dir=out / "cookhla",
        out_name=f"{study.study_id}+1000G_REF.{study.reference_population}",
        genetic_map=gm,
        error_rate=ae,
        java_mem_gb=p.java_mem_gb,
        n_processes=p.n_processes,
        nthreads=p.nthreads,
        liftover_dir=liftover_dir(),
    )
    ok, need, avail = check_memory_budget(cp)
    res.metrics.update(
        {"memory_needed_gb": need, "memory_available_gb": round(avail, 1), "cookhla_input_build": f"hg{hg}"}
    )
    if not ok:
        res.status, res.error_kind = "failed", "resource_error"
        res.error_message = (
            f"CookHLA needs about {need:.0f} GB ({p.n_processes} processes x {p.java_mem_gb} GB) but only "
            f"{avail:.1f} GB is available (limit 80%). Lower n_processes or java_mem_gb."
        )
        return res
    outs, cmds = run_cookhla(
        cp,
        log_path=out / "cookhla.log",
        docker=ctx.docker,
        container_name=container_name(ctx.run_dir.name, study.study_id),
    )
    res.commands += cmds

    # QC summaries
    al = read_alleles(outs.alleles)
    summ = alleles_summary(al, p.conf_threshold)
    dr2 = vcf_dr2_summary(outs.raw_vcfs)
    (out / "imputation_qc.json").write_text(json.dumps({"alleles": summ, "dr2": dr2}, indent=1))
    for g, s in summ.items():
        res.metrics[f"{g}_conf_mean"] = round(s["conf_mean"], 4)
        res.metrics[f"{g}_frac_conf_lt_{p.conf_threshold}"] = round(s["frac_conf_below_threshold"], 4)
    for k, v in dr2.items():
        res.metrics[f"DR2_{k}_median_maf_ge_{v['min_maf']}"] = round(v["median"], 4)
        res.metrics[f"DR2_{k}_n_markers_maf_ge_{v['min_maf']}"] = v["n_maf_ge_min"]
    missing = [g for g in ("DPA1", "DPB1", "DQA1") if g not in REFERENCE_HLA_GENES]
    res.warnings.append(
        f"The 1000G_REF panel imputes {', '.join(REFERENCE_HLA_GENES)} only; "
        f"{', '.join(missing)} are left untyped."
    )
    low = [g for g, s in summ.items() if s["frac_conf_below_threshold"] > 0.2]
    if low:
        res.warnings.append(
            f"More than 20% of calls below confidence {p.conf_threshold} for: {', '.join(low)}"
        )

    # HPED with sex/phenotype restored from Stage D (CookHLA writes sex=0, pheno=-9)
    hped = read_hped(outs.hped)
    fam = read_fam(Path(f"{d.art('snps_hg18')}.fam"))
    hped = hped.drop(columns=["PID", "MID", "SEX", "PHENO"]).merge(fam, on=["FID", "IID"], how="left")
    hped = hped[
        [
            "FID",
            "IID",
            "PID",
            "MID",
            "SEX",
            "PHENO",
            *[c for c in hped.columns if c[:-2] in ("A", "B", "C", "DPA1", "DPB1", "DQA1", "DQB1", "DRB1")],
        ]
    ]
    hped = hped.fillna({"PID": "0", "MID": "0", "SEX": "0", "PHENO": "-9"})
    hped_path = out / "hla.hped"
    hped.to_csv(hped_path, sep="\t", header=False, index=False)
    res.artifacts["hla"] = ArtifactRef.of("hped", hped_path, description="CookHLA HLA types (2-field, HPED)")
    res.artifacts["alleles"] = ArtifactRef.of(
        "alleles", outs.alleles, description="CookHLA allele calls + posteriors"
    )
    if outs.lifted_bfile is not None:
        res.artifacts["snps_hg18"] = ArtifactRef.of(
            "bfile",
            outs.lifted_bfile,
            build="hg18",
            description="SNPs as aligned by CookHLA to the reference (hg18)",
        )
    res.metrics["n_samples_imputed"] = int(pd.Series(al["IID"]).nunique())
    if res.warnings:
        res.status = "warning"
    return res
