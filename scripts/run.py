"""Single-command local launch; dependencies must be installed first."""
import argparse
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["dev", "start"])
    args = parser.parse_args()
    os.chdir(ROOT)
    environment = {**os.environ, "PYTHONPATH": str(ROOT / "backend"), "AWAY_DEV": "1" if args.mode == "dev" else "0"}
    children = []

    def stop(*_):
        for child in children:
            if child.poll() is None:
                child.terminate()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    if args.mode == "start" and not (ROOT / "frontend/dist/index.html").exists():
        raise SystemExit("Build the frontend first: npm --prefix frontend run build")
    port = environment.get("AWAY_PORT", "8765")
    print(f"While I Was Away: http://127.0.0.1:{'5173' if args.mode == 'dev' else port}", flush=True)
    try:
        children.append(subprocess.Popen([sys.executable, "-m", "uvicorn", "away.main:app", "--host", "127.0.0.1", "--port", port, "--no-access-log"], env=environment))
        if args.mode == "dev":
            npm = shutil.which("npm")
            if not npm:
                raise SystemExit("Node/npm required for development")
            children.append(subprocess.Popen([npm, "run", "dev"], cwd=ROOT / "frontend", env=environment))
        while all(child.poll() is None for child in children):
            try:
                children[0].wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                pass
    finally:
        stop()
        for child in children:
            try:
                child.wait(timeout=8)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == "__main__":
    main()
