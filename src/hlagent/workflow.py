from __future__ import annotations

import sqlite3
import threading
from typing import TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from hlagent.models import AnalysisIntent, AnalysisOptions, PlanApproval, uid
from hlagent.planning import apply_answers, assess, build_plan
from hlagent.settings import Settings
from hlagent.storage import Store


class State(TypedDict, total=False):
    project_id: str
    intent: dict
    options: dict
    questions: list[dict]
    plan_id: str
    job_id: str
    error: str | None
    revision: int
    changes: dict


class Workflow:
    def __init__(self, settings: Settings, store: Store):
        self.settings, self.store = settings, store
        self.connection = sqlite3.connect(settings.home / "checkpoints.sqlite3", check_same_thread=False)
        self.checkpointer = SqliteSaver(self.connection)
        self.lock = threading.RLock()
        graph = StateGraph(State)
        graph.add_node("assess", self._assess)
        graph.add_node("ask", self._ask)
        graph.add_node("plan", self._plan)
        graph.add_node("approve", self._approve)
        graph.add_edge(START, "assess")
        graph.add_conditional_edges("assess", lambda s: END if s.get("error") else "ask" if s["questions"] else "plan")
        graph.add_edge("ask", "assess")
        graph.add_conditional_edges("plan", lambda s: END if s.get("error") else "approve")
        graph.add_conditional_edges("approve", lambda s: "assess" if not s.get("job_id") else END)
        self.graph = graph.compile(checkpointer=self.checkpointer)

    def _assess(self, state: State):
        try:
            intent = AnalysisIntent.model_validate(state["intent"])
            if intent.unsupported_reason:
                return {"error": intent.unsupported_reason, "questions": []}
            questions = assess(intent, self.store.datasets(state["project_id"]))
            return {"questions": [q.model_dump() for q in questions], "error": None}
        except ValueError as exc:
            return {"error": str(exc), "questions": []}

    def _ask(self, state: State):
        answers = interrupt({"kind": "questions", "questions": state["questions"]})
        intent = apply_answers(AnalysisIntent.model_validate(state["intent"]), answers)
        return {"intent": intent.model_dump(mode="json"), "questions": []}

    def _plan(self, state: State):
        try:
            plan = build_plan(state["project_id"], AnalysisIntent.model_validate(state["intent"]),
                              self.store.datasets(state["project_id"]), AnalysisOptions.model_validate(state["options"]),
                              self.settings, revision=state.get("revision", 1))
            try:
                plan = self.store.plan(plan.id)
            except KeyError:
                self.store.put_plan(plan)
            return {"plan_id": plan.id, "error": None}
        except (ValueError, OSError) as exc:
            return {"error": str(exc)}

    def _approve(self, state: State):
        plan = self.store.plan(state["plan_id"])
        reply = interrupt({"kind": "approval", "plan_id": plan.id, "plan_hash": plan.plan_hash,
                           "revision": plan.revision, "steps": [s.id for s in plan.steps], "warnings": plan.warnings})
        if reply.get("action") == "revise":
            intent = apply_answers(AnalysisIntent.model_validate(state["intent"]), reply.get("answers", {}))
            options = AnalysisOptions.model_validate({**state["options"], **reply.get("options", {})})
            updated = intent.model_dump(mode="json")
            changes = {k: {"before": state["intent"].get(k), "after": v}
                       for k, v in updated.items() if v != state["intent"].get(k)}
            changes.update({"options." + k: {"before": state["options"].get(k), "after": v}
                            for k, v in options.model_dump().items() if v != state["options"].get(k)})
            return {"intent": updated, "plan_id": "", "job_id": "", "options": options.model_dump(),
                    "revision": plan.revision + 1, "changes": changes}
        approval = PlanApproval.model_validate({k: reply[k] for k in ("plan_id", "plan_hash", "revision")})
        if approval.plan_id != state["plan_id"]:
            raise ValueError("Approval targets a different conversation plan")
        job = self.store.approve(approval)
        return {"job_id": job.id}

    def start(self, project_id: str, intent: AnalysisIntent, options: AnalysisOptions) -> dict:
        thread_id = uid()
        self.store.set_config("conversation:" + thread_id, project_id)
        with self.lock:
            self.graph.invoke({"project_id": project_id, "intent": intent.model_dump(mode="json"),
                               "options": options.model_dump(), "questions": [], "error": None},
                              {"configurable": {"thread_id": thread_id}})
            return self.snapshot(thread_id)

    def resume(self, project_id: str, thread_id: str, reply: dict) -> dict:
        if self.store.config("conversation:" + thread_id) != project_id:
            raise ValueError("Conversation does not belong to this project")
        with self.lock:
            config = {"configurable": {"thread_id": thread_id}}
            state = self.graph.get_state(config)
            if not state.next:
                raise ValueError("This conversation has ended; create a revised request")
            self.graph.invoke(Command(resume=reply), config)
            return self.snapshot(thread_id)

    def snapshot(self, thread_id: str):
        state = self.graph.get_state({"configurable": {"thread_id": thread_id}})
        interrupts = [item.value for task in state.tasks for item in task.interrupts]
        return {"conversation_id": thread_id, "state": dict(state.values), "pending": interrupts,
                "finished": not bool(state.next)}

    def close(self):
        self.connection.close()
