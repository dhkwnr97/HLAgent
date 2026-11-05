"""Stage R: facts sheet, optional LLM narrative (validated against the facts), Markdown + HTML report."""

from __future__ import annotations

from hlagent.logging_utils import get_logger
from hlagent.pipeline.contracts import ArtifactRef, NodeResult
from hlagent.report.facts import build_facts
from hlagent.report.render import collect_figures, render

log = get_logger(__name__)


def run(ctx, _study=None) -> NodeResult:
    p = ctx.params.stage_r
    out = ctx.run_dir / "report"
    res = NodeResult(node="StageR", study_id=None, status="ok", cache_key="")
    facts = build_facts(ctx)
    narrative = None
    if p.use_llm_narrative:
        try:
            from hlagent.agents.reporter import narrate_sync

            narrative = narrate_sync(facts)
            res.metrics["narrative"] = "llm" if narrative else "none"
        except Exception as e:  # noqa: BLE001 - the report must not depend on an LLM being reachable
            log.warning("LLM narrative skipped: %s", e)
            res.warnings.append(f"LLM narrative skipped ({type(e).__name__}); deterministic summary used.")
            res.metrics["narrative"] = "deterministic"
    files = render(facts, collect_figures(ctx, out), out, narrative)
    res.artifacts["report_md"] = ArtifactRef.of("report", files["md"])
    res.artifacts["report_html"] = ArtifactRef.of("report", files["html"])
    res.artifacts["facts"] = ArtifactRef.of("json", out / "facts.json")
    if res.warnings:
        res.status = "warning"
    return res
