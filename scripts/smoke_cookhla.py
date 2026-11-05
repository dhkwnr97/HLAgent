"""Run a user-supplied CookHLA example; no accuracy claim is made by this smoke test."""
import argparse
import json
from pathlib import Path

from hlagent.data import inspect_dataset
from hlagent.models import AnalysisIntent, AnalysisOptions, Goal, PlanApproval
from hlagent.planning import build_plan
from hlagent.settings import Settings
from hlagent.storage import Store
from hlagent.worker import run_until_finished

p = argparse.ArgumentParser()
p.add_argument("--target", required=True)
p.add_argument("--reference", required=True)
p.add_argument("--genetic-map", required=True)
p.add_argument("--error-rate", required=True)
p.add_argument("--target-build", default="GRCh37")
p.add_argument("--ancestry", default="EUR")
p.add_argument("--result", required=True)
args = p.parse_args()
settings = Settings().initialize()
store = Store(settings.db_path)
project = store.create_project("CookHLA installation smoke (10 sample example)")
target = inspect_dataset(project["id"], args.target, genome_build=args.target_build, ancestry=args.ancestry)
reference = inspect_dataset(project["id"], args.reference, kind="reference", genome_build="GRCh36",
                            ancestry=args.ancestry,
                            metadata={"genetic_map": args.genetic_map, "error_rate": args.error_rate})
for dataset in (target, reference):
    store.put_dataset(dataset)
intent = AnalysisIntent(goals=[Goal.imputation], dataset_ids=[target.id], reference_id=reference.id)
plan = build_plan(project["id"], intent, store.datasets(project["id"]), AnalysisOptions(memory_gb=8, threads=4), settings)
store.put_plan(plan)
job = store.approve(PlanApproval(plan_id=plan.id, plan_hash=plan.plan_hash, revision=plan.revision))
print(json.dumps({"project_id": project["id"], "job_id": job.id}), flush=True)
run_until_finished(settings, store, job.id)
result = {"job": store.job(job.id).model_dump(), "artifacts": [a.model_dump() for a in store.artifacts(job.id)]}
Path(args.result).write_text(json.dumps(result, indent=2))
print(json.dumps(result["job"]), flush=True)
raise SystemExit(0 if store.job(job.id).state == "succeeded" else 1)
