"""Private process guardian: survives worker/API restarts and records an exit status."""
import json
import subprocess
import sys
from pathlib import Path


def main():
    command = Path(sys.argv[1])
    data = json.loads(command.read_text())
    with Path(data["log"]).open("ab", buffering=0) as log:
        try:
            result = subprocess.run(data["argv"], cwd=data["cwd"], stdout=log, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, check=False)
            status = {"returncode": result.returncode}
        except Exception as exc:
            log.write((type(exc).__name__ + ": " + str(exc) + "\n").encode())
            status = {"returncode": 127}
    out = Path(data["exit"])
    temp = out.with_suffix(".partial")
    temp.write_text(json.dumps(status))
    temp.replace(out)


if __name__ == "__main__":
    main()
