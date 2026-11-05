"""Mode 1: HLA expert answers (graduate level) grounded in the local knowledge base and, optionally, the web.

Retrieved passages get ids K1, K2, ... (knowledge base) and W1, W2, ... (Tavily web search). The answer
must cite with these ids; an output validator rejects ids that were never retrieved, and the reference list
is appended by code from what was actually retrieved, so citations cannot be invented.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from pydantic_ai import Agent, ModelRetry, RunContext

from hlagent.logging_utils import get_logger

log = get_logger(__name__)

_CITE = re.compile(r"\[([KW]\d+)\]")


@dataclass
class ExpertDeps:
    kb: Any | None = None  # rag.store.KnowledgeBase
    tavily_key: str | None = None
    k: int = 6
    sources: dict[str, dict[str, Any]] = field(default_factory=dict)

    def _add(self, prefix: str, item: dict[str, Any]) -> str:
        for sid, s in self.sources.items():  # same passage retrieved twice keeps its id
            if s.get("key") == item["key"]:
                return sid
        sid = f"{prefix}{sum(1 for x in self.sources if x.startswith(prefix)) + 1}"
        self.sources[sid] = item
        return sid


INSTRUCTIONS = """\
You are HLAgent's HLA expert: an immunogeneticist answering at graduate (MSc-PhD) level about HLA/MHC
biology, nomenclature (IMGT/HLA, G/P groups), typing and imputation (e.g. CookHLA, SNP2HLA, HIBAG),
fine-mapping (binary markers, amino-acid omnibus tests, conditional analysis), meta-analysis and disease
associations.

Method:
1. Call search_knowledge first (rephrase the question into 1-2 focused English queries).
2. If the knowledge base is thin or the question needs recent facts, call web_search when it is available.
3. Answer precisely: mechanisms, definitions, typical effect sizes or study designs, caveats (LD in the MHC,
   population differences, imputation accuracy, multiple testing). Use LaTeX ($...$, $$...$$) for formulas.
4. Cite every sourced statement with the passage ids in square brackets, e.g. [K2] or [W1]. Use only ids that
   the tools returned. Mark statements from general knowledge without a citation as such; never invent
   references, DOIs, numbers or author names.
5. Answer in the user's language (Korean if the user writes Korean); keep technical terms in English in
   parentheses where helpful. Do not add a reference list; it is appended automatically.
"""

expert_agent: Agent[ExpertDeps, str] = Agent(
    deps_type=ExpertDeps, output_type=str, instructions=INSTRUCTIONS, name="hla_expert", retries=2
)


@expert_agent.tool
def search_knowledge(ctx: RunContext[ExpertDeps], query: str) -> list[dict[str, Any]]:
    """Search the local HLA literature knowledge base (indexed PDFs). Returns passages with citation ids."""
    kb = ctx.deps.kb
    if kb is None:
        return [{"note": "knowledge base not available (no embedding model or not indexed)"}]
    try:
        hits = kb.query(query, ctx.deps.k)
    except RuntimeError as e:
        return [{"note": str(e)}]
    out = []
    for h in hits:
        sid = ctx.deps._add(
            "K", {"key": h.id, "title": h.title or h.source, "page": h.page, "doi": h.doi, "source": h.source}
        )
        out.append(
            {"id": sid, "title": h.title or h.source, "page": h.page, "similarity": h.score, "text": h.text}
        )
    return out or [{"note": "no passages found"}]


@expert_agent.tool
async def web_search(ctx: RunContext[ExpertDeps], query: str) -> list[dict[str, Any]]:
    """Search the web (Tavily) for recent or missing information. Returns results with citation ids."""
    if not ctx.deps.tavily_key:
        return [{"note": "web search is disabled (no Tavily API key)"}]
    from tavily import AsyncTavilyClient

    try:
        res = await AsyncTavilyClient(api_key=ctx.deps.tavily_key).search(query, max_results=5)
    except Exception as e:  # noqa: BLE001 - search is optional
        log.warning("tavily search failed: %s", type(e).__name__)
        return [{"note": f"web search failed ({type(e).__name__})"}]
    out = []
    for r in res.get("results", []):
        sid = ctx.deps._add("W", {"key": r.get("url"), "title": r.get("title", ""), "url": r.get("url", "")})
        out.append(
            {
                "id": sid,
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "text": r.get("content", "")[:1500],
            }
        )
    return out or [{"note": "no web results"}]


@expert_agent.output_validator
def _citations_exist(ctx: RunContext[ExpertDeps], text: str) -> str:
    unknown = sorted({c for c in _CITE.findall(text) if c not in ctx.deps.sources})
    if unknown:
        raise ModelRetry(f"You cited {', '.join(unknown)}, which no tool returned. Cite only returned ids.")
    return text


def references(text: str, sources: dict[str, dict[str, Any]]) -> str:
    cited = list(dict.fromkeys(_CITE.findall(text)))
    if not cited:
        return ""
    lines = ["", "**References**", ""]
    for c in cited:
        s = sources[c]
        if c.startswith("K"):
            doi = f" https://doi.org/{s['doi']}" if s.get("doi") else ""
            lines.append(f"- [{c}] {s['title']}, p.{s['page']} ({s['source']}){doi}")
        else:
            lines.append(f"- [{c}] {s['title']}: {s['url']}")
    return "\n".join(lines)


async def answer(question: str, model, deps: ExpertDeps, message_history=None):
    """Return (markdown answer with references, new messages)."""
    r = await expert_agent.run(question, model=model, deps=deps, message_history=message_history)
    return r.output + references(r.output, deps.sources), r.new_messages()
