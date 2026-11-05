# Statistical methods

Notation: person $i = 1, \dots, n$, marker $j$, binary phenotype $Y_i \in \{0, 1\}$, marker dosage $x_{ij} \in \{0, 1, 2\}$, covariate vector $\mathbf{c}_i$.

## Node2: marker-level regression

$$\operatorname{logit}\Pr(Y_i = 1) = \beta_0 + \beta_j x_{ij} + \boldsymbol{\gamma}^\top \mathbf{c}_i, \qquad \mathrm{OR}_j = e^{\beta_j}$$

The Wald statistic is $Z_j = \hat\beta_j / \mathrm{SE}(\hat\beta_j)$ with $p_j = 2\{1 - \Phi(|Z_j|)\}$. The `SE` column of PLINK 1.9 `--logistic --ci` is the standard error of $\log \mathrm{OR}$, so $\hat\beta_j = \ln(\mathrm{OR}_j)$. Quantitative traits use the linear model $Y_i = \beta_0 + \beta_j x_{ij} + \boldsymbol{\gamma}^\top \mathbf{c}_i + \varepsilon_i$. The effect allele is fixed with `--a1-allele`. For binary HLA markers (`HLA_`, `AA_`, `SNPS_`) the effect allele is "present", so $\mathrm{OR} > 1$ means that carrying the allele or residue increases risk.

## Node3: stepwise conditional regression

Start with $S_0 = \varnothing$. At step $k$, test every marker $j \notin S_{k-1}$ with $S_{k-1}$ as covariates and select $j^* = \arg\min_j p_j$. If $p_{j^*} < \alpha$, set $S_k = S_{k-1} \cup \{j^*\}$; otherwise stop. By default $\alpha = 0.05/M$, where $M$ is the number of markers with a non-missing P-value in Node2 (Bonferroni); $5 \times 10^{-8}$ is available as an option. At most 10 steps are run. Because MHC markers are strongly correlated, the Bonferroni threshold is conservative, and the report says so.

## Node4: omnibus test

For an amino-acid position $a$ with $K_a$ residue groups, a model with $K_a - 1$ haplotype-dosage terms is compared with the null model (covariates and conditioning terms only):

$$\Lambda_a = D_0 - D_1 \;\overset{H_0}{\sim}\; \chi^2_{K_a - 1} \ (\text{asymptotically})$$

where $D$ is the deviance. The choice of reference residue and the handling of rare residues follow the HATK R script `OmnibusTest_BHv5.R`, which reports $\log_{10} p$.

## Node5: meta-analysis over $k$ studies

Allele alignment (study 1 is the reference):

| Case | Action |
|---|---|
| $(A1_s, A2_s) = (A1_1, A2_1)$ | keep |
| $(A1_s, A2_s) = (A2_1, A1_1)$ | $\hat\beta_s \leftarrow -\hat\beta_s$ |
| alleles match after strand complement | complement, then apply the two rules above |
| A/T or C/G SNP (strand-ambiguous) | exclude |
| HATK binary marker (`p`/`a`) | align by name and A1 (`p`); never complemented |
| any other mismatch | exclude and report the count |

Fixed effect (inverse variance):

$$w_s = \frac{1}{\mathrm{SE}_s^2}, \qquad \hat\beta_F = \frac{\sum_s w_s \hat\beta_s}{\sum_s w_s}, \qquad \mathrm{SE}(\hat\beta_F) = \Big(\sum_s w_s\Big)^{-1/2}$$

Heterogeneity:

$$Q = \sum_s w_s (\hat\beta_s - \hat\beta_F)^2 \;\overset{H_0}{\sim}\; \chi^2_{k-1}, \qquad I^2 = \max\Big\{0, \frac{Q - (k - 1)}{Q}\Big\}$$

Random effects (DerSimonian–Laird):

$$\hat\tau^2 = \max\Big\{0, \frac{Q - (k - 1)}{\sum_s w_s - \sum_s w_s^2 / \sum_s w_s}\Big\}, \qquad w_s^* = \frac{1}{\mathrm{SE}_s^2 + \hat\tau^2}$$

$\hat\beta_R$, $\mathrm{SE}(\hat\beta_R)$ and $p_R$ use $w_s^*$ in the fixed-effect formulas.

Reference values used by the unit tests (checked by hand), for $\hat\beta = (0.40, 0.10)$ and $\mathrm{SE} = (0.10, 0.20)$:

| Quantity | Value |
|---|---|
| $\sum w$ | 125 |
| $\hat\beta_F$, $\mathrm{SE}_F$ | 0.340000, 0.089443 |
| $Z_F$, $p_F$ | 3.80132, $1.4393 \times 10^{-4}$ |
| $Q$, $p_Q$, $I^2$ | 1.8000, 0.1797, 0.4444 |
| $\hat\tau^2$ | 0.0200 |
| $\hat\beta_R$, $\mathrm{SE}_R$, $p_R$ | 0.300000, 0.141421, $3.3895 \times 10^{-2}$ |

Caveats that the report states automatically:

1. With $k = 2$ studies, $Q$ has one degree of freedom, so $I^2$ and $\hat\tau^2$ are imprecise.
2. When different phenotypes are combined (for example the HATK RA and Crohn's disease example), $p_F$ tests a common effect; effects of opposite sign cancel, so per-study estimates and $Q$ are always shown.
3. Overlapping samples (for example shared controls) violate independence and make $p$ too small; Stage D warns when sample IDs overlap.

## Summary statistics in the report

- Significance is shown against both Bonferroni $0.05/M$ and $5 \times 10^{-8}$.
- $\lambda_{GC} = \operatorname{median}(\chi^2_{1,j}) / 0.4549$ is shown as a descriptive statistic only: within the MHC, true signals and strong LD make it invalid as a measure of population stratification.

## Synthetic phenotypes (demonstration only)

- **Null mode:** $Y_i \sim \mathrm{Bernoulli}(0.5)$, independent of genotype, with the seed recorded. No signal is expected.
- **Spike-in mode:** $\operatorname{logit}\Pr(Y_i = 1) = \beta_0 + \beta x_i$, where $x_i$ is the dosage of a chosen allele (default `HLA_DRB1*15:01`), $\mathrm{OR} = 5$ by default ($\beta = \ln 5$), and $\beta_0$ is set so that about half of the samples are cases.
- Every artifact of a run with a synthetic phenotype is labelled `SYNTHETIC`, and the report states that the results carry no biological meaning. The label cannot be disabled.
