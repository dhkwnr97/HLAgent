from __future__ import annotations

import secrets
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from hlagent import __version__
from hlagent.adapters import tool_versions
from hlagent.agents import (
    ExtractedIntent,
    explain_with_evidence,
    extract,
    probe_provider,
    probe_text_provider,
)
from hlagent.data import inspect_dataset
from hlagent.fixtures import create_demo
from hlagent.knowledge import (
    KnowledgeIndex,
    pubmed_search,
    scholarly_search,
    start_index_watcher,
    tavily_search,
)
from hlagent.models import (
    AnalysisIntent,
    AnalysisOptions,
    Contract,
    Evidence,
    PlanApproval,
    ProviderConfig,
    uid,
)
from hlagent.planning import CAPABILITIES, build_plan
from hlagent.secrets import SecretVault, api_token
from hlagent.settings import Settings
from hlagent.storage import Store
from hlagent.workflow import Workflow


class Registration(Contract):
    path: str
    label: str = ""
    kind: str | None = None
    genome_build: str | None = None
    ancestry: str | None = None
    resolution: str | None = None
    imgt_release: str | None = None
    metadata: dict = Field(default_factory=dict)


class PlanRequest(Contract):
    intent: AnalysisIntent
    options: AnalysisOptions = Field(default_factory=AnalysisOptions)


class ChatRequest(Contract):
    message: str
    dataset_ids: list[str] = Field(default_factory=list)


class ProviderRequest(Contract):
    config: ProviderConfig
    api_key: str = ""
    remember: bool = False
    passphrase: str = ""


def create_app(settings: Settings | None = None, watch: bool = True) -> FastAPI:
    settings = (settings or Settings()).initialize()
    store, vault = Store(settings.db_path), SecretVault(settings.home)
    workflow = Workflow(settings, store)
    index = KnowledgeIndex(settings.home / "knowledge", settings.knowledge_inbox, settings.embedding_model)
    token, stop = api_token(settings.home), threading.Event()

    @asynccontextmanager
    async def lifespan(app):
        if watch:
            start_index_watcher(index, stop)
        yield
        stop.set()
        vault.clear()
        workflow.close()

    app = FastAPI(title="HLAgent", version=__version__, lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])
    app.state.settings, app.state.store, app.state.vault, app.state.workflow = settings, store, vault, workflow

    def authenticate(x_hlagent_token: Annotated[str | None, Header()] = None):
        if x_hlagent_token is None or not secrets.compare_digest(x_hlagent_token, token):
            raise HTTPException(401, "Local application token required")

    auth = [Depends(authenticate)]

    @app.exception_handler(ValueError)
    async def bad_input(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @app.exception_handler(KeyError)
    async def not_found(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=404)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        # Never reflect submitted credentials in validation responses.
        return JSONResponse({"detail": [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]}
                                         for e in exc.errors()]}, status_code=422)

    @app.get("/health")
    def health():
        return {"status": "ok", "version": __version__}

    @app.get("/capabilities", dependencies=auth)
    def capabilities():
        return CAPABILITIES

    @app.get("/projects", dependencies=auth)
    def projects():
        return store.projects()

    @app.post("/projects", dependencies=auth)
    def project(body: dict):
        return store.create_project(str(body.get("label", "HLA project")))

    @app.post("/demo", dependencies=auth)
    def demo():
        return create_demo(store, settings.home)

    @app.get("/projects/{project_id}/datasets", dependencies=auth)
    def datasets(project_id: str):
        store.require_project(project_id)
        return store.datasets(project_id)

    @app.post("/projects/{project_id}/datasets", dependencies=auth)
    def register(project_id: str, body: Registration):
        store.require_project(project_id)
        params = body.model_dump()
        params["value"] = params.pop("path")
        dataset = inspect_dataset(project_id, **params)
        store.put_dataset(dataset)
        return dataset

    @app.post("/projects/{project_id}/uploads", dependencies=auth)
    async def upload(project_id: str, files: Annotated[list[UploadFile], File()]):
        store.require_project(project_id)
        directory = settings.home / "projects" / project_id / "uploads" / uid()
        directory.mkdir(parents=True)
        paths = []
        used = set()
        for file in files:
            name = Path((file.filename or "input").replace("\\", "/")).name
            if name in ("", ".", "..") or name in used:
                raise ValueError("Use distinct valid filenames within an upload")
            used.add(name)
            path = directory / name
            total = 0
            with path.open("xb") as handle:
                while chunk := await file.read(1024 * 1024):
                    total += len(chunk)
                    if total > 2 * 1024**3:
                        path.unlink(missing_ok=True)
                        raise ValueError("For files above 2 GB use local path registration")
                    handle.write(chunk)
            paths.append(str(path))
        return {"paths": paths}

    @app.post("/projects/{project_id}/plans", dependencies=auth)
    def plans(project_id: str, body: PlanRequest):
        plan = build_plan(project_id, body.intent, store.datasets(project_id), body.options, settings)
        try:
            plan = store.plan(plan.id)
        except KeyError:
            store.put_plan(plan)
        return {"plan": plan.model_dump(mode="json"), "plan_hash": plan.plan_hash}

    @app.get("/plans/{plan_id}", dependencies=auth)
    def plan(plan_id: str):
        plan = store.plan(plan_id)
        return {"plan": plan.model_dump(mode="json"), "plan_hash": plan.plan_hash}

    @app.post("/plans/{plan_id}/approve", dependencies=auth)
    def approve(plan_id: str, body: PlanApproval):
        if plan_id != body.plan_id:
            raise ValueError("Plan identity mismatch")
        return store.approve(body)

    def remember(project_id, result):
        store.set_config("active_conversation:" + project_id, result["conversation_id"])
        return result

    @app.post("/projects/{project_id}/conversations", dependencies=auth)
    def conversations(project_id: str, body: PlanRequest):
        store.require_project(project_id)
        return remember(project_id, workflow.start(project_id, body.intent, body.options))

    @app.get("/projects/{project_id}/conversation", dependencies=auth)
    def conversation(project_id: str):
        identifier = store.config("active_conversation:" + project_id)
        return workflow.snapshot(identifier) if identifier else None

    @app.post("/projects/{project_id}/conversations/{conversation_id}/resume", dependencies=auth)
    def resume_conversation(project_id: str, conversation_id: str, body: dict):
        return workflow.resume(project_id, conversation_id, body)

    @app.post("/projects/{project_id}/chat", dependencies=auth)
    def chat(project_id: str, body: ChatRequest):
        store.require_project(project_id)
        config = store.config("provider")
        if not config:
            raise ValueError("LLM을 설정에서 활성화하거나 구조화된 분석 양식을 사용해주세요.")
        provider = ProviderConfig.model_validate(config)
        data = store.datasets(project_id)
        import re

        from hlagent.data import resolve_path
        # Only explicit user-message paths are considered; retrieved documents never register files.
        mentioned = re.findall(r'["\']([A-Za-z]:[\\/][^"\']+|/(?:mnt|home|root)/[^"\']+)["\']', body.message)
        mentioned += re.findall(r'(?<![\w])([A-Za-z]:[\\/][^\s"\'<>|]+)', body.message)
        inferred_ids = []
        for value in list(dict.fromkeys(mentioned))[:3]:
            path = resolve_path(value.rstrip(".,"))
            if not path.is_file() and not Path(str(path) + ".bed").is_file():
                continue
            if path.suffix.lower() in (".pdf", ".docx", ".md", ".txt"):
                continue
            registered = next((d for d in data if any(f.path == str(path) for f in d.files)), None)
            if registered is None:
                try:
                    registered = inspect_dataset(project_id, str(path))
                    store.put_dataset(registered)
                    data.append(registered)
                except ValueError:
                    continue
            if registered.kind not in ("phenotype", "reference", "sequence"):
                inferred_ids.append(registered.id)
        if inferred_ids and not body.dataset_ids:
            body = body.model_copy(update={"dataset_ids": inferred_ids})
        try:
            result = extract(body.message, data, provider, vault) if provider.validated else ExtractedIntent(
                route="expert", explanation="Structured planning disabled for this provider",
                unsupported_reason="이 모델은 구조화 출력 검사를 통과하지 않아 문헌 검색만 제공합니다. 분석 양식은 사용할 수 있습니다.")
        except Exception:
            raise HTTPException(502, "LLM connection/structured-output check failed. Review Settings; existing jobs are unaffected.")
        store.event(project_id, "user_message", {"text": body.message})
        if result.route == "analysis" and not result.unsupported_reason:
            import re
            if result.action in ("cancel", "resume", "status"):
                jobs = store.jobs(project_id)
                states = {"cancel": {"queued", "running"}, "resume": {"failed", "cancelled"},
                          "status": {"queued", "running", "failed", "cancelled", "succeeded"}}[result.action]
                candidates = [j for j in jobs if j.state in states]
                if result.action == "status" or len(candidates) != 1:
                    return {"route": "analysis", "message": "결과 탭에서 작업을 선택해주세요.", "jobs": candidates}
                explicit = re.search(r"취소|중단|\bcancel\b|\bstop\b", body.message, re.I) if result.action == "cancel" else re.search(r"재개|이어|\bresume\b|\bretry\b|\brecover\b", body.message, re.I)
                if not explicit:
                    return {"route": "analysis", "message": "결과 탭의 취소·재개 버튼에서 작업을 지정해주세요."}
                job = store.cancel(candidates[0].id) if result.action == "cancel" else store.resume(candidates[0].id)
                return {"route": "analysis", "message": "작업 요청을 반영했습니다.", "job": job}
            active = store.config("active_conversation:" + project_id)
            previous = workflow.snapshot(active) if active else None
            if result.action == "revise" and previous and previous["pending"] and previous["pending"][0]["kind"] == "approval":
                answers = {}
                if result.goals:
                    answers["goals"] = result.goals
                if result.phenotype_column:
                    answers["phenotype_column"] = result.phenotype_column
                if result.phenotype_type:
                    answers["phenotype_type"] = result.phenotype_type
                if result.covariates:
                    answers["covariates"] = result.covariates
                if body.dataset_ids:
                    answers["dataset_ids"] = body.dataset_ids
                return {"route": "analysis", "conversation": workflow.resume(project_id, active, {"action": "revise", "answers": answers})}
            intent = AnalysisIntent(question=body.message, goals=result.goals, dataset_ids=body.dataset_ids,
                                    phenotype_column=result.phenotype_column, phenotype_type=result.phenotype_type,
                                    covariates=result.covariates)
            return {"route": "analysis", "conversation": remember(project_id, workflow.start(project_id, intent, AnalysisOptions()))}
        evidence = index.search(body.message)
        if len(evidence) < 3 and store.config("allow_web", settings.allow_web):
            try:
                evidence += scholarly_search(body.message)
            except (httpx.HTTPError, ValueError):
                try:
                    evidence += pubmed_search(body.message)
                except (httpx.HTTPError, ValueError):
                    pass
            if len(evidence) < 3 and vault.get("tavily"):
                try:
                    evidence += tavily_search(body.message, vault.get("tavily"))
                except (httpx.HTTPError, ValueError):
                    pass
        try:
            answer = explain_with_evidence(body.message, evidence, provider, vault, result.unsupported_reason)
        except Exception:
            answer = explain_with_evidence(body.message, evidence, None, vault, result.unsupported_reason)
        store.event(project_id, "expert_answer", answer.model_dump())
        return {"route": "expert", "answer": answer}

    @app.get("/projects/{project_id}/jobs", dependencies=auth)
    def jobs(project_id: str):
        return store.jobs(project_id)

    @app.get("/jobs/{job_id}", dependencies=auth)
    def job(job_id: str):
        return store.job(job_id)

    @app.post("/jobs/{job_id}/cancel", dependencies=auth)
    def cancel(job_id: str):
        return store.cancel(job_id)

    @app.post("/jobs/{job_id}/resume", dependencies=auth)
    def resume_job(job_id: str):
        return store.resume(job_id)

    @app.get("/jobs/{job_id}/artifacts", dependencies=auth)
    def artifacts(job_id: str):
        store.job(job_id)
        return store.artifacts(job_id)

    @app.post("/jobs/{job_id}/explanation", dependencies=auth)
    def explain_results(job_id: str):
        import json

        import pandas as pd

        from hlagent.data import sha256
        job = store.job(job_id)
        plan = store.plan(job.plan_id)
        evidence = []
        allowed = {"association.tsv", "conditional.tsv", "omnibus.tsv", "meta.tsv", "imputation_quality.tsv", "haplotype_frequencies.tsv"}
        for item in store.artifacts(job_id):
            if item.label not in allowed:
                continue
            path = Path(item.path)
            if sha256(path) != item.sha256:
                raise ValueError("Result changed after validation")
            frame = pd.read_csv(path, sep="\t")
            if "p" in frame:
                frame = frame.sort_values("p")
            text = frame.head(10).to_json(orient="records", force_ascii=False)
            evidence.append(Evidence(id=item.id, title=item.label, locator="validated result rows; see artifact checksum",
                                     text=text, source_hash=item.sha256))
        evidence.append(Evidence(id="approved-methods", title="Approved analysis definitions", locator=plan.plan_hash,
                                  text=json.dumps({"goals": plan.intent.goals, "phenotype_type": plan.intent.phenotype_type,
                                                   "options": plan.options.model_dump(), "limitations": plan.warnings})))
        config = store.config("provider")
        provider = ProviderConfig.model_validate(config) if config else None
        try:
            answer = explain_with_evidence("검증된 HLA 결과의 효과 방향, 다중검정 및 분석 한계를 한국어로 설명해주세요.", evidence, provider, vault)
        except Exception:
            answer = explain_with_evidence("결과 요약", evidence, None, vault)
        store.event(job.project_id, "result_explanation", {"job_id": job_id, **answer.model_dump()})
        return answer

    @app.get("/jobs/{job_id}/artifacts/{artifact_id}", dependencies=auth)
    def artifact(job_id: str, artifact_id: str):
        item = next((a for a in store.artifacts(job_id) if a.id == artifact_id), None)
        if item is None:
            raise KeyError("Artifact not found")
        path = Path(item.path).resolve()
        if not path.is_relative_to(settings.home / "projects") or not path.is_file():
            raise ValueError("Artifact path is unavailable")
        from hlagent.data import sha256
        if sha256(path) != item.sha256:
            raise ValueError("Artifact changed after validation")
        return FileResponse(path, filename=path.name, media_type=item.media_type)

    @app.get("/projects/{project_id}/events", dependencies=auth)
    def events(project_id: str, after: int = 0):
        return store.events(project_id, after)

    @app.get("/settings", dependencies=auth)
    def get_settings():
        return {"provider": store.config("provider"), "allow_web": store.config("allow_web", settings.allow_web),
                "home": str(settings.home), "inbox": str(settings.knowledge_inbox), "vault_exists": vault.path.exists(),
                "embedding": settings.embedding_model or "lexical-hashing-2048 (semantic model not configured)"}

    @app.post("/settings/provider", dependencies=auth)
    def set_provider(body: ProviderRequest):
        config = body.config.model_copy(update={"validated": False, "validated_at": None})
        if body.api_key:
            vault.set(config.provider, body.api_key)
        try:
            config = probe_provider(config, vault)
        except Exception:
            try:
                config = probe_text_provider(config, vault)
            except Exception:
                raise HTTPException(422, "Provider connection failed; no model was activated.")
        if body.remember:
            vault.save(body.passphrase)
        store.set_config("provider", config.model_dump())
        return config

    @app.post("/settings/tavily", dependencies=auth)
    def configure_search(body: dict):
        vault.set("tavily", str(body.get("api_key", "")))
        return {"configured": bool(vault.get("tavily"))}

    @app.post("/settings/unlock", dependencies=auth)
    def unlock(body: dict):
        vault.unlock(str(body.get("passphrase", "")))
        return {"unlocked": True}

    @app.post("/settings/web", dependencies=auth)
    def web_setting(body: dict):
        if not isinstance(body.get("enabled"), bool):
            raise ValueError("enabled must be a boolean")
        store.set_config("allow_web", body["enabled"])
        return {"enabled": body["enabled"]}

    @app.get("/settings/ollama", dependencies=auth)
    def ollama_models():
        config = store.config("provider") or {}
        base = config.get("base_url") if config.get("provider") == "ollama" else None
        response = httpx.get((base or "http://127.0.0.1:11434").rstrip("/").removesuffix("/v1") + "/api/tags", timeout=5)
        response.raise_for_status()
        return [m["name"] for m in response.json().get("models", [])]

    @app.get("/tools", dependencies=auth)
    def tools_status():
        return tool_versions(settings)

    @app.post("/knowledge/index", dependencies=auth)
    def index_documents():
        return index.sync()

    @app.get("/knowledge", dependencies=auth)
    def knowledge_status():
        return index.status()

    @app.get("/knowledge/search", dependencies=auth)
    def search(q: str):
        return index.search(q)

    return app


def app_factory():
    return create_app()
