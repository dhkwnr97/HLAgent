# Manhattan Plot Generator for HATK Analysis

This tool generates interactive Manhattan plots for both logistic regression and omnibus test results from HATK analysis, with comprehensive support for HLA-specific analysis and exon annotations.

## Features

- **Interactive Plotly visualizations** with hover information and zoom capabilities
- **HLA region focus** with exon structure annotations
- **Multiple plot types**: Regression and Omnibus test results
- **Comprehensive marker categorization** with color coding
- **Significance threshold lines** (genome-wide, suggestive, nominal)
- **Top signal annotations** for significant markers
- **Export options**: HTML (interactive), PNG, PDF, SVG
- **Performance optimization** with data filtering and sampling

## Installation Requirements

```bash
pip install pandas numpy matplotlib plotly seaborn
```

## Usage

### Basic Command Structure

```bash
python manhattanPlot.py -i <input_file> -o <output_dir> -t <type> [options]
```

### Required Arguments

- `-i, --input`: Input file path (`.assoc.logistic` or `.omnibus`)
- `-o, --output`: Output directory path
- `-t, --type`: Analysis type (`regression` or `omnibus`)

### Optional Arguments

- `--format`: Output format (`html`, `png`, `pdf`, `svg`) - default: `html`
- `--title`: Custom plot title
- `--hla-region`: Focus on HLA region (chr6:29-34Mb) with exon annotations
- `--verbose`: Enable verbose logging

## Examples

### 1. Basic Regression Plot

```bash
python manhattanPlot.py \
    -i data/output/BMarkerRegression/wtccc_filtered_58C_RA.hatk.300+300_REG_bMGen_wtccc_filtered_58C_RA.hatk.300+300.imgt3320.2field.hg18.assoc.logistic \
    -o data/output/BMarkerRegression \
    -t regression
```

### 2. HLA Region Focused Plot (Recommended for HLA Analysis)

```bash
python manhattanPlot.py \
    -i data/output/BMarkerRegression/wtccc_filtered_58C_RA.hatk.300+300_REG_bMGen_wtccc_filtered_58C_RA.hatk.300+300.imgt3320.2field.hg18.assoc.logistic \
    -o data/output/BMarkerRegression \
    -t regression \
    --hla-region
```

### 3. Omnibus Test Plot

```bash
python manhattanPlot.py \
    -i data/output/OmnibusTest/omnibus_results.omnibus \
    -o data/output/OmnibusTest \
    -t omnibus
```

### 4. Static PNG Output

```bash
python manhattanPlot.py \
    -i data/output/BMarkerRegression/wtccc_filtered_58C_RA.hatk.300+300_REG_bMGen_wtccc_filtered_58C_RA.hatk.300+300.imgt3320.2field.hg18.assoc.logistic \
    -o data/output/BMarkerRegression \
    -t regression \
    --hla-region \
    --format png
```

### 5. Custom Title and Verbose Output

```bash
python manhattanPlot.py \
    -i data/output/BMarkerRegression/wtccc_filtered_58C_RA.hatk.300+300_REG_bMGen_wtccc_filtered_58C_RA.hatk.300+300.imgt3320.2field.hg18.assoc.logistic \
    -o data/output/BMarkerRegression \
    -t regression \
    --hla-region \
    --title "HLA Association Analysis - Rheumatoid Arthritis" \
    --verbose
```

## Input File Formats

### Logistic Regression Results (`.assoc.logistic`)

Required columns:
- `CHR`: Chromosome number
- `BP`: Base pair position
- `SNP`: SNP identifier
- `P`: P-value

Optional columns:
- `OR`: Odds ratio
- `SE`: Standard error
- `BETA`: Beta coefficient

Example format:
```
CHR     BP      SNP     P       OR      SE      BETA
6       30018537        AA_A_9_30018537_F       0.001   1.5     0.2     0.4
6       30018538        HLA_A*01:01      0.0001  2.1     0.3     0.7
```

### Omnibus Test Results (`.omnibus`)

Required columns:
- `Variant`: Variant identifier
- `log10_P`: Log10 of P-value

Optional columns:
- `deltaDeviance`: Change in deviance
- `deltaDF`: Change in degrees of freedom
- `Residues`: Amino acid residues

Example format:
```
Variant log10_P  deltaDeviance deltaDF Residues
AA_A_9  -4.5     12.3          2       F
INS_AA_C_300x301_31345772      -3.2     8.1           1       -
```

## Output Files

### HTML Output (Default)
- Interactive plot with zoom, pan, and hover capabilities
- Metadata file with analysis parameters and summary statistics
- Static preview image (PNG)

### Static Outputs (PNG/PDF/SVG)
- High-resolution publication-ready figures
- Suitable for presentations and manuscripts

## HLA Region Focus

When using `--hla-region`:

- **Focus**: Chromosome 6, positions 28.8-34.2 Mb
- **Exon annotations**: Shaded regions showing HLA gene structure
- **Start codon markers**: Triangle markers indicating translation start sites
- **Strand information**: Color-coded by DNA strand (+/-)
- **Enhanced visualization**: Optimized for HLA-specific analysis

## Marker Categories and Colors

The tool automatically categorizes markers and assigns colors:

- **HLA_Allele** (Gold): HLA allele markers (e.g., `HLA_A*01:01`)
- **AA** (Red): Amino acid markers (e.g., `AA_A_9_30018537_F`)
- **DNA_Intragenic** (Dark Grey): Intragenic DNA markers
- **DNA_Intergenic** (Light Grey): Intergenic DNA markers
- **dbSNP** (Royal Blue): dbSNP markers (e.g., `rs12345`)
- **Insertion** (Dark Orange): Insertion markers
- **Unknown** (Grey): Unclassified markers

## Significance Thresholds

The plot includes standard GWAS significance lines:

- **Genome-wide significance**: P = 5×10⁻⁸ (red solid line)
- **Suggestive significance**: P = 1×10⁻⁵ (orange dashed line)
- **Nominal significance**: P = 0.05 (grey dotted line, shown when appropriate)

## Performance Optimization

For large datasets, the tool automatically:

- **Filters data**: Keeps all significant signals (P ≤ 0.05)
- **Samples non-significant**: Randomly samples remaining points for performance
- **Removes duplicates**: Keeps most significant marker at each position
- **Optimizes rendering**: Sorts data for efficient plotting

## Troubleshooting

### Common Issues

1. **File not found error**
   - Ensure input file path is correct
   - Check file permissions

2. **Missing columns error**
   - Verify input file has required columns
   - Check file format (tab-separated for logistic, space-separated for omnibus)

3. **No data in HLA region**
   - Ensure data contains chromosome 6 markers
   - Check position range (28.8-34.2 Mb for HLA region)

4. **Memory issues with large files**
   - Use `--verbose` to monitor data processing
   - Consider filtering input data before plotting

### Debug Mode

Use `--verbose` flag for detailed logging:

```bash
python manhattanPlot.py -i input.assoc.logistic -o output/ -t regression --verbose
```

## Integration with HATK Pipeline

This tool is designed to work seamlessly with HATK analysis outputs:

1. **BMarkerRegression**: Use `.assoc.logistic` output files
2. **OmnibusTest**: Use `.omnibus` output files
3. **MetaAnalysis**: Use `.meta` output files (convert to required format)

## Citation

If you use this tool in your research, please cite:

```
HLAgent Development Team. (2025). Manhattan Plot Generator for HATK Analysis.
HLA Association Toolkit (HATK) Visualization Suite.
```