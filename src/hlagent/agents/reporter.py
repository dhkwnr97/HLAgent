"""Report narrative: an LLM summary written only from facts.json and checked number by number.

The model sees aggregate results (metrics, top markers, meta-analysis rows, warnings), never sample data.
Every number in its text must occur in the facts (report.validate); otherwise the model is asked to retry,
and after the retries the deterministic summary is kept. Without an LLM key nothing is called.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.exceptions import UnexpectedModelBehavior

from hlagent.logging_utils import get_logger
from hlagent.report.facts import numbers_in
from hlagent.report.validate import unsupported_numbers

log = get_logger(__name__)

INSTRUCTIONS = """\
You write the Summary section of an HLA fine-mapping report for a statistical geneticist.
Use ONLY the JSON facts given. Copy every number exactly as it appears there (same digits or fewer,
correctly rounded; e-notation allowed); do not compute new numbers (no conversions, no sums).
Cover per study: samples and phenotype, the top Node2 marker with effect and P, how many markers pass
Bonferroni, Node3 independent signals, the top Node4 amino-acid position; then the meta-analysis
(top marker, OR_FE, P_FE, I2 and the heterogeneity caveat). State limitations from the warnings
(small samples, synthetic phenotypes, imputation confidence). If the phenotype is synthetic say so first.
Write 2-4 short paragraphs of plain Markdown, no headings, no tables. Do not claim causality.
Write in {language}."""


reporter_agent: Agent[dict[str, Any], str] = Agent(
    deps_type=dict, output_type=str, name="reporter", retries=2
)


@reporter_agent.instructions
def _instr(ctx: RunContext[dict[str, Any]]) -> str:
    return INSTRUCTIONS.format(language=ctx.deps.get("language", "English"))


@reporter_agent.output_validator
def _grounded(ctx: RunContext[dict[str, Any]], text: str) -> str:
    bad = unsupported_numbers(text, ctx.deps["values"])
    if bad:
        raise ModelRetry(
            f"These numbers are not in the facts: {', '.join(bad[:15])}. Use only numbers copied "
            "from the facts JSON and do not derive new ones."
        )
    return text


def facts_for_llm(facts: dict[str, Any], top_n: int = 5) -> dict[str, Any]:
    """Compact facts: metrics, short top lists and warnings (aggregate results only)."""
    out: dict[str, Any] = {
        "goal": facts.get("goal"),
        "synthetic": facts.get("synthetic"),
        "studies": {},
        "warnings": facts.get("warnings", [])[:25],
    }
    for sid, st in facts.get("studies", {}).items():
        steps = {}
        for step, e in st.get("steps", {}).items():
            d = {"status": e.get("status"), "metrics": e.get("metrics", {})}
            if e.get("top_markers"):
                d["top_markers"] = e["top_markers"][:top_n]
            if e.get("conditional_steps"):
                d["conditional_steps"] = e["conditional_steps"][:top_n]
            steps[step] = d
        out["studies"][sid] = {"external_summary": st.get("external_summary"), "steps": steps}
    if facts.get("meta"):
        out["meta"] = {"metrics": facts["meta"]["metrics"], "top": facts["meta"].get("top", [])[:top_n]}
    return out


async def narrate(facts: dict[str, Any], model, language: str = "English") -> str | None:
    compact = facts_for_llm(facts)
    deps = {"values": numbers_in(compact), "language": language}
    try:
        r = await reporter_agent.run(json.dumps(compact, default=str), model=model, deps=deps)
    except UnexpectedModelBehavior as e:
        log.warning("narrative rejected after retries: %s", e)
        return None
    return r.output.strip() or None


def narrate_sync(facts: dict[str, Any], keys=None, language: str = "English") -> str | None:
    """Used by Stage R inside the pipeline process: only .env keys are visible there."""
    from hlagent.llm.registry import Keys, NoModelAvailable, chat_model

    try:
        model = chat_model(keys or Keys.resolve())
    except NoModelAvailable:
        return None
    import asyncio

    return asyncio.run(narrate(facts, model, language))


async def add_narrative(run_dir: Path, model, language: str = "English") -> bool:
    """Re-render an existing report with an LLM narrative (GUI path; keys stay in the GUI process)."""
    from hlagent.report.render import render

    rep = Path(run_dir) / "report"
    facts = json.loads((rep / "facts.json").read_text())
    figures = json.loads((rep / "figures.json").read_text()) if (rep / "figures.json").exists() else {}
    text = await narrate(facts, model, language)
    if not text:
        return False
    render(facts, figures, rep, text)
    return True
