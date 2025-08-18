# HATK Phasing Pipeline

A comprehensive haplotype phasing pipeline with a clean two-stage architecture that supports multiple input formats and BEAGLE versions.

## 🚀 New Refactored Architecture

The phasing pipeline has been completely refactored following [code refactoring best practices](https://marutitech.com/code-refactoring-best-practices/) to improve maintainability, readability, and extensibility.

### Two-Stage Architecture

**Stage 1: Input Format Conversion**
- Converts various input formats (PLINK, VCF, BEAGLE) to standardized BEAGLE format
- Handles format-specific preprocessing and validation
- Modular design allows easy addition of new input formats

**Stage 2: BEAGLE Phasing with GCtrick**
- Implements the 6-step GCtrick workflow for optimal BEAGLE compatibility
- Supports both BEAGLE 3.3.2 (local jar) and BEAGLE 5.4+ (system command)
- Comprehensive parameter control and resource management

## 🎯 Key Features

### Multiple Input Formats
- **PLINK** (.bed/.bim/.fam) - Standard genotype format
- **VCF** (.vcf/.vcf.gz) - Variant Call Format
- **BEAGLE** (.bgl + .markers) - Native BEAGLE format

### BEAGLE Version Support
- **BEAGLE 3.3.2** (recommended for HATK compatibility)
  - Uses local jar file: `src/beagle.jar`
  - Avoids same base position marker issues
  - Optimal for Omnibus Test integration

- **BEAGLE 5.4+** (latest features)
  - Uses system-installed BEAGLE command
  - Advanced phasing algorithms
  - Better performance for large datasets

### GCtrick Workflow
The pipeline implements a mandatory 6-step GCtrick workflow for optimal BEAGLE compatibility:

1. **GCtrick**: Convert alleles to G/C for BEAGLE compatibility
2. **beagle2vcf**: Convert BEAGLE to VCF format
3. **beagle phasing**: Perform haplotype phasing
4. **vcf2beagle**: Convert phased VCF back to BEAGLE
5. **FixBglHeader**: Fix BEAGLE header format
6. **unGCtrick**: Restore original alleles

## 🛠 Installation & Requirements

### Dependencies
- Python 3.7+
- Java 8+ (for BEAGLE execution)
- Required tools in `dependency/` folder:
  - `beagle2vcf.jar`
  - `vcf2beagle.jar`
  - `linkage2beagle.jar` (for PLINK conversion)

### BEAGLE Installation
**Option 1: BEAGLE 3.3.2 (Recommended)**
- Already included: `src/tools/HATK/Phasing/src/beagle.jar`
- No additional installation required

**Option 2: BEAGLE 5.4+**
```bash
# Install via conda
conda install -c bioconda beagle

# Or download from official site
# https://faculty.washington.edu/browning/beagle/beagle.html
```

## 📖 Usage Examples

### Basic Usage

```python
from src.tools.HATK.Phasing import HATK_Phasing

# PLINK input
result = HATK_Phasing(
    out_prefix="results/my_phased_data",
    bfile="data/my_genotypes",  # .bed/.bim/.fam files
    beagle_version="3.3.2",
    java_mem="4G",
    nthreads=4
)

# VCF input
result = HATK_Phasing(
    out_prefix="results/my_phased_data",
    vcf="data/my_genotypes.vcf.gz",
    beagle_version="5.4+",
    java_mem="8G",
    nthreads=8
)

# BEAGLE input
result = HATK_Phasing(
    out_prefix="results/my_phased_data",
    bgl="data/my_genotypes.bgl",
    markers="data/my_genotypes.markers",
    beagle_version="3.3.2"
)
```

### Command Line Usage

```bash
# PLINK input with BEAGLE 3.3.2
python -m src.tools.HATK.Phasing \
    --bfile data/my_genotypes \
    --out results/my_phased_data \
    --beagle-version 3.3.2 \
    --java-mem 4G \
    --nthreads 4

# VCF input with BEAGLE 5.4+ and custom parameters
python -m src.tools.HATK.Phasing \
    --vcf data/my_genotypes.vcf.gz \
    --out results/my_phased_data \
    --beagle-version 5.4+ \
    --beagle-params "iterations=15,ne=50000" \
    --java-mem 8G \
    --nthreads 8 \
    --save-intermediates

# BEAGLE input
python -m src.tools.HATK.Phasing \
    --bgl data/my_genotypes.bgl \
    --markers data/my_genotypes.markers \
    --out results/my_phased_data \
    --beagle-version 3.3.2
```

### Advanced Usage - Stage by Stage

```python
from src.tools.HATK.Phasing import InputFormatConverter, BEAGLEPhasingEngine

# Stage 1: Input conversion
converter = InputFormatConverter()
bgl_file, markers_file, input_format = converter.convert_to_beagle(
    bfile="data/my_genotypes",
    out_prefix="temp/converted",
    java_mem="2G"
)

# Stage 2: BEAGLE phasing
phasing_engine = BEAGLEPhasingEngine(beagle_version="3.3.2")
final_phased = phasing_engine.run_full_phasing_pipeline(
    bgl_file=bgl_file,
    markers_file=markers_file,
    out_prefix="results/my_phased_data",
    java_mem="4G",
    nthreads=4,
    beagle_params={"niterations": "20", "nsamples": "8"}
)
```

## ⚙️ Configuration Options

### BEAGLE Parameters

**BEAGLE 3.3.2 Parameters:**
- `niterations`: Number of phasing iterations (default: 10)
- `nsamples`: Number of haplotype samples (default: 4)
- `verbose`: Enable detailed logging (true/false)
- `seed`: Random seed for reproducibility

**BEAGLE 5.4+ Parameters:**
- `iterations`: Number of phasing iterations (default: 12)
- `ne`: Effective population size (default: 100000)
- `window`: Window size in cM (default: 40.0)
- `overlap`: Overlap between windows in cM (default: 2.0)

### Resource Management
- `java_mem`: Java heap memory (e.g., "1G", "4G", "8G")
- `nthreads`: Number of processing threads
- `save_intermediates`: Keep intermediate files for debugging

## 📊 Output Files

The pipeline generates several output files:

- `{prefix}.bgl.phased` - **Final phased BEAGLE file** (main result)
- `{prefix}.phased.vcf.gz` - Phased VCF file (intermediate)
- `{prefix}.markers` - Markers file (if converted from other formats)

Optional intermediate files (with `--save-intermediates`):
- `{prefix}.P2B.bgl/.markers` - PLINK to BEAGLE conversion
- `{prefix}.V2B.bgl.gz/.markers` - VCF to BEAGLE conversion
- Various GCtrick intermediate files

## 🔄 Migration from Legacy Code

### Old Usage (Deprecated)
```python
# OLD - Don't use this
from src.tools.HATK.Phasing.BEAGLE_Phase import Phasing_wrapper
result = Phasing_wrapper(bgl, markers, out_prefix, beagle2vcf, vcf2beagle, beagle)
```

### New Usage (Recommended)
```python
# NEW - Use this instead
from src.tools.HATK.Phasing import HATK_Phasing
result = HATK_Phasing(out_prefix=out_prefix, bgl=bgl, markers=markers)
```

## 🐛 Troubleshooting

### Common Issues

**1. BEAGLE jar file not found**
```
Error: beagle.jar not found at src/tools/HATK/Phasing/src/beagle.jar
```
- Ensure BEAGLE 3.3.2 jar file is present in the correct location
- Or use `--beagle-version 5.4+` with system BEAGLE

**2. Dependency jar files missing**
```
Error: 'beagle2vcf.jar' module can't be found
```
- Download required jar files from BEAGLE utilities
- Place them in `src/tools/HATK/dependency/` folder

**3. Java memory issues**
```
Error: Java heap space
```
- Increase `--java-mem` parameter (e.g., `--java-mem 8G`)
- Monitor system memory usage

**4. Input file format errors**
```
Error: No valid input format detected
```
- Ensure input files exist and have correct extensions
- Use only one input format at a time
- For BEAGLE input, both `--bgl` and `--markers` are required

## 📚 References

- [BEAGLE Official Website](https://faculty.washington.edu/browning/beagle/beagle.html)
- [BEAGLE 3.3.2 Documentation](src/about_beagle3.3.2.md)
- [BEAGLE 5.4 Documentation](src/about_beagle5.4.md)
- [Code Refactoring Best Practices](https://marutitech.com/code-refactoring-best-practices/)

## 🤝 Contributing

When contributing to this module:

1. Follow the two-stage architecture pattern
2. Add comprehensive docstrings and type hints
3. Include error handling and validation
4. Update this README with new features
5. Maintain backward compatibility when possible

## 📄 License

This module is part of the HATK project. Please refer to the main project license for usage terms. 