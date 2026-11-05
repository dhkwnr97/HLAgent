"""Filesystem layout of an HLAgent v3 installation.

Everything is resolved relative to the project root, which is the directory holding
`pyproject.toml` (or `HLAGENT_HOME` when set). Nothing is created at import time.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def project_root() -> Path:
    env = os.environ.get("HLAGENT_HOME")
    if env:
        return Path(env).expanduser().resolve()
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists() and (parent / "src" / "hlagent").exists():
            return parent
    return Path.cwd().resolve()


def resources_dir() -> Path:
    return project_root() / "resources"


def reference_panels_dir() -> Path:
    return resources_dir() / "reference_panels"


def imgt_dir() -> Path:
    return resources_dir() / "imgt"


def hatk_cache_dir() -> Path:
    """IMGT2Seq dictionaries keyed by (hg, imgt)."""
    return resources_dir() / "hatk_cache"


def examples_dir() -> Path:
    return resources_dir() / "examples"


def anchors_dir() -> Path:
    return resources_dir() / "anchors"


def beagle_dir() -> Path:
    return project_root() / "third_party" / "beagle"


def runs_dir() -> Path:
    return project_root() / "runs"


def workspace_dir() -> Path:
    return project_root() / "workspace"


def knowledge_dir() -> Path:
    return project_root() / "knowledge" / "articles"


def chroma_dir() -> Path:
    return project_root() / "data" / "chroma"


def vendor_dir() -> Path:
    return project_root() / "vendor" / "hatk_port"


def ensure_within(path: Path, *allowed: Path) -> Path:
    """Resolve `path` and refuse anything outside the allowed roots (path traversal guard)."""
    resolved = path.expanduser().resolve()
    roots = allowed or (workspace_dir(), resources_dir(), runs_dir())
    for root in roots:
        try:
            resolved.relative_to(root.resolve())
            return resolved
        except ValueError:
            continue
    raise PermissionError(f"{resolved} is outside the allowed directories: {[str(r) for r in roots]}")
