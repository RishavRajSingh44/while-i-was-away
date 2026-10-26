"""Export only known synthetic fixtures for the isolated static frontend."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from away.demo import demo_briefing, demo_session, demo_snapshot  # noqa: E402

repository = {"id": "public-demo", "name": "Northstar", "path": "demo://northstar", "demo": True, "created_at": "2026-10-24T10:00:00Z", "acknowledged_snapshot_id": None}
snapshot = demo_snapshot(repository["id"], "demo-snapshot")
snapshot["created_at"] = repository["created_at"]
briefing = demo_briefing(repository, snapshot, "demo-briefing")
briefing["created_at"] = repository["created_at"]
fixture = {"repository": repository, "overview": {"repository": repository, "snapshot": snapshot, "briefing": briefing, "sessions": [demo_session()], "jobs": [], "history": [briefing]},
           "health": {"version": "0.1.0 · public demo", "git": {"ok": False, "message": "Synthetic Git snapshot; no filesystem access"}, "github": {"ok": False, "message": "Synthetic cached PRs; no GitHub connection"}, "ollama": {"ok": False, "message": "Precomputed synthetic briefing; no live inference", "models": []}},
           "settings": {"model": "gemma3:4b", "exclusions": []}}
assert fixture["repository"]["path"].startswith("demo://")
assert fixture["overview"]["briefing"]["demo"]
target = ROOT / "frontend/public/demo-data.json"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(fixture, indent=2) + "\n")
print("Exported explicitly synthetic public fixture:", target.name)
