"""Populate `resources/` from an HLAgent v1 checkout (local folder or GitHub clone).

Large data (reference panels, IMGT/HLA releases, example studies) is not stored in the v3
repository. This module copies it from v1, which already ships it:

    hlagent setup-resources --from-v1 /mnt/f/Claude_cw/HLAgent/HLAgent-main_v1.0.0
    hlagent setup-resources --clone            # git clone github.com/dhkwnr97/HLAgent
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from hlagent import paths
from hlagent.tools import proc

V1_GIT_URL = "https://github.com/dhkwnr97/HLAgent"


@dataclass(frozen=True)
class CopySpec:
    src: str  # relative to v1 root
    dst: str  # relative to resources/ (or project root when it starts with "@root/")
    glob: str | None = None


# hg18 / IMGT 3.32.0 dictionaries shipped with the HATK example seed the IMGT2Seq cache.
_HATK_CACHE = "hatk_cache/hg18_imgt3320"

SPECS: list[CopySpec] = [
    CopySpec("data/reference_panels/1000G_REF", "reference_panels/1000G_REF"),
    CopySpec(
        "src/tools/HATK/IMGT2Seq/data_for_imgt2seq/imgthla/IMGTHLA-3.32.0-alpha", "imgt/IMGTHLA-3.32.0-alpha"
    ),
    CopySpec("data/examples/RESULT_EXAMPLE", _HATK_CACHE, "HLA_DICTIONARY_*.hg18.imgt3320.*"),
    CopySpec("data/examples/RESULT_EXAMPLE", _HATK_CACHE, "HLA_ALLELE_TABLE.imgt3320.hat"),
    CopySpec(
        "data/examples/RESULT_EXAMPLE", _HATK_CACHE, "HLA_MAPTABLE_*.hg18.imgt3320.txt"
    ),  # Node2 heatmaps
    CopySpec("data/input/BMExample", "examples/BMExample"),
    CopySpec("data/input/GenotypeExample", "examples/GenotypeExample"),
    CopySpec("data/input/FastqExample", "examples/FastqExample"),
    CopySpec("data/examples", "examples/hatk_wtccc", "wtccc_filtered_58C_RA.hatk.300+300*"),
    CopySpec("data/examples/RESULT_EXAMPLE", "examples/hatk_wtccc/RESULT_EXAMPLE"),
    CopySpec("data/examples/MetaAnalysis", "examples/hatk_wtccc/MetaAnalysis"),
    CopySpec("data/examples/OmnibusTest", "examples/hatk_wtccc/OmnibusTest"),
    CopySpec("data/output/HLAImputation/cookhla", "examples/cookhla_v1_output"),
    CopySpec("data/knowledge/Articles", "@root/knowledge/articles"),
]


def _dst_root(spec: CopySpec) -> Path:
    if spec.dst.startswith("@root/"):
        return paths.project_root() / spec.dst.removeprefix("@root/")
    return paths.resources_dir() / spec.dst


def _copy_one(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.name.endswith(":Zone.Identifier"):
        return
    if not dst.exists() or dst.stat().st_size != src.stat().st_size:
        shutil.copy2(src, dst)


def setup_from_v1(v1_root: Path, *, dry_run: bool = False) -> dict[str, int]:
    v1_root = v1_root.expanduser().resolve()
    if not (v1_root / "src" / "tools" / "HATK").exists():
        raise FileNotFoundError(
            f"{v1_root} does not look like an HLAgent v1 checkout (src/tools/HATK missing)"
        )
    counts: dict[str, int] = {}
    for spec in SPECS:
        src_dir = v1_root / spec.src
        key = f"{spec.src}{'/' + spec.glob if spec.glob else ''} -> {spec.dst}"
        if not src_dir.exists():
            counts[key] = -1
            continue
        dst_dir = _dst_root(spec)
        files = sorted(src_dir.glob(spec.glob)) if spec.glob else sorted(p for p in src_dir.rglob("*"))
        n = 0
        for f in files:
            if not f.is_file() or f.name == ".gitkeep" or f.name.endswith(":Zone.Identifier"):
                continue
            rel = f.name if spec.glob else str(f.relative_to(src_dir))
            if not dry_run:
                _copy_one(f, dst_dir / rel)
            n += 1
        counts[key] = n
    if not dry_run:
        write_manifest()
    return counts


def clone_v1(target: Path) -> Path:
    if (target / ".git").exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    proc.run(
        ["git", "clone", "--depth", "1", V1_GIT_URL, str(target)],
        env={"GIT_LFS_SKIP_SMUDGE": "1"},
        timeout=3600,
    )
    return target


def _sha256(path: Path, limit: int = 1 << 20) -> str:
    """sha256 of the first `limit` bytes plus the size (fast fingerprint for big panels)."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        h.update(fh.read(limit))
    h.update(str(path.stat().st_size).encode())
    return h.hexdigest()


def write_manifest() -> Path:
    root = paths.resources_dir()
    entries = {}
    for f in sorted(root.rglob("*")):
        if f.is_file() and f.name != "MANIFEST.json":
            entries[str(f.relative_to(root))] = {"size": f.stat().st_size, "fingerprint": _sha256(f)}
    out = root / "MANIFEST.json"
    out.write_text(json.dumps(entries, indent=1))
    return out
