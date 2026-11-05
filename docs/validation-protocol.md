# 논문 검증 프로토콜

## 현재 증거와 출시 조건

이 저장소의 테스트는 구현 정확성과 실행 동작을 검사합니다. 생물학적 정확도, 자연어 모델 성능, 문헌 답변의 사실성, 사용자 편의성은 서로 다른 평가 단위입니다. 어느 한 검증의 통과로 다른 성능을 주장하지 않습니다.

| 주장 | 필요한 증거 | 현재 준비된 자료 |
|---|---|---|
| 동일 확정 계획의 재현성 | 입력·도구·reference·seed 고정, 수치 및 실패 동작 비교 | exact approval, 단계 checksum, 실제 PLINK/Beagle 및 CookHLA smoke, 독립 회귀/R 비교 |
| 의도에서 올바른 계획으로 변환 | 검토된 요청·자료 문맥·질문·금지 행동 정답, 모델별 반복 평가 | 한·영 120개 초안, 예측 저장·평가 CLI; 실제 모델 평가는 미실시 |
| 올바른 HLA 분석 | 독립 reference와 truth, locus/ancestry/frequency별 비교 | 합성 자료와 설치 예제; 독립 생물학적 검증 미실시 |
| 출처에 충실한 지식 설명 | 문헌 위치 확인, 2명의 독립 전문가 검토와 합의 | 한·영 60개 질문, rubric과 검토 양식; 검토 미실시 |
| 비전공자가 더 쉽게 사용 | 동일 엔진의 GUI 비교, 순서 균형, 완료율·시간·도움 요청 | 평가 설계와 빈 기록 양식; 참가자 실험 미실시 |

## 사전 고정할 항목

평가 자료를 보기 전에 tool digest, reference checksum, IMGT release, ancestry strata, HLA resolution, 빈도 구간, confidence cutoff, MAC/missingness, phenotype 생성 seed, 회귀 covariates, 검정군, 통계 허용오차를 고정합니다. 평가용 표본과 가족은 reference에서 배제합니다. 가용 locus·해상도만 정확도 주장에 포함합니다.

통계 비교의 초기 허용오차는 PLINK 텍스트 출력의 반올림을 고려하여 상대오차 `3e-5`, 절대오차 `1e-8`로 둡니다. `metafor` beta/SE/P/Q/I² 비교는 상대오차 `1e-10`, 절대오차 `1e-12`입니다. 이는 현재 테스트의 기준이며 전체 생물학적 데이터 검증을 대신하지 않습니다.

## 생물정보학 평가

CookHLA/HATK 예제는 설치 재현성에만 사용합니다. 1000 Genomes의 HLA 자료에는 실험 기반 typing과 예측 자료가 함께 연결되어 있으므로 origin을 확인해야 합니다. 예측 haplotype을 실험적 위상 정답으로 사용하지 않습니다. [IGSR HLA 자료 안내](https://www.internationalgenome.org/faq/was-hla-diversity-studied-in-igsr/)

`data_sources.json`에 다운로드 원본·이용 조건·locus·해상도·truth 유형·중복 배제 결과·체크섬을 기록한 뒤 동결합니다. 다운로드하지 않은 데이터의 checksum이나 truth status는 비워 둡니다.

`genotype_accuracy()`는 exact pre-harmonized genotype concordance와 call rate를 분리합니다. `phase_accuracy()`는 diploid genotype 불일치, 정보가 있는 transition의 switch error, 전체 haplotype pair 일치를 분리하고 전역 phase 뒤집기는 허용합니다. 실제 평가에서는 allele 빈도별 및 ancestry별 집계를 추가하고 각 분모를 함께 보고합니다.

통계적 제1종 오류와 검정력은 실제 LD를 보존하는 유전형에 사전 지정된 null/alternative phenotype을 반복 생성하여 평가합니다. 다양한 표본 수·case fraction·희귀 allele·공선성·완전 분리를 포함합니다. 정확한 빈도·효과크기 그리드는 pilot 이후 독립 평가 전에 동결합니다. 현재 합성 smoke는 이 대규모 반복 실험을 수행한 것이 아닙니다.

## 에이전트 평가

`workflow_requests.jsonl`은 60개의 한·영 쌍, 총 120개 문항 초안입니다. 각 문항에 고정된 DatasetManifest와 초기 checkpoint를 연결해야 end-to-end 평가가 됩니다. 현재 routing 정답도 전문가 adjudication 이전 초안이며 일부 오류 입력은 질문보다 실행 차단이 올바른 정답일 수 있습니다. 이를 합의 후 동결합니다. 같은 의미의 언어 쌍은 독립 사례로 과대계산하지 않습니다.

각 실행에서 실제 goals·compiled steps·질문 field·승인 유무·실행 step·작업 상태·latency·token·비용을 저장합니다. 정답은 문장 유사도가 아니라 필요한 단계·질문·허용 선택·금지 행동으로 정의합니다. 수집하지 않은 비용이나 실행 지표를 0 또는 성공으로 채우지 않습니다.

`hlagent evaluate-routing`은 사용자가 명시적으로 실행하는 routing 전용 평가입니다. 전체 질문·실행 성능을 측정하지 않습니다. 활성 모델과 `HLAGENT_EVAL_API_KEY`를 사용하며 공급자 사용량이 발생할 수 있습니다. API key는 결과 파일에 쓰지 않습니다.

```bash
hlagent evaluate-routing evaluation/workflow_requests.jsonl evaluation/results/routing.json
hlagent score-evaluation evaluation/workflow_requests.jsonl evaluation/results/routing.json evaluation/results/scores.json
```

비교할 네 구성은 동일한 분석 엔진 위에서 구조화 GUI, 자연어+고정 질문, 자연어+적응형 질문, 문헌 근거를 포함한 전체 구성을 사용합니다. provider·model·prompt hash·seed·반복 횟수를 기록합니다. 계획의 차이와 확정 계획 실행 결과의 차이를 별도로 분석합니다. 현재 UI는 구조화/대화형 두 입력 경로를 제공하며, 네 조건의 사용자 실험 배정은 평가 운영자가 수행합니다.

`knowledge_questions.jsonl`은 30개의 한·영 쌍, 총 60개 초안입니다. HLA 전문가 두 명이 factual correctness, citation support, uncertainty, unsupported claims를 독립 채점합니다. 원문 구간의 실제 주장 지지 여부를 확인하고 불일치 이유와 합의 결과를 저장합니다. BLEU/ROUGE를 핵심 지표로 사용하지 않습니다.

## 사용성 평가

생물학 연구자 12–20명을 모집하고 분석 엔진을 고정합니다. GUI 및 CLI 경험을 기초 조사합니다. 구조화 GUI와 대화형 GUI의 과제 순서를 균형 배정하고 동일 참가자의 대응 결과를 보고합니다.

과제는 자료 등록, 추정 계획 준비, 연관분석 계획 수정, 결과 해석, 실패 후 복구입니다. 완료 여부·시간·도움 요청·오류 수·사용성 설문과 관찰 메모를 `usability.csv`에 기록합니다. 연구에 필요한 동의 및 기관 절차를 완료한 뒤 실제 참가자 데이터를 수집합니다. 작은 표본의 유의성만으로 우월성을 주장하지 않습니다.

## 출시 점검

- 고정된 자료에서 지원 경로의 end-to-end 완료와 과학적 오류 차단.
- 승인한 계획·버전·실제 명령의 일치.
- 독립 구현과 수치·실패 동작의 일치.
- worker 재시작·UI 종료·LLM 장애·취소·중복 승인·입력 변경의 처리.
- 보고서 수치·원문 인용·산출물 checksum의 추적.
- key 활성화 이후 자연어 흐름의 모델별 실제 검증.
- 비전공자 주요 과제의 콘솔 없는 완료.
- 외부 도구·reference·서열·모델의 배포 조건 확인.

이 항목과 인간 참여 평가가 완료되기 전에는 정식 출시 또는 논문 평가 완료로 표시하지 않습니다.
