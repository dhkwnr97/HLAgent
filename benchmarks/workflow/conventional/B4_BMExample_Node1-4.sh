#!/usr/bin/env bash
# Conventional route for B4_BMExample_Node1-4 (see benchmarks/workflow/conventional.py).
# Paths are relative to one working directory holding the inputs, dictionaries and reference panel.
# HLAgent equivalent: "Use BMExample: build the HLA marker panel, test association, run stepwise conditional analysis and the omnibus test." + 2 click(s).
set -euo pipefail

# --- Stage D
# rsID-based re-mapping to hg18
awk 'NR==FNR{pos[$2]=$4; next} ($2 in pos){print $2"\t"pos[$2]}' 1000G_REF.EUR.chr6.hg18.29mb-34mb.inT1DGC.bim HAPMAP_CEU.bim > remap.txt
# PLINK 1.9
plink --bfile HAPMAP_CEU --extract remap.txt --update-map remap.txt --make-bed --allow-no-sex --keep-allele-order --out CEU.hg18
# PLINK 1.9
plink --bfile CEU.hg18 --chr 6 --from-mb 29 --to-mb 34 --filter-founders --geno 0.05 --mind 0.05 --maf 0.01 --hwe 1e-6 --make-bed --allow-no-sex --keep-allele-order --out CEU.qc

# --- Node1
# drop untyped DPA1/DPB1 columns (all '0'), which break HATK's positional gene layout
cut -f 1-12,17-22 HAPMAP_CEU_HLA.imgt3320.4field.chped > CEU.noDP.chped
# HATK v1 docs 3
python3 HATK.py --nomencleaner --hat HLA_ALLELE_TABLE.imgt3320.hat --hped CEU.noDP.chped --out CEU.2field --2field --imgt 3320

# --- Node2
# user-written script: no standard tool simulates a spike-in phenotype
python spike_in_phenotype.py --chped CEU.2field.chped --fam CEU.qc.fam --allele DRB1*15:01 --odds-ratio 5 --seed 20261023 --out spike.phe

# --- Node1-2, Stage P, Node4
# HATK v2 README, whole pipeline
python HATK.py --hg 18 --chped CEU.2field.chped --bfile CEU.qc --pheno spike.phe --pheno-name SYNTHETIC --imgt 3320 --imgt-dir IMGTHLA3320 --multiprocess 4 --out hatk/CEU --java-mem 4g --nthreads 4

# --- Node3
# Bonferroni denominator
awk 'NR>1 && $12!="NA"' hatk/CEU.assoc.logistic | wc -l
# round 1 top marker
sort -g -k 12 hatk/CEU.assoc.logistic | head -n 3

# Manual decisions:
#  - recognise that the positions match no standard build and choose a re-mapping strategy
#  - restrict association to founders (family data)
#  - identify untyped genes in the 4-field typing and remove them
#  - decide how to obtain a phenotype for a demonstration run
#  - round 1: compare the top P with the Bonferroni threshold and stop
