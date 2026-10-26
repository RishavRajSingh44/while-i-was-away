"""Real local inference on synthetic sources; never reads a user's repositories."""
import asyncio
import json
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from away.db import now  # noqa: E402
from away.demo import demo_snapshot  # noqa: E402
from away.git_context import collect_git  # noqa: E402
from away.inference import Ollama, add_verified_facts, make_handoff, synthesize  # noqa: E402
from away.sessions import preview_sessions  # noqa: E402


async def main():
    model = sys.argv[1] if len(sys.argv) > 1 else "gemma3:4b"
    ollama = Ollama()
    digest = await ollama.model_identity(model)
    with tempfile.TemporaryDirectory(prefix="away-synthetic-") as temp:
        path = Path(temp)
        def git(*args):
            return subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false", "-C", temp, *args], check=True, capture_output=True, text=True).stdout
        git("init", "-b", "main")
        git("config", "user.name", "Synthetic developer")
        git("config", "user.email", "demo@example.invalid")
        (path / "cache.py").write_text("def key(workspace):\n    return 'tasks'\n")
        git("add", "cache.py")
        git("commit", "-m", "Initial synthetic task cache")
        git("switch", "-c", "fix/cache-invalidation")
        (path / "cache.py").write_text("def key(workspace):\n    return f'tasks:{workspace}'\n")
        git("add", "cache.py")
        (path / "regression-notes.txt").write_text("Untracked content must not be collected")
        context = collect_git(temp, "2026-10-01T00:00:00+00:00")
        session = preview_sessions(None, json.dumps({"repo_path": temp, "messages": [
            {"role": "user", "text": "Fix stale task lists when switching workspaces. Preserve offline reads and the public cache API."},
            {"role": "assistant", "text": "Workspace-scoped cache keys are staged in cache.py. I reported an earlier test run passed, but no current regression run exists. Global cache clearing was tried and rejected because it broke offline reads."},
            {"role": "user", "text": "Next finish the offline workspace-switch regression. Do not repeat global cache clearing."},
        ]}), "manual", temp)["candidates"][0]
        fixture = demo_snapshot("synthetic-real-inference", "synthetic-observation")
        fixture["git"] = context
        fixture["evidence"] = context["evidence"] + fixture["github"]["evidence"] + session["evidence"]
        fixture["created_at"] = now()
        repository = {"name": "Synthetic Gemma verification", "path": temp}
        started = time.perf_counter()
        try:
            output = await synthesize(ollama, model, fixture["evidence"], lambda: False, lambda stage, progress: print(f"{progress}% {stage}", flush=True))
            output["sections"] = add_verified_facts(output["sections"], fixture)
            handoff = make_handoff(repository, fixture, output["sections"], fixture["evidence"])
            report = {"status": "passed", "checked_at": now(), "model": model, "digest": digest, "runtime": await ollama.request("/api/version"), "hardware": {"system": platform.system(), "architecture": platform.machine()},
                      "elapsed_seconds": round(time.perf_counter() - started, 3), "synthetic_inputs": True, "real_inference": True, "evidence": fixture["evidence"], "output": output, "handoff": handoff,
                      "limitations": ["One synthetic case is not a general quality benchmark.", "Citation validation checks source existence and trust; model prose is interpretation, not independently verified truth.", "No repository tests were run by the app; transcript test statements are historical claims."]}
        except Exception as exc:
            report = {"status": "failed", "checked_at": now(), "model": model, "digest": digest, "elapsed_seconds": round(time.perf_counter() - started, 3), "error": str(exc), "synthetic_inputs": True, "real_inference": True}
        if platform.system() == "Darwin":
            report["memory_bytes"] = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True))
        target = ROOT / "docs/evidence/gemma-run.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2).replace(temp, "<synthetic-repository>") + "\n")
        print(json.dumps({key: report[key] for key in ("status", "model", "elapsed_seconds")}), flush=True)
        if report["status"] != "passed":
            raise SystemExit(report["error"])


if __name__ == "__main__":
    asyncio.run(main())
