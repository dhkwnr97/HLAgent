"""Route each user message to a mode: HLA expert Q&A, analysis planning, plan response or run status.

Order: (1) deterministic rules for unambiguous replies (e.g. "go ahead" while a plan awaits approval),
(2) Jev decision model with FallbackModel hand-off to the chat LLM when Jev is unsure, (3) keyword rules
when no model is configured. The message text is all the router sees.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

from hlagent.logging_utils import get_logger

log = get_logger(__name__)

Intent = Literal["ask_hla", "request_analysis", "respond_to_plan", "ask_run_status", "other"]


class Route(BaseModel):
    """Decide which part of HLAgent (an HLA analysis assistant) should handle the user's latest message."""

    intent: Intent = Field(
        description=(
            "What does the latest user message ask for? "
            "ask_hla: a question about HLA/MHC biology, immunogenetics, methods, tools or literature; "
            "request_analysis: run, set up or change an HLA data analysis (imputation, phasing, association, "
            "omnibus, meta-analysis, Node1-Node5) on a dataset; "
            "respond_to_plan: approve, reject or edit the analysis plan that is waiting for approval; "
            "ask_run_status: progress, results or files of an analysis that was started; "
            "other: greetings or anything else"
        )
    )


@dataclass
class RouterState:
    pending_plan: bool = False
    has_runs: bool = False


router_agent: Agent[RouterState, Route] = Agent(
    deps_type=RouterState, output_type=Route, name="router", retries=1
)


@router_agent.instructions
def _state(ctx: RunContext[RouterState]) -> str:
    return (
        f"Session state: an analysis plan is {'waiting for approval' if ctx.deps.pending_plan else 'not pending'}; "
        f"analyses {'have been started' if ctx.deps.has_runs else 'have not been started'} in this session."
    )


# Keyword lists accept English and Korean replies, because users may write in either language.
_YES = re.compile(
    r"^\s*(네|예|응|ㅇㅇ|ㅇㅋ|좋아|좋습니다|진행|승인|할래|해줘|해 줘|고고|go|yes|y|ok|okay|sure|approve|run( it)?|start)"
    r"[\s!.~요해줘]*$",
    re.I,
)
_NO = re.compile(r"^\s*(아니|아니요|아뇨|싫어|취소|no|n|cancel|stop)\b", re.I)
_NODES = re.compile(r"node\s*[1-5]|노드\s*[1-5]|node\s*[1-5]\s*[~-]\s*[1-5]", re.I)
_ANALYSIS = re.compile(
    r"분석|돌려|실행|임퓨테이션|imputation|impute|phasing|페이징|cookhla|beagle|omnibus|옴니버스|"
    r"회귀|regression|association|연관|meta|메타|fine.?mapping|파인매핑|run |analy[sz]",
    re.I,
)
_STATUS = re.compile(
    r"진행\s*상황|상태|어디까지|끝났|완료|status|progress|결과\s*(보여|어때|파일)|report|보고서", re.I
)


def rule_route(text: str, state: RouterState, *, final: bool = False) -> Intent | None:
    """Deterministic routing. With final=True always returns an intent (keyword fallback)."""
    if state.pending_plan and (_YES.match(text) or _NO.match(text) or _NODES.search(text)):
        return "respond_to_plan"
    if not final:
        return None
    if state.has_runs and _STATUS.search(text):
        return "ask_run_status"
    if _ANALYSIS.search(text) or _NODES.search(text):
        return "respond_to_plan" if state.pending_plan else "request_analysis"
    return "ask_hla"


@dataclass
class RouteResult:
    intent: Intent
    by: Literal["rule", "jev", "llm", "keyword"]


async def route(text: str, state: RouterState, model) -> RouteResult:
    r = rule_route(text, state)
    if r:
        return RouteResult(r, "rule")
    if model is None:
        return RouteResult(rule_route(text, state, final=True) or "ask_hla", "keyword")
    try:
        res = await router_agent.run(text, model=model, deps=state)
    except Exception as e:  # noqa: BLE001 - routing must never break the chat
        log.warning("router model failed (%s); keyword routing", type(e).__name__)
        return RouteResult(rule_route(text, state, final=True) or "ask_hla", "keyword")
    name = (res.response.model_name or "").lower()
    return RouteResult(res.output.intent, "jev" if "jev" in name else "llm")
