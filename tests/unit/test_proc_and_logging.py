from __future__ import annotations

import pytest

from hlagent.logging_utils import redact, register_secret
from hlagent.tools import proc


def test_run_records_command_and_log(tmp_path):
    log = tmp_path / "x.log"
    r = proc.run(["python3", "-c", "print('hello')"], log_path=log)
    assert r.returncode == 0
    assert r.command.startswith("python3 -c")
    assert "hello" in log.read_text()


def test_run_stdout_to_file(tmp_path):
    out = tmp_path / "o.txt"
    proc.run(["python3", "-c", "print('payload')"], stdout_path=out, log_path=tmp_path / "l.log")
    assert out.read_text().strip() == "payload"


def test_run_failure_raises_with_tail(tmp_path):
    with pytest.raises(proc.ToolError) as ei:
        proc.run(
            ["python3", "-c", "import sys; sys.stderr.write('boom\\n'); sys.exit(3)"],
            log_path=tmp_path / "l.log",
        )
    assert ei.value.returncode == 3
    assert "boom" in ei.value.log_tail


def test_run_rejects_shell_strings():
    with pytest.raises(TypeError):
        proc.run("echo hi")  # type: ignore[arg-type]


def test_missing_executable(tmp_path):
    with pytest.raises(proc.ToolError, match="executable not found"):
        proc.run(["definitely-not-a-real-binary-xyz"], log_path=tmp_path / "l.log")


def test_redaction_of_registered_and_pattern_keys():
    register_secret("my-very-secret-value-123")
    text = "key my-very-secret-value-123 and AIzaSyA1234567890abcdefghijklmnopqrstuv and api_key=abc123def"
    out = redact(text)
    assert "my-very-secret-value-123" not in out
    assert "AIzaSy" not in out
    assert "abc123def" not in out
