from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import typer

from hlagent.adapters import tool_versions
from hlagent.fixtures import create_demo
from hlagent.models import AnalysisIntent, AnalysisOptions, AnalysisPlan, PlanApproval
from hlagent.planning import build_plan
from hlagent.secrets import api_token
from hlagent.settings import Settings
from hlagent.storage import Store
from hlagent.worker import Worker, run_until_finished

app = typer.Typer(help="HLAgent local application and reproducible workflow runner")


@app.command("evaluate-routing")
def evaluate_routing(cases: Path, output: Path):
    """Opt-in live model evaluation on public benchmark prompts; may consume provider quota."""
    from hlagent.evaluation import evaluate_live_routing
    evaluate_live_routing(cases, output, Settings().initialize())


@app.command("score-evaluation")
def score_evaluation(cases: Path, predictions: Path, output: Path):
    from hlagent.evaluation import score_agent_predictions
    gold = [json.loads(line) for line in cases.read_text().splitlines() if line]
    actual = json.loads(predictions.read_text())
    if isinstance(actual, dict):
        actual = actual["predictions"]
    output.write_text(json.dumps(score_agent_predictions(gold, actual), indent=2))


@app.command()
def doctor():
    settings = Settings().initialize()
    typer.echo(json.dumps({"home": str(settings.home), "tools": tool_versions(settings)}, indent=2))


@app.command()
def api():
    import uvicorn
    settings = Settings().initialize()
    if settings.api_host not in ("127.0.0.1", "localhost"):
        raise typer.BadParameter("This release supports loopback binding only")
    uvicorn.run("hlagent.api:app_factory", factory=True, host=settings.api_host, port=settings.api_port,
                access_log=False)


@app.command()
def worker(once: bool = False):
    runner = Worker(Settings())
    runner.run_once() if once else runner.serve()


@app.command()
def demo(run: bool = False):
    settings = Settings().initialize()
    store = Store(settings.db_path)
    result = create_demo(store, settings.home)
    if run:
        plan = build_plan(result["project"]["id"], AnalysisIntent.model_validate(result["intent"]),
                          store.datasets(result["project"]["id"]), AnalysisOptions(), settings)
        store.put_plan(plan)
        job = store.approve(PlanApproval(plan_id=plan.id, plan_hash=plan.plan_hash, revision=plan.revision))
        run_until_finished(settings, store, job.id)
        result["job"] = store.job(job.id).model_dump()
        result["artifacts"] = [a.path for a in store.artifacts(job.id)]
        if store.job(job.id).state != "succeeded":
            typer.echo(json.dumps(result, indent=2))
            raise typer.Exit(1)
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@app.command()
def replay(plan_file: Path, approve: bool = False):
    """Replay an exported plan. --approve explicitly authorizes the exact imported plan."""
    settings = Settings().initialize()
    store = Store(settings.db_path)
    plan = AnalysisPlan.model_validate_json(plan_file.read_text())
    if not approve:
        typer.echo(json.dumps({"plan_id": plan.id, "hash": plan.plan_hash,
                               "steps": [s.id for s in plan.steps], "warnings": plan.warnings}, indent=2))
        typer.echo("Pass --approve after reviewing this exact plan.")
        return
    try:
        store.require_project(plan.project_id)
    except KeyError:
        from hlagent.models import now
        with store.connection() as con:
            con.execute("INSERT INTO projects VALUES (?,?,?)", (plan.project_id, "Imported approved analysis", now()))
    try:
        stored = store.plan(plan.id)
        if stored.plan_hash != plan.plan_hash:
            raise typer.BadParameter("Imported plan differs from stored plan")
    except KeyError:
        store.put_plan(plan)
    job = store.approve(PlanApproval(plan_id=plan.id, plan_hash=plan.plan_hash, revision=plan.revision))
    if job.state in ("failed", "cancelled"):
        store.resume(job.id)
    typer.echo(job.id)


@app.command()
def start(open_browser: bool = False):
    """Start API, independent worker and Streamlit in separate background processes."""
    settings = Settings().initialize()
    api_token(settings.home)
    processes = []
    pid_file = settings.home / "services.json"
    old = json.loads(pid_file.read_text()) if pid_file.exists() else []
    import psutil

    from hlagent.execution import alive, process_identity
    from hlagent.models import digest
    signature = digest({"home": str(settings.home), "inbox": str(settings.knowledge_inbox),
                        "source": tool_versions(settings)["hlagent_source_sha256"]})
    for role, command in (
        ("api", [sys.executable, "-m", "hlagent.cli", "api"]),
        ("worker", [sys.executable, "-m", "hlagent.cli", "worker"]),
        ("ui", [sys.executable, "-m", "streamlit", "run", str(Path(__file__).with_name("ui.py")),
                "--server.address", "127.0.0.1", "--server.port", str(settings.ui_port),
                "--server.headless", "true", "--browser.gatherUsageStats", "false"]),
    ):
        existing = next((p for p in old if p["role"] == role and alive(p)), None)
        if existing and existing.get("signature") == signature:
            processes.append(existing)
            continue
        for proc in owned_services(settings, role):
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except psutil.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        with (settings.home / "logs" / (role + ".log")).open("ab") as log:
            p = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                 stdin=subprocess.DEVNULL, start_new_session=True, env=os.environ.copy())
        processes.append(dict(role=role, signature=signature, **process_identity(p.pid)))
    pid_file.write_text(json.dumps(processes, indent=2))
    for _ in range(40):
        try:
            if httpx.get(f"http://127.0.0.1:{settings.api_port}/health", timeout=1).is_success:
                break
        except httpx.HTTPError:
            pass
        time.sleep(.5)
    else:
        raise typer.BadParameter("API did not start; see " + str(settings.home / "logs/api.log"))
    url = f"http://127.0.0.1:{settings.ui_port}"
    typer.echo(url)
    if open_browser:
        if "WSL_DISTRO_NAME" in os.environ:
            subprocess.run(["cmd.exe", "/c", "start", url], capture_output=True)
        else:
            import webbrowser
            webbrowser.open(url)


@app.command()
def stop():
    """Stop application services. Bioinformatics commands can be recovered on the next start."""
    import signal

    import psutil
    settings = Settings().initialize()
    pid_file = settings.home / "services.json"
    for proc in owned_services(settings):
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except psutil.TimeoutExpired:
            proc.kill()
    pid_file.unlink(missing_ok=True)


def owned_services(settings: Settings, role: str | None = None):
    """Discover only this venv/home's fixed service commands, including orphaned stale service records."""
    import psutil
    for proc in psutil.process_iter():
        try:
            args = proc.cmdline()
            if not args or Path(args[0]).parent != Path(sys.executable).parent:
                continue
            matched = None
            if args[1:] == ["-m", "hlagent.cli", "api"]:
                matched = "api"
            elif args[1:] == ["-m", "hlagent.cli", "worker"]:
                matched = "worker"
            elif args[1:4] == ["-m", "streamlit", "run"] and len(args) > 4 and Path(args[4]) == Path(__file__).with_name("ui.py"):
                matched = "ui"
            if matched and (role is None or role == matched):
                configured_home = proc.environ().get("HLAGENT_HOME", str(Path.home() / ".local/share/hlagent"))
                if Path(configured_home).resolve() == settings.home:
                    yield proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue


if __name__ == "__main__":
    app()
