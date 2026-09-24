"""Real local worker/HTTP/SQLite restart. No Meta calls or real publications."""
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.request


def test_worker_and_queue_survive_process_restart(tmp_path):
    root = Path(__file__).resolve().parents[1]
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    db = tmp_path / "runtime.db"
    env = {k: v for k, v in os.environ.items() if not k.startswith(
        ("META_", "FACEBOOK_", "INSTAGRAM_", "RAILWAY_", "AUTOMATION_", "SCHEDULE", "ENVIRONMENT"))}
    env.update({"SCHEDULE_DB_PATH": str(db), "SCHEDULER_ENABLED": "true",
                "SCHEDULER_POLL_SECONDS": "5", "PORT": str(port),
                "ENVIRONMENT": "test", "AUTOMATION_API_KEY": "local-runtime-test",
                "FACEBOOK_PAGE_ID": "123", "INSTAGRAM_BUSINESS_ACCOUNT_ID": "456"})
    base = f"http://127.0.0.1:{port}"

    def request(path, payload=None):
        req = urllib.request.Request(base + path,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={"x-automation-key": "local-runtime-test", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=2) as response:
            return json.load(response)

    def start():
        return subprocess.Popen([sys.executable, "-m", "uvicorn", "SOCIALMEDIAAUTOMATION:app",
                                 "--host", "127.0.0.1", "--port", str(port)],
            cwd=root, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)

    def await_cycle(process, previous=None):
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            assert process.poll() is None, "Local service exited before worker verification"
            try:
                state = request("/scheduler/status")
                if state["last_finished_at"] and state["last_finished_at"] != previous:
                    assert state["worker_running"] is True
                    assert state["paused"] is True
                    assert state["last_result"]["published"] == 0
                    return state
            except (OSError, ValueError):
                pass
            time.sleep(0.1)
        raise AssertionError("Local worker did not finish a cycle")

    def stop(process):
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    process = start()
    try:
        first = await_cycle(process)
        item = request("/editorial/posts", {"idempotency_key": "runtime-draft",
            "platform": "facebook", "caption": "Local persistence fixture; never publish"})
        request(f"/editorial/posts/{item['id']}/approve", {})
        request(f"/editorial/posts/{item['id']}/schedule", {"publish_at": "2099-01-01T12:00:00-05:00"})
        interrupted = request("/editorial/posts", {"idempotency_key": "interrupted-fixture",
            "platform": "instagram", "caption": "Local interrupted fixture", "image_url": "https://example.com/test.jpg"})
    finally:
        stop(process)
    # Simulate a previous process dying after storing the provider container.
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE editorial_posts SET status='publishing',started_at='2020-01-01T00:00:00+00:00',container_id='fixture_container' WHERE id=?", (interrupted["id"],))
    process = start()
    try:
        await_cycle(process, first["last_finished_at"])
        rows = {row["id"]: row for row in request("/editorial/posts")}
        assert rows[item["id"]]["status"] == "scheduled"
        assert rows[item["id"]]["approved_at"] is not None
        assert rows[item["id"]]["timezone"] == "America/New_York"
        assert rows[interrupted["id"]]["status"] == "needs_review"
        assert rows[interrupted["id"]]["container_id"] == "fixture_container"
    finally:
        stop(process)
