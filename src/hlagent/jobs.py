"""Background analysis jobs: one subprocess per run (`python -m hlagent.pipeline.run --run-dir ...`).

State lives on disk (runs/<run_id>/status.json), so the GUI can be reloaded or restarted without losing
jobs. No API key is passed to the subprocess; the pipeline never needs one (the optional LLM narrative
uses .env keys only, or is added later from the GUI).
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

from hlagent import paths
from hlagent.config import get_settings
from hlagent.pipeline.dag import AnalysisPlan
from hlagent.pipeline.runner import prepare_run_dir, write_json_atomic
from hlagent.tools.cookhla import container_name

ACTIVE = ("queued", "running")


def status(run_dir: Path) -> dict[str, Any]:
    f = run_dir / "status.json"
    if not f.exists():
        return {"state": "queued", "run_id": run_dir.name, "progress": {"done": 0, "total": 0}}
    try:
        st = json.loads(f.read_text())
    except json.JSONDecodeError:  # being rewritten; atomic writes make this rare
        return {"state": "running", "run_id": run_dir.name}
    pid = st.get("pid")
    if st.get("state") in ACTIVE and pid and not _alive(int(pid)):
        st["state"] = "failed"
        st["message"] = st.get("message") or "the analysis process exited unexpectedly"
    return st


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:  # a finished child that was not reaped is a zombie: treat as dead
        with open(f"/proc/{pid}/stat") as fh:
            return fh.read().split()[2] != "Z"
    except OSError:
        return True


def list_runs(limit: int = 50) -> list[dict[str, Any]]:
    root = paths.runs_dir()
    if not root.exists():
        return []
    dirs = sorted((d for d in root.iterdir() if (d / "plan.json").exists()), reverse=True)[:limit]
    out = []
    for d in dirs:
        st = status(d)
        try:
            goal = json.loads((d / "plan.json").read_text()).get("goal", "")
        except (OSError, json.JSONDecodeError):
            goal = ""
        out.append(
            {
                "run_id": d.name,
                "run_dir": str(d),
                "goal": goal,
                **{k: st.get(k) for k in ("state", "progress", "current", "message")},
            }
        )
    return out


def n_active() -> int:
    return sum(1 for r in list_runs(200) if r["state"] in ACTIVE)


def start(plan: AnalysisPlan) -> str:
    """Create the run directory and launch the pipeline process. Returns run_id."""
    limit = get_settings().hlagent_max_parallel_jobs
    if n_active() >= limit:
        raise RuntimeError(
            f"{limit} analysis job(s) already running (HLAGENT_MAX_PARALLEL_JOBS); wait or cancel one."
        )
    run_dir = prepare_run_dir(plan, paths.runs_dir())
    (run_dir / "logs").mkdir(parents=True, exist_ok=True)
    out = open(run_dir / "logs" / "process.out", "ab")  # noqa: SIM115 - handed to the child
    env = {k: v for k, v in os.environ.items() if not k.endswith("_API_KEY")}
    env["HLAGENT_HOME"] = str(paths.project_root())
    p = subprocess.Popen(  # noqa: S603
        [sys.executable, "-m", "hlagent.pipeline.run", "--run-dir", str(run_dir)],  # noqa: S603
        stdout=out,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        env=env,
        cwd=str(paths.project_root()),
        start_new_session=True,
    )
    write_json_atomic(
        run_dir / "status.json",
        {
            "run_id": run_dir.name,
            "state": "queued",
            "pid": p.pid,
            "progress": {"done": 0, "total": 0},
            "message": "",
        },
    )
    return run_dir.name


def cancel(run_id: str) -> bool:
    run_dir = paths.runs_dir() / run_id
    st = status(run_dir)
    pid = st.get("pid")
    if st.get("state") not in ACTIVE or not pid:
        return False
    try:
        os.killpg(int(pid), signal.SIGTERM)
    except ProcessLookupError:
        pass
    # CookHLA runs in Docker under a deterministic name; remove it too
    docker = get_settings().hlagent_docker
    plan = json.loads((run_dir / "plan.json").read_text())
    for s in plan.get("studies", []):
        subprocess.run(  # noqa: S603
            [docker, "rm", "-f", container_name(run_id, s["study_id"])],  # noqa: S603
            capture_output=True,
            check=False,
        )
    st.update({"state": "cancelled", "message": "cancelled by user"})
    write_json_atomic(run_dir / "status.json", st)
    return True


def outputs(run_id: str) -> list[dict[str, Any]]:
    """Artifacts of every finished step (for the results page)."""
    run_dir = paths.runs_dir() / run_id
    out = []
    for f in sorted(run_dir.glob("**/node_result.json")):
        try:
            r = json.loads(f.read_text())
        except json.JSONDecodeError:
            continue
        for name, a in r.get("artifacts", {}).items():
            out.append(
                {
                    "step": r["node"],
                    "study_id": r.get("study_id"),
                    "name": name,
                    "kind": a.get("kind"),
                    "path": a.get("path"),
                    "description": a.get("description", ""),
                }
            )
    return out
