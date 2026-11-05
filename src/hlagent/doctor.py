"""Environment checks shared by `hlagent doctor` and the GUI settings page."""

from __future__ import annotations

import subprocess
from typing import Literal, TypedDict

from hlagent import paths

Status = Literal["PASS", "WARN", "FAIL"]


class Check(TypedDict):
    name: str
    status: Status
    detail: str
    fix: str


def _version(cmd: list[str]) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)  # noqa: S603
        text = [t for t in (r.stdout + r.stderr).strip().splitlines() if "JAVA_TOOL_OPTIONS" not in t]
        return text[0] if text else "?"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def _c(name: str, ok: bool, detail: str, fix: str = "", level: Status = "FAIL") -> Check:
    return {"name": name, "status": "PASS" if ok else level, "detail": detail, "fix": "" if ok else fix}


def run_checks(keys=None) -> list[Check]:
    """Tools, resources, Docker image, memory and API keys (`keys`: llm.registry.Keys; defaults to .env)."""
    from hlagent.config import get_settings
    from hlagent.tools.cookhla import COOKHLA_IMAGE, mem_available_gb

    s = get_settings()
    out: list[Check] = []
    pv = _version([s.hlagent_plink, "--version"])
    out.append(
        _c(
            "PLINK 1.9",
            pv.startswith("PLINK v1.9"),
            pv or "not found",
            "mamba install -c bioconda plink=1.90 (binary name per HLAGENT_PLINK)",
        )
    )
    jv = _version([s.hlagent_java, "-version"])
    out.append(_c("Java", bool(jv), jv or "not found", "mamba install -c conda-forge openjdk=17"))
    rv = _version(
        [
            s.hlagent_rscript,
            "-e",
            "suppressMessages({library(gplots);library(RColorBrewer);library(shape)});cat('ok')",
        ]
    )
    out.append(
        _c(
            "R + gplots/RColorBrewer/shape",
            rv.endswith("ok"),
            rv or "not found",
            "mamba install -c conda-forge r-base r-gplots r-rcolorbrewer r-shape",
        )
    )
    dv = _version([s.hlagent_docker, "info", "--format", "{{.ServerVersion}}"])
    docker_ok = bool(dv) and "error" not in dv.lower() and "cannot connect" not in dv.lower()
    out.append(
        _c(
            "Docker daemon",
            docker_ok,
            dv or "not reachable",
            "start Docker Desktop (WSL integration) or `sudo service docker start`",
            "WARN",
        )
    )
    img_ok = (
        docker_ok
        and subprocess.run(  # noqa: S603
            [s.hlagent_docker, "image", "inspect", COOKHLA_IMAGE],  # noqa: S603
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )
    out.append(
        _c(
            "CookHLA image (pinned)",
            img_ok,
            COOKHLA_IMAGE.split("@")[1][:19] + "...",
            f"docker pull {COOKHLA_IMAGE}",
            "WARN",
        )
    )
    jars = ["beagle.jar", "beagle2vcf.jar", "vcf2beagle.jar", "linkage2beagle.jar"]
    out.append(
        _c(
            "BEAGLE 3.3.2 + utilities",
            all((paths.beagle_dir() / j).exists() for j in jars),
            str(paths.beagle_dir()),
        )
    )
    ref = paths.reference_panels_dir() / "1000G_REF"
    out.append(
        _c(
            "1000G_REF panels",
            ref.exists() and any(ref.glob("*.bgl.phased")),
            str(ref),
            "hlagent setup-resources --from-v1 <path to HLAgent-main_v1.0.0>",
        )
    )
    cache = paths.hatk_cache_dir() / "hg18_imgt3320"
    out.append(
        _c(
            "HATK hg18/IMGT3320 cache",
            (cache / "HLA_ALLELE_TABLE.imgt3320.hat").exists(),
            str(cache),
            "hlagent setup-resources --from-v1 <v1 path>",
        )
    )
    lo = paths.resources_dir() / "liftover"
    out.append(
        _c(
            "Liftover chains (hg19/hg38)",
            (lo / "hg19ToHg18.over.chain.gz").exists(),
            str(lo),
            "optional: hlagent setup-resources --liftover-chains (rsID re-mapping is used otherwise)",
            "WARN",
        )
    )
    mem = mem_available_gb()
    out.append(
        _c(
            "Available memory",
            mem >= 6,
            f"{mem:.1f} GB",
            "raise memory= in %UserProfile%\\.wslconfig",
            "WARN",
        )
    )
    if keys is None:
        from hlagent.llm.registry import Keys

        keys = Keys.resolve(s)
    names = ("google", "openai", "anthropic", "tavily", "typesafe")
    out.append(
        _c(
            "LLM key (any)",
            bool(keys.providers()),
            ", ".join(f"{n}={'set' if keys.has(n) else '-'}" for n in names),
            "put GOOGLE_API_KEY in .env or enter it in the GUI",
            "WARN",
        )
    )
    return out
