"""Subprocess entry point: `python -m hlagent.pipeline.run --run-dir <dir>`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hlagent.pipeline.runner import execute, write_json_atomic


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True, type=Path)
    a = ap.parse_args(argv)
    try:
        res = execute(a.run_dir)
    except Exception as e:  # noqa: BLE001 - report every crash through status.json
        write_json_atomic(a.run_dir / "status.json", {"state": "failed", "message": f"runner crashed: {e}"})
        raise
    print(json.dumps(res))
    return 0 if res["state"] in ("done", "blocked") else 1


if __name__ == "__main__":
    sys.exit(main())
