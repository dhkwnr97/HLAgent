# CookHLA: Accurate HLA Imputation Docker Container

🧬 **An accurate and efficient HLA imputation method in a ready-to-use Docker container**

## Overview

CookHLA is a state-of-the-art method for Human Leukocyte Antigen (HLA) imputation that substantially improves accuracy over previous methods. This Docker container provides a complete, ready-to-run environment for CookHLA analysis without the need for complex dependency management.

## 📚 Citation

**Please cite the following paper when using CookHLA:**

S. Cook, W. Choi, H. Lim, Y. Luo, K. Kim, X. Jia, S. Raychaudhuri and B. Han, CookHLA: Accurate Imputation of Human Leukocyte Antigens. https://www.nature.com/articles/s41467-021-21541-5

## 🔬 Key Features

- **Improved Accuracy**: Uses Beagle v5 HMM for enhanced imputation performance
- **Local Variability Handling**: Accounts for highly polymorphic exons (exon 2/3/4 in Class I and 2/3 in Class II)
- **Adaptive Genetic Map**: Learns data-specific LD structure within MHC region
- **Multiple Markers**: Consensus posterior probabilities from repeated analyses

## 🐳 Container Specifications

**Base Image**: `mambaorg/micromamba:debian11-slim`

### Pre-installed Packages

- **Python 3.8** with pandas, numpy
- **Bioinformatics Tools**: PLINK, pyliftover
- **System Software**: Perl, R, Java, tcsh
- **Container Management**: micromamba environment

## 🚀 Quick Start

### Option 1: With Pre-generated AGM Files

If you have Adaptive Genetic Map files (`.aver.erate` and `.mach_step.avg.clpsB`):

```bash
docker run --user root \
  -v /path/to/your/data:/data \
  --rm dhkwnr97/cookhla:latest \
  CookHLA.py \
  -i /data/1958BC.hg19 \
  -hg 19 \
  -o /data/MyHLAImputation/1958BC+HM_CEU_REF \
  -ref /data/HM_CEU_REF \
  -gm /data/AGM.1958BC+HM_CEU_REF.mach_step.avg.clpsB \
  -ae /data/AGM.1958BC+HM_CEU_REF.aver.erate \
  -mem 4g \
  -mp 4
```

### Option 2: Auto-generate AGM Files (Recommended)

If you don't have AGM files, CookHLA will automatically generate them:

```bash
docker run --user root \
  -v /path/to/your/example/data:/data \
  -v /path/to/your/reference/data:/ref \
  --rm dhkwnr97/cookhla:latest \
  CookHLA.py \
  -i /data/1958BC.hg19 \
  -hg 19 \
  -o /data/MyHLAImputation/1958BC+1000G_REF.EUR \
  -ref /ref/1000G_REF.EUR.chr6.hg18.29mb-34mb.inT1DGC \
  -mem 4g \
  -mp 4
```

## 📖 Command Line Arguments

| Argument | Description | Required |
|----------|-------------|----------|
| `-i` | Input target genotype data (PLINK format prefix) | ✅ |
| `-hg` | Human genome version of INPUT data (18, 19, or 38) | ✅ |
| `-o` | Output file prefix | ✅ |
| `-ref` | Reference panel prefix (SNP2HLA format) | ✅ |
| `-gm` | Adaptive genetic map file (`.mach_step.avg.clpsB`) | Optional* |
| `-ae` | Average error rate file (`.aver.erate`) | Optional* |
| `-mem` | Memory allocation per core (e.g., 2g, 4g) | ✅ |
| `-mp` | Number of cores for multiprocessing (default=1) | Optional |
| `-bgl4` | Use Beagle4 instead of Beagle5 | Optional |

*If `-gm` and `-ae` are not provided, CookHLA automatically generates AGM files.

## 🧬 Adaptive Genetic Map (AGM) Generation

### Automatic Generation
When `-gm` and `-ae` arguments are omitted, CookHLA automatically:
1. Generates AGM using the MakeGeneticMap module
2. Creates `AGM.{target}+{reference}.aver.erate` and `AGM.{target}+{reference}.mach_step.avg.clpsB` files
3. Uses these files for imputation

### Sample Requirements
- **Minimum**: 100 samples each from target and reference panels (200 total)
- **Fallback**: If target < 100 samples, uses 200 samples from reference
- **Failure**: If both target and reference < 100 samples

### Manual AGM Generation
For custom AGM generation:

```bash
docker run --user root \
  -v /path/to/data:/data \
  -v /path/to/reference:/ref \
  --rm dhkwnr97/cookhla:latest \
  python -m MakeGeneticMap \
  -i /data/1958BC.hg19 \
  -hg 19 \
  -ref /ref/1000G_REF.EUR.chr6.hg18.29mb-34mb.inT1DGC \
  -o /data/MyAGM/1958BC+1000G_REF.EUR
```

## 📁 File Formats

### Input Requirements
- **Target Data**: PLINK format files (.bed, .bim, .fam)
- **Reference Panel**: PLINK format or Beagle format files
- **AGM Files** (optional): `.aver.erate` and `.mach_step.avg.clpsB`

### Output Files
- **HLA Alleles**: `.alleles` file with imputed HLA types
- **PLINK Format**: `.hped` file (PLINK PED-like format)
- **Quality Metrics**: Posterior probabilities and confidence scores
- **Log Files**: Detailed execution logs

### Output File Columns (`.alleles` file)
1. Family ID (FID)
2. Individual ID (IID)  
3. HLA gene
4. 2-digit (1-field) allele pair
5. 4-digit (2-field) allele pair
6. Posterior probability of allele 1
7. Posterior probability of allele 2
8. Confidence score

## 🔧 Advanced Usage

### Interactive Shell
```bash
docker run -it --user root \
  -v /path/to/data:/data \
  dhkwnr97/cookhla:latest bash
```

### Version Information
```bash
docker run --rm dhkwnr97/cookhla:latest --version
```

### Help Information
```bash
docker run --rm dhkwnr97/cookhla:latest --help
```

## ⚠️ Important Notes

- **User Permissions**: Use `--user root` flag for file system access
- **Memory Requirements**: Allocate sufficient memory per core (2-4GB recommended)
- **Data Organization**: Input must be PLINK binary format (.bed, .bim, .fam)
- **Sample Size**: Verify adequate sample sizes for reliable AGM generation
- **Genome Coordinates**: Target data will be automatically lifted to hg18 if needed
- **SNP Region**: CookHLA uses only SNPs in chr6:29-34Mb region

## 🆘 Support

For issues and questions:
- **Original CookHLA**: https://github.com/WansonChoi/CookHLA
- **Docker Container**: Report issues through Docker Hub

## 📄 License

The CookHLA Software is freely available for **non-commercial academic research use**. For other usage, contact Buhm Han at buhm.han@snu.ac.kr (patent pending).

## 🔗 Related Tools

- **HATK**: For downstream amino acid analysis (https://github.com/WansonChoi/HATK)
- **SNP2HLA**: Predecessor method for HLA imputation
- **1000 Genomes Reference Panels**: Built-in support for AFR, AMR, EAS, EUR, SAS populations

---

**Built with ❤️ for the genomics community**