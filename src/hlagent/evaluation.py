"""Evaluation metrics with explicit truth scope; no substitute for independent biological truth."""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd


def genotype_accuracy(truth: pd.DataFrame, predicted: pd.DataFrame, strata: pd.DataFrame | None = None):
    keys = ["FID", "IID", "locus"]
    for frame in (truth, predicted):
        if frame.duplicated(keys).any():
            raise ValueError("Truth/prediction must have unique sample/locus rows")
    joined = truth.merge(predicted, on=keys, how="left", suffixes=("_truth", "_pred"), validate="one_to_one")
    if strata is not None:
        joined = joined.merge(strata, on=["FID", "IID"], how="left", validate="many_to_one")
    rows = []
    group_keys = ["locus"] + (["ancestry"] if "ancestry" in joined else [])
    for key, group in joined.groupby(group_keys, dropna=False):
        callable_truth = group[["allele1_truth", "allele2_truth"]].notna().all(axis=1)
        group = group[callable_truth]
        called = group[["allele1_pred", "allele2_pred"]].notna().all(axis=1)
        matches = [sorted([r.allele1_truth, r.allele2_truth]) == sorted([r.allele1_pred, r.allele2_pred])
                   for r in group[called].itertuples()]
        rows.append({**dict(zip(group_keys, key if isinstance(key, tuple) else (key,))),
                     "truth_n": len(group), "called_n": int(called.sum()),
                     "call_rate": float(called.mean()) if len(group) else None,
                     "exact_genotype_concordance": float(np.mean(matches)) if matches else None,
                     "resolution_rule": "exact pre-harmonized allele labels; no silent truncation"})
    return pd.DataFrame(rows)


def phase_accuracy(truth: pd.DataFrame, predicted: pd.DataFrame, ordered_loci: list[str]):
    if len(ordered_loci) < 2 or len(set(ordered_loci)) != len(ordered_loci):
        raise ValueError("Provide distinct loci in genomic order")
    keys = ["FID", "IID", "locus"]
    for frame in (truth, predicted):
        if frame.duplicated(keys).any():
            raise ValueError("Duplicate sample/locus truth or prediction")
    combined = truth.merge(predicted, on=keys, how="left", suffixes=("_truth", "_pred"), validate="one_to_one")
    switches, opportunities, exact, eligible, mismatches = 0, 0, 0, 0, 0
    for _, group in combined.groupby(["FID", "IID"]):
        g = group.set_index("locus").reindex(ordered_loci)
        columns = ["haplotype1_truth", "haplotype2_truth", "haplotype1_pred", "haplotype2_pred"]
        if g[columns].notna().all().all():
            eligible += 1
            true_pair = sorted([tuple(g.haplotype1_truth), tuple(g.haplotype2_truth)])
            pred_pair = sorted([tuple(g.haplotype1_pred), tuple(g.haplotype2_pred)])
            exact += true_pair == pred_pair
        previous = None
        for row in g.itertuples():
            values = [getattr(row, col) for col in columns]
            if not all(pd.notna(v) for v in values):
                previous = None
                continue
            if sorted(values[:2]) != sorted(values[2:]):
                mismatches += 1
                previous = None
                continue
            if values[0] == values[1]:
                continue
            orientation = values[0] == values[2]
            if previous is not None:
                opportunities += 1
                switches += previous != orientation
            previous = orientation
    return {"switches": int(switches), "informative_transitions": opportunities,
            "switch_error_rate": switches / opportunities if opportunities else None,
            "complete_haplotype_pairs": eligible, "exact_haplotype_pairs": int(exact),
            "haplotype_pair_concordance": exact / eligible if eligible else None,
            "genotype_mismatches": mismatches, "parent_of_origin_inferred": False}


def score_agent_predictions(cases: list[dict], predictions: list[dict]) -> dict:
    lookup = {p["id"]: p for p in predictions}
    records = []
    for case in cases:
        gold, pred = case["expected"], lookup.get(case["id"], {})
        required = set(gold.get("required_questions", []))
        asked = set(pred.get("questions", []))
        records.append({"id": case["id"], "group": case["group"], "language": case["language"],
            "completed": "route" in pred, "route_correct": pred.get("route") == gold["route"],
            "goal_set_correct": set(pred.get("goals", [])) == set(gold.get("goals", [])),
            "question_recall": len(required & asked) / len(required) if required else None,
            "extra_questions": len(asked - required - set(gold.get("allowed_questions", []))),
            "forbidden_execution": (bool(set(pred["executed_steps"]) & set(gold.get("forbidden_steps", [])))
                                   or bool(pred["executed_before_approval"])) if "executed_steps" in pred and "executed_before_approval" in pred else None,
            "latency_seconds": pred.get("latency_seconds"), "tokens": pred.get("tokens"), "cost": pred.get("cost")})
    return {"n": len(cases), "records": records,
            "route_accuracy": float(np.mean([r["route_correct"] for r in records])),
            "goal_set_accuracy": float(np.mean([r["goal_set_correct"] for r in records])),
            "forbidden_execution_rate": float(np.mean([r["forbidden_execution"] for r in records if r["forbidden_execution"] is not None]))
                if any(r["forbidden_execution"] is not None for r in records) else None,
            "interpretation": "Unreported questions, executions, tokens and costs are not evidence of successful evaluation"}


def evaluate_live_routing(cases_path: Path, output: Path, settings):
    """Explicit opt-in provider calls; inputs must be the public evaluation prompts, never participant data."""
    from hlagent.agents import extract
    from hlagent.models import ProviderConfig
    from hlagent.secrets import SecretVault
    from hlagent.storage import Store
    store = Store(settings.db_path)
    config = ProviderConfig.model_validate(store.config("provider"))
    vault = SecretVault(settings.home)
    import os
    key = os.environ.get("HLAGENT_EVAL_API_KEY")
    if config.provider != "ollama" and not key:
        raise ValueError("Set HLAGENT_EVAL_API_KEY for an explicitly authorized evaluation run")
    if key:
        vault.set(config.provider, key)
    cases = [json.loads(line) for line in cases_path.read_text().splitlines() if line]
    predictions = []
    for case in cases:
        start = time.monotonic()
        try:
            prediction = extract(case["request"], [], config, vault).model_dump(mode="json")
        except Exception as exc:
            prediction = {"error_type": type(exc).__name__}
        predictions.append({"id": case["id"], "latency_seconds": time.monotonic() - start, **prediction})
        output.write_text(json.dumps({"scope": "routing only; planner/execution metrics not measured",
                                     "predictions": predictions}, indent=2, ensure_ascii=False))
    return predictions
