# 구현 구조와 실행 계약

Streamlit은 사용자 입력과 상태 조회만 담당합니다. FastAPI는 loopback에 바인딩하며 로컬 애플리케이션 토큰을 검사합니다. 장시간 분석은 별도 worker에서 실행됩니다. UI·LLM의 수명과 작업의 수명이 다릅니다.

LangGraph는 `assess → ask → assess → plan → approve`를 관리합니다. 추가 질문과 승인에는 SQLite checkpointer와 interrupt/resume를 사용합니다. Pydantic AI는 해석과 설명만 수행하며 그래프나 범용 실행 도구를 소유하지 않습니다. 지원 기능과 실제 파일 조건은 Python 계획 컴파일러가 다시 검사합니다.

| 계약 | 검증 기준 |
|---|---|
| DatasetManifest | 파일 역할·SHA256·크기, 표본, build, 해상도, phase/dosage 의미 |
| AnalysisIntent | 분석 목표, 자료, 표현형·보정 변수·코호트 독립성의 명시적 확인 |
| AnalysisPlan | 순서가 유효한 DAG, 도구·소스 해시, reference, 자원, QC, 버전 |
| PlanApproval | 정확한 plan ID·revision·전체 JSON 해시 |
| JobRecord | queued/running/succeeded/failed/cancel_requested/cancelled |
| ArtifactManifest | 작업 폴더 안의 실제 파일, SHA256, 형식 검사, 생성 단계 |
| EvidenceAnswer | 실제 색인 구간 또는 결과 파일에 연결된 근거와 한계 |

대용량 파일은 SQLite나 그래프 상태에 넣지 않습니다. 상태에는 경로·해시·구조화된 메타데이터만 저장합니다. 동일 계획의 중복 승인은 SQLite의 원자적 트랜잭션과 unique constraint로 하나의 작업에 연결됩니다.

## 복구 동작

worker는 file lock으로 하나만 실행됩니다. 외부 명령은 독립 guardian 프로세스가 시작하며, 명령 JSON·PID·종료 코드·로그를 보관합니다. Linux에서는 `/proc`의 start ticks와 boot ID를 함께 비교하여 WSL 시계 보정 때문에 프로세스 생성 시각이 달라져도 같은 프로세스를 식별합니다. worker가 종료되어도 guardian은 계속 실행할 수 있습니다. 실행 바로가기는 이 가상환경과 홈 디렉터리에 속한 고정 서비스 명령만 발견·복구합니다.

CookHLA는 작업 ID와 계획 fingerprint label을 가진 Docker 컨테이너에서 실행됩니다. 재시작 때 살아 있는 같은 컨테이너에 연결합니다. 취소는 해당 작업의 프로세스 그룹과 컨테이너에만 적용합니다. Beagle·PLINK가 내부 checkpoint를 제공하지 않는 경우 실패한 명령 또는 단계부터 다시 실행합니다.

완료 단계는 입력·계획·도구 fingerprint와 산출물 체크섬이 맞을 때만 재사용합니다. 실제 산출물 파싱과 sample/allele 보존 검사가 먼저 통과해야 성공으로 기록합니다. 디스크 손실, WSL 전체 종료, 컨테이너 엔진 종료에서는 해당 단계의 재실행이 필요할 수 있습니다.

## 외부 호출과 자격증명

분석 도구에는 모델이 생성한 shell/Python/R 문자열을 실행하는 인터페이스가 없습니다. 어댑터가 구성한 인자 목록만 실행합니다. CookHLA의 컨테이너 내부 코드와 바이너리는 image digest로 고정하고 네트워크를 비활성화합니다. 원본과 reference mount는 읽기 전용입니다.

Cloud LLM 요청의 자료 문맥에는 종류·표본 수·build·dosage/phase 여부만 포함합니다. 사용자 문장은 길이·표 형태·경로를 검사합니다. 임의의 자연어에 포함된 모든 개인정보를 탐지하는 보장은 없으므로 사용자 질문과 참고문헌 전용 폴더의 의미를 GUI에 명시합니다.

LLM key는 메모리 또는 Scrypt로 키를 유도한 Fernet 저장소에 보관합니다. 암호화 저장소의 암호 자체는 저장하지 않습니다. 로컬 API 토큰 파일은 mode 0600, 홈 디렉터리는 mode 0700입니다. 다중 사용자 서버, 원격 공개 배포 및 인증 위임은 현재 범위가 아닙니다.

## 주요 API

프로젝트·자료 등록, 대화 시작/재개, 계획 조회/승인, 작업 상태/취소/재개, 산출물 다운로드, 결과 해석, LLM 설정, 문헌 색인/검색만 제공합니다. 승인 없이 `/conversations`를 호출해도 작업은 제출되지 않습니다. `/plans/{id}/approve`는 정확한 해시와 버전을 요구합니다.
