"""Command line interface: `hlagent doctor | setup-resources | example-plan | run | ingest | ui`."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import typer

from hlagent import paths

app = typer.Typer(add_completion=False, help="HLAgent v3: HLA expert Q&A and HLA analysis pipeline")


@app.command()
def doctor() -> None:
    """Check tools, resources, Docker image, memory and API keys."""
    from hlagent.doctor import run_checks

    checks = run_checks()
    for c in checks:
        typer.echo(
            f"[{c['status']:4}] {c['name']:28} {c['detail']}"
            + (f"\n        fix: {c['fix']}" if c["fix"] else "")
        )
    if any(c["status"] == "FAIL" for c in checks):
        raise typer.Exit(1)


@app.command("setup-resources")
def setup_resources(
    from_v1: Path = typer.Option(
        None, help="HLAgent v1 checkout (e.g. /mnt/f/Claude_cw/HLAgent/HLAgent-main_v1.0.0)"
    ),
    clone: bool = typer.Option(False, help="git clone github.com/dhkwnr97/HLAgent into resources/_v1"),
    liftover_chains: bool = typer.Option(False, help="download hg19ToHg18 / hg38ToHg19 chains from UCSC"),
) -> None:
    """Copy reference panels, IMGT data and examples from HLAgent v1; optionally fetch liftover chains."""
    from hlagent.resources_setup import clone_v1, setup_from_v1

    if clone:
        from_v1 = clone_v1(paths.resources_dir() / "_v1")
    if from_v1:
        for k, v in setup_from_v1(from_v1).items():
            typer.echo(f"{v:6} files  {k}")
    if liftover_chains:
        import urllib.request

        from hlagent.tools.cookhla import UCSC_CHAIN_URL

        d = paths.resources_dir() / "liftover"
        d.mkdir(parents=True, exist_ok=True)
        for src, name in (("hg19", "hg19ToHg18.over.chain.gz"), ("hg38", "hg38ToHg19.over.chain.gz")):
            dst = d / name
            if not dst.exists():
                typer.echo(f"downloading {name}")
                urllib.request.urlretrieve(UCSC_CHAIN_URL.format(src=src, name=name), dst)  # noqa: S310
            typer.echo(f"ok {dst}")
    if not (from_v1 or liftover_chains):
        typer.echo("nothing to do: pass --from-v1 PATH, --clone and/or --liftover-chains")


@app.command("example-plan")
def example_plan(
    scenario: str = typer.Argument(..., help="S2 | S3 | S4 | S5"),
    out: Path = typer.Option(None, help="write plan JSON here"),
) -> None:
    """Write a ready-made plan for an acceptance scenario."""
    from hlagent.examples import scenario as sc
    from hlagent.pipeline.dag import resolve

    plan = sc(scenario)
    text = plan.model_dump_json(indent=1)
    if out:
        out.write_text(text)
        typer.echo(f"wrote {out}")
    else:
        typer.echo(text)
    r = resolve(plan)
    for t in r.tasks:
        typer.echo(f"  - {t.step:7} {t.study_id or ''}", err=True)
    for n in r.notes:
        typer.echo(f"  note: {n}", err=True)


@app.command()
def run(
    plan: Path = typer.Option(..., help="plan JSON (AnalysisPlan)"),
    run_dir: Path = typer.Option(None, help="resume in an existing run directory"),
) -> None:
    """Run a plan in the foreground (the GUI uses the same engine in a background process)."""
    from hlagent.pipeline.dag import AnalysisPlan
    from hlagent.pipeline.runner import execute, prepare_run_dir

    p = AnalysisPlan.model_validate_json(plan.read_text())
    if run_dir is None:
        run_dir = prepare_run_dir(p, paths.runs_dir())
    elif not (run_dir / "plan.json").exists():
        run_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(plan, run_dir / "plan.json")
    typer.echo(f"run dir: {run_dir}")
    res = execute(run_dir)
    typer.echo(json.dumps(res, indent=1))
    if res["state"] == "failed":
        raise typer.Exit(1)


@app.command("eval-planning")
def eval_planning(
    models: str = typer.Option(
        ...,
        help="comma-separated: google:gemini-3-flash-preview,openai:gpt-5.5,"
        "anthropic:claude-sonnet-5-5,ollama:llama3.1:8b; 'oracle'/'naive' run offline",
    ),
    repeats: int = typer.Option(3, min=1, max=50),
    out: Path = typer.Option(Path("benchmarks/planning/results"), help="results folder (resumable)"),
    tasks: Path = typer.Option(Path("benchmarks/planning/tasks.json")),
    concurrency: int = typer.Option(2, min=1, max=16),
    routing: bool = typer.Option(True, help="also score the router on the routing items"),
) -> None:
    """Per-step benchmark of LLM planning (resolved execution graph, parameters, protocol, latency)."""
    import asyncio

    from hlagent.eval.planning import run_suite, write_summary

    raw = asyncio.run(
        run_suite(
            tasks, [m.strip() for m in models.split(",") if m.strip()], repeats, out, concurrency, routing
        )
    )
    path = write_summary(raw, out)
    typer.echo(f"raw: {raw}\nsummary: {path} and {out / 'summary.md'}")


@app.command()
def ingest(rebuild: bool = typer.Option(False, help="drop and rebuild the collection")) -> None:
    """Index knowledge/articles (PDF, Markdown, text) into ChromaDB for the HLA expert."""
    from hlagent.config import get_settings
    from hlagent.llm.registry import Keys, NoModelAvailable, embedder
    from hlagent.rag.store import KnowledgeBase, ingest_folder

    s = get_settings()
    try:
        emb = embedder(Keys.resolve(s), s)
    except NoModelAvailable as e:
        typer.echo(str(e))
        raise typer.Exit(1) from e
    kb = KnowledgeBase(emb, s.embedding_model)
    for name, n in ingest_folder(paths.knowledge_dir(), kb, rebuild=rebuild).items():
        typer.echo(f"{n:6} new chunks  {name}" if n >= 0 else f"FAILED        {name}")
    typer.echo(f"collection: {kb.count()} chunks, embedding model {kb.built_with()}")


@app.command()
def ui(port: int = 8501) -> None:
    """Launch the Streamlit GUI."""
    app_py = Path(__file__).parent / "ui" / "app.py"
    raise typer.Exit(
        subprocess.call([sys.executable, "-m", "streamlit", "run", str(app_py), "--server.port", str(port)])  # noqa: S603
    )


if __name__ == "__main__":
    app()
