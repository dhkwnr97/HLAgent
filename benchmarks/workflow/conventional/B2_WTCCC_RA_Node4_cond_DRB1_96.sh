#!/usr/bin/env bash
# Conventional route for B2_WTCCC_RA_Node4_cond_DRB1_96 (see benchmarks/workflow/conventional.py).
# Paths are relative to one working directory holding the inputs, dictionaries and reference panel.
# HLAgent equivalent: "Run the omnibus test in WTCCC_RA conditioned on HLA-DRB1 amino-acid position 96 (AA_DRB1_96)." + 1 click(s).
set -euo pipefail

# --- Stage D
# PLINK 1.9
plink --bfile wtccc_filtered_58C_RA.hatk.300+300.hg18.chr6.29-34mb --chr 6 --from-mb 29 --to-mb 34 --geno 0.05 --mind 0.05 --maf 0.01 --hwe 1e-6 --make-bed --allow-no-sex --keep-allele-order --out RA.qc

# --- Node1-2, Stage P, Node4
# HATK v2 README, whole pipeline
python HATK.py --hg 18 --chped wtccc_filtered_58C_RA.hatk.300+300.imgt3320.2field.chped --bfile RA.qc --pheno wtccc_filtered_58C_RA.hatk.300+300.phe --pheno-name RA --imgt 3320 --imgt-dir IMGTHLA3320 --multiprocess 4 --out hatk/RA --java-mem 4g --nthreads 4

# --- Node4
# HATK v1 docs 4-1
python3 HATK.py --omnibus --fam hatk/RA.fam --phased hatk/RA.bgl.phased --out omnibus/RA --pheno wtccc_filtered_58C_RA.hatk.300+300.phe --pheno-name RA --condition AA_DRB1_96

# Manual decisions:
#  - confirm the genome build of the genotypes
