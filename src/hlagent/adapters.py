from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from hlagent.data import load_hla, normalize_allele, sha256
from hlagent.execution import Runner
from hlagent.models import AnalysisIntent, AnalysisOptions
from hlagent.settings import Settings
from hlagent.statistics import condition_columns, correction


def command_version(command: str, args: list[str] | None = None) -> str:
    executable = shutil.which(command)
    if not executable:
        return "unavailable"
    result = subprocess.run([executable, *(args or ["--version"])], capture_output=True, text=True, timeout=20)
    return ((result.stdout or result.stderr).strip().splitlines() or ["unknown"])[0]


def tool_versions(settings: Settings) -> dict[str, str]:
    from importlib.metadata import version
    result = {p: version(p) for p in ("hlagent", "numpy", "scipy", "statsmodels", "pydantic-ai-slim", "langgraph")}
    from hlagent.models import digest
    result["hlagent_source_sha256"] = digest({p.name: sha256(p) for p in sorted(Path(__file__).parent.glob("*.py"))})
    for tool in ("plink2", "plink", "bcftools", "java"):
        executable = shutil.which(getattr(settings, tool))
        result[tool + "_binary_sha256"] = sha256(Path(executable).resolve()) if executable else "unavailable"
    result.update(plink2=command_version(settings.plink2), plink=command_version(settings.plink),
                  bcftools=command_version(settings.bcftools), java=command_version(settings.java, ["-version"]))
    for build in ("hg19", "hg38"):
        chain = settings.home / "tools/chains" / f"{build}ToHg18.over.chain.gz"
        result[build + "_chain_sha256"] = sha256(chain) if chain.is_file() else "unavailable"
    if settings.beagle_jar and settings.beagle_jar.is_file():
        result["beagle_sha256"] = sha256(settings.beagle_jar)
    else:
        result["beagle_sha256"] = "unavailable"
    try:
        response = subprocess.run(["docker", "image", "inspect", settings.cookhla_image],
                                  capture_output=True, text=True, check=True, timeout=15)
        image = json.loads(response.stdout)[0]
        result["cookhla"] = next((r for r in image.get("RepoDigests", []) if "cookhla@" in r), image["Id"])
    except (OSError, subprocess.SubprocessError, ValueError):
        result["cookhla"] = "unavailable"
    return result


def marker_vcf(markers: pd.DataFrame, path: Path) -> dict[str, str]:
    mapping = {f"V{i}": c for i, c in enumerate(markers.columns[2:])}
    with path.open("w") as handle:
        handle.write('##fileformat=VCFv4.3\n##contig=<ID=6>\n')
        handle.write('##FORMAT=<ID=GT,Number=1,Type=String,Description="Nearest hard call for interchange">\n')
        handle.write('##FORMAT=<ID=DS,Number=1,Type=Float,Description="Diploid alternate allele dosage">\n')
        handle.write("#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\t" +
                     "\t".join(f"S{i}" for i in range(len(markers))) + "\n")
        for index, (key, col) in enumerate(mapping.items()):
            values = []
            for dosage in markers[col].to_numpy(float):
                if not np.isfinite(dosage):
                    values.append("./.:.")
                else:
                    hard = int(np.clip(np.rint(dosage), 0, 2))
                    values.append(["0/0", "0/1", "1/1"][hard] + f":{dosage:.12g}")
            handle.write(f"6\t{index + 1}\t{key}\tA\tC\t.\tPASS\t.\tGT:DS\t" + "\t".join(values) + "\n")
    path.with_suffix(".mapping.json").write_text(json.dumps(mapping))
    return mapping


def plink_association(runner: Runner, settings: Settings, markers: pd.DataFrame, y: np.ndarray,
                      cov: pd.DataFrame, metadata: pd.DataFrame, intent: AnalysisIntent,
                      options: AnalysisOptions, conditions: list[str] | None = None,
                      tag: str = "association") -> pd.DataFrame:
    directory = runner.directory
    prefix = directory / "genotypes"
    vcf = directory / "markers.vcf"
    if not vcf.exists():
        marker_vcf(markers, vcf)
    mapping = json.loads(vcf.with_suffix(".mapping.json").read_text())
    runner.run("convert", [settings.plink2, "--vcf", str(vcf), "dosage=DS", "--double-id", "--make-pgen",
                           "--threads", str(options.threads), "--memory", str(options.memory_gb * 800), "--out", str(prefix)])
    samples = [f"S{i}" for i in range(len(y))]
    phenotype_path = directory / "phenotype.tsv"
    pd.DataFrame({"#FID": samples, "IID": samples, "Y": y + 1 if intent.phenotype_type == "binary" else y}).to_csv(
        phenotype_path, sep="\t", index=False)
    out = directory / tag
    command = [settings.plink2, "--pfile", str(prefix), "--pheno", str(phenotype_path), "--pheno-name", "Y",
               "--glm", "hide-covar", "omit-ref", "allow-no-covars"]
    if intent.phenotype_type == "binary":
        command.append("firth-fallback")
    else:
        command.append("no-firth")
    cc = cov.copy()
    columns = condition_columns(metadata, conditions or [])
    for i, column in enumerate(columns):
        cc[f"COND_{i}"] = markers[column].to_numpy()
    if len(cc.columns):
        cc.columns = [f"C{i}" for i in range(cc.shape[1])]
        cc.insert(0, "IID", samples)
        cc.insert(0, "#FID", samples)
        cov_path = directory / (tag + ".covariates.tsv")
        cc.to_csv(cov_path, sep="\t", index=False, na_rep="NA")
        command.extend(["--covar", str(cov_path), "--covar-variance-standardize"])
    command.extend(["--mac", str(options.min_count), "--geno", str(options.max_missing),
                    "--threads", str(options.threads), "--memory", str(options.memory_gb * 800),
                    "--out", str(out)])
    runner.run(tag, command)
    candidates = list(directory.glob(tag + ".Y.glm.*"))
    if len(candidates) != 1:
        raise RuntimeError("Expected exactly one PLINK phenotype association result")
    raw = pd.read_csv(candidates[0], sep="\t")
    raw = raw[raw.TEST == "ADD"].copy()
    if "A1" in raw and not raw.A1.eq("C").all():
        raise ValueError("PLINK effect orientation changed")
    raw["marker"] = raw.ID.map(mapping)
    if raw.marker.isna().any():
        raise ValueError("Unrecognized PLINK result marker")
    raw["beta"] = pd.to_numeric(raw.BETA, errors="coerce") if "BETA" in raw else np.log(pd.to_numeric(raw.OR, errors="coerce"))
    raw["se"] = pd.to_numeric(raw["LOG(OR)_SE"] if "LOG(OR)_SE" in raw else raw.SE, errors="coerce")
    raw["p"] = pd.to_numeric(raw.P, errors="coerce")
    raw["n"] = raw.OBS_CT
    raw["method"] = np.where(raw.FIRTH_YN.eq("Y"), "Firth", "logistic") if "FIRTH_YN" in raw else "linear"
    raw["status"] = np.where(raw.p.notna() & raw.beta.notna() & raw.se.gt(0), "ok", "failed")
    raw["error"] = raw["ERRCODE"] if "ERRCODE" in raw else ""
    keep = raw[["marker", "beta", "se", "p", "n", "method", "status", "error"]]
    result = metadata.merge(keep, on="marker", how="left", validate="one_to_one")
    result["status"] = result.status.fillna("filtered")
    result["error"] = result.error.fillna("Filtered by MAC/missingness or conditioning")
    result["unit"] = "individual"
    result["ci_lower"] = result.beta - 1.959963984540054 * result.se
    result["ci_upper"] = result.beta + 1.959963984540054 * result.se
    result["ci_method"] = "approximate_Wald_on_model_scale"
    if intent.phenotype_type == "binary":
        result["odds_ratio"] = np.exp(result.beta)
        result["or_ci_lower"] = np.exp(result.ci_lower)
        result["or_ci_upper"] = np.exp(result.ci_upper)
    return correction(result, len(metadata))


def convert_genotypes(runner: Runner, settings: Settings, path: Path, kind: str,
                      target: str, options: AnalysisOptions) -> Path:
    prefix = runner.directory / "converted"
    if kind == "plink_bed":
        command = [settings.plink2, "--bfile", str(path)]
    elif kind == "plink_pgen":
        command = [settings.plink2, "--pfile", str(path)]
    else:
        command = [settings.plink2, "--bcf" if kind == "bcf" else "--vcf", str(path)]
    if target == "bed":
        command += ["--make-bed"]
    else:
        command += ["--export", "vcf", "bgz", "id-paste=iid"]
    command += ["--threads", str(options.threads), "--memory", str(options.memory_gb * 800), "--out", str(prefix)]
    runner.run("convert_input", command)
    return prefix if target == "bed" else prefix.with_suffix(".vcf.gz")


def cookhla(runner: Runner, image: str, input_prefix: Path, reference_prefix: Path,
            target_build: str, options: AnalysisOptions, container_name: str,
            fingerprint: str, reference_metadata: dict, chain_directory: Path | None = None) -> Path:
    output = runner.directory / "output"
    output.mkdir(exist_ok=True)
    command = ["python", "-u", "CookHLA.py", "-i", "/input/" + input_prefix.name,
               "-hg", {"GRCh36": "18", "GRCh37": "19", "GRCh38": "38"}[target_build],
               "-ref", "/ref/" + reference_prefix.name, "-o", "/output/imputed",
               "-mem", f"{max(1, options.memory_gb // options.cookhla_processes - 1)}g",
               "--nthreads", str(max(1, options.threads // options.cookhla_processes))]
    if options.cookhla_processes > 1:
        command += ["-mp", str(options.cookhla_processes)]
    if reference_metadata.get("genetic_map") and reference_metadata.get("error_rate"):
        command += ["-gm", "/ref/" + Path(reference_metadata["genetic_map"]).name,
                    "-ae", "/ref/" + Path(reference_metadata["error_rate"]).name]
    mounts = {input_prefix.parent: ("/input", True), reference_prefix.parent: ("/ref", True),
              output: ("/output", False)}
    if target_build != "GRCh36":
        if chain_directory is None or not chain_directory.is_dir():
            raise ValueError("Install and pin the input-to-hg18 liftover chain before CookHLA")
        mounts[chain_directory] = ("/root/.pyliftover", True)
    runner.docker(container_name, image, command, mounts, options.memory_gb, options.threads, fingerprint)
    files = list(output.rglob("*.hped"))
    if len(files) != 1:
        raise RuntimeError("CookHLA did not produce exactly one final HPED")
    calls = load_hla(files[0])
    if calls.empty:
        raise RuntimeError("CookHLA produced no HLA calls")
    expected = pd.read_csv(str(input_prefix) + ".fam", sep=r"\s+", header=None, dtype=str)
    if set(zip(calls.FID, calls.IID)) != set(zip(expected[0], expected[1])):
        raise ValueError("CookHLA output changed target sample identities")
    score_files = list(output.rglob("*.alleles"))
    if len(score_files) != 1:
        raise ValueError("Expected one final CookHLA allele confidence file")
    calls = attach_cookhla_scores(calls, score_files[0])
    calls.to_csv(runner.directory / "hla_calls_unfiltered.tsv", sep="\t", index=False)
    quality = []
    for locus, group in calls.groupby("locus"):
        for threshold in sorted(set([0.0, 0.5, 0.9, options.cookhla_confidence_min or 0])):
            passing = group.allele1.notna() & group.allele2.notna() & group.confidence.ge(threshold)
            quality.append(dict(locus=locus, threshold=threshold, n=len(group), called=int(passing.sum()),
                                call_rate=float(passing.mean()), score_definition="CookHLA native score; not genotype probability"))
    pd.DataFrame(quality).to_csv(runner.directory / "imputation_quality.tsv", sep="\t", index=False)
    if options.cookhla_confidence_min is not None:
        calls.loc[calls.confidence.lt(options.cookhla_confidence_min), ["allele1", "allele2"]] = None
    result = runner.directory / "hla_calls.tsv"
    calls.to_csv(result, sep="\t", index=False)
    return result


def attach_cookhla_scores(calls: pd.DataFrame, path: Path) -> pd.DataFrame:
    scores = pd.read_csv(path, sep=r"\s+", header=None, dtype=str, keep_default_na=False)
    if scores.shape[1] != 8:
        raise ValueError("Unsupported CookHLA confidence output schema; cannot interpret scores safely")
    scores.columns = ["FID", "IID", "locus", "two_field_legacy", "four_digit", "score_component1", "score_component2", "confidence"]
    if scores.duplicated(["FID", "IID", "locus"]).any():
        raise ValueError("Duplicate CookHLA confidence records")
    result = calls.merge(scores, on=["FID", "IID", "locus"], validate="one_to_one", how="left")
    result["confidence"] = pd.to_numeric(result.confidence, errors="raise")
    called = result.allele1.notna() | result.allele2.notna()
    if not np.isfinite(result.loc[called, "confidence"]).all() or np.isinf(result.confidence).any():
        raise ValueError("Missing or invalid CookHLA confidence score")
    result["score_emitted"] = result.confidence.notna()
    for row in result.itertuples():
        if pd.isna(row.four_digit) and pd.isna(row.allele1) and pd.isna(row.allele2):
            continue
        pair = [normalize_allele(a, row.locus) for a in row.four_digit.split(",")]
        expected = [row.allele1, row.allele2]
        if sorted(str(a) for a in pair) != sorted(str(a) for a in expected):
            raise ValueError("CookHLA HPED and confidence-file allele pairs disagree")
    return result


def beagle(runner: Runner, settings: Settings, vcf: Path, options: AnalysisOptions,
           reference: Path | None = None, genetic_map: Path | None = None) -> Path:
    if not settings.beagle_jar or not settings.beagle_jar.is_file():
        raise ValueError("Install the pinned Beagle 5.5 JAR in Settings first")
    prefix = runner.directory / "phased"
    argv = [settings.java, f"-Xmx{options.memory_gb}g", "-jar", str(settings.beagle_jar),
            f"gt={vcf}", f"out={prefix}", f"nthreads={options.threads}", f"seed={options.seed}", "impute=false"]
    if reference:
        argv.append(f"ref={reference}")
    if genetic_map:
        argv.append(f"map={genetic_map}")
    runner.run("beagle", argv)
    output = prefix.with_suffix(".vcf.gz")
    if not output.is_file():
        raise RuntimeError("Beagle produced no phased VCF")
    return output
