"""Streamlit pages: Chat, Results, Data, Knowledge base, Settings."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from hlagent import datasets, jobs, paths
from hlagent.config import get_settings
from hlagent.ui import state

NODE_LABELS = {
    "Node1": "Node1 HLA marker panel",
    "Node2": "Node2 association test",
    "Node3": "Node3 conditional analysis",
    "Node4": "Node4 omnibus test",
    "Node5": "Node5 meta-analysis",
}
STATE_ICON = {
    "done": "✅",
    "running": "⏳",
    "queued": "🕒",
    "failed": "❌",
    "blocked": "⛔",
    "cancelled": "🚫",
}


# ----------------------------------------------------------------------------------------------- chat
def _approval_card(i: int, msg: dict, active: bool) -> None:
    st.markdown(msg["content"])
    if not active:
        st.caption("This plan has been handled.")
        return
    nodes = st.multiselect(
        "Nodes to run (editable)",
        list(NODE_LABELS),
        default=msg["data"]["nodes"],
        format_func=NODE_LABELS.get,
        key=f"nodes_{i}",
    )
    c1, c2 = st.columns(2)
    if c1.button(
        "Approve and run", type="primary", key=f"approve_{i}", disabled=not nodes, use_container_width=True
    ):
        with st.spinner("Starting the analysis..."):
            replies = state.bridge().run(state.session().approve(nodes))
        msg["data"]["resolved"] = True
        state.add_replies(replies)
        st.rerun()
    if c2.button("Cancel", key=f"deny_{i}", use_container_width=True):
        replies = state.bridge().run(state.session().deny("cancelled from the approval card"))
        msg["data"]["resolved"] = True
        state.add_replies(replies)
        st.rerun()


@st.fragment(run_every="3s")
def _live_runs() -> None:
    s = state.session()
    active = [r for r in s.runs if jobs.status(paths.runs_dir() / r).get("state") in jobs.ACTIVE]
    for rid in s.runs[-3:]:
        st_ = jobs.status(paths.runs_dir() / rid)
        pr = st_.get("progress") or {}
        total = max(pr.get("total") or 0, 1)
        cur = (st_.get("current") or {}).get("title") or ""
        st.progress(
            1.0 if st_.get("state") == "done" else min((pr.get("done") or 0) / total, 1.0),
            text=f"{STATE_ICON.get(st_.get('state'), '')} {rid} · {st_.get('state')} · {cur}",
        )
        if st_.get("state") == "failed" and st_.get("message"):
            st.error(st_["message"])
    if not active and s.runs:
        st.caption("Results are available on the Results page.")


def chat_page() -> None:
    st.title("HLAgent")
    st.caption("HLA expert Q&A and HLA analysis (CookHLA → BEAGLE → HATK Node1–5 → report)")
    with st.sidebar:
        st.radio(
            "Mode",
            ["auto", "expert", "analysis"],
            key="mode",
            horizontal=True,
            format_func={"auto": "Auto", "expert": "HLA expert", "analysis": "Analysis"}.get,
        )
        st.selectbox(
            "LLM",
            ["google", "openai", "anthropic"],
            key="provider",
            index=["google", "openai", "anthropic"].index(get_settings().default_provider),
        )
        k = state.keys()
        st.caption("Keys: " + " ".join(f"{n}{'✓' if k.has(n) else '✗'}" for n in state.KEY_FIELDS))
        if st.button("Reset conversation"):
            for key in ("messages", "chat_session", "chat_sig"):
                st.session_state.pop(key, None)
            st.rerun()
    s = state.session()
    msgs = state.transcript()
    last_approval = max((i for i, m in enumerate(msgs) if m["kind"] == "approval"), default=-1)
    for i, m in enumerate(msgs):
        with st.chat_message(m["role"]):
            if m["kind"] == "approval":
                _approval_card(
                    i,
                    m,
                    active=(i == last_approval and s.pending is not None and not m["data"].get("resolved")),
                )
            elif m["kind"] == "error":
                st.error(m["content"])
            elif m["kind"] == "status":
                st.info(m["content"])
            else:
                st.markdown(m["content"])
    if s.runs:
        with st.container(border=True):
            _live_runs()
    if not msgs:
        st.markdown(
            "Examples: *How is HLA-DRB1\\*15:01 linked to multiple sclerosis?* · *Run an HLA analysis on BMExample* · "
            "*Meta-analyse BMExample and GenotypeExample*"
        )
    if text := st.chat_input("Ask a question or request an analysis"):
        state.add_user(text)
        with st.spinner("Thinking..."):
            replies = state.bridge().run(s.send(text))
        state.add_replies(replies)
        st.rerun()


# ----------------------------------------------------------------------------------------------- results
def _zip_dir(d: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(d.rglob("*")):
            if f.is_file() and f.stat().st_size < 200 * 1024 * 1024:
                z.write(f, f.relative_to(d.parent))
    return buf.getvalue()


def results_page() -> None:
    st.title("Results")
    runs = jobs.list_runs(100)
    if not runs:
        st.info("No analysis has been run yet.")
        return
    labels = {r["run_id"]: f"{STATE_ICON.get(r['state'], '')} {r['run_id']} — {r['goal'][:60]}" for r in runs}
    rid = st.selectbox("Run", list(labels), format_func=labels.get)
    run_dir = paths.runs_dir() / rid
    stt = jobs.status(run_dir)
    pr = stt.get("progress") or {}
    c1, c2, c3 = st.columns(3)
    c1.metric("State", stt.get("state", "?"))
    c2.metric("Progress", f"{pr.get('done', 0)}/{pr.get('total', 0)}")
    if stt.get("state") in jobs.ACTIVE and c3.button("Cancel run"):
        jobs.cancel(rid)
        st.rerun()
    if stt.get("message"):
        (st.error if stt.get("state") == "failed" else st.info)(stt["message"])
    tab_rep, tab_fig, tab_tab, tab_files = st.tabs(["Report", "Figures", "Tables", "Files"])
    rep = run_dir / "report" / "report.html"
    with tab_rep:
        if rep.exists():
            components.html(rep.read_text(), height=900, scrolling=True)
            k = state.keys()
            if k.providers() and st.button("Add an LLM-written summary (numbers checked against facts.json)"):
                from hlagent.agents.reporter import add_narrative

                with st.spinner("Writing the summary..."):
                    ok = state.bridge().run(add_narrative(run_dir, state.session().chat(), "English"))
                st.success("Summary added.") if ok else st.warning(
                    "No summary passed the number check; the existing summary was kept."
                )
                st.rerun()
        else:
            st.caption("The report appears when Stage R has finished.")
    outs = jobs.outputs(rid)
    with tab_fig:
        for o in [o for o in outs if o["kind"] == "plot" and Path(o["path"]).exists()]:
            st.image(o["path"], caption=f"{o['step']} · {o['study_id'] or 'all'} · {o['name']}")
    with tab_tab:
        for o in [o for o in outs if o["kind"] in ("table",) and Path(o["path"]).exists()]:
            st.markdown(f"**{o['step']} · {o['study_id'] or 'all'} · {o['name']}**")
            st.dataframe(pd.read_csv(o["path"], sep="\t").head(200), use_container_width=True)
    with tab_files:
        st.dataframe(
            pd.DataFrame(outs)[["step", "study_id", "name", "kind", "path"]] if outs else pd.DataFrame(),
            use_container_width=True,
        )
        if (run_dir / "report").exists():
            st.download_button("Report folder (zip)", _zip_dir(run_dir / "report"), f"{rid}_report.zip")
        st.download_button(
            "Plan, parameters and environment (for reproduction)",
            json.dumps(
                {
                    "plan": json.loads((run_dir / "plan.json").read_text()),
                    "env": json.loads((run_dir / "env.lock.json").read_text())
                    if (run_dir / "env.lock.json").exists()
                    else {},
                },
                indent=1,
            ),
            f"{rid}_reproduce.json",
        )


# ----------------------------------------------------------------------------------------------- data
def data_page() -> None:
    st.title("Data")
    st.caption(
        "Datasets available for analysis. Uploaded files are stored in workspace/<name>/; language models only see file names and summary statistics."
    )
    rows = [d.summary() for d in datasets.catalog()]
    st.dataframe(pd.DataFrame(rows), use_container_width=True)
    with st.form("upload", clear_on_submit=True):
        name = st.text_input("Dataset name (letters, digits, _ . + -)", placeholder="MyCohort_hg19")
        files = st.file_uploader(
            "PLINK .bed/.bim/.fam, HLA .chped/.hped, phenotype .phe (FID IID <name>...)",
            accept_multiple_files=True,
        )
        if st.form_submit_button("Upload") and name and files:
            import re

            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.+-]{0,63}", name):
                st.error("Names may contain only letters, digits and _ . + -")
            else:
                d = paths.ensure_within(paths.workspace_dir() / name, paths.workspace_dir())
                d.mkdir(parents=True, exist_ok=True)
                for f in files:
                    dst = paths.ensure_within(d / Path(f.name).name, d)
                    dst.write_bytes(f.getvalue())
                st.success(f"Saved {len(files)} file(s) to workspace/{name}")
                st.rerun()


# ----------------------------------------------------------------------------------------------- knowledge
def knowledge_page() -> None:
    from hlagent.llm.registry import NoModelAvailable, embedder
    from hlagent.rag.store import KnowledgeBase, ingest_folder

    st.title("Knowledge base")
    s = get_settings()
    try:
        kb = KnowledgeBase(embedder(state.keys(), s), s.embedding_model)
    except NoModelAvailable as e:
        st.warning(str(e))
        return
    c1, c2 = st.columns(2)
    c1.metric("chunks", kb.count())
    c2.metric("embedding", kb.built_with() or s.embedding_model)
    st.write("Documents:", ", ".join(kb.sources()) or "(empty)")
    up = st.file_uploader(
        "Add papers (PDF or Markdown)", type=["pdf", "md", "txt"], accept_multiple_files=True
    )
    rebuild = st.checkbox("Rebuild the whole index (after changing the embedding model)")
    if st.button("Index", type="primary"):
        kd = paths.knowledge_dir()
        kd.mkdir(parents=True, exist_ok=True)
        for f in up or []:
            paths.ensure_within(kd / Path(f.name).name, kd).write_bytes(f.getvalue())
        with st.spinner("Converting PDFs and computing embeddings..."):
            res = ingest_folder(kd, kb, rebuild=rebuild)
        st.json(res)


# ----------------------------------------------------------------------------------------------- settings
def settings_page() -> None:
    from hlagent.doctor import run_checks

    st.title("Settings")
    st.subheader("API keys")
    st.caption(
        "Keys entered here are kept only in this browser session's memory and are never written to files or logs. For permanent settings, use the .env file."
    )
    ov = state.key_overrides()
    k = state.keys()
    with st.form("keys"):
        vals = {}
        for name, label in state.KEY_FIELDS.items():
            vals[name] = st.text_input(
                f"{label} {'(set)' if k.has(name) else ''}", type="password", key=f"key_{name}"
            )
        if st.form_submit_button("Apply"):
            for name, v in vals.items():
                if v.strip():
                    ov[name] = v.strip()
            st.session_state["keys_version"] = st.session_state.get("keys_version", 0) + 1
            st.success("Applied.")
    if ov and st.button("Clear keys entered here"):
        ov.clear()
        st.session_state["keys_version"] = st.session_state.get("keys_version", 0) + 1
        st.rerun()
    st.subheader("Models")
    s = get_settings()
    st.table(
        pd.DataFrame(
            {
                "setting": [
                    "default provider",
                    "google",
                    "google fallback",
                    "openai",
                    "anthropic",
                    "router (Jev)",
                    "embedding",
                ],
                "value": [
                    s.default_provider,
                    s.google_model,
                    s.google_fallback_model,
                    s.openai_model,
                    s.anthropic_model,
                    s.router_jev_model,
                    s.embedding_model,
                ],
            }
        )
    )
    st.subheader("Environment check (doctor)")
    if st.button("Run checks"):
        st.dataframe(pd.DataFrame(run_checks(state.keys())), use_container_width=True)
