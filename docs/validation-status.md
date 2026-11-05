# HLAgent 2.0 alpha 구현·검증 현황

2026-09-06, WSL2 Ubuntu 22.04에서 확인했습니다. 현재 결과는 실행 가능한 alpha의 구현 검증이며, 논문 성능 평가 또는 정식 출시 승인에 해당하지 않습니다.

## 확인한 실행 증거

| 항목 | 실제 결과 | 근거 |
|---|---|---|
| 자동 검증 | 45 passed, 실패·건너뛴 검사 없음; Ruff 통과 | `tests/`, `scripts/validate_release.py` |
| 기본·정밀 분석 | 실제 PLINK 2 선형·이분형 회귀, 조건부·단계적 분석, omnibus, 보고서 생성 | `tests/test_integration.py`, `tests/test_extended_pipelines.py`, `tests/test_statistics.py`, `tests/test_validation.py` |
| 통계 수치 비교 | PLINK와 독립 회귀 구현, Python 메타분석과 R metafor 비교 통과 | `tests/test_validation.py`; 사전 허용오차는 `validation-protocol.md` 참조 |
| Beagle 5.5 | HLA 다중 대립유전자 인코딩과 SNP scaffold 경로에서 실제 Java 실행·diploid genotype 보존 확인 | `tests/test_integration.py`, `tests/test_extended_pipelines.py` |
| CookHLA | 기존 10명 설치 예제, 고정 Docker 이미지로 입력부터 confidence·HPED 파싱 및 보고서 생성까지 성공 | `scripts/smoke_cookhla.py` |
| 작업 수명주기 | 승인 전 미실행, 동시 중복 승인 단일 작업, 독립 프로세스 재연결, 해당 작업만 취소, 입력·도구 변경 차단 | `tests/test_contracts.py`, `tests/test_workflow.py`, `tests/test_recovery.py` |
| GUI | 실제 브라우저에서 예제 생성, 계획 수정·재승인, 작업 완료, HTML 보고서 및 다운로드 준비 확인 | `tests/test_ui.py`는 프로젝트 선택 유지와 승인 전 미실행 회귀 검사 |
| Windows 실행 바로가기 | 서비스를 종료한 뒤 `Launch-HLAgent.ps1`로 재시작; API 및 Streamlit health 응답 정상 | 로컬 실행 확인, API `status=ok`, version `2.0.0a1` |
| 문헌 검색 | 로컬 다국어 임베딩 실추론·FAISS 검색, Europe PMC 및 PubMed 실제 응답 확인 | `src/hlagent/knowledge.py`; 로컬 inbox 예제는 구현 설명 문서 |

최종 자동 검증 시각은 `2026-09-06T04:52:55Z`입니다. Python 3.12.14, Pydantic AI 2.40.0, LangGraph 1.2.11을 사용했습니다. Python 의존성은 `uv.lock`에 고정했습니다. 실행 바이너리·참조 chain·이미지 digest와 상세 테스트 로그는 검증 PC의 로컬 결과 폴더에 기록했으며, 개인 자료가 섞이지 않도록 브랜치에서 제외합니다.

검증한 HLAgent Python 소스 SHA-256:

`7de0de44b19bc8da81750f47592f770a9a258436a9aaa3dfd8223a361770e6c7`

테스트에는 Starlette 및 Streamlit 의존성의 폐기 예정 API 경고 세 건이 남아 있습니다. 해당 실행에서 실패는 없었으며, 의존성 갱신 시 다시 확인해야 합니다.

## 실제 실행 확인과 예제 산출물

최종 CookHLA 실행은 한 번의 시도에서 완료되었습니다. 원본 예제와 reference는 기존 저장소에서 읽었고 재배포하지 않습니다. 이 예제는 설치·파싱 검증용이며 imputation 정확도를 측정한 결과가 아닙니다.

최종 GUI 검증은 240명의 합성 표현형·HLA 자료로 수행했습니다. 아미노산 사전도 인공 자료이며, 실제 질병 또는 HLA 아미노산 효과의 근거로 사용할 수 없습니다.

검증 PC에는 HTML 보고서와 재현 자료 ZIP을 만들고 CRC 검사를 통과시켰습니다. 이 개인용 출력과 상세 실행 기록은 로컬 `evaluation/results/` 폴더에 보관하며 Git 브랜치에는 올리지 않았습니다.

## 논문 출시 전 남은 작업

| 항목 | 현재 상태 | 완료에 필요한 자료 또는 작업 |
|---|---|---|
| 독립 imputation 평가 | 미실시 | 검증된 실험 HLA typing, reference와 표본·가족 중복 배제, locus·ancestry·빈도별 집계 |
| 위상 정확도 평가 | 미실시 | Trio 또는 독립 확인 위상; 구조적 round-trip을 정확도 평가로 대체하지 않음 |
| 실제 모델 비교 | 미실시 | 사용자 API key 또는 Ollama 모델 연결, 고정된 자료 문맥과 전문가가 검토한 정답 |
| 자연어 요청 120개 | 초안 및 평가 CLI 준비 | 문항·허용 계획·필수 질문·금지 행동 adjudication, end-to-end 반복 실행 |
| 지식 질문 60개 | 초안 및 검토 양식 준비 | 두 HLA 전문가의 독립 채점과 합의, 실제 인용의 주장 지지 여부 확인 |
| 비전공자 사용성 | 프로토콜·빈 기록 양식 준비 | 12–20명 모집 및 균형 배정, 실제 완료율·시간·도움 요청 관찰 |
| 대규모 성능·통계 보정 | 미실시 | 실제 LD를 보존한 반복 null/alternative 실험, 수백~1만 명 자원 측정 |
| 배포 조건 | 외부 구성요소 목록과 조건 문서 작성 | 배포할 reference·서열·바이너리별 최종 확인 및 프로젝트 소유자의 라이선스 선택 |

Google·Anthropic·OpenAI·Ollama 연결 및 구조화 출력 검사는 구현되어 있지만, 이번 검증에서는 개인 API key를 사용하지 않았고 Ollama 서버도 연결되지 않았습니다. 실제 자연어 모델 성능이나 비용을 측정했다고 주장하지 않습니다. Tavily 연결은 구현되어 있으나 실제 key를 이용한 검색은 미검증입니다.

초기 typing 변환 어댑터는 명시적으로 지원하는 표 구조와 열 매핑을 대상으로 합니다. 공급자 버전별 모든 출력 변형을 검증한 상태는 아닙니다. HATK 형식의 서열 사전을 읽을 수 있지만, IPD-IMGT/HLA 서열 데이터나 외부 바이너리를 패키지에 재배포하지 않습니다.

자세한 평가 정의와 수치 허용오차는 [논문 검증 프로토콜](validation-protocol.md), 사용법은 [README](../README.md), 배포 조건은 [THIRD_PARTY](../THIRD_PARTY.md)를 참조하십시오.
