from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from hlagent.tools.cookhla import (
    COOKHLA_IMAGE,
    CookHLAParams,
    alleles_summary,
    build_command,
    check_memory_budget,
    read_alleles,
)


def _params(tmp_path: Path, **kw) -> CookHLAParams:
    base = dict(
        input_prefix=tmp_path / "in" / "study",
        hg="18",
        reference_prefix=tmp_path / "ref" / "panel",
        out_dir=tmp_path / "out",
        out_name="study+REF",
    )
    base.update(kw)
    return CookHLAParams(**base)


def test_command_shape_and_offline(tmp_path):
    cmd = build_command(_params(tmp_path), user="1000:1000")
    assert cmd[:3] == ["docker", "run", "--rm"]
    assert ["--network", "none"] == cmd[cmd.index("--network") : cmd.index("--network") + 2]
    assert "--user" in cmd and cmd[cmd.index("--user") + 1] == "1000:1000"
    assert COOKHLA_IMAGE in cmd
    i = cmd.index(COOKHLA_IMAGE)
    assert cmd[i + 1] == "CookHLA.py"
    assert cmd[cmd.index("-o") + 1] == "/out/study+REF"
    assert "-mp" not in cmd  # n_processes == 1 must be omitted (argparse choices 2..9)


def test_mp_and_agm(tmp_path):
    gm, ae = tmp_path / "in" / "AGM.x.mach_step.avg.clpsB", tmp_path / "in" / "AGM.x.aver.erate"
    cmd = build_command(_params(tmp_path, n_processes=4, genetic_map=gm, error_rate=ae), user="1:1")
    assert cmd[cmd.index("-mp") + 1] == "4"
    assert cmd[cmd.index("-gm") + 1] == "/data/in/AGM.x.mach_step.avg.clpsB"


@pytest.mark.parametrize("bad", ["study.", "has space", "a/b"])
def test_out_name_validation(tmp_path, bad):
    with pytest.raises(ValidationError):
        _params(tmp_path, out_name=bad)


def test_agm_must_be_pair(tmp_path):
    with pytest.raises(ValidationError):
        _params(tmp_path, genetic_map=tmp_path / "x.clpsB")


def test_memory_budget(tmp_path):
    p = _params(tmp_path, n_processes=6, java_mem_gb=16)
    ok, need, _ = check_memory_budget(p, available_gb=24)
    assert need == 98 and not ok
    ok2, _, _ = check_memory_budget(_params(tmp_path, n_processes=2, java_mem_gb=4), available_gb=24)
    assert ok2


def test_liftover_chains_required_for_hg19(tmp_path):
    p = _params(tmp_path, hg="19")
    assert p.missing_chains() == ["hg19ToHg18.over.chain.gz"]
    chains = tmp_path / "chains"
    chains.mkdir()
    (chains / "hg19ToHg18.over.chain.gz").write_bytes(b"x")
    p2 = _params(tmp_path, hg="19", liftover_dir=chains)
    assert p2.missing_chains() == []
    cmd = build_command(p2, user="1:1")
    assert f"{chains.resolve()}:/tmp/.pyliftover:ro" in cmd
    assert _params(tmp_path, hg="38").missing_chains() == [
        "hg38ToHg19.over.chain.gz",
        "hg19ToHg18.over.chain.gz",
    ]


def test_read_alleles_headerless(tmp_path):
    f = tmp_path / "x.alleles"
    f.write_text(
        "S1 S1 A 02,24 0201,2402 0.5 0.485 0.985\nS2 S2 A 01,03 0101,0301 0.5 0.5 1\n"
        "S1 S1 B 07,37 0702,3701 0.34 0.34 0.68\n"
    )
    df = read_alleles(f)
    assert list(df.columns)[:3] == ["FID", "IID", "gene"] and len(df) == 3
    s = alleles_summary(df, conf_threshold=0.8)
    assert s["A"]["n_calls"] == 2 and s["B"]["frac_conf_below_threshold"] == 1.0
