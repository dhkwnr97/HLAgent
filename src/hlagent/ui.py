from __future__ import annotations

import json

import httpx
import streamlit as st
import streamlit.components.v1 as components

from hlagent.models import AnalysisIntent, AnalysisOptions, Goal
from hlagent.secrets import api_token
from hlagent.settings import Settings

st.set_page_config(page_title="HLAgent", page_icon="🧬", layout="wide")
settings = Settings().initialize()
BASE = f"http://127.0.0.1:{settings.api_port}"
HEADERS = {"X-HLAgent-Token": api_token(settings.home)}


def call(method, endpoint, **kwargs):
    response = httpx.request(method, BASE + endpoint, headers=HEADERS, timeout=120, **kwargs)
    if not response.is_success:
        try:
            message = response.json().get("detail", response.text)
        except ValueError:
            message = response.text
        raise ValueError(str(message))
    return response.json()


def attempt(method, endpoint, **kwargs):
    try:
        return call(method, endpoint, **kwargs)
    except (ValueError, httpx.HTTPError) as exc:
        st.error(str(exc))
        return None


try:
    projects = call("GET", "/projects")
except (httpx.HTTPError, ValueError):
    st.error("HLAgent 서비스를 연결할 수 없습니다. 실행 바로가기로 앱을 시작해주세요.")
    st.stop()

with st.sidebar:
    st.title("HLAgent")
    st.caption("HLA research workspace · 2.0 alpha")
    if st.button("합성 예제로 시작", use_container_width=True):
        result = attempt("POST", "/demo")
        if result:
            st.session_state["project_id"] = result["project"]["id"]
            st.session_state["project_picker"] = result["project"]["id"]
            st.session_state["demo_intent"] = result["intent"]
            st.rerun()
    with st.form("new_project"):
        label = st.text_input("새 프로젝트 이름")
        if st.form_submit_button("프로젝트 만들기"):
            result = attempt("POST", "/projects", json={"label": label})
            if result:
                st.session_state["project_id"] = result["id"]
                st.session_state["project_picker"] = result["id"]
                st.rerun()
    if projects:
        ids = [p["id"] for p in projects]
        lookup = {p["id"]: p["label"] for p in projects}
        if st.session_state.get("project_picker") not in ids:
            st.session_state["project_picker"] = ids[0]
        project_id = st.selectbox("프로젝트", ids, key="project_picker",
                                  format_func=lambda key: lookup[key] + " · " + key[:6])
        st.session_state["project_id"] = project_id
    else:
        project_id = None
    st.divider()
    st.caption("자료는 이 PC에서 처리됩니다. 연구용 통계 결과는 임상 진단이나 인과관계의 증명이 아닙니다.")

st.title("연구 질문에서 재현 가능한 HLA 분석까지")
st.caption("자료를 등록하고 분석 계획을 확인하면, 화면을 닫아도 승인된 계산은 계속 진행됩니다.")
analysis_tab, data_tab, results_tab, knowledge_tab, settings_tab = st.tabs(["분석", "자료", "결과", "문헌", "설정"])
datasets = call("GET", f"/projects/{project_id}/datasets") if project_id else []
labels = {d["id"]: f"{d['label']} · {d['kind']}" for d in datasets}


def format_dataset(value):
    return labels.get(value, value)


with analysis_tab:
    if not project_id:
        st.info("왼쪽에서 프로젝트를 만들거나 합성 예제를 시작해주세요.")
    else:
        selected = st.multiselect("분석할 자료", [d["id"] for d in datasets if d["kind"] not in ("phenotype", "reference", "sequence")],
                                  format_func=format_dataset, key="chat_datasets_" + project_id)
        message = st.chat_input("예: 이 자료에서 질병과 관련된 HLA와 독립적인 신호를 찾고 싶어요.")
        if message:
            with st.spinner("요청을 확인하고 있습니다…"):
                result = attempt("POST", f"/projects/{project_id}/chat", json={"message": message, "dataset_ids": selected})
                if result:
                    if result.get("message"):
                        st.session_state["chat_notice"] = result["message"]
                    st.rerun()
        if st.session_state.get("chat_notice"):
            st.info(st.session_state.pop("chat_notice"))
        with st.expander("분석 양식으로 시작 · LLM 없이도 사용 가능", expanded=not bool(datasets)):
            with st.form("structured_" + project_id):
                question = st.text_input("연구 질문", value="HLA association analysis")
                goals = st.multiselect("수행할 분석", [g.value for g in Goal], default=["association"])
                st.caption("imputation 추정 · phasing 위상 · association 연관 · conditional 조건부 · omnibus 위치별 검정 · meta 코호트 통합")
                left, right = st.columns(2)
                with left:
                    pheno_id = st.selectbox("표현형 자료", [None] + [d["id"] for d in datasets if d["kind"] == "phenotype"],
                                            format_func=lambda x: format_dataset(x) if x else "질문에 답하며 선택")
                    phenotype = st.text_input("표현형 열 이름")
                    phenotype_type = st.selectbox("표현형 종류", [None, "binary", "continuous"])
                    covariates = st.text_input("공변량 열 이름 · 쉼표로 구분", value="")
                with right:
                    reference = st.selectbox("CookHLA reference", [None] + [d["id"] for d in datasets if d["kind"] == "reference"],
                                             format_func=lambda x: format_dataset(x) if x else "필요하면 나중에 선택")
                    sequence = st.selectbox("아미노산 서열 사전", [None] + [d["id"] for d in datasets if d["kind"] == "sequence"],
                                            format_func=lambda x: format_dataset(x) if x else "없음")
                    scaffold = st.selectbox("HLA phasing에 함께 사용할 SNP 자료 · 선택", [None] + [d["id"] for d in datasets if d["kind"] in ("vcf", "bcf", "plink_bed", "plink_pgen")],
                                           format_func=lambda x: format_dataset(x) if x else "HLA만 사용 · 탐색적 추론")
                    phase_reference = st.selectbox("동일 인코딩의 phased reference VCF · 선택", [None] + [d["id"] for d in datasets if d["kind"] == "vcf" and d["has_phase"]],
                                                   format_func=lambda x: format_dataset(x) if x else "없음")
                    conditions = st.text_input("조건부 분석의 marker/위치 · 쉼표로 구분")
                with st.expander("실행 자원과 QC"):
                    memory = st.slider("분석 메모리 한도 (GB)", 1, 12, 4)
                    threads = st.slider("CPU threads", 1, 12, 4)
                    min_count = st.number_input("최소 allele/residue count", min_value=1, value=20)
                    export_directory = st.text_input("결과 묶음을 복사할 Windows/WSL 폴더 · 선택")
                    confidence = st.text_input("CookHLA 기본 confidence cutoff · 빈 값은 미적용", value="")
                if st.form_submit_button("질문과 계획 준비", type="primary"):
                    try:
                        cutoff = float(confidence) if confidence else None
                        if cutoff is not None and not 0 <= cutoff <= 2:
                            raise ValueError()
                    except ValueError:
                        st.error("Confidence cutoff은 0과 2 사이의 숫자 또는 빈 값이어야 합니다.")
                        st.stop()
                    intent = AnalysisIntent(question=question, goals=goals, dataset_ids=selected,
                        phenotype_id=pheno_id, phenotype_column=phenotype or None, phenotype_type=phenotype_type,
                        covariates=[c.strip() for c in covariates.split(",") if c.strip()],
                        reference_id=reference, sequence_id=sequence,
                        scaffold_id=scaffold, phase_reference_id=phase_reference,
                        conditioning=[c.strip() for c in conditions.split(",") if c.strip()])
                    result = attempt("POST", f"/projects/{project_id}/conversations", json={
                        "intent": intent.model_dump(mode="json"),
                        "options": AnalysisOptions(memory_gb=memory, threads=threads, min_count=min_count,
                            export_directory=export_directory or None,
                            cookhla_confidence_min=cutoff).model_dump()})
                    if result:
                        st.rerun()
        if st.session_state.get("demo_intent") and st.session_state["demo_intent"]["dataset_ids"][0] in labels:
            if st.button("예제의 검증 가능한 분석 계획 열기"):
                result = attempt("POST", f"/projects/{project_id}/conversations", json={"intent": st.session_state["demo_intent"]})
                if result:
                    st.rerun()
        conversation = call("GET", f"/projects/{project_id}/conversation")
        if conversation:
            if conversation["state"].get("error"):
                st.error(conversation["state"]["error"])
            for pending in conversation["pending"]:
                if pending["kind"] == "questions":
                    st.subheader("분석을 준비하기 위해 필요한 정보")
                    with st.form("questions_" + conversation["conversation_id"] + "_" + str(pending)):
                        answers = {}
                        for q in pending["questions"]:
                            st.caption(q["reason"])
                            field = q["field"]
                            if field in ("goals", "dataset_ids", "covariates"):
                                choices = q["options"]
                                answers[field] = st.multiselect(q["prompt"], choices, format_func=format_dataset)
                            elif q["options"]:
                                answers[field] = st.selectbox(q["prompt"], ["모르겠어요"] + q["options"], format_func=format_dataset)
                            else:
                                answers[field] = st.text_input(q["prompt"])
                        if st.form_submit_button("답변 반영", type="primary"):
                            result = attempt("POST", f"/projects/{project_id}/conversations/{conversation['conversation_id']}/resume", json=answers)
                            if result:
                                st.rerun()
                if pending["kind"] == "approval":
                    plan_result = call("GET", "/plans/" + pending["plan_id"])
                    plan = plan_result["plan"]
                    st.subheader("실행할 분석 계획")
                    st.write(plan["intent"]["question"])
                    st.caption(f"계획 버전 {pending['revision']} · {plan['options']['memory_gb']} GB · {plan['options']['threads']} threads")
                    if conversation["state"].get("changes"):
                        st.dataframe([{"변경 항목": k, "이전": str(v["before"]), "변경": str(v["after"])}
                                      for k, v in conversation["state"]["changes"].items()], hide_index=True)
                    st.write("표현형:", plan["intent"].get("phenotype_column") or "해당 없음",
                             "· 보정 변수:", ", ".join(plan["intent"]["covariates"]) or "없음")
                    st.dataframe([{ "단계": s["id"], "선행 단계": ", ".join(s["depends_on"])} for s in plan["steps"]], hide_index=True)
                    for warning in pending["warnings"]:
                        st.info(warning)
                    with st.expander("매개변수·도구·입력과 확인 해시"):
                        st.json(plan)
                        st.code(pending["plan_hash"])
                    left, right = st.columns(2)
                    if left.button("이 계획으로 실행", type="primary", use_container_width=True):
                        result = attempt("POST", f"/projects/{project_id}/conversations/{conversation['conversation_id']}/resume",
                                         json={"plan_id": pending["plan_id"], "plan_hash": pending["plan_hash"], "revision": pending["revision"]})
                        if result:
                            st.rerun()
                    if right.button("수정하기", use_container_width=True):
                        st.session_state["revise_" + pending["plan_id"]] = True
                    if st.session_state.get("revise_" + pending["plan_id"]):
                        with st.form("revise_form_" + pending["plan_id"]):
                            revised_goals = st.multiselect("수정할 분석 목표", [g.value for g in Goal], default=plan["intent"]["goals"])
                            revised_trait = st.text_input("표현형 열", value=plan["intent"]["phenotype_column"] or "")
                            revised_cov = st.text_input("공변량", value=", ".join(plan["intent"]["covariates"]))
                            revised_cond = st.text_input("보정 marker/위치", value=", ".join(plan["intent"]["conditioning"]))
                            revised_mem = st.number_input("메모리 (GB)", 1, 128, plan["options"]["memory_gb"])
                            if st.form_submit_button("변경 내용 반영하고 다시 확인"):
                                result = attempt("POST", f"/projects/{project_id}/conversations/{conversation['conversation_id']}/resume",
                                    json={"action": "revise", "answers": {"goals": revised_goals,
                                        "phenotype_column": revised_trait or None, "covariates": revised_cov,
                                        "conditioning": revised_cond}, "options": {"memory_gb": revised_mem}})
                                if result:
                                    st.rerun()
            if conversation["state"].get("job_id"):
                st.success("분석 작업이 등록되었습니다. 결과 탭에서 진행 상황을 확인하세요.")
        events = call("GET", f"/projects/{project_id}/events")
        for event in events:
            if event["kind"] == "user_message":
                with st.chat_message("user"):
                    st.write(event["body"]["text"])
            elif event["kind"] == "expert_answer":
                with st.chat_message("assistant"):
                    st.write(event["body"]["answer"])
                    for citation in event["body"]["citations"]:
                        with st.expander(citation["title"] + " · " + citation["locator"]):
                            st.write(citation["text"])
                            if citation.get("url"):
                                st.link_button("출처 열기", citation["url"])

with data_tab:
    if project_id:
        st.subheader("로컬 자료 등록")
        st.caption("큰 파일은 경로로 등록하세요. PLINK 파일은 같은 폴더의 BED/BIM/FAM 또는 PGEN/PVAR/PSAM을 함께 검사합니다.")
        uploads = st.file_uploader("파일 업로드", accept_multiple_files=True)
        if uploads and st.button("업로드 파일 저장"):
            files = [("files", (f.name, f.getvalue(), "application/octet-stream")) for f in uploads]
            result = attempt("POST", f"/projects/{project_id}/uploads", files=files)
            if result:
                st.session_state["uploaded_path"] = result["paths"][0]
                st.success("저장했습니다. 아래에서 자료의 종류와 정보를 확인하여 등록하세요.")
        kind = st.selectbox("자료 종류", ["hla", "hla_dosage", "plink_bed", "plink_pgen", "vcf", "bcf", "phenotype", "summary", "reference", "sequence"])
        with st.form("registration_" + kind):
            path = st.text_input("파일 또는 PLINK prefix 경로", value=st.session_state.get("uploaded_path", ""),
                                 placeholder=r"C:\Users\June\Downloads\mydata.bed")
            label = st.text_input("자료 이름")
            cols = st.columns(3)
            build = cols[0].selectbox("Genome build", [None, "GRCh37", "GRCh38", "GRCh36"])
            ancestry = cols[1].text_input("Ancestry")
            resolution = cols[2].text_input("HLA 해상도", placeholder="2-field / G-group / P-group")
            release = st.text_input("IPD-IMGT/HLA release · 서열 사전에 필수")
            metadata_fields = {}
            if kind in ("hla", "hla_dosage", "phenotype", "summary"):
                with st.expander("파일의 열 이름 연결"):
                    st.caption("표준 열 이름과 다를 때만 원본 열 이름을 입력하세요. 자료는 로컬에서 처리됩니다.")
                    targets = {"hla": ["FID", "IID", "locus", "allele1", "allele2"],
                               "hla_dosage": ["FID", "IID", "locus", "allele", "dosage"],
                               "phenotype": ["FID", "IID"],
                               "summary": ["marker", "beta", "se", "effect_allele", "other_allele"]}[kind]
                    column_map = {}
                    for target in targets:
                        original = st.text_input(target + "에 해당하는 원본 열", key="map_" + kind + target)
                        if original:
                            column_map[original] = target
                    metadata_fields["mapping"] = {"columns": column_map}
            if kind == "hla":
                typing_tool = st.selectbox("Typing 결과 형식", ["standard", "optitype", "hlahd", "xhla", "hibag", "axiom"])
                sample_id = st.text_input("단일 표본 결과의 sample ID · 필요한 형식에만 입력")
                if typing_tool != "standard":
                    metadata_fields["tool"] = typing_tool
                if sample_id:
                    metadata_fields["mapping"]["sample_id"] = sample_id
            if kind in ("hla", "plink_bed", "plink_pgen", "vcf", "bcf"):
                with st.expander("SNP와 HLA를 함께 phasing할 때의 좌표"):
                    st.caption("동일 genome build의 HLA anchor 좌표를 명시하세요. 선택한 locus만 입력합니다.")
                    anchors = {}
                    for locus in ("A", "B", "C", "DPA1", "DPB1", "DQA1", "DQB1", "DRB1"):
                        value = st.text_input(locus + " anchor 위치", key=kind + "_anchor_" + locus)
                        if value.isdigit():
                            anchors[locus] = int(value)
                    if anchors:
                        metadata_fields["phase_positions"] = anchors
                if kind == "vcf":
                    codebook = st.text_input("Phased reference의 HLA codebook 파일 경로 · 해당할 때만 입력")
                    if codebook:
                        metadata_fields["codebook_path"] = codebook
            if kind == "hla_dosage":
                metadata_fields["dosage_source"] = st.text_input("Dosage를 생성한 도구·버전과 정의")
            if kind == "reference":
                metadata_fields["genetic_map"] = st.text_input("호환 genetic map 경로 · 선택")
                metadata_fields["error_rate"] = st.text_input("호환 average error rate 경로 · 선택")
            if kind == "sequence":
                sequence_format = st.selectbox("서열 사전 형식", ["allele / position / residue TSV", "HATK AA dictionary"])
                if sequence_format == "HATK AA dictionary":
                    metadata_fields.update(format="hatk_dictionary_aa", position_system="alignment_column_1based")
                    st.caption("위치는 정렬된 서열의 열 번호로 표시됩니다. 성숙 단백질의 아미노산 번호로 추측하지 않습니다.")
            if kind == "summary":
                st.write("코호트의 분석 정의")
                metadata_fields["design"] = {
                    "cohort": st.text_input("코호트 이름"), "phenotype": st.text_input("표현형 이름"),
                    "phenotype_type": st.selectbox("표현형 종류", ["binary", "continuous"]),
                    "effect_scale": st.selectbox("효과 척도", ["log_odds", "mean_difference"]),
                    "unit": st.text_input("표현형 단위", value="log_odds"),
                    "genome_build": build or "HLA", "resolution": resolution, "imgt_release": release,
                    "conditioning": [x.strip() for x in st.text_input("조건부 보정 marker 목록").split(",") if x.strip()],
                    "covariates": [x.strip() for x in st.text_input("보정 공변량 목록").split(",") if x.strip()],
                    "strand": "forward"}
            with st.expander("형식별 열 매핑과 연구 설계"):
                st.caption('HLA 열 매핑 예: {"mapping":{"columns":{"sample":"IID","gene":"locus","a1":"allele1","a2":"allele2"}}}')
                st.caption('Typing 도구: tool = optitype / hlahd / xhla / hibag / axiom. 파일 형식과 sample_id를 명시하세요.')
                metadata = st.text_area("Metadata JSON", value="{}")
            if st.form_submit_button("검사 후 등록", type="primary"):
                try:
                    result = attempt("POST", f"/projects/{project_id}/datasets", json={"path": path, "label": label,
                        "kind": kind, "genome_build": build, "ancestry": ancestry or None, "resolution": resolution or None,
                        "imgt_release": release or None, "metadata": {**metadata_fields, **json.loads(metadata)}})
                    if result:
                        st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        st.dataframe([{"이름": d["label"], "형식": d["kind"], "표본 수": d["sample_count"], "Build": d["genome_build"],
                       "Dosage": d["has_dosage"], "Phase": d["has_phase"]} for d in datasets], hide_index=True)

with results_tab:
    if project_id:
        @st.fragment(run_every="3s")
        def jobs_view():
            jobs = call("GET", f"/projects/{project_id}/jobs")
            if not jobs:
                st.info("아직 실행한 분석이 없습니다.")
            for job in reversed(jobs):
                st.subheader(f"{job['state']} · {job['id'][:8]}")
                st.write("현재 단계:", job["current_step"] or "실행 대기")
                if job["error"]:
                    st.error(job["error"])
                if job["state"] in ("queued", "running") and st.button("이 작업 취소", key="cancel_" + job["id"]):
                    attempt("POST", f"/jobs/{job['id']}/cancel")
                if job["state"] in ("failed", "cancelled") and st.button("검증된 단계부터 재개", key="resume_" + job["id"]):
                    attempt("POST", f"/jobs/{job['id']}/resume")
                if job["state"] == "succeeded" and st.button("검증된 결과 해석", key="explain_" + job["id"]):
                    result = attempt("POST", f"/jobs/{job['id']}/explanation")
                    if result:
                        st.session_state["explanation_" + job["id"]] = result
                if st.session_state.get("explanation_" + job["id"]):
                    result = st.session_state["explanation_" + job["id"]]
                    st.write(result["answer"])
                    with st.expander("해석에 사용한 실제 결과"):
                        for e in result["citations"]:
                            st.write(e["title"], e["locator"])
                            st.write(e["text"])
                artifacts = call("GET", f"/jobs/{job['id']}/artifacts")
                with st.expander(f"결과 파일 {len(artifacts)}개", expanded=job["state"] == "succeeded"):
                    visible = [a for a in artifacts if a["step_id"] != "prepare"]
                    visible.sort(key=lambda a: 0 if a["label"] == "report.html" else 1 if a["label"] == "report-bundle.zip" else 2)
                    if visible:
                        selected_file = st.selectbox("파일", visible, format_func=lambda a: f"{a['step_id']} / {a['label']}", key="file_" + job["id"])
                        st.code(selected_file["path"], language=None)
                        st.caption("Windows 탐색기 위치")
                        st.code("\\\\wsl.localhost\\Ubuntu-22.04" + selected_file["path"].replace("/", "\\"), language=None)
                        if st.button("파일 읽기 / 다운로드 준비", key="read_" + job["id"]):
                            response = httpx.get(BASE + f"/jobs/{job['id']}/artifacts/{selected_file['id']}", headers=HEADERS, timeout=120)
                            if response.is_success:
                                st.session_state["content_" + job["id"]] = (selected_file["id"], response.content)
                            else:
                                st.error("결과 파일 검증 또는 읽기에 실패했습니다.")
                        cached = st.session_state.get("content_" + job["id"])
                        if cached and cached[0] == selected_file["id"]:
                            st.download_button("다운로드", cached[1], file_name=selected_file["label"],
                                               mime=selected_file["media_type"], key="download_" + job["id"])
                            if selected_file["label"] == "report.html":
                                components.html(cached[1].decode(), height=800, scrolling=True)
        jobs_view()

with knowledge_tab:
    state = call("GET", "/settings")
    st.subheader("참고문헌")
    st.write("다음 폴더의 PDF, DOCX, TXT, MD를 자동으로 색인합니다.")
    st.caption("참고문헌 전용 폴더입니다. 상담에 선택된 문헌 구간은 활성 LLM에 전달됩니다. Ollama를 선택하면 로컬에서 처리할 수 있습니다.")
    st.code(state["inbox"], language=None)
    st.caption("검색 방식: " + state["embedding"])
    if st.button("지금 색인 갱신"):
        with st.spinner("문서를 읽고 있습니다…"):
            attempt("POST", "/knowledge/index")
    st.dataframe(call("GET", "/knowledge"), hide_index=True)
    query = st.text_input("문헌 구간 검색")
    if query:
        for item in call("GET", "/knowledge/search", params={"q": query}):
            with st.expander(item["title"] + " · " + item["locator"]):
                st.write(item["text"])

with settings_tab:
    state = call("GET", "/settings")
    st.subheader("LLM 연결")
    active = state["provider"]
    st.write("활성 모델:", f"{active['provider']}:{active['model']}" if active else "없음 · 분석 양식은 사용 가능")
    provider = st.selectbox("공급자", ["google", "anthropic", "openai", "ollama"])
    defaults = {"google": "gemini-3.5-flash-lite", "anthropic": "claude-sonnet-4-6", "openai": "gpt-5.2", "ollama": "qwen3:8b"}
    with st.form("provider_" + provider, clear_on_submit=True):
        model = st.text_input("모델 ID", value=defaults[provider])
        key = st.text_input("API key · Ollama는 불필요", type="password")
        url = st.text_input("Ollama 서버 URL", value="http://127.0.0.1:11434") if provider == "ollama" else None
        remember = st.checkbox("이 PC에 암호화하여 저장")
        password = st.text_input("저장소 암호 · 12자 이상", type="password")
        if st.form_submit_button("연결·구조화 출력 검사 후 활성화", type="primary"):
            with st.spinner("모델 연결을 검사합니다…"):
                result = attempt("POST", "/settings/provider", json={"config": {"provider": provider, "model": model,
                    "base_url": url}, "api_key": key, "remember": remember, "passphrase": password})
                if result:
                    if result["validated"]:
                        st.success("분석 계획과 상담에 사용할 수 있습니다.")
                    else:
                        st.warning("일반 연결은 성공했지만 구조화 검사는 실패했습니다. 문헌 검색과 분석 양식을 이용하세요.")
    if provider == "ollama" and st.button("설치된 Ollama 모델 확인"):
        result = attempt("GET", "/settings/ollama")
        if result:
            st.write(result)
    if state["vault_exists"]:
        with st.form("unlock", clear_on_submit=True):
            password = st.text_input("저장된 key 잠금 해제", type="password")
            if st.form_submit_button("잠금 해제"):
                if attempt("POST", "/settings/unlock", json={"passphrase": password}):
                    st.success("잠금을 해제했습니다.")
    web = st.checkbox("문헌 근거가 부족하면 웹 문헌 검색 허용", value=state["allow_web"])
    if web != state["allow_web"]:
        attempt("POST", "/settings/web", json={"enabled": web})
    with st.expander("선택적 일반 웹 검색 · Tavily"):
        with st.form("tavily", clear_on_submit=True):
            tavily_key = st.text_input("Tavily API key", type="password")
            if st.form_submit_button("일반 웹 검색 연결"):
                if attempt("POST", "/settings/tavily", json={"api_key": tavily_key}):
                    st.success("현재 세션에 등록했습니다.")
    st.caption("API 사용량 제한·요금은 공급자 정책을 따릅니다. 원시 유전형과 개인별 표현형은 모델 요청에 포함하지 않습니다.")
    with st.expander("분석 도구와 설치 상태"):
        st.json(call("GET", "/tools"))
