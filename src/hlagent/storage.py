from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from hlagent.models import (
    AnalysisPlan,
    ArtifactManifest,
    DatasetManifest,
    JobRecord,
    PlanApproval,
    now,
    uid,
)


class Store:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as con:
            con.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, label TEXT NOT NULL, created TEXT);
                CREATE TABLE IF NOT EXISTS datasets(id TEXT PRIMARY KEY, project_id TEXT NOT NULL, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS plans(id TEXT PRIMARY KEY, project_id TEXT NOT NULL, hash TEXT NOT NULL, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS approvals(plan_id TEXT PRIMARY KEY, hash TEXT NOT NULL, created TEXT);
                CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, project_id TEXT NOT NULL, plan_id TEXT UNIQUE NOT NULL,
                    state TEXT NOT NULL, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS steps(job_id TEXT, step_id TEXT, fingerprint TEXT, body TEXT NOT NULL,
                    PRIMARY KEY(job_id,step_id));
                CREATE TABLE IF NOT EXISTS artifacts(id TEXT PRIMARY KEY, job_id TEXT NOT NULL, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT, kind TEXT, body TEXT, created TEXT);
                CREATE TABLE IF NOT EXISTS config(key TEXT PRIMARY KEY, body TEXT NOT NULL);
            """)

    @contextmanager
    def connection(self):
        con = sqlite3.connect(self.path, timeout=30)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA busy_timeout=30000")
        try:
            yield con
            con.commit()
        except BaseException:
            con.rollback()
            raise
        finally:
            con.close()

    def create_project(self, label: str) -> dict:
        project = {"id": uid(), "label": label.strip() or "HLA project", "created": now()}
        with self.connection() as con:
            con.execute("INSERT INTO projects VALUES (:id,:label,:created)", project)
        return project

    def projects(self) -> list[dict]:
        with self.connection() as con:
            return [dict(r) for r in con.execute("SELECT * FROM projects ORDER BY created DESC")]

    def require_project(self, project_id: str):
        with self.connection() as con:
            if not con.execute("SELECT 1 FROM projects WHERE id=?", (project_id,)).fetchone():
                raise KeyError("Project not found")

    def put_dataset(self, dataset: DatasetManifest):
        self.require_project(dataset.project_id)
        with self.connection() as con:
            con.execute("INSERT INTO datasets VALUES (?,?,?)",
                        (dataset.id, dataset.project_id, dataset.model_dump_json()))

    def datasets(self, project_id: str) -> list[DatasetManifest]:
        with self.connection() as con:
            return [DatasetManifest.model_validate_json(r[0]) for r in
                    con.execute("SELECT body FROM datasets WHERE project_id=?", (project_id,))]

    def put_plan(self, plan: AnalysisPlan):
        self.require_project(plan.project_id)
        with self.connection() as con:
            con.execute("INSERT INTO plans VALUES (?,?,?,?)",
                        (plan.id, plan.project_id, plan.plan_hash, plan.model_dump_json()))

    def plan(self, plan_id: str) -> AnalysisPlan:
        with self.connection() as con:
            r = con.execute("SELECT body FROM plans WHERE id=?", (plan_id,)).fetchone()
        if r is None:
            raise KeyError("Plan not found")
        return AnalysisPlan.model_validate_json(r[0])

    def approve(self, approval: PlanApproval) -> JobRecord:
        with self.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT body,hash FROM plans WHERE id=?", (approval.plan_id,)).fetchone()
            if row is None:
                raise KeyError("Plan not found")
            plan = AnalysisPlan.model_validate_json(row["body"])
            if approval.plan_hash != row["hash"] or approval.plan_hash != plan.plan_hash or approval.revision != plan.revision:
                raise ValueError("The plan changed. Review and approve its current version.")
            existing = con.execute("SELECT body FROM jobs WHERE plan_id=?", (plan.id,)).fetchone()
            if existing:
                return JobRecord.model_validate_json(existing[0])
            con.execute("INSERT INTO approvals VALUES (?,?,?)", (plan.id, plan.plan_hash, now()))
            job = JobRecord(project_id=plan.project_id, plan_id=plan.id, plan_hash=plan.plan_hash)
            con.execute("INSERT INTO jobs VALUES (?,?,?,?,?)",
                        (job.id, job.project_id, job.plan_id, job.state, job.model_dump_json()))
        return job

    def job(self, job_id: str) -> JobRecord:
        with self.connection() as con:
            r = con.execute("SELECT body FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not r:
            raise KeyError("Job not found")
        return JobRecord.model_validate_json(r[0])

    def jobs(self, project_id: str | None = None) -> list[JobRecord]:
        with self.connection() as con:
            query = "SELECT body FROM jobs" + (" WHERE project_id=?" if project_id else "")
            return [JobRecord.model_validate_json(r[0]) for r in
                    con.execute(query, (project_id,) if project_id else ())]

    def update_job(self, job_id: str, **changes) -> JobRecord:
        with self.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT body FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                raise KeyError("Job not found")
            data = json.loads(row[0])
            data.update(changes, updated_at=now())
            job = JobRecord.model_validate(data)
            con.execute("UPDATE jobs SET state=?,body=? WHERE id=?", (job.state, job.model_dump_json(), job.id))
            return job

    def claim_job(self) -> JobRecord | None:
        with self.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT body FROM jobs WHERE state='queued' ORDER BY rowid LIMIT 1").fetchone()
            if not row:
                return None
            job = JobRecord.model_validate_json(row[0])
            job.state, job.updated_at, job.attempt = "running", now(), job.attempt + 1
            con.execute("UPDATE jobs SET state=?,body=? WHERE id=?", (job.state, job.model_dump_json(), job.id))
            return job

    def cancel(self, job_id: str):
        job = self.job(job_id)
        if job.state == "queued":
            return self.update_job(job_id, state="cancelled")
        if job.state == "running":
            return self.update_job(job_id, state="cancel_requested")
        return job

    def resume(self, job_id: str):
        job = self.job(job_id)
        if job.state not in ("failed", "cancelled"):
            raise ValueError("Only failed or cancelled jobs can resume")
        return self.update_job(job_id, state="queued", error=None)

    def event(self, project_id: str, kind: str, body: dict):
        with self.connection() as con:
            con.execute("INSERT INTO events(project_id,kind,body,created) VALUES (?,?,?,?)",
                        (project_id, kind, json.dumps(body, ensure_ascii=False), now()))

    def events(self, project_id: str, after: int = 0):
        with self.connection() as con:
            return [{**dict(r), "body": json.loads(r["body"])} for r in con.execute(
                "SELECT * FROM events WHERE project_id=? AND seq>? ORDER BY seq LIMIT 300", (project_id, after))]

    def put_step(self, job_id: str, step_id: str, fingerprint: str, body: dict):
        with self.connection() as con:
            con.execute("INSERT OR REPLACE INTO steps VALUES (?,?,?,?)",
                        (job_id, step_id, fingerprint, json.dumps(body, allow_nan=False)))

    def step(self, job_id: str, step_id: str) -> dict | None:
        with self.connection() as con:
            r = con.execute("SELECT fingerprint,body FROM steps WHERE job_id=? AND step_id=?", (job_id, step_id)).fetchone()
        return {"fingerprint": r[0], **json.loads(r[1])} if r else None

    def put_artifact(self, artifact: ArtifactManifest):
        with self.connection() as con:
            con.execute("INSERT OR REPLACE INTO artifacts VALUES (?,?,?)",
                        (artifact.id, artifact.job_id, artifact.model_dump_json()))

    def artifacts(self, job_id: str) -> list[ArtifactManifest]:
        with self.connection() as con:
            return [ArtifactManifest.model_validate_json(r[0]) for r in
                    con.execute("SELECT body FROM artifacts WHERE job_id=?", (job_id,))]

    def config(self, key: str, default=None):
        with self.connection() as con:
            r = con.execute("SELECT body FROM config WHERE key=?", (key,)).fetchone()
        return json.loads(r[0]) if r else default

    def set_config(self, key: str, value):
        with self.connection() as con:
            con.execute("INSERT OR REPLACE INTO config VALUES (?,?)", (key, json.dumps(value)))
