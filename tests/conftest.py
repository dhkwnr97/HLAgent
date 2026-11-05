from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from pydantic_ai import models

from hlagent import paths

# Unit tests must never call real model APIs.
models.ALLOW_MODEL_REQUESTS = False

ROOT = paths.project_root()
RES = paths.resources_dir()
HATK_EX = RES / "examples" / "hatk_wtccc"


def _has(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _docker_ok() -> bool:
    if not _has("docker"):
        return False
    try:
        return (
            subprocess.run(["docker", "info"], capture_output=True, timeout=20, check=False).returncode == 0
        )  # noqa: S603, S607
    except (OSError, subprocess.TimeoutExpired):
        return False


needs_plink = pytest.mark.skipif(not _has("plink"), reason="plink (1.9) not on PATH")
needs_r = pytest.mark.skipif(not _has("Rscript"), reason="Rscript not on PATH")
needs_java = pytest.mark.skipif(not _has("java"), reason="java not on PATH")
needs_docker = pytest.mark.skipif(not _docker_ok(), reason="docker daemon not available")
needs_resources = pytest.mark.skipif(not HATK_EX.exists(), reason="run `hlagent setup-resources` first")


@pytest.fixture
def hatk_ex() -> Path:
    return HATK_EX


@pytest.fixture
def ra_bfile() -> Path:
    return HATK_EX / "RESULT_EXAMPLE" / "RESULT_EXAMPLE_wtccc_filtered_58C_RA.hatk.300+300.chr6.hg18"
