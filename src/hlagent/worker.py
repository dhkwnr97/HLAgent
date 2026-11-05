from __future__ import annotations

import json
import mimetypes
import os
import signal
import subprocess
import time
from pathlib import Path

import pandas as pd
import psutil
from filelock import FileLock

from hlagent.adapters import beagle, convert_genotypes, cookhla, plink_association, tool_versions
from hlagent.data import (
    decode_hla_vcf,
    dosage_markers,
    hla_markers,
    load_dosages,
    load_hla,
    load_sequence,
    read_table,
    resolve_path,
    scaffold_hla_vcf,
    sha256,
    stage_dataset,
    validate_phase_reference,
    validate_snp_phasing,
    verify_files,
    write_hla_vcf,
)
from hlagent.execution import Cancelled, Runner, alive
from hlagent.models import ArtifactManifest, JobRecord, digest
from hlagent.reporting import render_report
from hlagent.settings import Settings
from hlagent.statistics import haplotype_dosages, meta_analysis, omnibus, prepare_design
from hlagent.storage import Store


class Worker:
    def __init__(self, settings: Settings):
        self.settings = settings.initialize()
        self.store = Store(settings.db_path)
        self.lock = FileLock(settings.home / "worker.lock")

    def job_dir(self, job: JobRecord) -> Path:
        return self.settings.home / "projects" / job.project_id / "runs" / job.id

    def _cancelled(self, job: JobRecord):
        return self.store.job(job.id).state in ("cancel_requested", "cancelled")

    def artifact(self, job, step, path: Path):
        if not path.is_file() or not path.resolve().is_relative_to(self.job_dir(job).resolve()):
            raise ValueError("Output must be a file inside the run directory")
        if path.suffix == ".tsv" and path.stat().st_size > 1:
            pd.read_csv(path, sep="\t", nrows=3)
        checksum = sha256(path)
        artifact = ArtifactManifest(id=digest([job.id, str(path)])[:32], job_id=job.id, step_id=step,
            path=str(path), sha256=checksum, size=path.stat().st_size,
            media_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream", label=path.name,
            validation={"file_integrity": "sha256", "exists": True})
        self.store.put_artifact(artifact)
        return {"path": str(path), "sha256": checksum}

    def recover(self):
        for job in self.store.jobs():
            if job.state == "running":
                self.store.update_job(job.id, state="queued", error="Recovered after worker interruption")
            if job.state in ("cancel_requested", "cancelled"):
                for path in self.job_dir(job).rglob("*.process.json"):
                    info = json.loads(path.read_text())
                    if alive(info):
                        os.killpg(info["pid"], signal.SIGTERM)
                if shutil_docker():
                    subprocess.run(["docker", "stop", "-t", "3", f"hlagent-{job.id}-impute"], capture_output=True)
                self.store.update_job(job.id, state="cancelled")

    def run_once(self) -> bool:
        with self.lock.acquire(timeout=0):
            self.recover()
            job = self.store.claim_job()
            if job is None:
                return False
            self.execute(job)
            return True

    def serve(self):
        with self.lock:
            self.recover()
            while True:
                job = self.store.claim_job()
                if job:
                    self.execute(job)
                else:
                    time.sleep(0.5)

    def execute(self, job: JobRecord):
        plan = self.store.plan(job.plan_id)
        root = self.job_dir(job)
        root.mkdir(parents=True, exist_ok=True)
        context = {"tables": {}, "audit": {}, "files": {}}
        try:
            if plan.plan_hash != job.plan_hash:
                raise ValueError("Approval hash does not match the stored plan")
            current_versions = tool_versions(self.settings)
            for name, version in plan.tools.items():
                if current_versions.get(name) != version:
                    raise ValueError(f"Tool version changed: {name}; create and approve a new plan")
            if plan.options.memory_gb * 1024**3 > psutil.virtual_memory().total * 0.8:
                raise ValueError("Requested memory exceeds 80% of detected WSL RAM; revise resource settings")
            for data in plan.datasets:
                verify_files(data.files)
            for step in plan.steps:
                if self._cancelled(job):
                    raise Cancelled()
                fingerprint = digest([plan.plan_hash, step.model_dump()])
                previous = self.store.step(job.id, step.id)
                if previous and previous.get("state") == "succeeded" and previous["fingerprint"] == fingerprint:
                    files = previous.get("outputs", [])
                    if all(Path(f["path"]).is_file() and sha256(Path(f["path"])) == f["sha256"] for f in files):
                        context = previous["context"]
                        self.store.event(job.project_id, "reused", {"job_id": job.id, "step": step.id})
                        continue
                self.store.update_job(job.id, current_step=step.id)
                self.store.event(job.project_id, "step_started", {"job_id": job.id, "step": step.id})
                directory = root / step.id
                directory.mkdir(exist_ok=True)
                # Invalidate finished command caches when a step did not validate completely.
                for path in directory.glob("*.exit.json"):
                    path.unlink()
                runner = Runner(directory, lambda: self._cancelled(job), restart_completed=job.attempt > 1)
                outputs = self.run_step(step.tool, plan, job, runner, context)
                outputs = list(dict.fromkeys([*outputs, *directory.rglob("*.command.json"), *directory.rglob("*.log")]))
                manifests = [self.artifact(job, step.id, p) for p in outputs]
                self.store.put_step(job.id, step.id, fingerprint,
                                    {"state": "succeeded", "outputs": manifests, "context": context})
                self.store.event(job.project_id, "step_succeeded", {"job_id": job.id, "step": step.id})
            if self._cancelled(job):
                raise Cancelled()
            self.store.update_job(job.id, state="succeeded", error=None)
        except Cancelled:
            self.store.update_job(job.id, state="cancelled", error="Cancelled by user; validated outputs are retained")
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            self.store.update_job(job.id, state="failed", error=message)
            self.store.event(job.project_id, "failed", {"job_id": job.id, "error": message})
            for path in render_report(root / "partial-report", plan, context["tables"], context["audit"], message):
                self.artifact(job, "partial-report", path)
        finally:
            import shutil
            import zipfile
            manifest = root / "artifacts.json"
            manifest.write_text(json.dumps([a.model_dump() for a in self.store.artifacts(job.id)
                                           if a.label not in ("artifacts.json", "report-bundle.zip")], indent=2))
            self.artifact(job, "manifest", manifest)
            bundle = root / "report-bundle.zip"
            with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for artifact in self.store.artifacts(job.id):
                    path = Path(artifact.path)
                    if artifact.step_id == "prepare" or artifact.label == bundle.name:
                        continue
                    if path.is_file() and sha256(path) == artifact.sha256:
                        archive.write(path, path.relative_to(root))
            self.artifact(job, "bundle", bundle)
            if plan.options.export_directory and self.store.job(job.id).state == "succeeded":
                try:
                    destination = resolve_path(plan.options.export_directory) / ("HLAgent-" + job.id)
                    destination.mkdir(parents=True, exist_ok=True)
                    target = destination / bundle.name
                    if target.exists() and sha256(target) != sha256(bundle):
                        raise ValueError("Export file already exists with different contents")
                    shutil.copyfile(bundle, target)
                    if sha256(target) != sha256(bundle):
                        raise ValueError("Export checksum mismatch")
                    self.store.event(job.project_id, "exported", {"job_id": job.id, "path": str(target)})
                except (ValueError, OSError) as exc:
                    self.store.event(job.project_id, "export_failed", {"job_id": job.id, "error": str(exc)})

    def run_step(self, tool, plan, job, runner, context):
        directory, intent, options = runner.directory, plan.intent, plan.options
        data_by_id = {d.id: d for d in plan.datasets}
        primary = next((d for d in plan.datasets if d.id in intent.dataset_ids and d.kind != "summary"), None)

        def table(frame, name):
            path = directory / (name + ".tsv")
            frame.to_csv(path, sep="\t", index=False, na_rep="NA")
            context["tables"][name] = str(path)
            return path

        if tool == "prepare":
            outputs = []
            for data in plan.datasets:
                staged = stage_dataset(data, directory / data.id)
                context["files"][data.id] = {k: str(v) for k, v in staged.items()}
                outputs.extend(staged.values())
            context["audit"]["inputs"] = [{"dataset_id": d.id, "kind": d.kind, "sample_count": d.sample_count,
                                              "genome_build": d.genome_build, "resolution": d.resolution,
                                              "imgt_release": d.imgt_release} for d in plan.datasets]
            if primary:
                first = Path(next(iter(context["files"][primary.id].values())))
                context["primary"] = str(first.with_suffix("")) if primary.kind in ("plink_bed", "plink_pgen") else str(first)
                if primary.kind == "hla":
                    calls = load_hla(first, primary.metadata.get("mapping"), primary.metadata.get("tool"))
                    path = directory / "hla_calls.tsv"
                    calls.to_csv(path, sep="\t", index=False)
                    context["hla"] = str(path)
                    outputs.append(path)
                if primary.kind == "hla_dosage":
                    context["dosages"] = str(first)
            return outputs
        if tool == "impute":
            ref = data_by_id[intent.reference_id]
            reference_prefix = Path(next(iter(context["files"][ref.id].values()))).with_suffix("")
            input_prefix = Path(context["primary"])
            if primary.kind != "plink_bed":
                input_prefix = convert_genotypes(runner, self.settings, input_prefix, primary.kind, "bed", options)
            # Known reference membership is checked on stable FID/IID pairs before execution.
            a = pd.read_csv(str(input_prefix) + ".fam", sep=r"\s+", header=None, dtype=str)
            b = pd.read_csv(str(reference_prefix) + ".fam", sep=r"\s+", header=None, dtype=str)
            if set(zip(a[0], a[1])) & set(zip(b[0], b[1])):
                raise ValueError("Target/reference sample IDs overlap")
            path = cookhla(runner, plan.tools["cookhla"], input_prefix, reference_prefix,
                           primary.genome_build, options, f"hlagent-{job.id}-impute", plan.plan_hash, ref.metadata,
                           self.settings.home / "tools/chains")
            context["hla"] = str(path)
            context["audit"]["imputation"] = {"representation": "hard_calls", "image": plan.tools["cookhla"]}
            context["tables"]["imputation_quality"] = str(directory / "imputation_quality.tsv")
            context["unfiltered_hla"] = str(directory / "hla_calls_unfiltered.tsv")
            return [path, directory / "hla_calls_unfiltered.tsv", directory / "imputation_quality.tsv",
                    *list((directory / "output").rglob("*.alleles")), directory / "cookhla.log"]
        if tool == "markers":
            sequence = None
            if intent.sequence_id:
                sequence = load_sequence(Path(next(iter(context["files"][intent.sequence_id].values()))),
                                         data_by_id[intent.sequence_id].metadata)
            if "dosages" in context:
                dosages = load_dosages(Path(context["dosages"]), primary.metadata.get("mapping"))
                markers, metadata = dosage_markers(dosages, sequence)
            else:
                calls = load_hla(Path(context["hla"]))
                markers, metadata = hla_markers(calls, sequence)
            if metadata.empty:
                raise ValueError("No callable HLA markers")
            context["markers"] = str(table(markers, "marker_dosages"))
            context["metadata"] = str(table(metadata, "marker_definitions"))
            coverage = []
            for (kind, locus, position), group in metadata.groupby(["kind", "locus", "position"], dropna=False):
                complete = markers[group.marker].notna().all(axis=1)
                coverage.append(dict(kind=kind, locus=locus, position=position, n=len(markers),
                                      complete=int(complete.sum()), missing=int((~complete).sum()),
                                      coverage=float(complete.mean())))
            quality = table(pd.DataFrame(coverage), "marker_mapping_quality")
            return [Path(context["markers"]), Path(context["metadata"]), quality]
        if tool == "phase":
            if "hla" in context:
                calls = load_hla(Path(context["hla"]))
                vcf = directory / "hla.synthetic.vcf"
                reference, reference_book = None, None
                if intent.phase_reference_id:
                    ref = data_by_id[intent.phase_reference_id]
                    reference = Path(context["files"][ref.id][ref.files[0].path])
                    book_file = next(f for f in ref.files if f.role == "codebook")
                    reference_book = json.loads(Path(context["files"][ref.id][book_file.path]).read_text())
                    validate_phase_reference(reference, reference_book, set(calls.IID))
                if intent.scaffold_id:
                    scaffold = data_by_id[intent.scaffold_id]
                    snp_vcf = Path(next(iter(context["files"][scaffold.id].values())))
                    if scaffold.kind in ("plink_bed", "plink_pgen"):
                        snp_vcf = convert_genotypes(runner, self.settings, snp_vcf.with_suffix(""), scaffold.kind, "vcf", options)
                    elif scaffold.kind == "bcf":
                        snp_vcf = convert_genotypes(runner, self.settings, snp_vcf, scaffold.kind, "vcf", options)
                    codebook = scaffold_hla_vcf(calls, snp_vcf, vcf, primary.metadata["phase_positions"],
                                                primary.genome_build, intent.haplotype_loci or None, reference_book)
                else:
                    codebook = write_hla_vcf(calls, vcf, intent.haplotype_loci or None)
                output = beagle(runner, self.settings, vcf, options, reference=reference)
                validate_snp_phasing(vcf, output)
                phased = decode_hla_vcf(output, codebook, calls)
                context["phased_hla"] = str(table(phased, "phased_hla"))
                return [output, vcf.with_suffix(".codebook.json"), Path(context["phased_hla"]), directory / "beagle.log"]
            vcf = Path(context["primary"])
            if primary.kind in ("plink_bed", "plink_pgen", "bcf"):
                vcf = convert_genotypes(runner, self.settings, vcf, primary.kind, "vcf", options)
            output = beagle(runner, self.settings, vcf, options)
            validate_snp_phasing(vcf, output)
            return [output, directory / "beagle.log"]
        if tool == "haplotypes":
            phased = pd.read_csv(context["phased_hla"], sep="\t", dtype=str)
            loci = intent.haplotype_loci or sorted(phased.locus.unique())
            markers, metadata, frequencies = haplotype_dosages(phased, loci)
            context["hap_markers"] = str(table(markers, "haplotype_dosages"))
            context["hap_metadata"] = str(table(metadata, "haplotype_definitions"))
            freq = table(frequencies, "haplotype_frequencies")
            return [Path(context["hap_markers"]), Path(context["hap_metadata"]), freq]
        if tool in ("association", "conditional", "stepwise", "omnibus"):
            use_hap = tool != "omnibus" and "hap_markers" in context
            markers = pd.read_csv(context["hap_markers" if use_hap else "markers"], sep="\t", dtype={"FID": str, "IID": str})
            metadata = pd.read_csv(context["hap_metadata" if use_hap else "metadata"], sep="\t", keep_default_na=False)
            phenotype = read_table(Path(next(iter(context["files"][intent.phenotype_id].values()))))
            phenotype = phenotype.rename(columns=data_by_id[intent.phenotype_id].metadata.get("mapping", {}).get("columns", {}))
            markers, y, cov, audit = prepare_design(markers, phenotype, intent)
            context["audit"][tool] = audit
            if tool == "omnibus":
                result = omnibus(markers, y, cov, metadata, intent.phenotype_type == "binary", intent.conditioning, options.min_count)
            elif tool == "stepwise":
                selected = list(intent.conditioning)
                history = []
                for iteration in range(options.max_steps):
                    if self._cancelled(job):
                        raise Cancelled()
                    result = plink_association(runner, self.settings, markers, y, cov, metadata, intent, options,
                                               selected, f"round_{iteration}")
                    eligible = result[(result.status == "ok") & ~result.marker.isin(selected)].sort_values(["p", "marker"])
                    path = table(result, f"stepwise_round_{iteration}")
                    if eligible.empty or eligible.iloc[0].p >= options.alpha / len(metadata):
                        history.append(dict(round=iteration, action="stop", reason="No remaining marker meets fixed family threshold"))
                        break
                    lead = eligible.iloc[0]
                    selected.append(lead.marker)
                    history.append(dict(round=iteration, action="add", marker=lead.marker, p=float(lead.p)))
                result = pd.DataFrame(history)
                context["audit"][tool]["selected"] = selected
                context["audit"][tool]["interpretation"] = "exploratory adaptive conditional signals, not causal variants"
            else:
                result = plink_association(runner, self.settings, markers, y, cov, metadata, intent, options,
                                           intent.conditioning if tool == "conditional" else [], tool)
            output = table(result, tool)
            if tool == "association":
                context["association"] = str(output)
            extra = []
            if tool == "association" and "unfiltered_hla" in context and not use_hap:
                baseline_calls = load_hla(Path(context["unfiltered_hla"]))
                sequence = load_sequence(Path(next(iter(context["files"][intent.sequence_id].values()))),
                                         data_by_id[intent.sequence_id].metadata) if intent.sequence_id else None
                sensitivities = []
                for threshold in options.cookhla_sensitivity_thresholds:
                    calls = baseline_calls.copy()
                    calls.loc[calls.confidence.lt(threshold), ["allele1", "allele2"]] = None
                    mm, meta = hla_markers(calls, sequence)
                    sub = Runner(directory / ("sensitivity_" + str(threshold)), lambda: self._cancelled(job))
                    try:
                        mm, yy, cc, _ = prepare_design(mm, phenotype, intent)
                        frame = plink_association(sub, self.settings, mm, yy, cc, meta, intent, options)
                        frame["confidence_threshold"] = threshold
                        sensitivities.append(frame)
                    except (ValueError, RuntimeError) as exc:
                        sensitivities.append(pd.DataFrame([{"confidence_threshold": threshold, "status": "failed", "error": str(exc)}]))
                if sensitivities:
                    extra.append(table(pd.concat(sensitivities, ignore_index=True), "confidence_sensitivity"))
            return [output, *extra, *directory.glob("*.log"), *directory.glob("stepwise_round_*.tsv")]
        if tool == "meta":
            data = [data_by_id[i] for i in intent.dataset_ids]
            frames = [read_table(Path(next(iter(context["files"][d.id].values())))).rename(
                columns=d.metadata.get("mapping", {}).get("columns", {})) for d in data]
            results, leave = meta_analysis(frames, [d.metadata.get("design", {}) for d in data], intent.independent_cohorts is True)
            paths = [table(results, "meta")]
            if not leave.empty:
                paths.append(table(leave, "meta_leave_one_out"))
            return paths
        if tool == "visualize":
            for i in intent.dataset_ids:
                context["tables"]["input_" + i] = next(iter(context["files"][i].values()))
            return []
        if tool == "report":
            # Individual-level tables are downloadable but omitted from narrative/report rendering.
            result_tables = {k: v for k, v in context["tables"].items()
                             if k not in ("marker_dosages", "haplotype_dosages", "phased_hla")}
            return render_report(directory, plan, result_tables, context["audit"])
        raise ValueError("Unregistered tool; refusing execution")


def shutil_docker():
    import shutil
    return shutil.which("docker") is not None


def run_until_finished(settings: Settings, store: Store, job_id: str, timeout_seconds: int = 86400):
    """Use the same queue when a service worker is present, or run it locally otherwise."""
    from filelock import Timeout
    start = time.monotonic()
    while store.job(job_id).state not in ("succeeded", "failed", "cancelled"):
        if time.monotonic() - start > timeout_seconds:
            raise TimeoutError("Waiting stopped; the queued/running analysis remains available in the GUI")
        try:
            Worker(settings).run_once()
        except Timeout:
            time.sleep(.5)
    return store.job(job_id)
