import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from hlagent.fixtures import create_demo
from hlagent.models import AnalysisIntent, AnalysisOptions, PlanApproval
from hlagent.planning import assess, build_plan
from hlagent.workflow import Workflow


def demo_plan(store, settings):
    demo = create_demo(store, settings.home)
    plan = build_plan(demo["project"]["id"], AnalysisIntent.model_validate(demo["intent"]),
                      store.datasets(demo["project"]["id"]), AnalysisOptions(), settings)
    store.put_plan(plan)
    return plan


def test_approval_exact_hash_and_concurrent_idempotency(store, settings):
    plan = demo_plan(store, settings)
    with pytest.raises(ValueError, match="changed"):
        store.approve(PlanApproval(plan_id=plan.id, plan_hash="wrong", revision=plan.revision))
    approval = PlanApproval(plan_id=plan.id, plan_hash=plan.plan_hash, revision=plan.revision)
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = list(pool.map(lambda _: store.approve(approval), range(8)))
    assert len({j.id for j in jobs}) == 1
    assert len(store.jobs()) == 1


def test_langgraph_restart_and_approval(store, settings):
    plan = demo_plan(store, settings)
    workflow = Workflow(settings, store)
    state = workflow.start(plan.project_id, plan.intent, plan.options)
    assert not store.jobs()
    assert state["pending"][0]["kind"] == "approval"
    thread = state["conversation_id"]
    workflow.close()
    workflow = Workflow(settings, store)
    pending = workflow.snapshot(thread)["pending"][0]
    result = workflow.resume(plan.project_id, thread, {k: pending[k] for k in ("plan_id", "plan_hash", "revision")})
    assert result["finished"]
    assert store.job(result["state"]["job_id"]).state == "queued"
    workflow.close()


def test_questions_do_not_add_unnecessary_phasing(store, settings):
    plan = demo_plan(store, settings)
    assert "phase" not in [s.id for s in plan.steps]
    assert "impute" not in [s.id for s in plan.steps]
    intent = plan.intent.model_copy(update={"phenotype_id": None, "phenotype_type": None})
    qs = assess(intent, store.datasets(plan.project_id))
    assert "phenotype_id" in {q.field for q in qs}
    assert len(qs) <= 3


def test_plan_json_has_no_credentials(store, settings):
    plan = demo_plan(store, settings)
    value = json.loads(plan.model_dump_json())
    assert "api_key" not in value
    assert plan.plan_hash == plan.plan_hash
