"""One chat session: routes messages to the HLA expert (mode 1) or the analysis planner (mode 2),
holds the pending approval and the runs it started. UI-independent (Streamlit calls it through a bridge).

Without any LLM key the session still works for analyses: a rule-based planner reads dataset names and
"NodeX" from the message and builds the same approval card.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic_ai import DeferredToolRequests, DeferredToolResults, ToolApproved, ToolDenied

from hlagent import datasets, jobs
from hlagent.agents import expert as expert_mod
from hlagent.agents.planner import (
    PlanDraft,
    PlannerDeps,
    StudyDraft,
    build_plan,
    planner_agent,
    preview,
    render_proposal,
)
from hlagent.agents.router import RouterState, route
from hlagent.config import Settings, get_settings
from hlagent.llm.registry import Keys, NoModelAvailable, ProviderName, chat_model, embedder, router_model
from hlagent.logging_utils import get_logger

log = get_logger(__name__)

Mode = Literal["auto", "expert", "analysis"]
_KO = re.compile(r"[가-힣]")  # Hangul syllables: Korean requests are supported


@dataclass
class Reply:
    kind: Literal["text", "approval", "status", "error", "info"]
    content: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class Pending:
    draft: PlanDraft
    preview: dict[str, Any]
    tool_call_id: str | None = None  # None: rule-based plan (no LLM)
    messages: list = field(default_factory=list)


def is_korean(text: str) -> bool:
    return bool(_KO.search(text))


_NODE_RANGE = re.compile(
    # node ranges in English or Korean ("부터"/"에서" = "from")
    r"node\s*([1-5])\s*(?:~|-|–|to|부터|에서)\s*(?:node\s*)?([1-5])|([1-5])\s*~\s*([1-5])",
    re.I,
)
_NODE_ONE = re.compile(r"(?:node|노드)\s*([1-5])", re.I)


def parse_nodes(text: str) -> list[str]:
    m = _NODE_RANGE.search(text)
    if m:
        a, b = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        lo, hi = sorted((int(a), int(b)))
        return [f"Node{i}" for i in range(lo, hi + 1)]
    ones = sorted({int(x) for x in _NODE_ONE.findall(text)})
    # "까지" is Korean for "up to"
    if ones and re.search(r"까지|up to|through|until", text, re.I) and len(ones) == 1:
        return [f"Node{i}" for i in range(1, ones[0] + 1)]
    return [f"Node{i}" for i in ones]


def heuristic_draft(text: str) -> PlanDraft | None:
    """Rule-based draft: datasets named in the text + nodes; synthetic phenotype when none is usable."""
    from hlagent.agents.planner import inspect_dataset

    cat = datasets.catalog()
    low = text.lower()
    chosen = [d for d in cat if d.id.lower() in low]
    if not chosen:
        return None
    studies = []
    for d in chosen:
        sd = StudyDraft(dataset_id=d.id)
        if d.external_assoc is None:
            info = inspect_dataset(d.id)
            if not (info.get("phenotype") or {}).get("usable"):
                sd.phenotype = "synthetic_spike_in" if info.get("hla_genes_typed") else "synthetic_null"
        studies.append(sd)
    nodes = parse_nodes(text) or (
        ["Node1", "Node2", "Node5"] if len(studies) > 1 else ["Node1", "Node2", "Node3", "Node4"]
    )
    if len(studies) > 1 and "Node5" not in nodes and not parse_nodes(text):
        nodes.append("Node5")
    goal = text.strip().splitlines()[0][:120]
    return PlanDraft(goal=goal, studies=studies, nodes=sorted(set(nodes)))  # type: ignore[arg-type]


class ChatSession:
    def __init__(
        self,
        keys: Keys | None = None,
        settings: Settings | None = None,
        provider: ProviderName | None = None,
        mode: Mode = "auto",
        start_job: Callable[..., str] | None = None,
    ):
        self.settings = settings or get_settings()
        self.keys = keys or Keys.resolve(self.settings)
        self.provider = provider
        self.mode: Mode = mode
        self.start_job = start_job or jobs.start
        self.expert_history: list = []
        self.planner_history: list = []
        self.pending: Pending | None = None
        self.runs: list[str] = []
        self._kb = None
        self._models: dict[str, Any] = {}

    # ------------------------------------------------------------------ models
    def chat(self):
        if "chat" not in self._models:
            try:
                self._models["chat"] = chat_model(self.keys, self.settings, self.provider)
            except NoModelAvailable:
                self._models["chat"] = None
        return self._models["chat"]

    def router(self):
        if "router" not in self._models:
            self._models["router"] = router_model(self.keys, self.settings, self.provider)
        return self._models["router"]

    def kb(self):
        if self._kb is None:
            try:
                from hlagent.rag.store import KnowledgeBase

                self._kb = KnowledgeBase(embedder(self.keys, self.settings), self.settings.embedding_model)
            except (NoModelAvailable, ImportError) as e:
                log.info("knowledge base unavailable: %s", e)
                self._kb = False
        return self._kb or None

    # ------------------------------------------------------------------ entry point
    async def send(self, text: str) -> list[Reply]:
        text = text.strip()
        if not text:
            return []
        state = RouterState(pending_plan=self.pending is not None, has_runs=bool(self.runs))
        if self.mode == "expert":
            intent = "ask_hla"
        elif self.mode == "analysis":
            intent = (
                "respond_to_plan"
                if self.pending
                else ("ask_run_status" if self.runs and _status_q(text) else "request_analysis")
            )
        else:
            intent = (await route(text, state, self.router())).intent
        if intent == "respond_to_plan" and self.pending is None:
            intent = "request_analysis"
        if intent == "ask_hla" or intent == "other":
            return await self._expert(text)
        if intent == "ask_run_status":
            return [self.run_status()]
        if intent == "respond_to_plan":
            from hlagent.agents.router import _NO, _YES

            if _YES.match(text):
                return await self.approve()
            if _NO.match(text) and not parse_nodes(text):
                return await self.deny(text)
            return await self._revise(text)
        return await self._plan(text)

    # ------------------------------------------------------------------ mode 1
    async def _expert(self, text: str) -> list[Reply]:
        model = self.chat()
        if model is None:
            return [
                Reply(
                    "error",
                    "No LLM API key: add a Google, OpenAI or Anthropic key in Settings.",
                )
            ]
        deps = expert_mod.ExpertDeps(kb=self.kb(), tavily_key=self.keys.plain("tavily"))
        try:
            ans, new = await expert_mod.answer(text, model, deps, self.expert_history[-20:])
        except Exception as e:  # noqa: BLE001
            log.warning("expert failed: %s", type(e).__name__)
            return [Reply("error", f"Could not generate an answer: {type(e).__name__}: {e}"[:500])]
        self.expert_history += new
        return [Reply("text", ans, {"sources": deps.sources})]

    # ------------------------------------------------------------------ mode 2
    def _deps(self) -> PlannerDeps:
        return PlannerDeps(start_job=self._start)

    def _start(self, plan) -> str:
        run_id = self.start_job(plan)
        self.runs.append(run_id)
        return run_id

    def _approval_reply(self, pend: Pending) -> Reply:
        return Reply(
            "approval",
            render_proposal(pend.draft, pend.preview),
            {
                "nodes": list(pend.draft.nodes),
                "draft": pend.draft.model_dump(mode="json"),
                "tool_call_id": pend.tool_call_id,
            },
        )

    async def _plan(self, text: str) -> list[Reply]:
        model = self.chat()
        if model is None:
            draft = heuristic_draft(text)
            if draft is None:
                names = ", ".join(d.id for d in datasets.catalog())
                return [
                    Reply(
                        "info",
                        f"Name a dataset to analyse. Available: {names}. "
                        "(No LLM key is set, so the plan is built by rules.)",
                    )
                ]
            pv = preview(draft)
            if not pv["ok"]:
                return [Reply("error", "\n".join(pv["errors"] + pv["needs_user_choice"]))]
            self.pending = Pending(draft, pv)
            return [self._approval_reply(self.pending)]
        deps = self._deps()
        try:
            r = await planner_agent.run(
                text, model=model, deps=deps, message_history=self.planner_history[-30:]
            )
        except Exception as e:  # noqa: BLE001
            log.warning("planner failed: %s", type(e).__name__)
            return [Reply("error", f"Could not create a plan: {type(e).__name__}: {e}"[:500])]
        out: list[Reply] = []
        if isinstance(r.output, DeferredToolRequests):
            calls = [c for c in r.output.approvals if c.tool_name == "execute_plan"]
            if calls:
                c = calls[0]
                draft = PlanDraft.model_validate(c.args_as_dict()["draft"])
                pv = deps.previews.get(draft.model_dump_json()) or preview(draft)
                self.pending = Pending(draft, pv, c.tool_call_id, r.all_messages())
                out.append(self._approval_reply(self.pending))
            return out
        self.planner_history = r.all_messages()
        self.pending = None
        out.append(Reply("text", r.output))
        for run_id in deps.started:
            out.append(Reply("status", f"Analysis started: `{run_id}`", {"run_id": run_id}))
        return out

    async def approve(self, nodes: list[str] | None = None) -> list[Reply]:
        p = self.pending
        if p is None:
            return [Reply("info", "There is no plan to approve.")]
        draft = p.draft
        if nodes and sorted(nodes) != sorted(draft.nodes):
            draft = draft.model_copy(update={"nodes": sorted(set(nodes))})
            pv = preview(draft)
            if not pv["ok"]:
                return [Reply("error", "\n".join(pv["errors"] + pv["needs_user_choice"]))]
        if p.tool_call_id is None:  # rule-based plan
            self.pending = None
            try:
                run_id = self._start(build_plan(draft))
            except RuntimeError as e:
                return [Reply("error", str(e))]
            return [Reply("status", f"Analysis started: `{run_id}`", {"run_id": run_id})]
        decision: bool | ToolApproved = (
            True if draft is p.draft else ToolApproved(override_args={"draft": draft.model_dump(mode="json")})
        )
        self.pending = None
        return await self._resume(p, decision)

    async def _resume(self, p: Pending, decision, prompt: str | None = None) -> list[Reply]:
        deps = self._deps()
        try:
            r = await planner_agent.run(
                prompt,
                model=self.chat(),
                deps=deps,
                message_history=p.messages,
                deferred_tool_results=DeferredToolResults(approvals={p.tool_call_id: decision}),
            )
        except Exception as e:  # noqa: BLE001
            log.warning("planner resume failed: %s", type(e).__name__)
            return [Reply("error", f"Could not start the run: {type(e).__name__}: {e}"[:500])]
        out: list[Reply] = []
        for run_id in deps.started:
            out.append(Reply("status", f"Analysis started: `{run_id}`", {"run_id": run_id}))
        if isinstance(r.output, DeferredToolRequests):  # re-planned after an edit
            calls = [c for c in r.output.approvals if c.tool_name == "execute_plan"]
            if calls:
                c = calls[0]
                draft = PlanDraft.model_validate(c.args_as_dict()["draft"])
                self.pending = Pending(
                    draft,
                    deps.previews.get(draft.model_dump_json()) or preview(draft),
                    c.tool_call_id,
                    r.all_messages(),
                )
                out.append(self._approval_reply(self.pending))
            return out
        self.planner_history = r.all_messages()
        if r.output:
            out.append(Reply("text", r.output))
        return out

    async def deny(self, reason: str = "") -> list[Reply]:
        p = self.pending
        self.pending = None
        if p is None or p.tool_call_id is None:
            return [Reply("info", "Plan cancelled.")]
        return await self._resume(p, ToolDenied(f"The user declined the plan. {reason}".strip()))

    async def _revise(self, text: str) -> list[Reply]:
        """User answered the approval card with text (e.g. 'only up to Node2'): re-plan."""
        p = self.pending
        assert p is not None
        nodes = parse_nodes(text)
        if p.tool_call_id is None or self.chat() is None:
            if nodes:
                draft = p.draft.model_copy(update={"nodes": nodes})
                pv = preview(draft)
                if not pv["ok"]:
                    return [Reply("error", "\n".join(pv["errors"] + pv["needs_user_choice"]))]
                self.pending = Pending(draft, pv)
                return [self._approval_reply(self.pending)]
            self.pending = None
            return await self._plan(text)
        self.pending = None
        return await self._resume(
            p, ToolDenied("The user wants changes before approving; see their message."), text
        )

    # ------------------------------------------------------------------ status
    def run_status(self, run_id: str | None = None) -> Reply:
        rid = run_id or (self.runs[-1] if self.runs else None)
        if rid is None:
            rs = jobs.list_runs(1)
            if not rs:
                return Reply("info", "No analysis has been run yet.")
            rid = rs[0]["run_id"]
        from hlagent import paths

        st = jobs.status(paths.runs_dir() / rid)
        pr = st.get("progress") or {}
        cur = (st.get("current") or {}).get("title")
        lines = [f"**{rid}**: {st.get('state')} ({pr.get('done', 0)}/{pr.get('total', 0)} steps)"]
        if cur and st.get("state") == "running":
            lines.append(f"Current step: {cur}")
        if st.get("message"):
            lines.append(st["message"])
        rep = paths.runs_dir() / rid / "report" / "report.html"
        if rep.exists():
            lines.append(f"Report: `{rep}`")
        return Reply("status", "\n\n".join(lines), {"run_id": rid, "status": st})


def _status_q(text: str) -> bool:
    from hlagent.agents.router import _STATUS

    return bool(_STATUS.search(text))
