import pytest
from fastapi.testclient import TestClient

from hlagent.api import create_app
from hlagent.knowledge import KnowledgeIndex
from hlagent.secrets import SecretVault, api_token


def test_api_requires_local_token_and_rejects_command_surface(settings):
    app = create_app(settings, watch=False)
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/projects").status_code == 401
        client.headers["X-HLAgent-Token"] = api_token(settings.home)
        project = client.post("/projects", json={"label": "test"}).json()
        assert client.get(f"/projects/{project['id']}/datasets").json() == []
        assert client.post("/execute", json={"command": "echo unsafe"}).status_code == 404
        assert client.post("/plans/missing/approve", json={"plan_id": "missing", "plan_hash": "x", "revision": 1}).status_code == 404


def test_vault_roundtrip_and_wrong_password(settings):
    vault = SecretVault(settings.home)
    vault.set("google", "test-secret-never-plain")
    vault.save("a long test passphrase")
    assert "test-secret-never-plain" not in vault.path.read_text()
    vault.clear()
    with pytest.raises(ValueError, match="passphrase"):
        vault.unlock("a wrong test passphrase")
    vault.unlock("a long test passphrase")
    assert vault.get("google") == "test-secret-never-plain"


def test_incremental_retrieval_citations_and_deletion(settings):
    index = KnowledgeIndex(settings.home / "knowledge", settings.knowledge_inbox)
    paper = settings.knowledge_inbox / "reference.md"
    paper.write_text("HLA-DRB1*04:01 is an example allele. This source is a synthetic retrieval fixture.\n")
    index.sync()
    found = index.search("DRB1*04:01")
    assert found and found[0].source_hash
    old = found[0].id
    paper.write_text("A*02:01 is a different synthetic example.\n")
    index.sync()
    assert all(e.id != old for e in index.search("DRB1*04:01"))
    paper.unlink()
    index.sync()
    assert not index.search("A*02:01")
