"""Record local deterministic checks. Human/biological evaluation stays explicitly pending."""
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from hlagent.adapters import tool_versions
from hlagent.settings import Settings

root = Path(__file__).resolve().parents[1]
output = root / "evaluation/results"
output.mkdir(parents=True, exist_ok=True)
checks = []
for label, argv in (
    ("ruff", [sys.executable, "-m", "ruff", "check", "src", "tests", "scripts"]),
    ("pytest", [sys.executable, "-m", "pytest", "-q", "--junitxml=evaluation/results/junit.xml"]),
):
    result = subprocess.run(argv, cwd=root, capture_output=True, text=True)
    (output / (label + ".txt")).write_text(result.stdout + result.stderr)
    checks.append({"name": label, "exit_code": result.returncode, "log": label + ".txt"})
    print(label, "PASS" if result.returncode == 0 else "FAIL", flush=True)
    if result.returncode:
        print((result.stdout + result.stderr)[-6000:], flush=True)

result = {"timestamp": datetime.now(UTC).isoformat(), "tools": tool_versions(Settings().initialize()),
          "checks": checks, "not_performed": ["independent biological imputation benchmark",
          "independent trio phase benchmark", "live provider comparison", "two-expert knowledge review",
          "12-20 participant usability study", "large-cohort performance benchmark"]}
(output / "validation-summary.json").write_text(json.dumps(result, indent=2))
raise SystemExit(1 if any(c["exit_code"] for c in checks) else 0)
