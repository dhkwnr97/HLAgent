# 외부 구성요소와 배포 범위

이 디렉터리는 새 HLAgent 구현과 합성 예제 생성기를 포함합니다. HATK/CookHLA 코드, HLA reference panel, IPD-IMGT/HLA 서열 데이터, 외부 실행 바이너리와 임베딩 가중치는 저장소에 복사하여 포함하지 않았습니다. 설치 스크립트와 어댑터는 해당 외부 구성요소를 별도로 사용합니다.

| 구성요소 | 확인된 사용 방식과 배포 점검 |
|---|---|
| CookHLA | 사용자 지정 Docker 이미지를 digest로 고정하여 별도 실행. upstream은 비상업적 학술 연구 사용 조건을 명시하며 기타 사용은 저자에게 문의하도록 안내. 이미지에 포함된 패널·바이너리의 조건도 별도로 확인해야 함. [upstream](https://github.com/WansonChoi/CookHLA) |
| HATK | legacy 통계 코드를 복사하지 않고 사용자 제공 AA dictionary 결과를 독립 어댑터로 읽음. upstream의 코드 사용 조건은 비상업적 학술 연구. dictionary에 포함된 원본 서열 조건은 별도임. [upstream](https://github.com/WansonChoi/HATK) |
| Beagle 5.5 | 공식 JAR 별도 다운로드, SHA256 검사. 공식 배포는 GPL v3 또는 이후 버전을 명시. 재배포 시 해당 소스·라이선스 의무를 점검. [공식 배포](https://faculty.washington.edu/browning/beagle/beagle.html) |
| PLINK·bcftools·R | Ubuntu 패키지로 별도 설치. 포함 배포를 준비할 때 각 패키지의 copyright/license 및 소스 제공 조건을 확인 |
| UCSC chain | 공식 UCSC endpoint에서 별도 다운로드, 두 build의 파일 해시 고정. 재배포 조건은 원본 자료 정책과 대조 |
| HLA reference·IMGT 서열 | 사용자가 적법하게 확보한 파일을 등록. 저장소 자체에 배포하지 않으며 dataset manifest에 출처와 버전을 기록 |
| 다국어 임베딩 | FastEmbed가 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` ONNX 자산을 로컬 캐시에 다운로드. FastEmbed와 모델 가중치의 라이선스를 구분하여 배포 전 확인 |

HLAgent 자체의 공개 라이선스와 저작권자는 프로젝트 소유자가 출시 전에 확정해야 합니다. 외부 연구용 도구의 조건을 새 코드의 라이선스로 덮어쓰거나 모든 구성요소가 자유롭게 상업 재배포 가능하다고 표시하지 않습니다.

## 이 환경에서 검증한 외부 파일

CookHLA image digest: `sha256:0b374cef9cc352cfaa7aa5e89ad49d5b6c64274a6eb8100acbb7f6f452f0c5d6`

Beagle 5.5 JAR: `beagle.27Feb25.75f.jar`, SHA256 `7319f4af9638be05c18dcc1bfb8fb41a58a09293507ebf0d54617d0e40df5a70`

CookHLA 이미지 내부 `CookHLA.py` SHA256: `eae45ba7df09ef4502d8d1b1528668dada5b6bff1cf3345b681a93df9a532df1`. 내부 PLINK 출력은 `PLINK v1.90b6.10 64-bit (17 Jun 2019)`였습니다. 내부 Beagle JAR는 독립 phasing에 사용하는 Beagle 5.5와 교체하지 않았습니다.

실제 계획과 보고서는 현재 바이너리 해시와 HLAgent Python 소스 해시도 기록합니다. 동적인 패키지 설치 상태는 `hlagent doctor`로 확인합니다.
