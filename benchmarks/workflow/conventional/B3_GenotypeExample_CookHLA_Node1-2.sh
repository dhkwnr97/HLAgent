#!/usr/bin/env bash
# Conventional route for B3_GenotypeExample_CookHLA_Node1-2 (see benchmarks/workflow/conventional.py).
# Paths are relative to one working directory holding the inputs, dictionaries and reference panel.
# HLAgent equivalent: "GenotypeExample only has SNP array genotypes. Impute the classical HLA alleles with CookHLA, build the HLA binary marker panel and test the markers for association." + 2 click(s).
set -euo pipefail

# --- Stage D
# PLINK 1.9
plink --bfile 1958BC.hg19 --chr 6 --geno 0.05 --mind 0.05 --make-bed --allow-no-sex --keep-allele-order --out 1958BC.hg19.qc

# --- Stage I
# CookHLA README (Docker); CookHLA lifts hg19 input down to the hg18 panel itself
docker run --rm --user $(id -u):$(id -g) -v $PWD:/data -w /data dhkwnr97/cookhla@sha256:0b374cef9cc352cfaa7aa5e89ad49d5b6c64274a6eb8100acbb7f6f452f0c5d6 CookHLA.py -i 1958BC.hg19.qc -hg 19 -o out/1958BC+1000G_REF.EUR -ref ref/1000G_REF.EUR.chr6.hg18.29mb-34mb.inT1DGC -gm AGM.1958BC.hg19.COPY.LiftDown_hg18.NoAmbig+1000G_REF.EUR.chr6.hg18.29mb-34mb.inT1DGC.mach_step.avg.clpsB -ae AGM.1958BC.hg19.COPY.LiftDown_hg18.NoAmbig+1000G_REF.EUR.chr6.hg18.29mb-34mb.inT1DGC.aver.erate -mem 4g
# low-confidence calls per gene
awk '$8 < 0.8' out/1958BC+1000G_REF.EUR.MHC.HLA_IMPUTATION_OUT.alleles | cut -d ' ' -f 3 | sort | uniq -c

# --- Node1
# HATK v1 docs 3
python3 HATK.py --nomencleaner --hat HLA_ALLELE_TABLE.imgt3320.hat --hped out/1958BC+1000G_REF.EUR.MHC.HLA_IMPUTATION_OUT.hped --out 1958BC.2field --2field --imgt 3320
# HATK v1 docs 2
python3 HATK.py --bmarkergenerator --variants out/1958BC.hg19.qc.COPY.LiftDown_hg18.NoAmbig --chped 1958BC.2field.chped --out panel/1958BC --hg 18 --dict-AA HLA_DICTIONARY_AA.hg18.imgt3320 --dict-SNPS HLA_DICTIONARY_SNPS.hg18.imgt3320

# --- Node2
# synthetic null phenotype
awk 'BEGIN{print "FID IID SYNTHETIC"; srand(20261023)} {print $1, $2, (rand()<0.5)?2:1}' 1958BC.hg19.qc.fam > null.phe
# HATK v1 docs 4-2
python HATK.py --logistic --input panel/1958BC --pheno-name SYNTHETIC --pheno null.phe --out assoc/1958BC

# --- Node2 plots
# HATK v1 docs 5-1
python HATK.py --manhattan --ar assoc/1958BC.assoc.logistic --imgt 3320 --hg 18 --out plots/1958BC
# HATK v1 docs 5-2
python HATK.py --heatmap --ar assoc/1958BC.assoc.logistic --HLA A --maptable HLA_MAPTABLE_A.hg18.imgt3320.txt --out plots/1958BC
# HATK v1 docs 5-2
python HATK.py --heatmap --ar assoc/1958BC.assoc.logistic --HLA C --maptable HLA_MAPTABLE_C.hg18.imgt3320.txt --out plots/1958BC
# HATK v1 docs 5-2
python HATK.py --heatmap --ar assoc/1958BC.assoc.logistic --HLA DQB1 --maptable HLA_MAPTABLE_DQB1.hg18.imgt3320.txt --out plots/1958BC
# HATK v1 docs 5-2
python HATK.py --heatmap --ar assoc/1958BC.assoc.logistic --HLA DRB1 --maptable HLA_MAPTABLE_DRB1.hg18.imgt3320.txt --out plots/1958BC

# Manual decisions:
#  - identify the genome build (hg19) for CookHLA and pick the hg18 copy of the genotypes for HATK
#  - choose the reference panel and check that an adaptive genetic map matches it
#  - decide how to treat genes the panel cannot impute (DPA1, DPB1, DQA1)
#  - decide what to do about the constant phenotype
