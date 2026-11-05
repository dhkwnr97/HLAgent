"""Agents without network: FunctionModel scripts the LLM's tool calls (ALLOW_MODEL_REQUESTS is False)."""

from __future__ import annotations

import json

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel

from hlagent.agents import expert as expert_mod
from hlagent.agents.reporter import narrate
from hlagent.agents.router import RouterState, route, rule_route
from hlagent.agents.session import ChatSession, parse_nodes
from hlagent.llm.registry import Keys
from hlagent.rag.store import Hit
from tests.conftest import needs_resources

pytestmark = needs_resources

DRAFT = {
    "goal": "BMExample demo",
    "studies": [{"dataset_id": "BMExample", "phenotype": "synthetic_spike_in"}],
    "nodes": ["Node1", "Node2", "Node3", "Node4"],
}


def _returns(messages: list[ModelMessage]) -> list[ToolReturnPart]:
    return [
        p for m in messages if isinstance(m, ModelRequest) for p in m.parts if isinstance(p, ToolReturnPart)
    ]


def planner_script(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    done = {p.tool_name: p for p in _returns(messages)}
    if "execute_plan" in done:
        return ModelResponse(parts=[TextPart(f"started {json.dumps(done['execute_plan'].content)}")])
    if "preview_plan" in done:
        return ModelResponse(parts=[ToolCallPart("execute_plan", {"draft": DRAFT})])
    return ModelResponse(parts=[ToolCallPart("preview_plan", {"draft": DRAFT})])


class FakeJobs:
    def __init__(self):
        self.plans = []

    def __call__(self, plan):
        self.plans.append(plan)
        return f"run-{len(self.plans)}"


def _session(model, jobs) -> ChatSession:
    s = ChatSession(keys=Keys(), mode="analysis", start_job=jobs)
    s._models = {"chat": model, "router": None}
    return s


def test_rule_router():
    st = RouterState(pending_plan=True)
    # Korean and English inputs are both supported; Korean examples mean "go ahead", "only up to Node2", etc.
    assert rule_route("진행해", st) == "respond_to_plan"
    assert rule_route("Node2까지만", st) == "respond_to_plan"
    assert rule_route("HLA-B27이 뭐야?", RouterState(), final=True) == "ask_hla"
    assert rule_route("BMExample로 omnibus 분석 돌려줘", RouterState(), final=True) == "request_analysis"
    assert rule_route("진행 상황 알려줘", RouterState(has_runs=True), final=True) == "ask_run_status"


async def test_route_without_model_uses_keywords():
    r = await route("CookHLA로 imputation 해줘", RouterState(), None)
    assert (r.intent, r.by) == ("request_analysis", "keyword")


def test_parse_nodes():
    assert parse_nodes("Node1~3") == ["Node1", "Node2", "Node3"]
    assert parse_nodes("node 2 까지") == ["Node1", "Node2"]
    assert parse_nodes("Node1, Node4 해줘") == ["Node1", "Node4"]
    assert parse_nodes("그냥 해") == []


async def test_planner_approval_flow():
    jobs = FakeJobs()
    s = _session(FunctionModel(planner_script), jobs)
    out = await s.send("BMExample로 HLA 분석 데모 해줘")
    assert [r.kind for r in out] == ["approval"]
    assert "Node1 → Node4" in out[0].content and "Shall I proceed?" in out[0].content
    assert jobs.plans == []  # nothing runs before approval
    out = await s.approve()
    assert jobs.plans and jobs.plans[0].nodes == ["Node1", "Node2", "Node3", "Node4"]
    assert jobs.plans[0].studies[0].synthetic_phenotype.mode == "spike_in"
    assert any(r.kind == "status" and r.data["run_id"] == "run-1" for r in out)
    assert s.pending is None


async def test_planner_approval_with_node_override():
    jobs = FakeJobs()
    s = _session(FunctionModel(planner_script), jobs)
    await s.send("BMExample 분석")
    await s.approve(nodes=["Node1", "Node2"])
    assert jobs.plans[0].nodes == ["Node1", "Node2"]


async def test_rule_based_planner_without_llm():
    jobs = FakeJobs()
    s = ChatSession(keys=Keys(), mode="auto", start_job=jobs)
    s._models = {"chat": None, "router": None}
    out = await s.send("BMExample Node1~2 분석해줘")
    assert out[0].kind == "approval" and out[0].data["nodes"] == ["Node1", "Node2"]
    out = await s.send("Node3까지")  # edit while pending
    assert out[0].kind == "approval" and out[0].data["nodes"] == ["Node1", "Node2", "Node3"]
    out = await s.send("진행")
    assert out[0].kind == "status" and jobs.plans[0].nodes == ["Node1", "Node2", "Node3"]


class FakeKB:
    def query(self, text, k):
        return [
            Hit(
                "abc:3:0",
                "CookHLA imputes HLA alleles with accuracy above 0.9 in Europeans.",
                "paper.pdf",
                3,
                "HLA imputation review",
                "10.1007/x",
                0.82,
            )
        ]


async def test_expert_citations_validated():
    calls = {"n": 0}

    def script(messages, info):
        if not _returns(messages):
            return ModelResponse(parts=[ToolCallPart("search_knowledge", {"query": "CookHLA accuracy"})])
        calls["n"] += 1
        if calls["n"] == 1:
            return ModelResponse(parts=[TextPart("Accuracy is high [K1][K7].")])  # K7 was never retrieved
        return ModelResponse(parts=[TextPart("Accuracy is high in Europeans [K1].")])

    deps = expert_mod.ExpertDeps(kb=FakeKB())
    ans, _ = await expert_mod.answer("How accurate is CookHLA?", FunctionModel(script), deps)
    assert calls["n"] == 2
    assert "[K1]" in ans and "[K7]" not in ans
    assert "HLA imputation review, p.3" in ans and "https://doi.org/10.1007/x" in ans


async def test_reporter_rejects_unsupported_numbers():
    facts = {
        "goal": "g",
        "synthetic": False,
        "warnings": [],
        "studies": {
            "S": {
                "steps": {
                    "Node2": {
                        "status": "ok",
                        "metrics": {"top_marker": "AA_DRB1_96", "top_p": 3.24e-10, "n_sig_bonferroni": 591},
                    }
                }
            }
        },
    }
    seen = {"n": 0}

    def script(messages, info):
        seen["n"] += 1
        if seen["n"] == 1:
            return ModelResponse(parts=[TextPart("AA_DRB1_96 has P = 1.2e-11 and 600 markers pass.")])
        return ModelResponse(parts=[TextPart("AA_DRB1_96 has P = 3.24e-10; 591 markers pass Bonferroni.")])

    text = await narrate(facts, FunctionModel(script))
    assert seen["n"] == 2 and "3.24e-10" in text

    def always_bad(messages, info):
        return ModelResponse(parts=[TextPart("P = 0.0042")])

    assert await narrate(facts, FunctionModel(always_bad)) is None


async def test_router_hands_off_when_jev_is_unsure():
    from pydantic_ai.models.decision import UnsureRoute
    from pydantic_ai.models.fallback import FallbackModel

    def jev(messages, info):
        raise UnsureRoute("jev-latest", "ask_hla", {"ask_hla": 0.55, "request_analysis": 0.45}, 0.8)

    def llm(messages, info):
        tool = info.output_tools[0]
        return ModelResponse(
            parts=[ToolCallPart(tool.name, {"intent": "request_analysis"})], model_name="gemini-test"
        )

    r = await route(
        "WTCCC RA 데이터로 fine-mapping",
        RouterState(),
        FallbackModel(
            FunctionModel(jev, model_name="jev-latest"), FunctionModel(llm, model_name="gemini-test")
        ),
    )
    assert (r.intent, r.by) == ("request_analysis", "llm")
