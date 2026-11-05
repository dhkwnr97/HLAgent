"""Deterministic synthetic fixtures. These are not biological validation cohorts."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from hlagent.data import inspect_dataset, sha256
from hlagent.models import AnalysisIntent, Goal
from hlagent.storage import Store


def create_demo(store: Store, home: Path, n: int = 240) -> dict:
    rng = np.random.default_rng(20260906)
    project = store.create_project("Synthetic HLA demonstration")
    directory = home / "projects" / project["id"] / "demo"
    directory.mkdir(parents=True, exist_ok=True)
    haplotypes = [("A*01:01", "B*08:01", "DRB1*03:01"),
                  ("A*02:01", "B*07:02", "DRB1*15:01"),
                  ("A*03:01", "B*35:01", "DRB1*04:01"),
                  ("A*02:01", "B*08:01", "DRB1*04:01")]
    indexes = rng.choice(4, size=(n, 2), p=[0.30, 0.30, 0.25, 0.15])
    calls, truth = [], []
    for i, pair in enumerate(indexes):
        for j, locus in enumerate(("A", "B", "DRB1")):
            a, b = haplotypes[pair[0]][j], haplotypes[pair[1]][j]
            calls.append(dict(FID=f"demo{i:04}", IID=f"demo{i:04}", locus=locus, allele1=a, allele2=b))
            truth.append(dict(FID=f"demo{i:04}", IID=f"demo{i:04}", locus=locus, haplotype1=a, haplotype2=b))
    hla = directory / "hla_calls.tsv"
    pd.DataFrame(calls).to_csv(hla, sep="\t", index=False)
    pd.DataFrame(truth).to_csv(directory / "synthetic_phase_truth.tsv", sep="\t", index=False)
    age = rng.uniform(25, 75, n)
    pc1 = rng.normal(size=n)
    dosage = (indexes == 0).sum(axis=1)
    probability = 1 / (1 + np.exp(-(-1 + .7 * dosage + .015 * (age - 50))))
    pheno = directory / "phenotypes.tsv"
    pd.DataFrame({"FID": [f"demo{i:04}" for i in range(n)], "IID": [f"demo{i:04}" for i in range(n)],
                  "case": rng.binomial(1, probability), "trait": .8 * dosage + .03 * age + rng.normal(size=n),
                  "age": age, "PC1": pc1}).to_csv(pheno, sep="\t", index=False)
    rows = []
    # Artificial residue assignments are intentionally not labeled as IPD-IMGT biological sequences.
    alleles = sorted({a for hap in haplotypes for a in hap})
    for index, allele in enumerate(alleles):
        for position in (11, 13):
            rows.append(dict(allele=allele, position=position, residue="AV"[(index + position) % 2]))
    sequence = directory / "synthetic_sequences.tsv"
    pd.DataFrame(rows).to_csv(sequence, sep="\t", index=False)
    a = inspect_dataset(project["id"], str(hla), kind="hla", resolution="2-field", imgt_release="SYNTHETIC-NOT-IPD")
    b = inspect_dataset(project["id"], str(pheno), kind="phenotype")
    c = inspect_dataset(project["id"], str(sequence), kind="sequence", imgt_release="SYNTHETIC-NOT-IPD")
    for dataset in (a, b, c):
        store.put_dataset(dataset)
    intent = AnalysisIntent(question="Synthetic demonstration: HLA association with a simulated trait",
                            goals=[Goal.association, Goal.omnibus], dataset_ids=[a.id], phenotype_id=b.id,
                            sequence_id=c.id, phenotype_column="trait", phenotype_type="continuous",
                            covariates=["age", "PC1"], covariates_confirmed=True, unrelated_confirmed=True)
    design = {"phenotype": "simulated_trait", "phenotype_type": "continuous", "effect_scale": "mean_difference",
              "unit": "synthetic_units", "genome_build": "GRCh37", "resolution": "2-field",
              "imgt_release": "SYNTHETIC-NOT-IPD", "conditioning": [], "covariates": ["age", "PC1"], "strand": "forward"}
    summary_ids = []
    for index in range(3):
        path = directory / f"cohort_{index}.tsv"
        pd.DataFrame({"marker": ["HLA_A*01:01", "HLA_B*08:01"],
                      "effect_allele": ["A*01:01", "B*08:01"],
                      "other_allele": ["NOT_A*01:01", "NOT_B*08:01"],
                      "beta": [.3 + index * .05, -.2 + index * .02], "se": [.1, .15]}).to_csv(path, sep="\t", index=False)
        d = inspect_dataset(project["id"], str(path), kind="summary", metadata={"design": {**design, "cohort": f"synthetic_{index}"}})
        store.put_dataset(d)
        summary_ids.append(d.id)
    (directory / "provenance.json").write_text(json.dumps({"source": "synthetic generator", "seed": 20260906,
        "n": n, "truth_scope": "simulated haplotypes and phenotypes only; no biological accuracy claim",
        "files": {p.name: sha256(p) for p in directory.glob("*.tsv")}}, indent=2))
    return {"project": project, "intent": intent.model_dump(mode="json"), "summary_ids": summary_ids}
