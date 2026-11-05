"""Report rendering: every per-study and meta figure is referenced and embedded; no raw HTML passes."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from hlagent.report.render import render


def _png(path, width_in=3.0):
    fig, ax = plt.subplots(figsize=(width_in, 2), dpi=100)
    ax.plot([0, 1], [0, 1])
    fig.savefig(path)
    plt.close(fig)
    return path


def test_figures_are_embedded(tmp_path):
    small = _png(tmp_path / "manhattan.png")
    wide = _png(tmp_path / "heatmap.png", width_in=40)  # 4000 px, downscaled when embedded
    facts = {
        "run_id": "r",
        "goal": "goal <script>x</script>",
        "synthetic": False,
        "nodes_requested": ["Node2"],
        "tool_versions": {"hlagent": "t", "plink": "p", "cookhla_image": "c"},
        "warnings": [],
        "citations": [],
        "steps_run": ["Node2"],
        "studies": {
            "S1": {
                "steps": {"Node2": {"title": "Node2", "status": "ok", "metrics": {"top_p": 1e-5}}},
                "external_summary": False,
                "pheno_name": "RA",
            }
        },
    }
    figures = {
        "Node2:S1": [
            {"name": "manhattan", "rel": "../S1/node2/manhattan.png", "abs": str(small)},
            {"name": "heatmap", "rel": "../S1/node2/heatmap.png", "abs": str(wide)},
        ]
    }
    out = render(facts, figures, tmp_path / "report")
    md = out["md"].read_text()
    html = out["html"].read_text()
    assert md.count("![") == 2
    assert html.count("data:image/png;base64,") == 2
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert len(html) < wide.stat().st_size + 200_000
