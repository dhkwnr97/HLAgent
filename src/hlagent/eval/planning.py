"""Per-step evaluation of how accurately a language model plans each analysis step.

In HLAgent the LLM never computes: it turns a request into a validated plan, which the deterministic
engine executes after the user approves it. Analytical outputs are therefore identical for every LLM
that produces the same plan, and the LLM-dependent quality is the plan itself. For each task and model
this module records:

- behaviour: 'propose' (an execute_plan call awaiting approval) or 'clarify' (a question, no plan);
- plan correctness on the *resolved* execution graph (datasets x steps the engine would run), so that
  equivalent requests such as "Node2" and "Node1+Node2" are scored alike;
- phenotype handling and parameter extraction;
- protocol adherence (preview_plan called before execute_plan);
- retries (schema-invalid tool calls rejected by validation), latency and token use.

The approval gate is structural: execute_plan requires approval, so no analysis can start during an
evaluation run (start_job raises if it is ever called).
"""

from __future__ import annotations

import asyncio
import json
import math
import statistics
import time
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic_ai import DeferredToolRequests
from pydantic_ai.messages import ModelRequest, ModelResponse, RetryPromptPart, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from hlagent.agents.planner import PlanDraft, PlannerDeps, StudyDraft, build_plan, planner_agent
from hlagent.agents.router import RouterState, router_agent
from hlagent.pipeline.dag import resolve

PLAN_LEVEL = ("hla_resolution", "omnibus_conditions")
STUDY_LEVEL = ("reference_population", "spike_allele", "spike_odds_ratio")


# ----------------------------------------------------------------------------------------------- scoring
def expected_drafts(task: dict) -> list[PlanDraft]:
    out = []
    for nodes in task["accept_nodes"]:
        studies = []
        for s in task["studies"]:
            sd: dict[str, Any] = {"dataset_id": s["dataset_id"], "phenotype": s["phenotype"][0]}
            for k in STUDY_LEVEL:
                if k in task["params"]:
                    sd[k] = task["params"][k]
            studies.append(StudyDraft(**sd))
        plan_params = {k: task["params"][k] for k in PLAN_LEVEL if k in task["params"]}
        out.append(PlanDraft(goal=task["id"], studies=studies, nodes=nodes, **plan_params))
    return out


def steps_of(draft: PlanDraft) -> frozenset[tuple[str, str | None]]:
    return frozenset((t.step, t.study_id) for t in resolve(build_plan(draft)).tasks)


def _norm_allele(a: str) -> str:
    return a.upper().replace("HLA-", "").strip()


def _norm_cond(c: str) -> str:
    return c.upper().replace("HLA-", "").replace(" ", "")


def score(task: dict, rec: dict) -> dict:
    """Add correctness fields to a raw record."""
    s: dict[str, Any] = {"behavior_ok": rec["behavior"] == task["behavior"]}
    if task["behavior"] == "clarify":
        s["success"] = s["behavior_ok"]
        return s
    if rec["behavior"] != "propose" or rec.get("draft") is None:
        s.update(
            {
                "success": False,
                "steps_ok": False,
                "datasets_ok": False,
                "phenotype_ok": False,
                "params_ok": False,
            }
        )
        return s
    draft = PlanDraft.model_validate(rec["draft"])
    try:
        got = steps_of(draft)
    except Exception as e:  # noqa: BLE001 - an unbuildable plan (unknown dataset id, ...) is a wrong plan
        s.update(
            {
                "success": False,
                "steps_ok": False,
                "datasets_ok": False,
                "phenotype_ok": False,
                "params_ok": False,
                "plan_error": str(e)[:200],
            }
        )
        return s
    exp = [steps_of(d) for d in expected_drafts(task)]
    s["steps_ok"] = got in exp
    best = min(exp, key=lambda e: len(e ^ got))
    s["extra_steps"] = sorted(f"{a}:{b}" for a, b in got - best)
    s["missing_steps"] = sorted(f"{a}:{b}" for a, b in best - got)
    want = {x["dataset_id"] for x in task["studies"]}
    s["datasets_ok"] = {x.dataset_id for x in draft.studies} == want
    by_id = {x.dataset_id: x for x in draft.studies}
    s["phenotype_ok"] = all(
        x["dataset_id"] in by_id and by_id[x["dataset_id"]].phenotype in x["phenotype"]
        for x in task["studies"]
    )
    ok = True
    for k, v in task["params"].items():
        if k == "hla_resolution":
            ok &= draft.hla_resolution == v
        elif k == "omnibus_conditions":
            ok &= {_norm_cond(c) for c in draft.omnibus_conditions} == {_norm_cond(c) for c in v}
        elif k == "reference_population":
            ok &= any(x.reference_population == v for x in draft.studies)
        elif k == "spike_allele":
            ok &= any(
                _norm_allele(x.spike_allele) == _norm_allele(v)
                for x in draft.studies
                if x.phenotype == "synthetic_spike_in"
            )
        elif k == "spike_odds_ratio":
            ok &= any(
                abs(x.spike_odds_ratio - float(v)) < 1e-6
                for x in draft.studies
                if x.phenotype == "synthetic_spike_in"
            )
    s["params_ok"] = bool(ok)
    s["success"] = bool(
        s["behavior_ok"]
        and s["steps_ok"]
        and s["datasets_ok"]
        and s["phenotype_ok"]
        and s["params_ok"]
        and rec.get("preview_before_execute")
    )
    return s


# ----------------------------------------------------------------------------------------------- running
def _never_start(plan) -> str:
    raise RuntimeError("approval gate violated: a job was started without user approval")


def _trace(messages: list) -> tuple[list[str], int]:
    calls = [
        p.tool_name
        for m in messages
        if isinstance(m, ModelResponse)
        for p in m.parts
        if isinstance(p, ToolCallPart)
    ]
    retries = sum(
        isinstance(p, RetryPromptPart) for m in messages if isinstance(m, ModelRequest) for p in m.parts
    )
    return calls, retries


async def run_planning_task(task: dict, model, timeout: float = 240.0) -> dict:
    rec: dict[str, Any] = {"task_id": task["id"], "step": task["step"], "lang": task["lang"]}
    t0 = time.perf_counter()
    try:
        r = await asyncio.wait_for(
            planner_agent.run(task["prompt"], model=model, deps=PlannerDeps(start_job=_never_start)), timeout
        )
    except Exception as e:  # noqa: BLE001 - every failure is a scored outcome
        rec.update(
            {
                "behavior": "error",
                "error": f"{type(e).__name__}: {e}"[:400],
                "latency_s": round(time.perf_counter() - t0, 3),
            }
        )
        return rec
    rec["latency_s"] = round(time.perf_counter() - t0, 3)
    calls, retries = _trace(r.all_messages())
    u = r.usage() if callable(r.usage) else r.usage  # property in pydantic-ai 2.x
    rec.update(
        {
            "tool_calls": calls,
            "n_retries": retries,
            "input_tokens": u.input_tokens,
            "output_tokens": u.output_tokens,
            "requests": u.requests,
        }
    )
    if isinstance(r.output, DeferredToolRequests):
        ex = [c for c in r.output.approvals if c.tool_name == "execute_plan"]
        if ex:
            rec["behavior"] = "propose"
            rec["draft"] = ex[0].args_as_dict().get("draft")
        else:
            rec["behavior"] = "other_deferred"
    else:
        rec["behavior"] = "clarify"
        rec["reply"] = str(r.output)[:600]
    first_prev = calls.index("preview_plan") if "preview_plan" in calls else None
    first_exec = calls.index("execute_plan") if "execute_plan" in calls else None
    if rec["behavior"] == "propose":  # protocol adherence is defined for proposals only
        rec["preview_before_execute"] = bool(
            first_exec is not None and first_prev is not None and first_prev < first_exec
        )
    return rec


async def run_routing_item(item: dict, model, timeout: float = 120.0) -> dict:
    rec: dict[str, Any] = {"task_id": item["id"], "step": "routing", "expected": item["intent"]}
    t0 = time.perf_counter()
    try:
        r = await asyncio.wait_for(router_agent.run(item["text"], model=model, deps=RouterState()), timeout)
        rec.update({"predicted": r.output.intent, "success": r.output.intent == item["intent"]})
    except Exception as e:  # noqa: BLE001
        rec.update({"predicted": None, "success": False, "error": f"{type(e).__name__}: {e}"[:300]})
    rec["latency_s"] = round(time.perf_counter() - t0, 3)
    return rec


# ----------------------------------------------------------------------------------------------- reference models
def oracle_model(task: dict) -> FunctionModel:
    """Scripted model that behaves exactly as the task expects (validates the harness end to end)."""

    def fn(messages: list, info: AgentInfo) -> ModelResponse:
        done = [
            p.tool_name
            for m in messages
            if isinstance(m, ModelRequest)
            for p in m.parts
            if getattr(p, "part_kind", "") == "tool-return"
        ]
        if task["behavior"] == "clarify":
            return ModelResponse(
                parts=[TextPart("Which dataset should I use? Please name one of the listed datasets.")]
            )
        d = expected_drafts(task)[0].model_dump(mode="json")
        if "preview_plan" not in done:
            return ModelResponse(parts=[ToolCallPart("preview_plan", {"draft": d})])
        return ModelResponse(parts=[ToolCallPart("execute_plan", {"draft": d})])

    return FunctionModel(fn, model_name="oracle")


def naive_model(task: dict) -> FunctionModel:
    """Baseline that ignores the request and always proposes WTCCC_RA Node1-Node4."""
    d = {
        "goal": "default",
        "studies": [{"dataset_id": "WTCCC_RA"}],
        "nodes": ["Node1", "Node2", "Node3", "Node4"],
    }

    def fn(messages: list, info: AgentInfo) -> ModelResponse:
        done = [
            p.tool_name
            for m in messages
            if isinstance(m, ModelRequest)
            for p in m.parts
            if getattr(p, "part_kind", "") == "tool-return"
        ]
        if "preview_plan" not in done:
            return ModelResponse(parts=[ToolCallPart("preview_plan", {"draft": d})])
        return ModelResponse(parts=[ToolCallPart("execute_plan", {"draft": d})])

    return FunctionModel(fn, model_name="naive")


def model_factory(spec: str) -> Callable[[dict], Any]:
    """Return task -> model. 'oracle' and 'naive' are offline references; others are provider:model ids."""
    if spec == "oracle":
        return oracle_model
    if spec == "naive":
        return naive_model
    from hlagent.llm.registry import Keys, build_model

    m = build_model(spec, Keys.resolve())
    return lambda task: m


# ----------------------------------------------------------------------------------------------- driver
async def run_suite(
    tasks_file: Path,
    models: list[str],
    repeats: int,
    out_dir: Path,
    concurrency: int = 2,
    include_routing: bool = True,
    only_steps: set[str] | None = None,
) -> Path:
    suite = json.loads(tasks_file.read_text())
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = out_dir / "raw.jsonl"
    done = set()
    if raw.exists():
        for line in raw.read_text().splitlines():
            if line.strip():
                x = json.loads(line)
                done.add((x["model"], x["task_id"], x["rep"]))
    sem = asyncio.Semaphore(concurrency)
    lock = asyncio.Lock()
    by_id = {t["id"]: t for t in suite["planning"]}

    async def one(spec: str, make, kind: str, item: dict, rep: int) -> None:
        if (spec, item["id"], rep) in done:
            return
        async with sem:
            model = make(item) if kind == "planning" else make({"behavior": "clarify"})
            rec = await (
                run_planning_task(item, model) if kind == "planning" else run_routing_item(item, model)
            )
        if kind == "planning":
            rec.update(score(by_id[item["id"]], rec))
        rec.update({"model": spec, "rep": rep, "kind": kind})
        async with lock:
            with raw.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    jobs = []
    for spec in models:
        make = model_factory(spec)
        for rep in range(1, repeats + 1):
            for t in suite["planning"]:
                if only_steps is None or t["step"] in only_steps:
                    jobs.append(one(spec, make, "planning", t, rep))
            if include_routing and spec not in ("oracle", "naive"):
                for it in suite["routing"]:
                    jobs.append(one(spec, make, "routing", it, rep))
    await asyncio.gather(*jobs)
    return raw


# ----------------------------------------------------------------------------------------------- summary
def wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, c - h), min(1.0, c + h)


def summarize(raw: Path) -> dict[str, Any]:
    recs = [json.loads(x) for x in raw.read_text().splitlines() if x.strip()]
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in recs:
        groups[(r["model"], r["step"])].append(r)
        if r.get("kind") == "planning":
            groups[(r["model"], "ALL planning")].append(r)
    rows = []
    for (model, step), rs in sorted(groups.items()):
        k = sum(bool(r.get("success")) for r in rs)
        lo, hi = wilson(k, len(rs))
        lat = [r["latency_s"] for r in rs if r.get("latency_s") is not None]
        q = (
            statistics.quantiles(lat, n=4, method="inclusive")
            if len(lat) >= 2
            else [math.nan, math.nan, math.nan]
        )
        row = {
            "model": model,
            "step": step,
            "n": len(rs),
            "success": k,
            "rate": k / len(rs) if rs else math.nan,
            "ci_low": lo,
            "ci_high": hi,
            "latency_median_s": statistics.median(lat) if lat else math.nan,
            "latency_q1_s": q[0],
            "latency_q3_s": q[2],
        }
        pl = [r for r in rs if r.get("kind") == "planning"]
        if pl:

            def rate(key: str, pl: list[dict] = pl) -> float:
                xs = [bool(r.get(key)) for r in pl if key in r]
                return sum(xs) / len(xs) if xs else math.nan

            row.update(
                {
                    "behavior_ok": rate("behavior_ok"),
                    "steps_ok": rate("steps_ok"),
                    "params_ok": rate("params_ok"),
                    "phenotype_ok": rate("phenotype_ok"),
                    "preview_before_execute": rate("preview_before_execute"),
                    "mean_retries": statistics.fmean([r.get("n_retries", 0) for r in pl]),
                    "errors": sum(r.get("behavior") == "error" for r in pl),
                    "mean_input_tokens": statistics.fmean([r.get("input_tokens") or 0 for r in pl]),
                    "mean_output_tokens": statistics.fmean([r.get("output_tokens") or 0 for r in pl]),
                }
            )
        rows.append(row)
    return {"rows": rows, "n_records": len(recs)}


def write_summary(raw: Path, out_dir: Path) -> Path:
    import csv

    s = summarize(raw)
    keys = sorted({k for r in s["rows"] for k in r}, key=lambda k: (k not in ("model", "step", "n"), k))
    path = out_dir / "summary.csv"
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(s["rows"])
    lines = [
        "| Model | Step | n | Success | 95% CI (Wilson) | Plan graph correct | Params | Preview first | "
        "Median latency (s) |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in s["rows"]:

        def pct(x: float) -> str:
            return "-" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{100 * x:.1f}%"

        lines.append(
            f"| {r['model']} | {r['step']} | {r['n']} | {r['success']}/{r['n']} ({pct(r['rate'])}) | "
            f"{pct(r['ci_low'])}–{pct(r['ci_high'])} | {pct(r.get('steps_ok', math.nan))} | "
            f"{pct(r.get('params_ok', math.nan))} | {pct(r.get('preview_before_execute', math.nan))} | "
            f"{r['latency_median_s']:.2f} |"
        )
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n")
    return path
