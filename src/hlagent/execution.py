from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import psutil

from hlagent.models import digest


class Cancelled(Exception):
    pass


def alive(record: dict) -> bool:
    try:
        proc = psutil.Process(record["pid"])
        if proc.status() == psutil.STATUS_ZOMBIE:
            return False
        if "start_ticks" in record:
            current = process_identity(proc.pid)
            return current.get("start_ticks") == record["start_ticks"] and current.get("boot_id") == record.get("boot_id")
        return abs(proc.create_time() - record["created"]) < 0.1
    except (psutil.NoSuchProcess, KeyError):
        return False


def process_identity(pid: int) -> dict:
    record = {"pid": pid, "created": psutil.Process(pid).create_time()}
    stat = Path(f"/proc/{pid}/stat")
    if stat.exists():
        try:
            record["start_ticks"] = int(stat.read_text().rsplit(")", 1)[1].split()[19])
            record["boot_id"] = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        except FileNotFoundError as exc:
            raise psutil.NoSuchProcess(pid) from exc
    return record


class Runner:
    def __init__(self, directory: Path, cancelled=lambda: False, restart_completed: bool = False):
        self.directory = directory
        self.cancelled = cancelled
        self.restart_completed = restart_completed
        directory.mkdir(parents=True, exist_ok=True)

    def run(self, name: str, argv: list[str], cwd: Path | None = None) -> Path:
        if self.cancelled():
            raise Cancelled()
        cwd = (cwd or self.directory).resolve()
        argv = [str(a) for a in argv]
        prefix = self.directory / name
        command, exit_path, state_path, log = [prefix.with_suffix(ext) for ext in
                                              (".command.json", ".exit.json", ".process.json", ".log")]
        spec = dict(argv=argv, cwd=str(cwd), exit=str(exit_path), log=str(log))
        fingerprint = digest(spec)
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        same = state.get("fingerprint") == fingerprint
        if state and not same and alive(state):
            raise ValueError("A running command cannot be changed")
        if same and exit_path.exists() and json.loads(exit_path.read_text())["returncode"] == 0:
            return log
        if not (same and alive(state)):
            exit_path.unlink(missing_ok=True)
            command.write_text(json.dumps(spec))
            proc = subprocess.Popen([sys.executable, "-m", "hlagent.process_runner", str(command)],
                                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, start_new_session=True)
            state = {**process_identity(proc.pid), "fingerprint": fingerprint}
            state_path.write_text(json.dumps(state))
        while not exit_path.exists():
            if self.cancelled():
                if alive(state):
                    os.killpg(state["pid"], signal.SIGTERM)
                    for _ in range(20):
                        if not alive(state):
                            break
                        time.sleep(0.1)
                    if alive(state):
                        os.killpg(state["pid"], signal.SIGKILL)
                raise Cancelled()
            if not alive(state):
                time.sleep(0.1)
                if not exit_path.exists():
                    raise RuntimeError("Command was interrupted; resume restarts this command")
            time.sleep(0.2)
        code = json.loads(exit_path.read_text())["returncode"]
        if code:
            tail = log.read_text(errors="replace")[-3000:]
            raise RuntimeError(f"{name} exited with code {code}. {tail}")
        return log

    def docker(self, name: str, image: str, command: list[str], mounts: dict[Path, tuple[str, bool]],
               memory_gb: int, threads: int, fingerprint: str) -> Path:
        """Reattach to a labeled Docker job; never repeat a live container submission."""
        inspect = subprocess.run(["docker", "inspect", name], capture_output=True, text=True)
        if inspect.returncode == 0:
            info = json.loads(inspect.stdout)[0]
            if info["Config"]["Labels"].get("hlagent.fingerprint") != fingerprint:
                raise ValueError("Container identity does not match the approved analysis")
            if info["State"]["Status"] in ("exited", "dead") and (info["State"]["ExitCode"] != 0 or self.restart_completed):
                subprocess.run(["docker", "rm", name], check=True, capture_output=True)
                inspect = None
        if inspect is None or inspect.returncode != 0:
            argv = ["docker", "create", "--name", name, "--label", "hlagent.managed=true",
                    "--label", f"hlagent.fingerprint={fingerprint}", "--network", "none",
                    "--memory", f"{memory_gb}g", "--cpus", str(threads), "--user", "0:0"]
            for host, (container, read_only) in mounts.items():
                argv.extend(["--mount", f"type=bind,source={host.resolve()},target={container}" +
                             (",readonly" if read_only else "")])
            subprocess.run(argv + [image, *command], check=True, capture_output=True)
        current = json.loads(subprocess.run(["docker", "inspect", name], capture_output=True,
                                            text=True, check=True).stdout)[0]
        if current["State"]["Status"] == "created":
            subprocess.run(["docker", "start", name], check=True, capture_output=True)
        while True:
            if self.cancelled():
                subprocess.run(["docker", "stop", "-t", "5", name], capture_output=True)
                raise Cancelled()
            info = json.loads(subprocess.run(["docker", "inspect", name], check=True,
                                             capture_output=True, text=True).stdout)[0]
            if not info["State"]["Running"]:
                break
            time.sleep(1)
        log = self.directory / "cookhla.log"
        output = subprocess.run(["docker", "logs", name], capture_output=True)
        log.write_bytes(output.stdout + output.stderr)
        if info["State"]["ExitCode"] != 0:
            raise RuntimeError(f"CookHLA failed; see {log.name}: " + log.read_text(errors="replace")[-2000:])
        return log
