from pathlib import Path
from urllib.parse import urlsplit

import httpx
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from hlagent.api import create_app


def test_gui_demo_keeps_project_and_reaches_approval(settings, monkeypatch):
    monkeypatch.setenv("HLAGENT_HOME", str(settings.home))
    app = create_app(settings, watch=False)
    with TestClient(app) as client:
        def request(method, url, **kwargs):
            kwargs.pop("timeout", None)
            return client.request(method, urlsplit(url).path, **kwargs)
        monkeypatch.setattr(httpx, "request", request)
        path = Path(__file__).parents[1] / "src/hlagent/ui.py"
        ui = AppTest.from_file(path).run(timeout=30)
        assert not ui.exception
        next(b for b in ui.button if b.label == "합성 예제로 시작").click().run(timeout=30)
        project = ui.session_state["project_id"]
        assert not ui.exception
        next(b for b in ui.button if b.label == "예제의 검증 가능한 분석 계획 열기").click().run(timeout=30)
        assert not ui.exception
        assert ui.session_state["project_id"] == project
        assert any(b.label == "이 계획으로 실행" for b in ui.button)
        assert not app.state.store.jobs()
