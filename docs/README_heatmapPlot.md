# Heatmap Plot Generator for HATK Analysis

This tool generates interactive and static heatmaps of HLA amino acid and allele associations from HATK analysis results. It provides a clear visual summary of which amino acid positions and HLA alleles are associated with a given phenotype.

## Features

- **Dual Visualization Modes**: Supports both interactive `Plotly` heatmaps and publication-quality static `Matplotlib` heatmaps.
- **Comprehensive View**: Displays amino acid-level associations and overall HLA allele significance side-by-side.
- **Clear Annotations**: The color scale explicitly indicates "Risk" (OR > 1) and "Protective" (OR < 1) associations.
- **Highly Configurable**: All aspects of the analysis and visualization are controlled through a single, easy-to-edit YAML configuration file.
- **HATK Compatibility**: Generates intermediate files (`.map.txt`, `.assoc.txt`, `.alleleP.txt`) that are compatible with the original HATK pipeline.
- **Memory Efficient**: Optimized for processing large association datasets without consuming excessive memory.

## Installation Requirements

```bash
pip install pandas numpy matplotlib plotly seaborn pyyaml
```

## Usage

### Basic Command Structure

The tool is executed via the `run_heatmapPlot.py` script, which takes a YAML configuration file as an argument.

```bash
python src/tools/HATK/Runners/run_heatmapPlot.py [path_to_config_file]
```

- If no config file is specified, it defaults to `heatmap_run_config.yaml` in the same directory as the runner script.
- All parameters are controlled within the YAML file.

### Command-Line Options

The runner script has a few helpful command-line flags:

- `--validate-only`: Validates the configuration file for correctness without running the full analysis.
- `--verbose`: Enables detailed logging output to the console, overriding the setting in the YAML file.

## Configuration (`heatmap_run_config.yaml`)

All analysis parameters are set in the configuration file.

### Key Parameters

- `_assoc_file`: Path to the logistic regression association file.
- `_maptable_dir`: Directory containing the HLA maptable files.
- `_output_dir`: Directory where the output heatmaps will be saved.
- `_hla_genes`: A list of HLA genes to analyze (e.g., `["A", "B", "C"]`).
- `_imgt_version`: The IMGT version of the maptables (e.g., `"3320"`).
- `_genome_build`: The genome build of the maptables (e.g., `"hg18"`).
- `_visualization`:
    - `use_plotly`: `true` for interactive HTML, `false` for static PNG.
    - `save_intermediates`: `true` to save HATK-compatible intermediate files.
- `_figure_settings`: Control figure dimensions, font sizes, and colors.
- `_data_processing`:
    - `max_pvalue_display`: Sets the range of the color bar (e.g., a value of `5` sets the scale from -5 to +5).

## Examples

### 1. Basic Interactive Plot for a Single Gene

Edit `heatmap_run_config.yaml`:
```yaml
_hla_genes: ["A"]
_visualization:
  use_plotly: true
```
Then run:
```bash
python src/tools/HATK/Runners/run_heatmapPlot.py
```

### 2. Static PNG Plots for Multiple Genes

Edit `heatmap_run_config.yaml`:
```yaml
_hla_genes: ["B", "DRB1"]
_visualization:
  use_plotly: false
```
This will generate `heatmap_B.png` and `heatmap_DRB1.png` in the output directory.

### 3. Adjusting the Color Scale

To make subtle associations more visible, reduce the color scale range.

Edit `heatmap_run_config.yaml`:
```yaml
_data_processing:
  max_pvalue_display: 2.5
```

## Input File Formats

### 1. Association Results (`.assoc.logistic`)

A space-separated file containing logistic regression results.
**Required columns**: `SNP`, `A1`, `OR`, `P`.

- The `SNP` column must contain identifiers for both amino acids and HLA alleles.
  - Amino Acid Example: `AA_A_-15_30018338_exon1`
  - HLA Allele Example: `HLA_A*01:01`

### 2. HLA Maptable (`HLA_MAPTABLE_...`)

A tab-separated file that maps HLA alleles to their amino acid sequences.
- **Rows**: HLA allele names.
- **Columns**: A multi-level header describing amino acid positions.
- **File Naming Convention**: The tool finds the correct file using the pattern `HLA_MAPTABLE_{hla_gene}.{genome_build}.imgt{imgt_version}.txt`.

## Output Files

### Interactive HTML Output (Default)

- An interactive plot (`heatmap_{gene}.html`) with hover details, zoom, and pan.
- Allele names and amino acid characters are displayed directly on the heatmap.

### Static PNG Output

- A high-resolution, publication-ready figure (`heatmap_{gene}.png`).
- Includes a bottom color bar with "Higher Risk" and "Higher Protective" annotations.

### Intermediate Files

If `save_intermediates: true`, three HATK-compatible files are generated for each gene:
- `{output_prefix}_{gene}.map.txt`: The filtered amino acid sequence matrix.
- `{output_prefix}_{gene}.assoc.txt`: The matrix of signed -log10(p) values.
- `{output_prefix}_{gene}.alleleP.txt`: The significance values for each HLA allele.

## Troubleshooting

### Common Issues

1.  **FileNotFoundError**:
    -   Ensure the `_assoc_file` path is correct.
    -   Verify that the `_maptable_dir` contains the required maptable files and that the `_hla_genes`, `_genome_build`, and `_imgt_version` in the config match the filenames.

2.  **No matching markers/alleles found**:
    -   This error occurs if the HLA alleles in the association file do not match those in the maptable. Check for consistent allele nomenclature.
    -   Ensure the association file contains `AA_` markers for the specified genes.

3.  **Type Errors (e.g., `'>' not supported...`)**:
    -   This usually indicates a data formatting issue. Ensure the `P` and `OR` columns in your association file are valid numbers. The script is designed to handle this, but malformed input can still cause issues.

Use the `--verbose` flag to get detailed logs for diagnosing problems.

## Integration with HATK Pipeline

This tool is a direct visualizer for the outputs of the **BMarkerRegression** module in HATK. The `.assoc.logistic` file from that module can be used as the primary input for this script.

## Citation

If you use this tool in your research, please consider citing:

```
HLAgent Development Team. (2025). Heatmap Plot Generator for HATK Analysis.
HLA Association Toolkit (HATK) Visualization Suite.
``` 