from __future__ import annotations

import html
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from hlagent.models import AnalysisPlan


def render_report(directory: Path, plan: AnalysisPlan, tables: dict[str, str],
                  audit: dict, error: str | None = None) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    plan_path = directory / "approved-plan.json"
    plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    (directory / "methods.json").write_text(json.dumps({"plan_hash": plan.plan_hash, "tools": plan.tools,
        "references": plan.references, "options": plan.options.model_dump(), "audit": audit}, indent=2), encoding="utf-8")
    parts = ["<!doctype html><html lang='en'><head><meta charset='utf-8'>",
             "<meta name='viewport' content='width=device-width, initial-scale=1'>",
             "<title>HLAgent analysis report</title><style>html,body{background:#fff;color-scheme:light}body{font:16px system-ui;max-width:1200px;margin:40px auto;padding:0 24px;color:#172c36}"
             "h1,h2{color:#123847}table{border-collapse:collapse;display:block;overflow:auto;font-size:13px}"
             "td,th{border:1px solid #dce4e8;padding:7px;text-align:left}th{background:#eef4f5}"
             "code{word-break:break-all}pre{white-space:pre-wrap;overflow-wrap:anywhere}summary{cursor:pointer;padding:12px 0}.warning{color:#7b4919}li{margin:8px 0}</style></head><body>",
             "<h1>HLAgent analysis report</h1>",
             f"<p><b>Status:</b> {'Incomplete — see execution error' if error else 'Completed'}</p>",
             f"<p><b>Research question:</b> {html.escape(plan.intent.question)}</p>",
             f"<p><b>Plan hash:</b> <code>{plan.plan_hash}</code></p>",
             "<h2>Interpretation and limitations</h2><ul>"]
    parts += ["<li>" + html.escape(w) + "</li>" for w in plan.warnings]
    parts.append("<li>Computed associations describe the specified data and model; they do not establish causality.</li></ul>")
    if error:
        parts.append("<p class='warning'>" + html.escape(error) + "</p>")
    parts.append("<h2>Methods and provenance</h2><p>Statistical observation unit: individual. "
                 "Reported P-values include Bonferroni and exploratory Benjamini–Hochberg adjustment when applicable. "
                 "The exact model, contrast, sample exclusions and external-tool versions are recorded below.</p>")
    parts.append("<details><summary>View model details and execution records</summary><pre>" +
                 html.escape(json.dumps(audit, ensure_ascii=False, indent=2)) + "</pre></details>")
    outputs = [plan_path, directory / "methods.json"]
    js_included = False
    for name, file in tables.items():
        path = Path(file)
        if not path.exists() or path.stat().st_size == 0:
            continue
        try:
            table = pd.read_csv(path, sep="\t")
        except pd.errors.EmptyDataError:
            continue
        parts.append(f"<h2>{html.escape(name.replace('_', ' ').title())}</h2>")
        parts.append(f"<p>{len(table):,} records. The table below shows at most 100 rows; the TSV contains all records.</p>")
        view = table.sort_values("p", na_position="last") if "p" in table else table
        if {"p_bonferroni", "marker"}.issubset(table):
            passed = table[pd.to_numeric(table.p_bonferroni, errors="coerce").lt(plan.options.alpha)]
            parts.append(f"<p>{len(passed)} tests meet the prespecified Bonferroni family threshold. "
                         "This is a model-dependent association statement, not a causal conclusion.</p>")
        parts.append(view.head(100).to_html(index=False, escape=True))
        if "p" not in table or "marker" not in table:
            continue
        plot = table[pd.to_numeric(table.p, errors="coerce").notna()].copy()
        if plot.empty:
            continue
        plot["marker_index"] = np.arange(1, len(plot) + 1)
        plot["minus_log10_p"] = -np.log10(np.maximum(pd.to_numeric(plot.p), np.finfo(float).tiny))
        fig = px.scatter(plot, x="marker_index", y="minus_log10_p", hover_name="marker",
                         color="locus" if "locus" in plot else None,
                         labels={"marker_index": "Marker order (not physical genomic position)", "minus_log10_p": "−log10(P)"})
        parts.append(fig.to_html(full_html=False, include_plotlyjs=True if not js_included else False))
        js_included = True
        fig_path = directory / f"{name}.html"
        fig.write_html(fig_path, include_plotlyjs=True)
        outputs.append(fig_path)
        png = directory / f"{name}.png"
        f, ax = plt.subplots(figsize=(10, 4))
        ax.scatter(plot.marker_index, plot.minus_log10_p, s=12, color="#137d8b")
        ax.set(xlabel="Marker order (not genomic position)", ylabel="−log10(P)", title=name.replace("_", " "))
        f.tight_layout()
        f.savefig(png, dpi=160)
        plt.close(f)
        outputs.append(png)
        observed = np.sort(plot.minus_log10_p.to_numpy())
        expected = np.sort(-np.log10((np.arange(len(observed)) + 0.5) / len(observed)))
        qq = go.Figure(go.Scatter(x=expected, y=observed, mode="markers"))
        qq.add_scatter(x=[0, max(expected)], y=[0, max(expected)], mode="lines", showlegend=False)
        qq.update_layout(title="Q–Q plot; correlated HLA markers are not independent tests",
                         xaxis_title="Expected −log10(P)", yaxis_title="Observed −log10(P)")
        parts.append(qq.to_html(full_html=False, include_plotlyjs=False))
        if {"beta", "se"}.issubset(plot):
            top = plot.nsmallest(20, "p")
            forest = go.Figure(go.Scatter(x=top.beta, y=top.marker, mode="markers",
                                         error_x=dict(type="data", array=1.959963984540054 * top.se)))
            forest.update_layout(title="Top effects and approximate 95% confidence intervals", xaxis_title="Effect on model scale")
            parts.append(forest.to_html(full_html=False, include_plotlyjs=False))
        if "cohort_effects" in plot:
            for row in plot.nsmallest(3, "p").itertuples():
                cohorts = pd.DataFrame(json.loads(row.cohort_effects))
                cohort_forest = go.Figure(go.Scatter(x=cohorts.beta, y=cohorts.cohort, mode="markers",
                                                    error_x=dict(type="data", array=1.959963984540054 * cohorts.se)))
                cohort_forest.add_scatter(x=[row.beta], y=["Pooled fixed effect"], mode="markers",
                                         error_x=dict(type="data", array=[1.959963984540054 * row.se]))
                cohort_forest.update_layout(title="Cohort comparison: " + str(row.marker), xaxis_title="Harmonized effect")
                parts.append(cohort_forest.to_html(full_html=False, include_plotlyjs=False))
        if {"locus", "position", "effect_allele"}.issubset(plot):
            aa = plot[plot.marker.str.startswith("AA_")]
            if not aa.empty:
                matrix = aa.pivot_table(index="effect_allele", columns=["locus", "position"],
                                        values="minus_log10_p", aggfunc="max")
                matrix.columns = ["_".join(map(str, c)) for c in matrix.columns]
                heatmap = px.imshow(matrix, aspect="auto", labels=dict(color="−log10(P)"))
                parts.append(heatmap.to_html(full_html=False, include_plotlyjs=False))
    parts.append("<h2>Reproduction</h2><p>Use approved-plan.json with the same registered files, "
                 "reference snapshots and tool versions. Paths are local; this report does not upload genetic data.</p>")
    parts.append("<pre>" + html.escape(json.dumps(plan.tools, indent=2)) + "</pre></body></html>")
    report = directory / "report.html"
    report.write_text("\n".join(parts), encoding="utf-8")
    outputs.append(report)
    return outputs
