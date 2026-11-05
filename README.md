# HLAgent 2.0 alpha

자연어 또는 분석 양식으로 연구 목적을 확인하고, 승인된 계획을 독립 실행기(worker)가 수행하는 로컬 HLA 연구 애플리케이션입니다. 기존 `HLAgent-main_v1.0.0`과 분리하여 새로 작성했습니다.

현재 상태는 **실행 가능한 연구용 alpha**입니다. 설치·통계·실행 복구 검증은 자동화되어 있습니다. 독립 자료의 생물학적 정확도, 실제 모델별 계획 정확도, 전문가 문헌 평가, 비전공자 사용성 평가는 출시 전 별도로 완료해야 합니다. 예제 실행 성공을 논문 성능 결과로 해석하지 않습니다.

이 PC의 [구현·검증 현황](docs/validation-status.md)에 45개 자동 검사, 실제 CookHLA·Beagle·PLINK 실행, 브라우저 확인 결과와 남은 평가를 기록했습니다.

## 지금 실행하기

이 PC에서는 `Launch-HLAgent.cmd`를 더블클릭합니다. 브라우저 주소는 `http://127.0.0.1:8501`입니다. API key 없이도 **합성 예제로 시작 → 예제의 검증 가능한 분석 계획 열기 → 이 계획으로 실행 → 결과**를 사용할 수 있습니다.

처음 설치하는 WSL2 Ubuntu 22.04 환경에서는 프로젝트 폴더에서 다음을 한 번 실행합니다. Docker는 WSL에서 사용할 수 있도록 미리 설치되어 있어야 합니다.

```bash
bash scripts/bootstrap.sh
bash scripts/install-tools.sh
bash scripts/start.sh
```

Python 3.12와 프로젝트 의존성은 `uv.lock`으로 고정합니다. 가상환경·작업 자료는 기본적으로 Linux 파일시스템의 `~/.local/share/hlagent`에 생성합니다. 원본 Windows 파일은 경로 등록 후 체크섬을 기록하고 계산용 복사본을 만듭니다. 설치 이후 일상 분석에서 콘솔이나 YAML 편집은 필요하지 않습니다.

첫 로컬 의미 검색에는 다국어 임베딩 모델 약 241 MB가 내려받아질 수 있습니다. 이후 모델 추론과 FAISS 검색은 로컬에서 실행됩니다. 저장 위치는 `~/.local/share/hlagent/knowledge/models`입니다.

## 사용자 흐름

1. 프로젝트를 만들고 자료 탭에서 파일 또는 `C:\Users\...` 경로를 등록합니다. 파일 종류, build, ancestry, 필요한 열 이름을 확인합니다.
2. 분석 탭에서 자료를 선택합니다. 설정에서 LLM을 연결한 뒤 질문하거나, 분석 양식을 사용합니다.
3. 한 번에 최대 세 개의 질문에 답합니다. 표본·표현형 코딩·공변량 등을 임의로 추정하지 않습니다.
4. 분석 단계·변수·자원·QC 설정을 확인하고 실행합니다. 수정하면 변경 내용과 새 계획 버전을 확인합니다.
5. 결과 탭에서 취소·재개·다운로드·보고서와 결과 해석을 확인합니다. 브라우저 종료는 계산을 중단시키지 않습니다.

LLM은 Google Gemini, Anthropic Claude, OpenAI API, Ollama를 지원합니다. 기본 Google 모델 ID는 요청된 `gemini-3.5-flash-lite`이며 실제 사용 가능 여부는 연결 검사로 확인합니다. 자동 유료 모델 전환은 없습니다. 구조화 출력 검사를 통과한 모델만 계획을 작성합니다. 일반 연결만 가능한 모델은 문헌 검색을 이용하고 분석은 양식으로 진행합니다.

API key는 기본적으로 API 프로세스 메모리에 둡니다. 저장을 선택하면 사용자가 지정한 암호로 암호화합니다. 앱 재시작 후 설정에서 잠금을 해제합니다. 유전형·표현형 파일은 모델 요청에 넣지 않습니다. 선택된 참고문헌 구간, 사용자가 입력한 연구 질문 및 결과 집계는 활성 모델에 전달될 수 있습니다.

## 구현 범위

| 기능 | 실행 경로와 제한 |
|---|---|
| 입력 | BED/BIM/FAM, PGEN/PVAR/PSAM, VCF/BCF, HPED/CHPED, HLA TSV/CSV, 명시적인 dosage 표, 표현형·요약통계 |
| Typing 출력 | OptiType 단일 top row, HLA-HD 단일 표본 표, xHLA JSON, HIBAG/AXIOM의 명시적 열 매핑; 임의 형식 변형은 자동 추측하지 않음 |
| CookHLA | 고정 Docker digest, 로컬 좌표 변환 chain, reference·map 검사, hard call·원래 confidence 보존, call-rate 및 confidence 민감도 분석 |
| HLA 표현 | allele dosage, 명시적 서열 사전의 residue dosage, HATK AA 사전 입력; 누락·모호한 서열을 보충하지 않음 |
| 기본 회귀 | 실제 PLINK 2 로지스틱/Firth fallback 또는 선형 회귀; dosage 유지 |
| 정밀 분석 | 조건부·단계적 조건부·개인 단위 omnibus; 실패 검정을 다른 통계량으로 임의 대체하지 않음 |
| Phasing | Beagle 5.5 SNP phasing, HLA multiallelic round-trip, 선택적 SNP scaffold·동일 codebook reference; HLA haplotype은 탐색적 기능 |
| 메타분석 | 2개 이상 독립 코호트, 동일 효과 정의, 고정효과 역분산 통합, Q·I², 3개 이상 leave-one-out |
| 보고 | HTML, TSV, PNG, 대화형 그림, 승인 계획, 실행 명령·버전·로그·체크섬, ZIP 묶음, 선택적 결과 폴더 복사 |
| 문헌 | PDF 페이지·DOCX 문단·텍스트 구간 보존, 증분 색인, FTS5+로컬 다국어 임베딩+FAISS, 정확한 allele 검색, Europe PMC·PubMed·선택적 Tavily |

FASTQ/BAM typing, 생존·반복측정·혼합모형, 가족 기반 연관분석, 서로 다른 표현형의 효과 통합, random-effects 메타분석은 지원하지 않습니다. SNP scaffold를 포함한 HLA haplotype도 독립적인 정답 위상 자료로 평가되기 전에는 정확도를 보장하지 않습니다.

## 구성

| 위치 | 책임 |
|---|---|
| `models.py`, `planning.py` | 데이터 계약, 지원 기능, 질문, 계획 컴파일 |
| `workflow.py`, `agents.py` | LangGraph 체크포인트·승인과 Pydantic AI 2.x 구조화 해석 |
| `data.py`, `adapters.py`, `statistics.py` | 파일 검사·변환, CookHLA/Beagle/PLINK 실행, 통계 |
| `worker.py`, `execution.py`, `process_runner.py` | 작업 대기열, 단계 재사용, 독립 프로세스·컨테이너 복구 |
| `api.py`, `ui.py`, `cli.py` | FastAPI, Streamlit, 동일 실행 엔진의 재현 명령 |
| `knowledge.py`, `reporting.py`, `evaluation.py` | 근거 검색, 결정론적 보고서, 평가 지표 |

## 재현 및 개발

```bash
export UV_PROJECT_ENVIRONMENT="$HOME/.local/share/hlagent/venv"
uv sync --frozen
uv run --no-sync pytest -q
uv run --no-sync ruff check src tests scripts
uv run --no-sync hlagent doctor
uv run --no-sync hlagent demo --run
uv run --no-sync hlagent replay /path/to/approved-plan.json
uv run --no-sync hlagent replay /path/to/approved-plan.json --approve
```

`replay --approve`는 GUI와 같은 대기열에 넣습니다. worker가 실행 중이어야 합니다. 이미 끝난 같은 계획의 유효 결과는 재사용합니다. 입력·reference·도구·HLAgent 소스가 변경되면 기존 계획으로 실행하지 않고 새 계획을 요구합니다. 다른 PC에서 재현할 때는 원래 입력 경로가 접근 가능해야 하며 같은 도구와 reference가 필요합니다.

실행 바로가기는 저장소의 `knowledge/inbox`를 참고문헌 폴더로 사용합니다. 직접 CLI를 실행하면 기본 폴더는 `~/.local/share/hlagent/knowledge/inbox`입니다. `HLAGENT_INBOX`로 지정할 수 있으며 실제 폴더는 GUI 문헌 탭에 표시됩니다.

설계와 출시 준비는 `docs/architecture.md`, `docs/scientific-methods.md`, `docs/validation-protocol.md`를 참조합니다. 평가 문항은 `evaluation/`에 있습니다. 배포 전 외부 도구·reference·서열 데이터의 조건을 `THIRD_PARTY.md`와 대조해야 합니다.
