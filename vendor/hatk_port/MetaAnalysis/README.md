# HATK Meta-Analysis Module

## Overview

The Meta-Analysis module for HATK provides functionality to perform inverse-variance weighted meta-analysis on HLA association test results from multiple studies. This module follows the same design patterns as other HATK modules and integrates seamlessly with the HATK pipeline.

## Features

- **Inverse-variance weighted meta-analysis**: Combines effect sizes from multiple studies
- **Automatic allele flipping**: Handles allele orientation differences between studies
- **Flexible input formats**: Supports PLINK and custom logistic regression results
- **YAML configuration**: Easy-to-use configuration files
- **Comprehensive validation**: Input file validation and error checking
- **Detailed reporting**: Summary statistics and top associations

## Installation

The meta-analysis module is included in the HATK package. Required dependencies:
- pandas
- numpy
- scipy
- PyYAML

## Usage

### Command Line Interface

```bash
# Using default configuration file
python src/tools/HATK/Runners/run_metaanal.py

# Using custom configuration file
python src/tools/HATK/Runners/run_metaanal.py my_config.yaml

# With verbose output
python src/tools/HATK/Runners/run_metaanal.py -v
```

### Python API

```python
from src.tools.HATK.MetaAnalysis import run_meta_analysis

# Run meta-analysis
result_df, summary = run_meta_analysis(
    study1_logistic="path/to/study1.assoc.logistic",
    study2_logistic="path/to/study2.assoc.logistic",
    study1_bim="path/to/study1.bim",  # Optional
    study2_bim="path/to/study2.bim",  # Optional
    output_prefix="output/my_meta_analysis"
)
```

## Configuration File

The configuration file (`metaanal_run_config.yaml`) controls all aspects of the analysis:

### Required Parameters

```yaml
# Study 1 Files
_s1_logistic_result: "path/to/study1.assoc.logistic"
_s1_bim: "path/to/study1.bim"  # Optional but recommended

# Study 2 Files  
_s2_logistic_result: "path/to/study2.assoc.logistic"
_s2_bim: "path/to/study2.bim"  # Optional but recommended

# Output Settings
_out: "output/directory"
_output_name: "my_meta_analysis"  # User-defined output name
```

### Optional Parameters

```yaml
# Analysis Settings
_analysis_settings:
  use_allele_flipping: true
  significance_threshold: 0.05
  genome_wide_threshold: 5e-8

# Performance Settings
_performance:
  measure_time: true
  show_progress: true

# Verbosity
_verbose: true
```

## Input File Formats

### Logistic Regression Results

The module accepts two formats:

1. **PLINK format** (`.assoc.logistic`):
   - Standard PLINK logistic regression output
   - Required columns: CHR, SNP, BP, A1, TEST, NMISS, OR, SE, L95, U95, STAT, P

2. **Custom format**:
   - Tab or space-separated file
   - Required columns: SNP, and either (BETA or OR) and (SE or P)

### Marker Information Files (Optional)

1. **BIM format** (`.bim`):
   - Standard PLINK BIM format
   - Columns: CHR SNP GD BP A1 A2

2. **Markers format** (`.markers`):
   - HATK markers format
   - Columns: SNP BP A1 A2

## Output Files

The meta-analysis produces the following output files:

1. **Main results** (`{output_name}.meta`):
   - Tab-separated file with columns:
     - SNP: Variant identifier
     - BETA: Combined effect size
     - SE: Combined standard error
     - MetaP: Meta-analysis p-value

2. **Summary file** (`{output_name}_summary.txt`):
   - Analysis statistics
   - Configuration details
   - Execution time

## Algorithm Details

### Inverse-Variance Weighting

The module implements the standard inverse-variance weighted meta-analysis:

```
Weight for study i: w_i = 1 / SE_i²
Combined effect: β = Σ(β_i × w_i) / Σ(w_i)
Combined SE: SE = sqrt(1 / Σ(w_i))
Z-score: Z = β / SE
P-value: P = 2 × Φ(-|Z|)
```

### Allele Flipping

When marker files are provided, the module:
1. Checks if alleles need complementing (A↔T, C↔G)
2. Determines if effect direction needs flipping
3. Adjusts beta values accordingly

## Error Handling

The module includes comprehensive error handling:
- File existence validation
- Format validation
- Allele mismatch detection
- Missing data handling

## Example Workflow

```bash
# 1. Prepare configuration file
cp src/tools/HATK/Runners/metaanal_run_config.yaml my_analysis.yaml

# 2. Edit configuration with your file paths
# vim my_analysis.yaml

# 3. Run meta-analysis
python src/tools/HATK/Runners/run_metaanal.py my_analysis.yaml

# 4. Check results
# Results will be in the specified output directory
```

## Troubleshooting

### Common Issues

1. **File not found errors**:
   - Check that all paths in the config file are correct
   - Use absolute paths for reliability

2. **Allele mismatch errors**:
   - Ensure BIM files are provided for proper allele flipping
   - Check that marker files match the logistic regression results

3. **No common variants**:
   - Verify that both studies analyzed the same genomic region
   - Check SNP naming conventions

## Future Extensions

The module is designed to be extensible. Planned features:
- Random effects models
- Heterogeneity testing
- Forest plots
- Manhattan plots
- Multiple study support (>2 studies)

## Citation

If you use this module, please cite:
- HATK: [Original HATK publication]
- Meta-analysis method: Inverse-variance weighted meta-analysis

## Support

For issues or questions:
- Check the documentation
- Review the example configuration file
- Contact the HLAgent development team
