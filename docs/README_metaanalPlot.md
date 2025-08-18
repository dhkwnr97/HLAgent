# Meta-Analysis Visualization Tool (metaanalPlot.py)

## Overview

`metaanalPlot.py` is a comprehensive visualization tool for meta-analysis results in HLA association studies. It generates various plots to help researchers interpret and validate their meta-analysis findings.

## Available Plot Types

### 1. Q-Q Plot (`qq`)
**Purpose**: Assess the quality of p-value distribution and detect potential inflation or deflation.

**What it shows**:
- Expected vs observed -log10(p-values)
- λ (lambda) inflation factor
- Deviation from the diagonal line indicates potential issues

**Interpretation**:
- **Points on diagonal line**: P-values follow expected distribution
- **Points above diagonal**: P-value inflation (potential population stratification or technical artifacts)
- **Points below diagonal**: P-value deflation (potential issues with analysis)
- **λ > 1.05**: Suggests potential inflation requiring investigation
- **λ < 0.95**: Suggests potential deflation

**Biological relevance**: Helps identify systematic biases that could affect the validity of association signals.

### 2. Manhattan Plot (`manhattan`)
**Purpose**: Visualize genome-wide association signals from meta-analysis results across chromosomes.

**What it shows**:
- -log10(P-values) plotted against chromosomal position
- Genome-wide significance line (P < 5×10⁻⁸)
- Suggestive significance line (P < 1×10⁻⁵)
- Chromosome-specific color coding

**Interpretation**:
- **Points above red line**: Genome-wide significant associations
- **Points above orange line**: Suggestive associations requiring replication
- **Peak clusters**: Potential linkage disequilibrium regions
- **Isolated peaks**: Independent association signals
- **Overall pattern**: Genome-wide distribution of association signals

**Clinical relevance**: Identifies genomic regions harboring variants associated with the trait, guiding follow-up functional studies and clinical applications.

### 3. Effect Size Distribution (`effect_dist`)
**Purpose**: Examine the distribution of effect sizes across all variants in the meta-analysis.

**What it shows**:
- Histogram of effect sizes (BETA)
- Box plot of effect size distribution
- Effect size vs standard error scatter plot
- P-value distribution

**Interpretation**:
- **Effect size histogram**: 
  - Centered around 0: Most variants have no effect
  - Skewed distribution: Suggests directional bias
- **Effect size vs SE**: 
  - Negative correlation: Larger studies tend to find smaller effects (regression to mean)
  - No correlation: Effect sizes are independent of study size
- **P-value distribution**: 
  - Peak at low p-values: Strong association signals
  - Uniform distribution: No significant associations

**Clinical relevance**: Helps understand the overall pattern of genetic effects and identify potential outliers.

### 4. Study Comparison (`study_comp`)
**Purpose**: Compare results between individual studies and the meta-analysis to assess consistency and heterogeneity.

**What it shows**:
- Study 1 vs Study 2 scatter plot with correlation analysis
- Study 1 vs Meta-analysis scatter plot
- Study 2 vs Meta-analysis scatter plot
- Effect size differences histogram
- Bland-Altman plot
- Heterogeneity indicator

**Interpretation**:

**Study 1 vs Study 2**:
- **High correlation (r > 0.7)**: Studies are consistent
- **Low correlation (r < 0.3)**: Studies show different patterns
- **Points on y=x line**: Perfect agreement between studies
- **Regression line**: Shows the actual relationship between studies

**Study vs Meta-analysis**:
- **Points on y=x line**: Individual study agrees with meta-analysis
- **Points above line**: Individual study shows larger effects
- **Points below line**: Individual study shows smaller effects

**Effect Size Differences**:
- **Centered around 0**: Studies show similar effects
- **Skewed distribution**: Systematic differences between studies

**Bland-Altman Plot**:
- **Points around 0**: No systematic bias
- **Trending pattern**: Effect size-dependent bias
- **Wide spread**: High variability between studies

**Heterogeneity Indicator**:
- **SE Ratio ≈ 1.0**: Low heterogeneity
- **SE Ratio > 1.0**: High heterogeneity (meta-analysis less precise)
- **SE Ratio < 1.0**: Low heterogeneity (meta-analysis more precise)

**Statistical relevance**: Essential for assessing the quality and reliability of meta-analysis results.

### 5. Forest Plot (`forest`)
**Purpose**: Visualize effect sizes and confidence intervals for top significant variants across studies.

**What it shows**:
- Effect sizes with 95% confidence intervals for each study
- Meta-analysis summary effect
- Visual comparison of study-specific and combined results

**Interpretation**:
- **Confidence intervals overlapping**: Studies are consistent
- **Confidence intervals not overlapping**: Studies show different effects
- **Meta-analysis diamond**: Summary effect with confidence interval
- **Diamond crossing 0**: Non-significant overall effect
- **Diamond not crossing 0**: Significant overall effect

**Clinical relevance**: Helps clinicians and researchers understand the strength and consistency of genetic associations.

### 6. Funnel Plot (`funnel`)
**Purpose**: Detect publication bias and assess the symmetry of effect size distribution.

**What it shows**:
- Effect size vs standard error scatter plot
- Weighted mean effect size line
- 95% and 99% confidence interval lines forming funnel shape

**Interpretation**:
- **Symmetric funnel**: No publication bias
- **Asymmetric funnel**: Potential publication bias
- **Points outside funnel**: Potential outliers or high-precision studies
- **Gap in funnel**: Missing studies with certain effect sizes

**Publication bias indicators**:
- **Missing small studies with negative effects**: Positive publication bias
- **Missing small studies with positive effects**: Negative publication bias
- **Asymmetry test**: Statistical test for funnel plot asymmetry

**Research integrity**: Critical for assessing whether the meta-analysis results are influenced by selective publication of studies.

## Usage

### Basic Usage
```bash
python src/tools/HATK/Visualizer/metaanalPlot.py \
    --meta-file <path_to.meta> \
    --output-prefix <prefix> \
    [options]
```

### Complete Example
```bash
python src/tools/HATK/Visualizer/metaanalPlot.py \
    --meta-file data/output/MetaAnalysis/RA_vs_CD_MetaAnalysis.meta \
    --s1-logistic-result data/output/BMarkerRegression/wtccc_filtered_58C_RA.hatk.300+300_REG_bMGen_wtccc_filtered_58C_RA.hatk.300+300.imgt3320.2field.hg18.assoc.logistic \
    --s2-logistic-result data/examples/MetaAnalysis/RESULT_EXAMPLE_wtccc_filtered_NBS_CD.hatk.300+300.chr6.hg18.assoc.logistic \
    --output-prefix data/output/MetaAnalysis/RA_vs_CD_plots \
    --plot-types qq manhattan effect_dist study_comp forest funnel
```

### Command Line Arguments

#### Required Arguments
- `--meta-file`: Path to the meta-analysis result file (.meta format)
- `--output-prefix`: Prefix for output plot files

#### Optional Arguments
- `--plot-types`: Types of plots to generate (default: all plots)
  - `qq`: Q-Q plot
  - `manhattan`: Manhattan plot
  - `effect_dist`: Effect size distribution plots
  - `study_comp`: Study comparison plots
  - `forest`: Forest plot
  - `funnel`: Funnel plot
- `--s1-logistic-result`: Path to study 1 logistic regression results (required for manhattan, study_comp and forest plots)
- `--s2-logistic-result`: Path to study 2 logistic regression results (required for study_comp and forest plots)
- `--top-n-forest`: Number of top SNPs for forest plot (default: 10)

### Input File Formats

#### Meta-analysis file (.meta)
Tab-separated file with columns:
- `SNP`: Variant identifier
- `BETA`: Effect size
- `SE`: Standard error
- `MetaP`: Meta-analysis p-value

#### Logistic regression files (.assoc.logistic)
PLINK format files with columns:
- `SNP`: Variant identifier
- `OR`: Odds ratio
- `SE`: Standard error
- `BETA`: Effect size (calculated from OR)

## Output Files

The tool generates the following output files:
- `{prefix}_qq.png`: Q-Q plot
- `{prefix}_manhattan.png`: Manhattan plot
- `{prefix}_effect_distribution.png`: Effect size distribution plots
- `{prefix}_study_comparison.png`: Study comparison plots
- `{prefix}_forest.png`: Forest plot
- `{prefix}_funnel.png`: Funnel plot

## Quality Assessment Guidelines

### Good Meta-Analysis Indicators
1. **Q-Q Plot**: λ close to 1.0, points following diagonal
2. **Manhattan Plot**: Clear peaks above significance thresholds, reasonable distribution across genome
3. **Study Comparison**: High correlation between studies (r > 0.7)
4. **Forest Plot**: Overlapping confidence intervals
5. **Funnel Plot**: Symmetric funnel shape
6. **Effect Size Distribution**: Reasonable distribution without extreme outliers

### Warning Signs
1. **High λ inflation**: Population stratification or technical artifacts
2. **Low study correlation**: Inconsistent results between studies
3. **Asymmetric funnel**: Publication bias
4. **Non-overlapping CIs**: High heterogeneity
5. **Extreme effect sizes**: Potential outliers or errors

## Statistical Notes

### Effect Size Interpretation
- **BETA**: Log odds ratio (for binary traits)
- **OR**: Odds ratio (exponentiated BETA)
- **SE**: Standard error of the effect estimate
- **P-value**: Statistical significance

### Heterogeneity Assessment
- **I² statistic**: Percentage of variation due to heterogeneity
- **Q statistic**: Chi-square test for heterogeneity
- **τ²**: Between-study variance

### Publication Bias Detection
- **Egger's test**: Linear regression test for funnel plot asymmetry
- **Begg's test**: Rank correlation test
- **Trim and fill**: Method to estimate missing studies

## References

1. Higgins, J. P., & Thompson, S. G. (2002). Quantifying heterogeneity in a meta-analysis. Statistics in medicine, 21(11), 1539-1558.
2. Egger, M., Smith, G. D., Schneider, M., & Minder, C. (1997). Bias in meta-analysis detected by a simple, graphical test. BMJ, 315(7109), 629-634.
3. Sterne, J. A., & Harbord, R. M. (2004). Funnel plots in meta-analysis. The Stata Journal, 4(2), 127-141.
4. Bland, J. M., & Altman, D. G. (1986). Statistical methods for assessing agreement between two methods of clinical measurement. The lancet, 327(8476), 307-310.

## Citation

If you use this tool in your research, please cite:
```
HLAgent Development Team. (2025). Manhattan Plot Generator for HATK Analysis.
HLA Association Toolkit (HATK) Visualization Suite.
```