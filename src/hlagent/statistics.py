from __future__ import annotations

import json
import warnings
from itertools import combinations

import numpy as np
import pandas as pd
import scipy.linalg
import statsmodels.api as sm
from scipy import stats
from statsmodels.stats.multitest import multipletests
from statsmodels.tools.sm_exceptions import PerfectSeparationWarning

from hlagent.data import ids, unique_samples
from hlagent.models import AnalysisIntent


def prepare_design(markers: pd.DataFrame, phenotype: pd.DataFrame,
                   intent: AnalysisIntent) -> tuple[pd.DataFrame, np.ndarray, pd.DataFrame, dict]:
    markers, phenotype = ids(markers), ids(phenotype)
    unique_samples(markers)
    unique_samples(phenotype)
    if not intent.unrelated_confirmed:
        raise ValueError("Confirm unrelated participants; mixed/family models are not implemented")
    required = [intent.phenotype_column, *intent.covariates]
    if any(col not in phenotype for col in required):
        raise ValueError("Selected phenotype/covariates are missing")
    if intent.phenotype_column in intent.covariates:
        raise ValueError("Phenotype cannot also be a covariate")
    m = markers.set_index(["FID", "IID"])
    p = phenotype.set_index(["FID", "IID"]).reindex(m.index)
    vals = p[intent.phenotype_column].astype(str)
    if intent.phenotype_type == "binary":
        if intent.case_value is None or intent.control_value is None or intent.case_value == intent.control_value:
            raise ValueError("Explicit distinct case/control coding is required")
        unknown = set(vals[~vals.str.upper().isin(["", "NAN", "NA", "NONE"])]) - {intent.case_value, intent.control_value}
        if unknown:
            raise ValueError("Phenotype contains codes other than the specified case/control values")
        y = vals.map({intent.case_value: 1.0, intent.control_value: 0.0})
    elif intent.phenotype_type == "continuous":
        y = pd.to_numeric(vals.replace({"": np.nan, "NA": np.nan}), errors="raise")
    else:
        raise ValueError("Select binary or continuous phenotype")
    cov = p[intent.covariates].replace({"": np.nan, "NA": np.nan, "NaN": np.nan})
    keep = y.notna() & np.isfinite(y) & cov.notna().all(axis=1)
    cov = cov.loc[keep].copy()
    for col in cov:
        converted = pd.to_numeric(cov[col], errors="coerce")
        if converted.notna().all():
            cov[col] = converted.astype(float)
    cov = pd.get_dummies(cov, drop_first=True, dtype=float).astype(float)
    if len(cov.columns) and not np.isfinite(cov.to_numpy()).all():
        raise ValueError("Non-finite covariate values")
    cov.index = range(len(cov))
    yy = y.loc[keep].to_numpy(float)
    if len(yy) <= cov.shape[1] + 3 or np.unique(yy).size < 2:
        raise ValueError("Insufficient complete observations or constant phenotype")
    base = np.column_stack([np.ones(len(yy)), cov.to_numpy()])
    if np.linalg.matrix_rank(base) != base.shape[1]:
        raise ValueError("Covariates are constant or linearly dependent; revise the design")
    mm = m.loc[keep].apply(pd.to_numeric, errors="raise").reset_index()
    g = mm.drop(columns=["FID", "IID"]).to_numpy(float)
    if np.any(np.isfinite(g) & ((g < 0) | (g > 2))):
        raise ValueError("Diploid additive dosages must be between zero and two")
    return mm, yy, cov, {"input_samples": len(m), "analysed_samples": len(yy),
                         "excluded_missing_phenotype_or_covariate": int((~keep).sum()),
                         "unit": "individual", "phenotype_type": intent.phenotype_type}


def independent_columns(matrix: np.ndarray) -> np.ndarray:
    if matrix.shape[1] == 0:
        return matrix
    _, _, pivot = scipy.linalg.qr(matrix, mode="economic", pivoting=True)
    rank = np.linalg.matrix_rank(matrix)
    return matrix[:, sorted(pivot[:rank])]


def condition_columns(metadata: pd.DataFrame, conditions: list[str]) -> list[str]:
    columns = []
    for item in conditions:
        if item in set(metadata.marker):
            columns.append(item)
            continue
        matches = metadata[("AA_" + metadata.locus.astype(str) + "_" + metadata.position.astype(str)) == item]
        if matches.empty:
            raise ValueError(f"Unknown conditioning marker/position: {item}")
        # k categories have k-1 independent dosages with the intercept.
        columns.extend(sorted(matches.marker)[1:])
    return list(dict.fromkeys(columns))


def correction(frame: pd.DataFrame, family_size: int | None = None) -> pd.DataFrame:
    frame = frame.copy()
    if frame.empty or "p" not in frame:
        return frame
    n = family_size or len(frame)
    frame["n_tests"] = n
    frame["p_bonferroni"] = np.minimum(pd.to_numeric(frame.p, errors="coerce") * n, 1.0)
    frame["p_fdr"] = np.nan
    valid = pd.to_numeric(frame.p, errors="coerce").notna()
    # Unsuccessful tests count as p=1 so failures do not reduce the correction family.
    p = pd.to_numeric(frame.p, errors="coerce").fillna(1).to_numpy()
    padded = np.r_[p, np.ones(max(0, n - len(p)))]
    adjusted = multipletests(padded, method="fdr_bh")[1][:len(p)]
    frame.loc[valid, "p_fdr"] = adjusted[valid.to_numpy()]
    return frame


def reference_regression(y: np.ndarray, x: np.ndarray, cov: np.ndarray,
                         binary: bool) -> dict:
    """Independent reference implementation; production single-marker tests use PLINK 2."""
    design = np.column_stack([np.ones(len(y)), cov, x])
    if np.linalg.matrix_rank(design) != design.shape[1]:
        raise ValueError("Rank-deficient design")
    with warnings.catch_warnings():
        warnings.simplefilter("error", PerfectSeparationWarning)
        fit = sm.GLM(y, design, family=sm.families.Binomial()).fit() if binary else sm.OLS(y, design).fit()
    if hasattr(fit, "converged") and not fit.converged:
        raise ValueError("Regression did not converge")
    return dict(beta=float(fit.params[-1]), se=float(fit.bse[-1]), p=float(fit.pvalues[-1]))


def omnibus(markers: pd.DataFrame, y: np.ndarray, cov: pd.DataFrame, metadata: pd.DataFrame,
            binary: bool, conditions: list[str], min_count: int = 20) -> pd.DataFrame:
    """Nested models using one row per person and identical samples in both models."""
    result = []
    condition = condition_columns(metadata, conditions)
    groups = metadata[metadata.kind == "AA"].groupby(["locus", "position"], sort=True)
    if groups.ngroups == 0:
        raise ValueError("Omnibus requires an amino-acid sequence dictionary with mapped positions")
    for (locus, position), rows in groups:
        record = dict(marker=f"AA_{locus}_{position}", locus=locus, position=position,
                      method="logistic_LRT" if binary else "partial_F", unit="individual")
        try:
            cols = sorted(rows.marker)
            matrix = markers[cols].to_numpy(float)
            cond = markers[condition].to_numpy(float) if condition else np.empty((len(y), 0))
            valid = np.isfinite(matrix).all(axis=1) & np.isfinite(cond).all(axis=1)
            yy, aa = y[valid], matrix[valid]
            if len(yy) == 0 or len(cols) < 2:
                raise ValueError("No complete data or monomorphic amino-acid position")
            if not np.allclose(aa.sum(axis=1), 2, atol=1e-6):
                raise ValueError("Residue categories do not sum to diploid dosage two")
            if (aa.sum(axis=0) < min_count).any():
                raise ValueError("Sparse residue category; no unsupported automatic test substitution")
            base = np.column_stack([np.ones(len(yy)), cov.to_numpy()[valid], cond[valid]])
            base = independent_columns(base)
            # The most frequent category is the reference; explicit rank of both designs controls df.
            reference = int(np.argmax(aa.sum(axis=0)))
            alt = independent_columns(np.column_stack([base, np.delete(aa, reference, axis=1)]))
            df = int(np.linalg.matrix_rank(alt) - np.linalg.matrix_rank(base))
            if df <= 0 or len(yy) <= alt.shape[1] + 1:
                raise ValueError("No additional estimable degrees of freedom")
            with warnings.catch_warnings():
                warnings.simplefilter("error", PerfectSeparationWarning)
                if binary:
                    null = sm.GLM(yy, base, family=sm.families.Binomial()).fit(maxiter=100)
                    full = sm.GLM(yy, alt, family=sm.families.Binomial()).fit(maxiter=100)
                    if not null.converged or not full.converged or np.max(np.abs(full.params)) > 30:
                        raise ValueError("Separation or non-convergence")
                    statistic = max(0.0, 2 * float(full.llf - null.llf))
                    logp = float(stats.chi2.logsf(statistic, df))
                else:
                    null, full = sm.OLS(yy, base).fit(), sm.OLS(yy, alt).fit()
                    if full.ssr <= 0:
                        raise ValueError("Degenerate residual variance")
                    statistic = max(0.0, ((null.ssr - full.ssr) / df) / (full.ssr / full.df_resid))
                    logp = float(stats.f.logsf(statistic, df, full.df_resid))
            record.update(status="ok", n=len(yy), statistic=statistic, df=df,
                          p=float(np.exp(logp)), neg_log10_p=-logp / np.log(10),
                          reference_residue=rows.set_index("marker").loc[cols[reference], "effect_allele"])
        except (ValueError, np.linalg.LinAlgError, PerfectSeparationWarning) as exc:
            record.update(status="failed", p=np.nan, error=str(exc))
        result.append(record)
    return correction(pd.DataFrame(result))


META_DESIGN_KEYS = ("phenotype", "phenotype_type", "effect_scale", "unit", "genome_build",
                    "resolution", "imgt_release", "conditioning", "covariates", "strand")


def normalize_summary(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    required = {"marker", "effect_allele", "other_allele", "se"}
    if not required.issubset(frame):
        raise ValueError("Summary requires marker, effect_allele, other_allele, se and beta (or OR)")
    if frame.marker.duplicated().any():
        raise ValueError("Duplicate markers/contrasts in a cohort summary")
    if "beta" not in frame:
        if "OR" not in frame:
            raise ValueError("No effect size; omnibus P-values cannot be combined by inverse variance")
        odds = pd.to_numeric(frame.OR, errors="raise")
        if (odds <= 0).any():
            raise ValueError("Odds ratios must be positive")
        frame["beta"] = np.log(odds)
    for col in ("beta", "se"):
        frame[col] = pd.to_numeric(frame[col], errors="raise")
    if not np.isfinite(frame[["beta", "se"]].to_numpy()).all() or (frame.se <= 0).any():
        raise ValueError("Effects must be finite with positive standard errors")
    if (frame.effect_allele == frame.other_allele).any():
        raise ValueError("Effect and comparator cannot be identical")
    return frame


def fixed_effect(beta: np.ndarray, se: np.ndarray) -> dict:
    weights = 1 / np.square(se)
    estimate = float(np.sum(weights * beta) / weights.sum())
    error = float(1 / np.sqrt(weights.sum()))
    z = estimate / error
    logp = float(np.log(2) + stats.norm.logsf(abs(z)))
    q = float(np.sum(weights * np.square(beta - estimate)))
    df = len(beta) - 1
    return dict(beta=estimate, se=error, p=float(np.exp(logp)), neg_log10_p=-logp / np.log(10),
                ci_lower=estimate - 1.959963984540054 * error, ci_upper=estimate + 1.959963984540054 * error,
                k=len(beta), Q=q, Q_p=float(stats.chi2.sf(q, df)) if df > 0 else np.nan,
                I2=max(0.0, (q - df) / q) * 100 if q > 0 and df > 0 else 0.0)


def meta_analysis(frames: list[pd.DataFrame], designs: list[dict], independent: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not independent or len(frames) < 2 or len(designs) != len(frames):
        raise ValueError("Meta-analysis needs at least two explicitly independent cohorts")
    for key in META_DESIGN_KEYS:
        if any(key not in d for d in designs):
            raise ValueError(f"Missing meta-analysis design declaration: {key}")
        if any(d[key] != designs[0][key] for d in designs[1:]):
            raise ValueError(f"Incomparable cohort designs: {key}")
    names = [d.get("cohort") for d in designs]
    if any(not n for n in names) or len(set(names)) != len(names):
        raise ValueError("Distinct cohort identifiers are required")
    if designs[0]["effect_scale"] not in ("log_odds", "mean_difference"):
        raise ValueError("Unsupported effect scale")
    if designs[0]["strand"] != "forward":
        raise ValueError("Confirm forward-strand alignment before combining summaries")
    for a, b in combinations(designs, 2):
        if set(a.get("sample_hashes", [])) & set(b.get("sample_hashes", [])):
            raise ValueError("Detected overlapping participants")
    norm = []
    for f, name in zip(frames, names):
        if "OR" in f and "beta" not in f and designs[0]["effect_scale"] != "log_odds":
            raise ValueError("Odds ratios require a declared log-odds effect and SE scale")
        table = normalize_summary(f)
        table["cohort"] = name
        norm.append(table)
    merged = pd.concat(norm, ignore_index=True)
    results, leave_out = [], []
    for marker, group in merged.groupby("marker", sort=True):
        if len(group) < 2:
            continue
        first = group.iloc[0]
        beta, errors = [], []
        for row in group.itertuples():
            if (row.effect_allele, row.other_allele) == (first.effect_allele, first.other_allele):
                beta.append(row.beta)
            elif (row.other_allele, row.effect_allele) == (first.effect_allele, first.other_allele):
                beta.append(-row.beta)
            else:
                raise ValueError(f"Unresolved allele/contrast mismatch for {marker}")
            errors.append(row.se)
        beta, errors = np.asarray(beta), np.asarray(errors)
        result = dict(marker=marker, effect_allele=first.effect_allele, other_allele=first.other_allele,
                      method="fixed_effect_inverse_variance", **fixed_effect(beta, errors))
        result["cohort_effects"] = json.dumps([{"cohort": name, "beta": float(b), "se": float(s)}
                                              for name, b, s in zip(group.cohort, beta, errors)])
        results.append(result)
        if len(group) >= 3:
            for i, name in enumerate(group.cohort):
                leave_out.append(dict(marker=marker, omitted_cohort=name,
                                      **fixed_effect(np.delete(beta, i), np.delete(errors, i))))
    if not results:
        raise ValueError("No compatible markers present in two or more cohorts")
    return correction(pd.DataFrame(results)), pd.DataFrame(leave_out)


def haplotype_dosages(phased: pd.DataFrame, loci: list[str]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if len(loci) < 2 or not set(loci).issubset(set(phased.locus)):
        raise ValueError("Select at least two phased HLA loci")
    rows, observed = [], []
    for (fid, iid), group in phased.groupby(["FID", "IID"], sort=True):
        g = group.set_index("locus")
        if not set(loci).issubset(g.index):
            continue
        a = "~".join(g.loc[loci, "haplotype1"])
        b = "~".join(g.loc[loci, "haplotype2"])
        rows.append((fid, iid, a, b))
        observed.extend([a, b])
    counts = pd.Series(observed).value_counts()
    frequencies = pd.DataFrame({"haplotype": counts.index, "count": counts.values,
                                "frequency": counts.values / len(observed)})
    markers = pd.DataFrame([dict(FID=fid, IID=iid, **{"HAP_" + h: float((a == h) + (b == h)) for h in counts.index})
                            for fid, iid, a, b in rows])
    metadata = pd.DataFrame([dict(marker="HAP_" + h, kind="HAP", locus="~".join(loci), position="",
                                  effect_allele=h, other_allele="NOT_" + h) for h in counts.index])
    return markers, metadata, frequencies
