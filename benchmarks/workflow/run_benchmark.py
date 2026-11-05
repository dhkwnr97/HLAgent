"""Benchmark end-to-end HLAgent v3 runs on four example tasks (B1–B4).

Each scenario is executed `--reps` times in a fresh run directory (no step cache), one at a time.
Per-step wall-clock comes from node_result.json (started_at/finished_at); per-command tool time comes
from logs/commands.jsonl written by hlagent.tools.proc. Finished replicates are skipped on re-run, so
the script can be restarted after an interruption.

    python benchmarks/workflow/run_benchmark.py --out benchmarks/workflow/results --reps 3
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from hlagent import examples, paths
from hlagent.pipeline.dag import AnalysisPlan
from hlagent.pipeline.params import Node4Params, PipelineParams

SCENARIOS = {
    # full fine-mapping on real case-control data + RA-CD meta-analysis with published summary statistics
    "B1_WTCCC_RA_Node1-5": lambda: examples.scenario("S5"),
    # omnibus conditioned on AA_DRB1_96, compared with the published conditional omnibus
    "B2_WTCCC_RA_Node4_cond_DRB1_96": lambda: AnalysisPlan(
        goal="WTCCC RA omnibus conditioned on AA_DRB1_96",
        studies=[examples.wtccc_ra()],
        nodes=["Node4"],
        params=PipelineParams(node4=Node4Params(conditions=["AA_DRB1_96"])),
    ),
    # SNP genotypes only (hg19): CookHLA imputation, then marker panel and association
    "B3_GenotypeExample_CookHLA_Node1-2": lambda: examples.scenario("S3"),
    # unknown build, family data, 4-field typing with untyped genes: preflight-driven harmonisation
    "B4_BMExample_Node1-4": lambda: examples.scenario("S2"),
}


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def collect(run_dir: Path) -> dict:
    steps = []
    for f in sorted(run_dir.glob("**/node_result.json")):
        r = json.loads(f.read_text())
        dur = (_dt(r["finished_at"]) - _dt(r["started_at"])).total_seconds() if r.get("finished_at") else None
        steps.append(
            {
                "step": r["node"],
                "study_id": r.get("study_id"),
                "status": r["status"],
                "started_at": r["started_at"],
                "finished_at": r.get("finished_at"),
                "seconds": dur,
                "n_commands_recorded": len(r.get("commands", [])),
            }
        )
    ledger = []
    lf = run_dir / "logs" / "commands.jsonl"
    if lf.exists():
        ledger = [json.loads(x) for x in lf.read_text().splitlines() if x.strip()]
    for s in steps:  # attribute external commands to the step whose time window contains them
        t0, t1 = (
            _dt(s["started_at"]).timestamp(),
            _dt(s["finished_at"]).timestamp() if s["finished_at"] else 1e18,
        )
        own = [c for c in ledger if t0 - 0.5 <= c["ts"] - c["seconds"] and c["ts"] <= t1 + 0.5]
        s["n_external_commands"] = len(own)
        s["external_seconds"] = round(sum(c["seconds"] for c in own), 3)
    ev = [json.loads(x) for x in (run_dir / "logs" / "events.jsonl").read_text().splitlines() if x.strip()]
    start = next(_dt(e["ts"]) for e in ev if e["kind"] == "run_started")
    end = [_dt(e["ts"]) for e in ev if e["kind"] == "run_finished"][-1]
    status = json.loads((run_dir / "status.json").read_text())
    return {
        "run_dir": str(run_dir),
        "state": status["state"],
        "total_seconds": (end - start).total_seconds(),
        "steps": steps,
        "n_external_commands": len(ledger),
        "external_seconds": round(sum(c["seconds"] for c in ledger), 3),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--only", nargs="*", default=None)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    env = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "cpu": platform.processor(),
        "nproc": __import__("os").cpu_count(),
    }
    try:
        env["cpu_model"] = next(
            ln.split(":", 1)[1].strip() for ln in open("/proc/cpuinfo") if ln.startswith("model name")
        )
        env["mem_total_gb"] = round(
            int(next(ln.split()[1] for ln in open("/proc/meminfo") if ln.startswith("MemTotal"))) / 1e6, 1
        )
    except (OSError, StopIteration):
        pass
    (a.out / "environment.json").write_text(json.dumps(env, indent=1))
    for name, make in SCENARIOS.items():
        if a.only and name not in a.only:
            continue
        for rep in range(1, a.reps + 1):
            res_file = a.out / f"{name}.rep{rep}.json"
            if res_file.exists() and json.loads(res_file.read_text()).get("state") == "done":
                print(f"skip {name} rep{rep} (done)", flush=True)
                continue
            plan = make()
            run_dir = paths.runs_dir() / f"bench_{name}_rep{rep}_{int(time.time())}"
            run_dir.mkdir(parents=True)
            (run_dir / "plan.json").write_text(plan.model_dump_json(indent=1))
            t0 = time.monotonic()
            p = subprocess.run(  # noqa: S603 - fixed argument list
                [sys.executable, "-m", "hlagent.pipeline.run", "--run-dir", str(run_dir)],
                capture_output=True,
                text=True,
                check=False,
            )
            wall = time.monotonic() - t0
            out = collect(run_dir)
            out.update(
                {
                    "scenario": name,
                    "rep": rep,
                    "process_wall_seconds": round(wall, 3),
                    "returncode": p.returncode,
                }
            )
            res_file.write_text(json.dumps(out, indent=1))
            print(f"{name} rep{rep}: {out['state']} {wall:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
