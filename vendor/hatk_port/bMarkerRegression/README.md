# SmartRegression Module

An intelligent regression module for HLAgent that automatically determines whether to use linear or logistic regression based on the phenotype data. This module integrates with HATK (HLA Analysis Toolkit) and uses PLINK for association analysis.

## Features

- **Automatic Regression Type Selection**: Intelligently detects whether phenotype data is binary or continuous and selects the appropriate regression method
- **Phenotype Analysis**: Comprehensive analysis of phenotype distribution with validation
- **HLA-Specific Analysis**: Special handling for HLA variants and association analysis
- **Multiple Input Formats**: Support for both .fam file phenotypes and external phenotype files
- **Covariate Support**: Integration with covariate files for adjusted analysis
- **Result Processing**: Advanced result parsing, filtering, and export capabilities
- **HATK Integration**: Seamless integration with existing HATK analysis pipeline
- **YAML Configuration**: Easy-to-use YAML configuration for analysis setup

## Installation

The SmartRegression module is part of the HATK bMarkerRegression toolkit. No separate installation is required if you have the HATK framework.

### Dependencies

```bash
pip install pandas numpy pyyaml
```

External tools required:
- PLINK (v1.9 or later)

## Usage

### Using YAML Configuration (Recommended)

1. Create or modify a YAML configuration file (`bmarkerregression_run_config.yaml`):

```yaml
# Required Parameters
_bfile_prefix: "data/examples/mydata"
_out: "data/output/BMarkerRegression"

# Optional Parameters
_pheno_file: "data/phenotypes.txt"
_pheno_name: "Disease_Status"
_covar_file: "data/covariates.txt"
_covar_names: ["PC1", "PC2", "PC3", "Age", "Sex"]

# Analysis Configuration
_analysis_settings:
  automatic_phenotype_detection: true
  regression_type_selection: "automatic"
  hla_optimized: true
```

2. Run the analysis using `run_bmarkerregression.py`:

```bash
# Using default config file
python src/tools/HATK/Runners/run_bmarkerregression.py

# Using custom config file
python src/tools/HATK/Runners/run_bmarkerregression.py my_config.yaml

# With verbose output
python src/tools/HATK/Runners/run_bmarkerregression.py -c config.yaml -v
```

### Python API Usage

```python
from SmartRegression import SmartRegression

# Initialize SmartRegression
smart_reg = SmartRegression(
    bfile_prefix="data/mydata",
    output_prefix="results/myanalysis",
    pheno_file="phenotypes.txt",
    pheno_name="Disease_Status",
    covar_file="covariates.txt",
    covar_names=["PC1", "PC2", "PC3", "Age", "Sex"],
    verbose=True
)

# Run complete analysis
assoc_file, summary = smart_reg.run_complete_analysis()

# Or run step by step
phenotype_type = smart_reg.analyze_phenotype()
assoc_file = smart_reg.run_regression()
results = smart_reg.parse_results()
summary = smart_reg.generate_summary()
```

## Key Methods

### Core Analysis Methods

- `analyze_phenotype()`: Automatically detect phenotype type (binary/continuous)
- `run_regression()`: Execute appropriate regression analysis using PLINK
- `parse_results()`: Parse association results and add computed statistics
- `run_complete_analysis()`: Execute full analysis pipeline

### Utility Methods

- `filter_results_by_significance(p_threshold)`: Filter results by significance
- `get_hla_specific_results()`: Extract HLA-specific variants
- `get_top_associations(n, by_hla)`: Get top N associations
- `create_manhattan_data()`: Prepare data for Manhattan plots
- `export_results(format, filename)`: Export results in various formats
- `validate_phenotype_distribution()`: Validate and describe phenotype

## Output Files

### Association Results
- `.assoc.logistic` (for binary phenotypes)
- `.assoc.linear` (for continuous phenotypes)

### Summary Files
- `*_summary.json`: Comprehensive analysis summary
- `*_results.csv/tsv`: Exported results in tabular format
- `smart_regression_summary.txt`: Detailed analysis summary

### Log Files
- `*.log`: PLINK execution logs and analysis details

## Integration with HATK

The SmartRegression module is designed to work seamlessly with other HATK components:

```python
# Integration example with bMarkerGenerator output
from SmartRegression import SmartRegression

# Use bMarkerGenerator output as input
smart_reg = SmartRegression(
    bfile_prefix="bMGen_output.hg18",
    output_prefix="hla_association_results",
    chr=6,
    from_mb=29,
    to_mb=34,
    verbose=True
)

# Run HLA-focused analysis
assoc_file, summary = smart_reg.run_complete_analysis()

# Extract HLA-specific results
hla_results = smart_reg.get_hla_specific_results()
top_hla = smart_reg.get_top_associations(n=10, by_hla=True)
```

## Testing

Run the test suite to verify functionality:

```bash
python -m pytest test_smart_regression.py -v
```

## Error Handling

The module includes comprehensive error handling for:
- Missing input files
- Invalid phenotype data
- PLINK execution errors
- File I/O issues
- Data format problems
- Configuration validation

## Performance Considerations

- **Memory Usage**: Efficient pandas operations for large datasets
- **PLINK Integration**: Leverages PLINK's optimized algorithms
- **HLA Region Focus**: Default chromosome 6, positions 29-34 Mb
- **Parallel Processing**: PLINK handles multi-threading internally

## Compatibility

- **Python**: 3.6+
- **PLINK**: v1.9+
- **Operating Systems**: Linux, macOS, Windows (with WSL)
- **Data Formats**: PLINK binary format (.bed/.bim/.fam)

## Contributing

This module is part of the HLAgent/HATK ecosystem. For contributions:

1. Follow the existing code style and patterns
2. Add comprehensive tests for new features
3. Update documentation for any API changes
4. Ensure compatibility with HATK pipeline

## License

This module is distributed under the same license as the HATK framework.

## Support

For questions or issues:
- Check the test files for usage examples
- Review the YAML configuration examples
- Consult the HATK documentation for integration details

## Changelog

### Version 1.0.0
- Initial release with automatic regression type detection
- Full PLINK integration for association analysis
- Comprehensive phenotype validation
- HLA-specific analysis capabilities
- Export and visualization support
- YAML configuration support
- Extensive test coverage