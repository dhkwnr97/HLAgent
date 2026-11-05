"""Sequential pipeline runner with per-step caching, status.json and events.jsonl.

Run directory layout (plan section 4.5):
  plan.json, params.lock.json, env.lock.json, status.json, reproduce.sh
  <study_id>/<step>/...  node5_meta/  report/  logs/events.jsonl
"""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import sys
import traceback
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hlagent import __version__
from hlagent.config import get_settings
from hlagent.logging_utils import add_jsonl_handler, get_logger, redact
from hlagent.pipeline.contracts import STEP_TITLES, NodeResult
from hlagent.pipeline.dag import AnalysisPlan, Task, resolve

log = get_logger("hlagent.runner")

StepFn = Callable[..., NodeResult]  # (ctx: RunContext, study: StudySpec | None) -> NodeResult


def _now() -> str:
    return datetime.now(UTC).isoformat()


def write_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=1, default=str, ensure_ascii=False))
    os.replace(tmp, path)


class RunContext:
    def __init__(self, run_dir: Path, plan: AnalysisPlan):
        self.run_dir = run_dir
        self.plan = plan
        self.params = plan.params
        self.settings = get_settings()
        self.results: dict[str, NodeResult] = {}
        self.studies = {s.study_id: s for s in plan.studies}
        self.events_path = run_dir / "logs" / "events.jsonl"
        self.tool_versions: dict[str, str] = {}

    # tools ---------------------------------------------------------------
    @property
    def plink(self) -> str:
        return self.settings.hlagent_plink

    @property
    def java(self) -> str:
        return self.settings.hlagent_java

    @property
    def rscript(self) -> str:
        return self.settings.hlagent_rscript

    @property
    def docker(self) -> str:
        return self.settings.hlagent_docker

    # layout --------------------------------------------------------------
    def step_dir(self, step: str, study_id: str | None) -> Path:
        d = self.run_dir / (study_id or "_all") / step.lower() if study_id else self.run_dir / step.lower()
        d.mkdir(parents=True, exist_ok=True)
        return d

    def result(self, step: str, study_id: str | None) -> NodeResult | None:
        return self.results.get(f"{step}:{study_id or '-'}")

    def require(self, step: str, study_id: str | None) -> NodeResult:
        r = self.result(step, study_id)
        if r is None or r.status in ("failed", "blocked"):
            raise RuntimeError(f"{step} for {study_id} has no usable result")
        return r

    def is_synthetic(self) -> bool:
        return any(s.synthetic_phenotype is not None for s in self.plan.studies)

    def event(self, kind: str, **data: Any) -> None:
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        rec = {"ts": _now(), "kind": kind, **data}
        with open(self.events_path, "a", encoding="utf-8") as fh:
            fh.write(redact(json.dumps(rec, default=str, ensure_ascii=False)) + "\n")


def _registry() -> dict[str, StepFn]:
    from hlagent.pipeline.steps import (
        node1_bmarker,
        node2_regression,
        node3_stepwise,
        node4_omnibus,
        node5_meta,
        stage_d_data,
        stage_i_cookhla,
        stage_p_phasing,
        stage_r_report,
    )

    return {
        "StageD": stage_d_data.run,
        "StageI": stage_i_cookhla.run,
        "Node1": node1_bmarker.run,
        "Node2": node2_regression.run,
        "Node3": node3_stepwise.run,
        "StageP": stage_p_phasing.run,
        "Node4": node4_omnibus.run,
        "Node5": node5_meta.run,
        "StageR": stage_r_report.run,
    }


def cache_key(ctx: RunContext, task: Task, upstream: list[NodeResult]) -> str:
    h = hashlib.sha256()
    h.update(task.key.encode())
    h.update(ctx.params.for_step(task.step).model_dump_json().encode())
    if task.study_id:
        h.update(ctx.studies[task.study_id].model_dump_json().encode())
    else:
        h.update(json.dumps([s.model_dump(mode="json") for s in ctx.plan.studies], sort_keys=True).encode())
    for u in upstream:
        h.update(u.cache_key.encode())
    h.update(json.dumps(ctx.tool_versions, sort_keys=True).encode())
    h.update(__version__.encode())
    return h.hexdigest()


def _upstream(ctx: RunContext, task: Task) -> list[NodeResult]:
    out = []
    for k, r in ctx.results.items():
        st, sid = k.split(":")
        if task.study_id is None or sid == task.study_id:
            out.append(r)
    return out


def collect_tool_versions(ctx: RunContext) -> dict[str, str]:
    from hlagent.tools.cookhla import COOKHLA_IMAGE
    from hlagent.tools.plink import plink_version

    v = {
        "hlagent": __version__,
        "python": sys.version.split()[0],
        "plink": plink_version(ctx.plink),
        "cookhla_image": COOKHLA_IMAGE,
    }
    try:
        import pydantic_ai

        v["pydantic_ai"] = pydantic_ai.__version__
    except Exception:  # noqa: BLE001
        pass
    from hlagent import paths

    sums = paths.beagle_dir() / "SHA256SUMS"
    if sums.exists():
        v["beagle_jars_sha256"] = hashlib.sha256(sums.read_bytes()).hexdigest()[:16]
    return v


def write_status(
    ctx: RunContext, state: str, tasks: list[Task], current: Task | None = None, message: str = ""
) -> None:
    done = {k for k, r in ctx.results.items() if r.status in ("ok", "warning", "skipped_cached")}
    write_json_atomic(
        ctx.run_dir / "status.json",
        {
            "run_id": ctx.run_dir.name,
            "plan_id": ctx.plan.plan_id,
            "state": state,
            "updated_at": _now(),
            "pid": os.getpid(),
            "message": message,
            "current": None
            if current is None
            else {"step": current.step, "study_id": current.study_id, "title": STEP_TITLES[current.step]},
            "progress": {"done": len(done), "total": len(tasks)},
            "tasks": [
                {
                    "step": t.step,
                    "study_id": t.study_id,
                    "title": STEP_TITLES[t.step],
                    "status": (ctx.results[t.key].status if t.key in ctx.results else "pending"),
                }
                for t in tasks
            ],
            "synthetic": ctx.is_synthetic(),
        },
    )


def prepare_run_dir(plan: AnalysisPlan, runs_root: Path, name: str | None = None) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    slug = (name or plan.goal or "run").lower()
    # ASCII only: the run id is reused in Docker container names ([a-zA-Z0-9_.-])
    slug = "".join(c if (c.isascii() and c.isalnum()) else "-" for c in slug)
    slug = "-".join(t for t in slug.split("-") if t)[:32] or "run"
    run_dir = runs_root / f"{stamp}_{slug}_{plan.plan_id[:6]}"
    run_dir.mkdir(parents=True, exist_ok=False)
    write_json_atomic(run_dir / "plan.json", plan.model_dump(mode="json"))
    return run_dir


def execute(
    run_dir: Path, *, registry: dict[str, StepFn] | None = None, stop_on_block: bool = True
) -> dict[str, Any]:
    run_dir = Path(run_dir).resolve()  # artifacts are stored as absolute paths
    (run_dir / "logs").mkdir(parents=True, exist_ok=True)
    os.environ["HLAGENT_PROC_LEDGER"] = str(run_dir / "logs" / "commands.jsonl")  # per-command provenance
    plan = AnalysisPlan.model_validate_json((run_dir / "plan.json").read_text())
    ctx = RunContext(run_dir, plan)
    add_jsonl_handler(log, run_dir / "logs" / "runner.jsonl")
    resolved = resolve(plan)
    if not resolved.ok:
        write_status(ctx, "failed", resolved.tasks, message="; ".join(resolved.errors))
        return {"state": "failed", "errors": resolved.errors}
    reg = registry or _registry()
    ctx.tool_versions = collect_tool_versions(ctx)
    write_json_atomic(run_dir / "env.lock.json", ctx.tool_versions)
    write_json_atomic(run_dir / "params.lock.json", plan.params.model_dump(mode="json"))
    (run_dir / "reproduce.sh").write_text(
        "#!/usr/bin/env bash\n# Re-run this analysis with identical plan and parameters.\n"
        f"hlagent run --plan {shlex.quote(str(run_dir / 'plan.json'))}\n"
    )
    # reuse results of a previous attempt in the same run directory
    for t in resolved.tasks:
        f = ctx.step_dir(t.step, t.study_id) / "node_result.json"
        if f.exists():
            try:
                ctx.results[t.key] = NodeResult.model_validate_json(f.read_text())
            except ValueError:
                pass
    attempt_results: dict[str, NodeResult] = {}
    state = "done"
    message = ""
    ctx.event("run_started", tasks=[t.key for t in resolved.tasks], notes=resolved.notes)
    for task in resolved.tasks:
        upstream = [
            attempt_results[k]
            for k in attempt_results
            if task.study_id is None or k.endswith(f":{task.study_id}")
        ]
        key = cache_key(ctx, task, upstream)
        prev = ctx.results.get(task.key)
        # Stage R is cheap and must reflect the current results, so it is never served from cache
        if (
            task.step != "StageR"
            and prev is not None
            and prev.cache_key == key
            and prev.status in ("ok", "warning")
        ):
            cached = prev.model_copy(update={"status": prev.status})
            attempt_results[task.key] = cached
            ctx.event("step_cached", step=task.step, study_id=task.study_id)
            continue
        ctx.results.pop(task.key, None)
        write_status(ctx, "running", resolved.tasks, current=task)
        ctx.event("step_started", step=task.step, study_id=task.study_id)
        study = ctx.studies.get(task.study_id) if task.study_id else None
        try:
            result = reg[task.step](ctx, study)
        except Exception as e:  # noqa: BLE001 - step errors become failed results
            tb = redact(traceback.format_exc())
            (ctx.step_dir(task.step, task.study_id) / "error.txt").write_text(tb)
            result = NodeResult(
                node=task.step,
                study_id=task.study_id,
                status="failed",
                cache_key=key,
                error_kind="tool_error" if "ToolError" in tb else "input_error",
                error_message=redact(str(e))[:4000],
            )
        result.cache_key = key
        result.finished_at = datetime.now(UTC)
        if not result.tool_versions:
            result.tool_versions = ctx.tool_versions
        write_json_atomic(
            ctx.step_dir(task.step, task.study_id) / "node_result.json", result.model_dump(mode="json")
        )
        ctx.results[task.key] = result
        attempt_results[task.key] = result
        ctx.event(
            "step_finished",
            step=task.step,
            study_id=task.study_id,
            status=result.status,
            warnings=result.warnings,
            error=result.error_message,
        )
        if result.status == "failed":
            state, message = "failed", f"{task.step} ({task.study_id or 'all'}): {result.error_message}"
            break
        if result.status == "blocked" and stop_on_block:
            state, message = (
                "blocked",
                f"{task.step} ({task.study_id or 'all'}): {result.user_action or result.error_message}",
            )
            break
    write_status(ctx, state, resolved.tasks, message=message)
    ctx.event("run_finished", state=state, message=message)
    return {"state": state, "message": message, "run_dir": str(run_dir)}
