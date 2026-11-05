#!/usr/bin/env bash
# Conventional route for B1_WTCCC_RA_Node1-5 (see benchmarks/workflow/conventional.py).
# Paths are relative to one working directory holding the inputs, dictionaries and reference panel.
# HLAgent equivalent: "Run the complete HLA fine-mapping pipeline on WTCCC_RA and then meta-analyze it with NBS_CD." + 1 click(s).
set -euo pipefail

# --- Stage D
# PLINK 1.9
plink --bfile wtccc_filtered_58C_RA.hatk.300+300.hg18.chr6.29-34mb --chr 6 --from-mb 29 --to-mb 34 --geno 0.05 --mind 0.05 --maf 0.01 --hwe 1e-6 --make-bed --allow-no-sex --keep-allele-order --out RA.qc

# --- Node1-2, Stage P, Node4
# HATK v2 README, whole pipeline
python HATK.py --hg 18 --chped wtccc_filtered_58C_RA.hatk.300+300.imgt3320.2field.chped --bfile RA.qc --pheno wtccc_filtered_58C_RA.hatk.300+300.phe --pheno-name RA --imgt 3320 --imgt-dir IMGTHLA3320 --multiprocess 4 --out hatk/RA --java-mem 4g --nthreads 4

# --- Node3
# Bonferroni denominator
awk 'NR>1 && $12!="NA"' hatk/RA.assoc.logistic | wc -l
# round 1 top marker
sort -g -k 12 hatk/RA.assoc.logistic | head -n 3
printf '%s\n' SNPS_DQA1_348_32713561_intron1 > cond.round2.txt
# PLINK 1.9
plink --bfile hatk/RA --pheno wtccc_filtered_58C_RA.hatk.300+300.phe --pheno-name RA --logistic hide-covar --ci 0.95 --condition-list cond.round2.txt --allow-no-sex --keep-allele-order --out round2
# round 2 top marker
sort -g -k 12 round2.assoc.logistic | head -n 3

# --- Node5
# HATK v1 docs 4-3 (not exposed by the v2 command line)
python HATK.py --metaanalysis --s1-logistic-result hatk/RA.assoc.logistic --s1-bim hatk/RA.bim --s2-logistic-result RESULT_EXAMPLE_wtccc_filtered_NBS_CD.hatk.300+300.chr6.hg18.assoc.logistic --s2-bim RESULT_EXAMPLE_wtccc_filtered_NBS_CD.hatk.300+300.chr6.hg18.bim --out meta/RA_CD

# Manual decisions:
#  - confirm the genome build of the genotypes (HATK leaves build consistency to the user)
#  - round 1: compare the top P with the Bonferroni threshold and choose the conditioning marker
#  - round 2: decide to stop
