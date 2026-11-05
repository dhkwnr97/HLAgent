"""The only way HLAgent runs external programs.

Commands are argument lists (never shell strings), stdout/stderr go to a log file, and the
exact command line is returned so callers can record it in `NodeResult.commands`.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from hlagent.logging_utils import get_logger, redact

log = get_logger(__name__)


class ToolError(RuntimeError):
    """An external tool exited non-zero, timed out, or was not found."""

    def __init__(self, message: str, command: str, log_tail: str = "", returncode: int | None = None):
        super().__init__(message)
        self.command = command
        self.log_tail = log_tail
        self.returncode = returncode

    def __str__(self) -> str:
        tail = f"\n--- log tail ---\n{self.log_tail}" if self.log_tail else ""
        return f"{self.args[0]}\ncommand: {self.command}{tail}"


@dataclass(frozen=True)
class ProcResult:
    command: str
    returncode: int
    seconds: float
    log_path: Path | None
    stdout_path: Path | None


def _tail(path: Path | None, n: int = 40) -> str:
    if path is None or not path.exists():
        return ""
    lines = path.read_text(errors="replace").splitlines()
    return redact("\n".join(lines[-n:]))


def _ledger(command: str, returncode: int, seconds: float) -> None:
    """Append one line per external command to $HLAGENT_PROC_LEDGER (set per run by the runner):
    the provenance record of every tool call and its wall-clock time."""
    path = os.environ.get("HLAGENT_PROC_LEDGER")
    if not path:
        return
    import json

    with open(path, "a", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "ts": time.time(),
                    "seconds": round(seconds, 3),
                    "returncode": returncode,
                    "command": redact(command),
                }
            )
            + "\n"
        )


def run(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    log_path: Path | None = None,
    stdout_path: Path | None = None,
    stdin_path: Path | None = None,
    timeout: float | None = None,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> ProcResult:
    """Run `cmd` and return a `ProcResult`.

    - `stdout_path`: write stdout there (for tools that print their main output, e.g. linkage2beagle.jar);
      otherwise stdout is appended to `log_path`.
    - `stdin_path`: feed this file to stdin.
    - `env`: extra variables merged over the current environment.
    """
    if not isinstance(cmd, list) or not cmd or not all(isinstance(c, str) for c in cmd):
        raise TypeError("cmd must be a non-empty list[str]")
    command = shlex.join(cmd)
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
    if stdout_path is not None:
        stdout_path.parent.mkdir(parents=True, exist_ok=True)

    full_env = None
    if env:
        full_env = {**os.environ, **env}

    log.info("run: %s", command)
    t0 = time.monotonic()
    log_fh = open(log_path, "a", encoding="utf-8") if log_path else subprocess.DEVNULL  # noqa: SIM115
    out_fh = open(stdout_path, "wb") if stdout_path else log_fh  # noqa: SIM115
    in_fh = open(stdin_path, "rb") if stdin_path else subprocess.DEVNULL  # noqa: SIM115
    try:
        if log_path:
            log_fh.write(f"$ {redact(command)}\n")  # type: ignore[union-attr]
            log_fh.flush()  # type: ignore[union-attr]
        proc = subprocess.run(  # noqa: S603 - argument list, no shell
            cmd,
            cwd=str(cwd) if cwd else None,
            stdin=in_fh,
            stdout=out_fh,
            stderr=log_fh,
            timeout=timeout,
            env=full_env,
            check=False,
        )
    except FileNotFoundError as e:
        raise ToolError(f"executable not found: {cmd[0]}", command) from e
    except subprocess.TimeoutExpired as e:
        raise ToolError(f"timed out after {timeout}s", command, _tail(log_path)) from e
    finally:
        for fh in {id(log_fh): log_fh, id(out_fh): out_fh, id(in_fh): in_fh}.values():
            if fh is not subprocess.DEVNULL:
                fh.close()  # type: ignore[union-attr]
    seconds = time.monotonic() - t0
    _ledger(command, proc.returncode, seconds)
    if check and proc.returncode != 0:
        raise ToolError(f"exit code {proc.returncode}", command, _tail(log_path), proc.returncode)
    return ProcResult(command, proc.returncode, seconds, log_path, stdout_path)
