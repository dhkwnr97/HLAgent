"""The planning benchmark scores plans on the resolved execution graph and separates good from bad planners."""

from __future__ import annotations

import json

from hlagent import paths
from hlagent.eval.planning import expected_drafts, run_suite, score, steps_of, summarize
from tests.conftest import needs_resources

pytestmark = needs_resources
TASKS = paths.project_root() / "benchmarks" / "planning" / "tasks.json"


def _task(tid: str) -> dict:
    return next(t for t in json.loads(TASKS.read_text())["planning"] if t["id"] == tid)


def test_equivalent_plans_resolve_to_the_same_graph():
    t = _task("assoc-en-1")  # Node2 and Node1+Node2 are the same execution
    a, b = (steps_of(d) for d in expected_drafts(t))
    assert a == b and ("Node1", "WTCCC_RA") in a and ("StageP", "WTCCC_RA") not in a
    t = _task("imp-en-1")  # no HLA types: Stage I is added by the engine
    assert ("StageI", "GenotypeExample") in steps_of(expected_drafts(t)[0])


def test_score_flags_over_execution_and_wrong_parameters():
    t = _task("omni-en-2")
    draft = expected_drafts(t)[0].model_dump(mode="json")
    good = {"behavior": "propose", "draft": draft, "preview_before_execute": True}
    assert score(t, good)["success"]
    bad = json.loads(json.dumps(good))
    bad["draft"]["omnibus_conditions"] = []
    s = score(t, bad)
    assert not s["success"] and not s["params_ok"] and s["steps_ok"]
    over = json.loads(json.dumps(good))
    over["draft"]["nodes"] = ["Node1", "Node2", "Node3", "Node4"]
    s = score(t, over)
    assert not s["steps_ok"] and "Node2:WTCCC_RA" in s["extra_steps"]
    assert not score(t, {**good, "preview_before_execute": False})["success"]
    assert score(_task("clar-en-1"), {"behavior": "clarify"})["success"]


async def test_oracle_beats_naive_baseline(tmp_path):
    raw = await run_suite(TASKS, ["oracle", "naive"], 1, tmp_path, concurrency=4, include_routing=False)
    rows = {(r["model"], r["step"]): r for r in summarize(raw)["rows"]}
    assert rows[("oracle", "ALL planning")]["rate"] == 1.0
    assert rows[("oracle", "ALL planning")]["preview_before_execute"] == 1.0
    assert rows[("naive", "ALL planning")]["rate"] < 0.6
    assert rows[("naive", "clarification")]["rate"] == 0.0
