"""Stage D: data intake & QC (plan section 5.2).

Outputs (artifacts):
  snps_hg18  PLINK SNP data in hg18 coordinates, chr6 region, QC'd   (Node1 --variants, CookHLA -hg 18)
  snps_input PLINK SNP data in the original build (hg19/hg38 only)   (CookHLA with liftover chains)
  pheno      FID IID <name> table aligned to the QC'd samples
  hla        HLA types (chped/hped) restricted to the QC'd samples, when given
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from hlagent.io.formats import bfile_exists, hped_genes_typed, read_fam, read_hped, read_pheno
from hlagent.pipeline.contracts import ArtifactRef, NodeResult, StudySpec
from hlagent.pipeline.params import StageDParams
from hlagent.pipeline.steps.common import (
    classify_pheno,
    is_family_data,
    n_samples,
    n_variants,
    reference_bim,
)
from hlagent.stats import synthetic
from hlagent.stats.build import detect_build, position_match_fraction, remap_table
from hlagent.tools import proc

# ----------------------------------------------------------------------------- preflight


ASSOCIATION_NODES = frozenset({"Node2", "Node3", "Node4", "Node5"})


def preflight(study: StudySpec, params: StageDParams | None = None, needs_phenotype: bool = True) -> dict:
    """Quick checks for the plan card: inputs, build, family structure, phenotype, HLA genes.

    Uses only Python file reads (no PLINK), so the planner can call it before approval.
    `needs_phenotype` is False when the plan has no association node (e.g. imputation + marker panel only);
    a missing phenotype is then reported but does not block the plan.
    """
    p = params or StageDParams()
    rep: dict = {"study_id": study.study_id, "errors": [], "warnings": [], "needs_user_choice": []}
    fam = None
    if study.genotype_prefix is not None:
        if not bfile_exists(study.genotype_prefix):
            rep["errors"].append(f"PLINK files not found for prefix {study.genotype_prefix}")
        else:
            fam = read_fam(Path(f"{study.genotype_prefix}.fam"))
            rep["n_samples"] = len(fam)
            rep["n_snps"] = n_variants(study.genotype_prefix)
            rep["family_data"] = is_family_data(fam)
            rep["n_founders"] = int(((fam["PID"] == "0") & (fam["MID"] == "0")).sum())
            b = detect_build(Path(f"{study.genotype_prefix}.bim"), reference_bim(), p.build_match_threshold)
            rep["build"] = b.as_dict()
            if study.hg:
                rep["build"]["user_override"] = f"hg{study.hg}"
            elif b.build == "unknown":
                rep["warnings"].append(
                    f"Genome build not recognised ({b.note}). Coordinates will be re-mapped to hg18 by rsID "
                    f"({b.n_shared_rsids} rsIDs shared with the reference panel); other SNPs are dropped."
                )
            if rep.get("family_data") and p.founders_only:
                rep["warnings"].append(
                    f"Family data: association steps use the {rep['n_founders']} founders only (unrelated samples)."
                )
    if study.hla_file is not None:
        if not study.hla_file.exists():
            rep["errors"].append(f"HLA file not found: {study.hla_file}")
        else:
            hla = read_hped(study.hla_file)
            genes = hped_genes_typed(hla)
            rep["hla_genes_typed"] = {g: n for g, n in genes.items() if n}
            rep["hla_genes_missing"] = [g for g, n in genes.items() if n == 0]
            if fam is not None:
                common = set(fam["IID"]) & set(hla["IID"])
                rep["n_samples_with_hla"] = len(common)
                if len(common) < 0.95 * len(fam):
                    rep["warnings"].append(f"Only {len(common)}/{len(fam)} genotyped samples have HLA types.")
            if fam is None:
                fam = hla.iloc[:, :6].copy()
                fam.columns = ["FID", "IID", "PID", "MID", "SEX", "PHENO"]
                rep["n_samples"] = len(fam)
    # phenotype
    ph = _phenotype_source(study, fam)
    rep["phenotype"] = ph["info"]
    if ph["info"].get("source_error"):
        rep["errors"].append(ph["info"]["source_error"])
    elif not ph["info"].get("usable"):
        if study.synthetic_phenotype is None and not needs_phenotype:
            rep["phenotype"]["note"] = (
                "no usable phenotype; not needed because no association node is requested"
            )
        elif study.synthetic_phenotype is None:
            rep["needs_user_choice"].append(
                "phenotype: the phenotype has no usable variation "
                f"({ph['info'].get('type')}, cases={ph['info'].get('n_cases')}, controls={ph['info'].get('n_controls')}). "
                "Upload a phenotype file, or use a demo-only synthetic phenotype (null, or spike_in when HLA types exist)."
            )
        else:
            rep["warnings"].append(
                f"Using a SYNTHETIC {study.synthetic_phenotype.mode} phenotype (demo only)."
            )
    n = rep.get("n_founders") if rep.get("family_data") and p.founders_only else rep.get("n_samples")
    if n is not None and n < 50:
        rep["warnings"].append(
            f"Small sample (n={n}): regression estimates will be unstable; many markers may be NA."
        )
    if study.synthetic_phenotype and study.synthetic_phenotype.mode == "spike_in" and study.hla_file is None:
        rep["errors"].append(
            "spike_in synthetic phenotype needs HLA types at Stage D; use mode=null for imputed studies."
        )
    return rep


def _phenotype_source(study: StudySpec, fam: pd.DataFrame | None) -> dict:
    """Return {'table': FID IID <name> or None, 'name': str, 'info': {...}} without synthetic generation."""
    if study.pheno_file is not None:
        if not study.pheno_file.exists():
            return {
                "table": None,
                "name": None,
                "info": {"source_error": f"phenotype file not found: {study.pheno_file}"},
            }
        tab = read_pheno(study.pheno_file)
        cols = [c for c in tab.columns if c not in ("FID", "IID")]
        name = study.pheno_name or (cols[0] if len(cols) == 1 else None)
        if name is None or name not in tab.columns:
            return {
                "table": None,
                "name": None,
                "info": {"source_error": f"choose pheno_name from {cols}", "columns": cols},
            }
        info = classify_pheno(tab[name])
        info["source"] = f"{study.pheno_file.name}:{name}"
        return {"table": tab[["FID", "IID", name]], "name": name, "info": info}
    if fam is not None:
        name = study.pheno_name or "PHENO"
        info = classify_pheno(fam["PHENO"])
        info["source"] = "fam column 6"
        tab = fam[["FID", "IID", "PHENO"]].rename(columns={"PHENO": name})
        return {"table": tab, "name": name, "info": info}
    return {"table": None, "name": None, "info": {"type": "none", "usable": False, "source": "none"}}


# ----------------------------------------------------------------------------- run


def run(ctx, study: StudySpec) -> NodeResult:  # noqa: C901 - linear recipe, kept in one place on purpose
    p: StageDParams = ctx.params.stage_d
    out = ctx.step_dir("StageD", study.study_id)
    res = NodeResult(node="StageD", study_id=study.study_id, status="ok", cache_key="")
    log = out / "stage_d.log"
    needs_phenotype = bool(set(ctx.plan.nodes) & ASSOCIATION_NODES)
    pre = preflight(study, p, needs_phenotype)
    (out / "preflight.json").write_text(json.dumps(pre, indent=1, default=str))
    if pre["errors"]:
        res.status, res.error_kind = "failed", "input_error"
        res.error_message = "; ".join(pre["errors"])
        return res
    # synthetic-phenotype notices are re-issued below when the phenotype is generated
    res.warnings += [w for w in pre["warnings"] if not w.startswith("Using a SYNTHETIC")]
    keep_ids: set[str] | None = None

    # ---- genotypes
    if study.genotype_prefix is not None:
        src = study.genotype_prefix
        build = f"hg{study.hg}" if study.hg else pre["build"]["build"]
        res.metrics.update(
            {
                "build_detected": pre["build"]["build"],
                "build_input": build,
                "build_used": build,
                "build_exact_match": pre["build"]["exact_match_fraction"],
                "n_shared_rsids": pre["build"]["n_shared_rsids"],
                "n_samples_input": pre["n_samples"],
                "n_snps_input": pre["n_snps"],
            }
        )
        founders = ["--filter-founders"] if (p.founders_only and pre.get("family_data")) else []
        # hg18 coordinates
        if build == "hg18":
            hg18_src = src
        else:
            upd, ext, n_shared = remap_table(Path(f"{src}.bim"), reference_bim(), out / "remap")
            r = proc.run(
                [
                    ctx.plink,
                    "--bfile",
                    str(src),
                    "--extract",
                    str(ext),
                    "--update-map",
                    str(upd),
                    "--make-bed",
                    "--allow-no-sex",
                    "--keep-allele-order",
                    "--out",
                    str(out / "remapped"),
                ],
                log_path=log,
            )
            res.commands.append(r.command)
            hg18_src = out / "remapped"
            frac = position_match_fraction(Path(f"{hg18_src}.bim"), reference_bim())
            res.metrics.update(
                {
                    "remap_method": "rsid_to_reference_hg18",
                    "remap_n_snps": n_shared,
                    "remap_position_match": frac,
                }
            )
            if frac < p.harmonized_min_match:
                res.status, res.error_kind = "failed", "input_error"
                res.error_message = f"rsID re-mapping left only {frac:.1%} positions matching hg18."
                return res
            if build != "unknown":  # the unknown-build case was already reported by preflight
                res.warnings.append(
                    f"Coordinates re-mapped to hg18 by rsID ({n_shared} SNPs kept, build was {build})."
                )
            res.metrics["build_used"] = "hg18"
        # region + founders, then QC
        r = proc.run(
            [
                ctx.plink,
                "--bfile",
                str(hg18_src),
                "--chr",
                "6",
                "--from-mb",
                f"{p.region_from_mb:g}",
                "--to-mb",
                f"{p.region_to_mb:g}",
                *founders,
                "--make-bed",
                "--allow-no-sex",
                "--keep-allele-order",
                "--out",
                str(out / "region"),
            ],
            log_path=log,
        )
        res.commands.append(r.command)
        n_after_region = n_samples(out / "region")
        qc = ["--geno", f"{p.geno:g}", "--mind", f"{p.mind:g}"]
        if n_after_region >= p.min_n_for_maf_hwe:
            qc += ["--maf", f"{p.maf:g}", "--hwe", f"{p.hwe:g}"]
        else:
            res.warnings.append(f"n={n_after_region} < {p.min_n_for_maf_hwe}: MAF/HWE filters skipped.")
        r = proc.run(
            [
                ctx.plink,
                "--bfile",
                str(out / "region"),
                *qc,
                "--make-bed",
                "--allow-no-sex",
                "--keep-allele-order",
                "--out",
                str(out / "snps_hg18"),
            ],
            log_path=log,
        )
        res.commands.append(r.command)
        res.artifacts["snps_hg18"] = ArtifactRef.of(
            "bfile", out / "snps_hg18", build="hg18", description="QC'd SNPs, hg18, chr6 29-34 Mb"
        )
        keep_ids = set(read_fam(out / "snps_hg18.fam")["IID"])
        res.metrics.update({"n_samples_qc": len(keep_ids), "n_snps_qc": n_variants(out / "snps_hg18")})
        if build in ("hg19", "hg38"):
            keep = out / "keep.txt"
            read_fam(out / "snps_hg18.fam")[["FID", "IID"]].to_csv(keep, sep="\t", header=False, index=False)
            r = proc.run(
                [
                    ctx.plink,
                    "--bfile",
                    str(src),
                    "--chr",
                    "6",
                    "--keep",
                    str(keep),
                    "--geno",
                    f"{p.geno:g}",
                    "--make-bed",
                    "--allow-no-sex",
                    "--keep-allele-order",
                    "--out",
                    str(out / "snps_input"),
                ],
                log_path=log,
            )
            res.commands.append(r.command)
            res.artifacts["snps_input"] = ArtifactRef.of(
                "bfile",
                out / "snps_input",
                build=build,  # type: ignore[arg-type]
                description=f"QC'd SNPs in the original build ({build})",
            )
        for f in out.glob("region.*"):
            f.unlink()
        for f in out.glob("remapped.*"):
            f.unlink()

    # ---- HLA types
    hla_df = None
    if study.hla_file is not None:
        hla_df = read_hped(study.hla_file)
        if keep_ids is None:
            if p.founders_only:
                hla_df = hla_df[(hla_df["PID"] == "0") & (hla_df["MID"] == "0")]
            keep_ids = set(hla_df["IID"])
        else:
            hla_df = hla_df[hla_df["IID"].isin(keep_ids)]
        kind = "chped" if study.hla_file.suffix.lower() == ".chped" else "hped"
        hla_out = out / f"hla.{kind}"
        hla_df.to_csv(hla_out, sep="\t", header=False, index=False)
        res.artifacts["hla"] = ArtifactRef.of(kind, hla_out, description=f"HLA types ({len(hla_df)} samples)")
        res.metrics["n_samples_with_hla"] = len(hla_df)

    # ---- phenotype
    fam = (
        read_fam(out / "snps_hg18.fam")
        if "snps_hg18" in res.artifacts
        else (hla_df.iloc[:, :6] if hla_df is not None else None)
    )
    if fam is None:  # resolve() already refuses studies without genotypes or HLA types
        raise ValueError(f"{study.study_id}: no samples (give genotypes or HLA types)")
    src = _phenotype_source(study, fam)
    ids = fam[["FID", "IID"]].reset_index(drop=True)
    if study.synthetic_phenotype is not None:
        spec = study.synthetic_phenotype
        dosage = None
        if spec.mode == "spike_in":
            if hla_df is None:  # preflight blocks spike_in without HLA types
                raise ValueError("spike_in synthetic phenotype needs HLA types")
            hd = hla_df.set_index("IID").loc[ids["IID"]].reset_index()
            dosage = synthetic.allele_dosage(hd[[*hla_df.columns]], spec.allele)
        tab, meta = synthetic.generate(ids, spec, dosage)
        name = spec.name
        (out / "synthetic_phenotype.json").write_text(json.dumps(meta, indent=1))
        res.metrics.update({f"synthetic_{k}": v for k, v in meta.items() if isinstance(v, (int, float, str))})
        res.metrics["synthetic"] = True
        res.warnings.append(
            f"SYNTHETIC phenotype ({spec.mode}) generated for demonstration; results carry no biology."
        )
    else:
        if (src["table"] is None or not src["info"].get("usable")) and not needs_phenotype:
            res.metrics.update({"pheno_needed": False, "synthetic": False})
            if res.warnings:
                res.status = "warning"
            return res
        if src["table"] is None or not src["info"].get("usable"):
            res.status, res.error_kind = "blocked", "blocked"
            res.error_message = "phenotype has no usable variation"
            res.user_action = (
                "Provide a phenotype file (FID IID <name>) or choose a demo synthetic phenotype "
                "(null, or spike_in when HLA types exist), then re-run."
            )
            res.metrics.update(
                {f"pheno_{k}": v for k, v in src["info"].items() if isinstance(v, (int, float, str, bool))}
            )
            return res
        name = src["name"]
        tab = ids.merge(src["table"], on=["FID", "IID"], how="left")
        tab[name] = pd.to_numeric(tab[name], errors="coerce").fillna(-9)
        res.metrics["synthetic"] = False
    pheno_path = out / "pheno.tsv"
    tab.to_csv(pheno_path, sep="\t", index=False)
    info = classify_pheno(tab[name])
    res.metrics.update(
        {
            "pheno_name": name,
            "pheno_type": info.get("type"),
            "n_cases": info.get("n_cases"),
            "n_controls": info.get("n_controls"),
            "pheno_n_missing": info.get("n_missing"),
        }
    )
    res.artifacts["pheno"] = ArtifactRef.of("table", pheno_path, description=f"phenotype {name}")
    if info.get("type") == "binary" and min(info.get("n_cases", 0), info.get("n_controls", 0)) < 10:
        res.warnings.append("Fewer than 10 cases or controls: logistic estimates will be unreliable.")
    if res.warnings:
        res.status = "warning"
    return res
