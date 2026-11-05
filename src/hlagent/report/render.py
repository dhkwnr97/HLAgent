"""Report rendering (Markdown + self-contained HTML)."""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path
from typing import Any

import markdown as md
from jinja2 import Environment

from hlagent.pipeline.contracts import STEP_TITLES

MD_TEMPLATE = """\
# HLAgent v3 report: {{ facts.goal or facts.run_id }}

{% if facts.synthetic %}> **SYNTHETIC PHENOTYPE.** At least one study uses a demo-only synthetic phenotype. The associations below demonstrate the pipeline and carry no biological meaning.

{% endif %}| Item | Value |
|---|---|
| Run | `{{ facts.run_id }}` |
| Nodes requested | {{ facts.nodes_requested | join(", ") }} |
| Studies | {{ facts.studies | length }} |
| HLAgent | {{ facts.tool_versions.hlagent }} |
| PLINK | {{ facts.tool_versions.plink }} |
| CookHLA image | `{{ facts.tool_versions.cookhla_image }}` |

## 1. Summary
{% if narrative %}{{ narrative }}

*Narrative written by an LLM from facts.json; every number was checked against it.*

**Deterministic summary**

{{ auto_summary }}{% else %}{{ auto_summary }}{% endif %}

{% for sid, st in facts.studies.items() %}
## Study {{ sid }}
{% if st.external_summary %}External summary statistics ({{ st.pheno_name or "phenotype n/a" }}): used in the meta-analysis only; no genotype-level step was run.
{% endif %}{% for step, e in st.steps.items() %}
### {{ e.title }} ({{ e.status }})
{% if e.metrics %}| Metric | Value |
|---|---|
{% for k, v in e.metrics.items() %}| {{ k }} | {{ fmt(v) }} |
{% endfor %}{% endif %}
{% if e.top_markers %}
Top markers:

| Marker | Type | Effect allele | OR/BETA | 95% CI | P |
|---|---|---|---|---|---|
{% for r in e.top_markers %}| {{ r.SNP }} | {{ r.marker_type }} | {{ r.A1 }} | {{ fmt(r.OR if r.OR is not none else r.BETA) }} | {{ fmt(r.L95) }}-{{ fmt(r.U95) }} | {{ fmt(r.P) }} |
{% endfor %}{% endif %}
{% if e.conditional_steps %}
| Round | Marker | Effect | P | Conditioned on | Significant |
|---|---|---|---|---|---|
{% for r in e.conditional_steps %}| {{ r["round"] }} | {{ r.marker }} | {{ fmt(r.effect) }} | {{ fmt(r.P) }} | {{ r.conditioned_on or "-" }} | {{ r.significant }} |
{% endfor %}{% endif %}
{% for f in figures.get(step ~ ":" ~ sid, []) %}
![{{ f.name }}]({{ f.rel }})
{% endfor %}
{% endfor %}
{% endfor %}
{% if facts.meta %}
## Meta-analysis (Node5)
| Metric | Value |
|---|---|
{% for k, v in facts.meta.metrics.items() %}| {{ k }} | {{ fmt(v) }} |
{% endfor %}

| Marker | EA | OR (FE) | P (FE) | P (RE) | I2 | P_Q |
|---|---|---|---|---|---|---|
{% for r in facts.meta.top %}| {{ r.SNP }} | {{ r.EA }} | {{ fmt(r.OR_FE) }} | {{ fmt(r.P_FE) }} | {{ fmt(r.P_RE) }} | {{ fmt(r.I2) }} | {{ fmt(r.P_Q) }} |
{% endfor %}
{% for f in figures.get("Node5:-", []) %}
![{{ f.name }}]({{ f.rel }})
{% endfor %}
{% endif %}

## Limitations and warnings
{% for w in facts.warnings %}- {{ w }}
{% else %}- None recorded.
{% endfor %}

## Methods
{% for step in facts.steps_run if step in methods %}- {{ methods[step] }}
{% endfor %}
Exact commands, parameters and tool versions are in each step's `node_result.json`, `params.lock.json` and `env.lock.json`. Re-run with `reproduce.sh`.

## References
{% for c in facts.citations %}{{ loop.index }}. {{ c }}
{% endfor %}
"""


METHODS = {
    "StageD": "Stage D harmonised genotypes to hg18 (rsID re-mapping against the 1000G_REF panel when the build "
    "was not hg18), restricted them to chr6:29-34 Mb, kept founders of family data and applied PLINK QC "
    "(MAF/HWE filters only when n >= 50).",
    "StageI": "Stage I imputed HLA alleles with CookHLA (Docker image pinned by digest, run offline; 3 exons x 3 "
    "overlap windows of BEAGLE 5).",
    "Node1": "Node1 built the HATK binary marker panel: IMGT2Seq dictionaries (IMGT/HLA 3.32.0, hg18), allele "
    "truncation to the requested resolution (NomenCleaner for HPED input) and bMarkerGenerator "
    "(HLA alleles, amino-acid residues, intragenic SNPs and indels; genes without calls are left out).",
    "Node2": "Node2 tested each marker with PLINK 1.9 logistic (binary) or linear (continuous) regression under an "
    "additive model, with the HATK effect-allele rule (--a1-allele; presence 'p' for binary markers). "
    "Bonferroni uses the number of markers with a finite P. The genomic-control lambda is computed over "
    "the MHC region only and is dominated by rare binary markers, so it is not a genome-wide inflation "
    "measure.",
    "Node3": "Node3 ran stepwise conditional regression, adding the top marker of each round to --condition-list "
    "until no marker passed the threshold.",
    "StageP": "Stage P phased the marker panel with BEAGLE 3.3.2 (HATK chain: linkage2beagle, GC-trick base "
    "pairs, seed recorded) and derived per-haplotype amino-acid calls.",
    "Node4": "Node4 ran the HATK omnibus likelihood-ratio test per amino-acid position (all residues at a position "
    "jointly, df = residues - 1).",
    "Node5": "Node5 combined studies by inverse-variance fixed effect with Cochran Q, I2 and DerSimonian-Laird "
    "random effects after allele harmonisation.",
    "StageR": "Stage R compiled this report from the step outputs; every number comes from facts.json.",
}


def fmt(v: Any) -> str:
    if v is None:
        return "-"
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, float):
        if v != v:
            return "NA"
        if v != 0 and (abs(v) < 1e-3 or abs(v) >= 1e5):
            return f"{v:.3g}"
        return f"{v:.4g}"
    return str(v)


def auto_summary(facts: dict[str, Any]) -> str:
    lines = []
    for sid, st in facts["studies"].items():
        s = st["steps"]
        parts = [f"**{sid}**:"]
        if st.get("external_summary") and not s:
            lines.append(
                f"**{sid}**: external summary statistics ({st.get('pheno_name') or 'phenotype n/a'}), "
                "used in the meta-analysis only."
            )
            continue
        d = s.get("StageD", {}).get("metrics", {})
        if d:
            b_det, b_used = d.get("build_detected", "n/a"), d.get("build_used", "n/a")
            build = b_det if b_det == b_used else f"{b_det}, re-mapped to {b_used}"
            parts.append(
                f"{d.get('n_samples_qc', d.get('n_samples_with_hla', '?'))} samples after QC "
                f"(build {build}; phenotype {d.get('pheno_name')}: "
                f"{d.get('n_cases')} cases / {d.get('n_controls')} controls)."
            )
        n2 = s.get("Node2", {}).get("metrics", {})
        if n2.get("top_marker"):
            parts.append(
                f"Top Node2 marker {n2['top_marker']} (effect {fmt(n2.get('top_effect'))}, "
                f"P = {fmt(n2.get('top_p'))}); {n2.get('n_sig_bonferroni')} markers pass Bonferroni "
                f"({fmt(n2.get('bonferroni_threshold'))})."
            )
        if n2.get("spike_marker") and n2.get("spike_rank"):
            parts.append(
                f"Spike-in check: {n2['spike_marker']} ranks {n2['spike_rank']}/{n2['spike_n_tested']} "
                f"(OR {fmt(n2.get('spike_or'))}, 95% CI {fmt(n2.get('spike_l95'))}-{fmt(n2.get('spike_u95'))}; "
                f"generating OR {fmt(n2.get('spike_true_or'))})."
            )
        n3 = s.get("Node3", {}).get("metrics", {})
        if n3:
            parts.append(f"Node3 found {n3.get('n_independent_signals')} independent signal(s).")
        n4 = s.get("Node4", {}).get("metrics", {})
        if n4.get("top_position[NA]"):
            parts.append(
                f"Node4 top amino-acid position {n4['top_position[NA]']} (log10 P = {fmt(n4.get('top_log10_p[NA]'))})."
            )
        lines.append(" ".join(parts))
    if facts.get("meta"):
        m = facts["meta"]["metrics"]
        lines.append(
            f"**Meta-analysis** of {m.get('k_studies')} studies over {m.get('n_analyzed')} markers: top "
            f"{m.get('top_marker')} (OR_FE {fmt(m.get('top_or_fe'))}, P_FE = {fmt(m.get('top_p_fe'))}, "
            f"I2 = {fmt(m.get('top_i2'))})."
        )
    return "\n\n".join(lines)


def collect_figures(ctx, report_dir: Path) -> dict[str, list[dict[str, str]]]:
    figs: dict[str, list[dict[str, str]]] = {}
    for key, r in ctx.results.items():
        for name, a in r.artifacts.items():
            if a.kind == "plot" and a.path.exists():
                rel = Path("..") / a.path.relative_to(ctx.run_dir)
                figs.setdefault(key, []).append(
                    {"name": f"{STEP_TITLES[key.split(':')[0]]}: {name}", "rel": str(rel), "abs": str(a.path)}
                )
    return figs


def _embeddable_png(path: Path, max_width: int = 1600) -> bytes:
    """PNG bytes for the single-file HTML; wide figures (HATK heatmaps are ~4000 px) are downscaled.
    The original files in the step folders are left untouched."""
    raw = path.read_bytes()
    try:
        from PIL import Image
    except ImportError:
        return raw
    with Image.open(path) as im:
        if im.width <= max_width:
            return raw
        im = im.convert("RGB")
        im.thumbnail((max_width, max_width * im.height // im.width))
        buf = io.BytesIO()
        im.save(buf, format="PNG", optimize=True)
        return buf.getvalue()


def render(
    facts: dict[str, Any],
    figures: dict[str, list[dict[str, str]]],
    report_dir: Path,
    narrative: str | None = None,
) -> dict[str, Path]:
    report_dir.mkdir(parents=True, exist_ok=True)
    # Markdown is plain text: no HTML escaping here. Raw HTML is neutralised when converting to HTML below.
    env = Environment(autoescape=False, trim_blocks=False, lstrip_blocks=False)  # noqa: S701
    env.globals["fmt"] = fmt
    text = env.from_string(MD_TEMPLATE).render(
        facts=facts, figures=figures, narrative=narrative, auto_summary=auto_summary(facts), methods=METHODS
    )
    md_path = report_dir / "report.md"
    md_path.write_text(text)
    (report_dir / "facts.json").write_text(json.dumps(facts, indent=1, default=str))
    (report_dir / "figures.json").write_text(json.dumps(figures, indent=1))
    if narrative:
        (report_dir / "narrative.md").write_text(narrative)
    # HTML with embedded images (single file)
    conv = md.Markdown(extensions=["tables"])
    # escape raw HTML coming from user text (goal, study ids, file names) instead of passing it through
    conv.preprocessors.deregister("html_block")
    conv.inlinePatterns.deregister("html")
    html_body = conv.convert(text)
    for figs in figures.values():
        for f in figs:
            data = base64.b64encode(_embeddable_png(Path(f["abs"]))).decode()
            html_body = html_body.replace(f'src="{f["rel"]}"', f'src="data:image/png;base64,{data}"')
    html = (
        "<!doctype html><html><head><meta charset='utf-8'><title>HLAgent report</title>"
        "<style>body{font-family:system-ui,sans-serif;max-width:1100px;margin:2em auto;padding:0 1em;line-height:1.5}"
        "table{border-collapse:collapse;margin:1em 0;font-size:0.9em}td,th{border:1px solid #ccc;padding:3px 8px}"
        "img{max-width:100%}blockquote{background:#fff3cd;border-left:4px solid #e0a800;margin:0;padding:.5em 1em}"
        "</style></head><body>" + html_body + "</body></html>"
    )
    html_path = report_dir / "report.html"
    html_path.write_text(html)
    return {"md": md_path, "html": html_path}
