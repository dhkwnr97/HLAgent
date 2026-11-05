# 분석 정의와 과학적 제한

## 입력·표현

관측 단위는 개인입니다. HLA hard call은 개인별 allele 복제 수 0/1/2로 변환합니다. 명시적 dosage 입력은 기대 복제 수를 유지하며 개인·locus별 합이 2인지 검사합니다. CookHLA confidence를 확률 또는 dosage로 해석하지 않습니다. 원래 confidence와 구성 점수는 별도 열로 남기고, 품질 임계값별 call rate와 사전 지정된 연관분석 민감도 결과를 제공합니다.

HLA 명칭은 모호한 allele을 임의로 선택하지 않습니다. G/P group과 발현 suffix를 보존합니다. 서로 다른 IMGT release를 같은 서열 정의로 취급하지 않습니다. HATK 두 열 AA 사전에서는 alignment column을 사용한다고 명시하며, 성숙 단백질의 아미노산 번호를 추측하지 않습니다. 서열이 없는 allele의 residue는 결측입니다.

CookHLA 어댑터는 hg18 SNP2HLA 형식 reference를 사용합니다. 입력 build는 별도로 확인하고 로컬에 고정된 UCSC chain을 CookHLA에 전달합니다. 원래 도구의 harmonization 동작을 사용하며, adapter 수준에서 파일·표본·reference 중복·map 조건을 추가 검사합니다. 가족 중복과 ancestry 적합성은 ID 일치만으로 완전히 판별할 수 없으므로 실제 평가 코호트의 계보·표본 목록을 별도로 확인해야 합니다. [CookHLA](https://github.com/WansonChoi/CookHLA)

## 회귀와 omnibus

기본 이분형 분석은 PLINK 2 로지스틱 회귀이며 Firth fallback 적용 여부를 결과마다 기록합니다. 연속형은 선형 회귀입니다. 효과 대립유전자와 비교 기준을 결과에 보존합니다. 공변량의 상수·공선성 및 표현형 코딩은 계산 전에 검사합니다. [PLINK 2 GLM](https://www.cog-genomics.org/plink/2.0/assoc)

아미노산 위치의 category dosage를 $D$라고 할 때 각 개인에서 합은 2입니다. 기준 category 하나를 제외하고 동일 개인 집합의 축소·전체 모형을 비교합니다. 자유도는 category 수를 그대로 사용하는 대신 실제 설계행렬의 rank 차이로 정합니다.

$$
q = \operatorname{rank}(X_{full})-\operatorname{rank}(X_{reduced}).
$$

이분형은 $2(\ell_{full}-\ell_{reduced})$의 우도비 검정, 연속형은 다음 부분 F 검정입니다.

$$
F = \frac{(RSS_{reduced}-RSS_{full})/q}{RSS_{full}/(n-\operatorname{rank}(X_{full}))}.
$$

두 모형의 표본을 동일하게 유지합니다. 희소 residue, 분리, 수렴 실패, 자유도 없음은 실패로 보고합니다. 다른 검정의 통계량을 임의로 결합하지 않습니다. 조건부 위치 전체는 독립적인 category 변수 집합으로 보정합니다. 단계적 선택의 최대 횟수와 고정된 검정군 임계값은 승인된 계획에 포함됩니다.

Bonferroni 보정은 실패한 검정 때문에 검정군 크기가 줄어들지 않도록 계산합니다. 탐색용 Benjamini–Hochberg FDR을 별도로 제공합니다. 단계적 선택 이후의 신호와 P값은 탐색적이며 인과관계 또는 선택 후 추론의 보장을 의미하지 않습니다.

## 메타분석

동일 표현형·단위·효과 척도·조건부 변수·공변량·HLA 해상도·서열 release·build·strand 정의의 독립 코호트만 통합합니다. OR 입력의 SE는 log-odds 척도여야 합니다. Omnibus P값은 scalar beta/SE가 아니므로 이 경로에서 거절합니다.

$$
w_i=1/SE_i^2,\qquad \hat\beta=\frac{\sum_iw_i\beta_i}{\sum_iw_i},\qquad SE(\hat\beta)=\sqrt{1/\sum_iw_i}.
$$

$$
Q=\sum_iw_i(\beta_i-\hat\beta)^2,\qquad I^2=\max\left(0,\frac{Q-(k-1)}{Q}\right)\times100\%.
$$

$Q=0$이면 $I^2=0$으로 정의합니다. 3개 이상 코호트에서는 하나씩 제외한 결과를 제공합니다. 코호트별 누락 marker는 해당 marker에 실제로 기여한 코호트 수로 표시합니다. 독립성은 사용자가 확인해야 하며 제공된 sample hash에 중복이 있으면 중단합니다. 같은 정의의 R `metafor` 고정효과 결과와 대조하는 테스트가 포함되어 있습니다.

## 위상 추론

Beagle 5.5에 HLA locus별 다중 대립유전자 표현을 전달하고 가역적인 codebook으로 되돌립니다. private HLA allele 코드는 DNA 변이의 생물학적 의미를 갖지 않습니다. HLA-only 모드는 합성 좌표계를 사용합니다. SNP scaffold 모드는 사용자가 제공한 같은 build의 HLA anchor 좌표와 SNP를 함께 사용합니다. Reference가 있다면 build·좌표·allele codebook·관측 phase를 검사합니다. [Beagle 5.5](https://faculty.washington.edu/browning/beagle/beagle.html)

전후 sample·allele dictionary·원래의 알려진 diploid genotype을 검사합니다. 동일 개인의 두 haplotype을 전역적으로 바꾼 것은 오류로 세지 않습니다. 부모 유래를 추론하지 않습니다. 실제 위상 정확도는 trio 또는 독립 phase truth로 별도 평가해야 하며, 합성 round-trip 성공으로 이를 대체하지 않습니다.
