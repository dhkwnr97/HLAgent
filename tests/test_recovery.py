import json
import subprocess
import sys
import time

import pytest

from hlagent.execution import Cancelled, Runner, alive, process_identity


def test_guardian_reattaches_after_worker_process_dies(tmp_path):
    script = tmp_path / "work.py"
    script.write_text("from pathlib import Path\nimport time\np=Path('submissions.txt')\nwith p.open('a') as f: f.write('once\\n')\ntime.sleep(3)\nPath('complete').write_text('ok')\n")
    launcher = tmp_path / "launch.py"
    launcher.write_text("from pathlib import Path\nfrom hlagent.execution import Runner\nimport sys\nRunner(Path(sys.argv[1])).run('work',[sys.executable,sys.argv[2]])\n")
    process = subprocess.Popen([sys.executable, str(launcher), str(tmp_path), str(script)])
    try:
        for _ in range(100):
            if (tmp_path / "submissions.txt").exists():
                break
            time.sleep(.05)
        assert (tmp_path / "submissions.txt").exists()
        before = json.loads((tmp_path / "work.process.json").read_text())
        process.terminate()
        process.wait(timeout=5)
        Runner(tmp_path).run("work", [sys.executable, str(script)])
        after = json.loads((tmp_path / "work.process.json").read_text())
        assert before == after
        assert (tmp_path / "submissions.txt").read_text() == "once\n"
        assert (tmp_path / "complete").read_text() == "ok"
    finally:
        if process.poll() is None:
            process.kill()


def test_cancellation_targets_only_this_guardian(tmp_path):
    unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(20)"])
    start = time.monotonic()
    try:
        runner = Runner(tmp_path, lambda: time.monotonic() - start > .5)
        with pytest.raises(Cancelled):
            runner.run("cancel", [sys.executable, "-c", "import time; time.sleep(20)"])
        assert not alive(json.loads((tmp_path / "cancel.process.json").read_text()))
        assert unrelated.poll() is None
    finally:
        unrelated.terminate()
        unrelated.wait(timeout=5)


def test_linux_identity_survives_wall_clock_adjustment():
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(20)"])
    try:
        identity = process_identity(process.pid)
        if "start_ticks" not in identity:
            pytest.skip("Linux /proc identity test")
        identity["created"] -= 30
        assert alive(identity)
        identity["start_ticks"] += 1
        assert not alive(identity)
    finally:
        process.terminate()
        process.wait(timeout=5)
