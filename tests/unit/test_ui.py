"""Streamlit AppTest: the GUI runs without API keys and the approval card starts a (fake) job."""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from hlagent import paths
from tests.conftest import needs_resources

APP = str(paths.project_root() / "src" / "hlagent" / "ui" / "app.py")


@pytest.fixture
def fake_jobs(monkeypatch):
    started = []

    def start(plan):
        started.append(plan)
        return f"fake-run-{len(started)}"

    monkeypatch.setattr("hlagent.jobs.start", start)
    monkeypatch.setattr(
        "hlagent.jobs.status",
        lambda run_dir: {
            "state": "running",
            "progress": {"done": 1, "total": 7},
            "current": {"title": "Data intake & QC"},
        },
    )
    return started


def test_app_renders_without_keys():
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert at.title[0].value == "HLAgent"


@needs_resources
def test_rule_based_plan_and_approval(fake_jobs):
    at = AppTest.from_file(APP, default_timeout=120).run()
    # Korean request ("analyse BMExample, Node1 to Node2"): Korean input must keep working
    at.chat_input[0].set_value("BMExample Node1~2 분석해줘").run()
    assert not at.exception
    assert any("Node1 → Node2" in m.value for m in at.markdown)
    at.button(key="approve_1").click().run()
    assert not at.exception
    assert len(fake_jobs) == 1 and fake_jobs[0].nodes == ["Node1", "Node2"]
    assert any("fake-run-1" in i.value for i in at.info)
