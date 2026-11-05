"""Stage P: phase the Node1 panel with BEAGLE 3.3.2 and derive amino-acid haplotype calls (.aa)."""

from __future__ import annotations

from pathlib import Path

from hlagent.pipeline.contracts import ArtifactRef, NodeResult, StudySpec
from hlagent.tools.beagle import check_phasing_consistency, phase_bmarker_panel
from hlagent.tools.omnibus import make_aa


def run(ctx, study: StudySpec) -> NodeResult:
    p = ctx.params.stage_p
    n1 = ctx.require("Node1", study.study_id)
    out = ctx.step_dir("StageP", study.study_id)
    res = NodeResult(node="StageP", study_id=study.study_id, status="ok", cache_key="")
    panel = n1.art("panel")
    bgl_phased, markers, cmds = phase_bmarker_panel(panel, out / "panel", p, plink=ctx.plink, java=ctx.java)
    res.commands += cmds
    aa, cmd = make_aa(bgl_phased, Path(f"{panel}.fam"), out / "panel", rscript=ctx.rscript)
    res.commands.append(cmd)
    check = check_phasing_consistency(panel, bgl_phased, max_markers=2000)
    res.metrics.update({f"consistency_{k}": v for k, v in check.items()})
    res.metrics.update({"beagle": "3.3.2", "seed": p.seed, "n_samples": int(n1.metrics.get("n_samples", 0))})
    if check["mismatched"]:
        res.status, res.error_kind = "failed", "tool_error"
        res.error_message = f"{check['mismatched']} phased genotypes disagree with the input panel"
        return res
    n = int(n1.metrics.get("n_samples", 0))
    if n and n < 100:
        res.warnings.append(
            f"Phasing without a reference panel on n={n} samples: haplotype accuracy is low "
            "(heuristic threshold n<100)."
        )
        res.status = "warning"
    res.artifacts["bgl_phased"] = ArtifactRef.of("bgl_phased", bgl_phased)
    res.artifacts["markers"] = ArtifactRef.of("markers", markers)
    res.artifacts["aa"] = ArtifactRef.of("aa", aa, description="phased amino-acid calls for the omnibus test")
    return res
