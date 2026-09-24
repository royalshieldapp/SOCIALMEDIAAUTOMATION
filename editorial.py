"""Durable approval queue. No network calls and no automatic retry of writes."""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException


def now():
    return datetime.now(timezone.utc).isoformat()


def zone(name):
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(422, "Unknown IANA timezone") from None


class EditorialStore:
    @contextmanager
    def connect(self):
        path = os.getenv("SCHEDULE_DB_PATH", "/tmp/socialmediaautomation.db")
        if os.getenv("ENVIRONMENT", "").lower() == "production":
            mount = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "")
            if not mount or not Path(path).resolve().is_relative_to(Path(mount).resolve()):
                raise HTTPException(503, "A persistent Railway volume is required for the editorial database")
        conn = sqlite3.connect(path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS editorial_posts (
                    id INTEGER PRIMARY KEY, idempotency_key TEXT NOT NULL UNIQUE,
                    payload_json TEXT NOT NULL, platform TEXT NOT NULL,
                    target_id TEXT NOT NULL, timezone TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'draft', created_at TEXT NOT NULL,
                    approved_at TEXT, publish_at TEXT, started_at TEXT,
                    published_at TEXT, external_id TEXT, permalink TEXT, last_error TEXT
                );
                CREATE TABLE IF NOT EXISTS editorial_control (
                    id INTEGER PRIMARY KEY CHECK(id=1), paused INTEGER NOT NULL
                );
                INSERT OR IGNORE INTO editorial_control VALUES(1,1);
                CREATE TABLE IF NOT EXISTS editorial_scheduler (
                    id INTEGER PRIMARY KEY CHECK(id=1), last_started_at TEXT,
                    last_finished_at TEXT, last_result TEXT
                );
                INSERT OR IGNORE INTO editorial_scheduler(id) VALUES(1);
                CREATE TABLE IF NOT EXISTS editorial_comments (
                    id INTEGER PRIMARY KEY, event_key TEXT NOT NULL UNIQUE,
                    platform TEXT NOT NULL, comment_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL, category TEXT NOT NULL,
                    suggested_reply TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending_review',
                    created_at TEXT NOT NULL
                );
            """)
            # Additive migration serialized across workers; preserve existing queues.
            conn.execute("BEGIN IMMEDIATE")
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(editorial_posts)")}
            if "container_id" not in columns:
                conn.execute("ALTER TABLE editorial_posts ADD COLUMN container_id TEXT")
            conn.commit()
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def record(row):
        item = dict(row)
        item.update(json.loads(item.pop("payload_json")))
        return item

    def get(self, post_id):
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM editorial_posts WHERE id=?", (post_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Draft not found")
        return self.record(row)

    def posts(self):
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM editorial_posts ORDER BY id DESC LIMIT 200").fetchall()
        return [self.record(row) for row in rows]

    def create(self, payload, key, target_id, timezone_name):
        zone(timezone_name)
        data = json.dumps(payload, sort_keys=True)
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM editorial_posts WHERE idempotency_key=?", (key,)).fetchone()
            if row:
                if (row["payload_json"], row["target_id"], row["timezone"]) != (data, target_id, timezone_name):
                    raise HTTPException(409, "Idempotency key already belongs to different content or destination")
                return self.record(row)
            cur = conn.execute("INSERT INTO editorial_posts(idempotency_key,payload_json,platform,target_id,timezone,created_at) VALUES(?,?,?,?,?,?)",
                               (key, data, payload["platform"], target_id, timezone_name, now()))
            post_id = cur.lastrowid
        return self.get(post_id)

    def approve(self, post_id):
        with self.connect() as conn:
            cur = conn.execute("UPDATE editorial_posts SET status='approved',approved_at=? WHERE id=? AND status='draft'", (now(), post_id))
            if cur.rowcount != 1:
                raise HTTPException(409, "Only a draft can be approved")
        return self.get(post_id)

    def schedule(self, post_id, value):
        item = self.get(post_id)
        if item["status"] != "approved":
            raise HTTPException(409, "Explicit approval is required before scheduling")
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None or dt <= datetime.now(timezone.utc):
                raise ValueError()
            if dt.utcoffset() != dt.astimezone(zone(item["timezone"])).utcoffset():
                raise ValueError()
        except (TypeError, ValueError):
            raise HTTPException(422, "Use a future timestamp with the offset of the draft's IANA timezone") from None
        with self.connect() as conn:
            cur = conn.execute("UPDATE editorial_posts SET status='scheduled',publish_at=? WHERE id=? AND status='approved'",
                               (dt.astimezone(timezone.utc).isoformat(), post_id))
            if cur.rowcount != 1:
                raise HTTPException(409, "Draft state changed; refresh before scheduling")
        return self.get(post_id)

    def control(self, paused=None):
        with self.connect() as conn:
            if paused is not None:
                conn.execute("UPDATE editorial_control SET paused=? WHERE id=1", (int(paused),))
            return {"paused": bool(conn.execute("SELECT paused FROM editorial_control WHERE id=1").fetchone()[0])}

    def cancel(self, post_id):
        with self.connect() as conn:
            cur = conn.execute("UPDATE editorial_posts SET status='cancelled' WHERE id=? AND status IN ('draft','approved','scheduled')", (post_id,))
            if cur.rowcount != 1:
                raise HTTPException(409, "Cannot cancel an in-flight or completed publication")
        return self.get(post_id)

    def claim_due(self):
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            cutoff = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
            conn.execute("UPDATE editorial_posts SET status='needs_review',last_error='Worker interrupted; verify Meta before any new attempt' WHERE status='publishing' AND started_at<?", (cutoff,))
            if conn.execute("SELECT paused FROM editorial_control WHERE id=1").fetchone()[0]:
                return None
            # A restart must not release old campaigns outside their approved window.
            conn.execute("UPDATE editorial_posts SET status='needs_review',last_error='Scheduled time missed by more than 15 minutes; review and approve a new schedule' WHERE status='scheduled' AND publish_at<?", (cutoff,))
            row = conn.execute("SELECT * FROM editorial_posts WHERE status='scheduled' AND approved_at IS NOT NULL AND publish_at<=? ORDER BY publish_at,id LIMIT 1", (now(),)).fetchone()
            if row is None:
                return None
            conn.execute("UPDATE editorial_posts SET status='publishing',started_at=? WHERE id=?", (now(), row["id"]))
            return self.record(row)

    def container(self, post_id, container_id):
        with self.connect() as conn:
            cur = conn.execute("UPDATE editorial_posts SET container_id=? WHERE id=? AND status='publishing'", (container_id, post_id))
            if cur.rowcount != 1:
                raise HTTPException(409, "Publication state changed before container could be saved")

    def scheduler_started(self):
        with self.connect() as conn:
            conn.execute("UPDATE editorial_scheduler SET last_started_at=? WHERE id=1", (now(),))

    def scheduler_finished(self, result):
        with self.connect() as conn:
            conn.execute("UPDATE editorial_scheduler SET last_finished_at=?,last_result=? WHERE id=1", (now(), json.dumps(result)))

    def scheduler_status(self):
        with self.connect() as conn:
            row = dict(conn.execute("SELECT last_started_at,last_finished_at,last_result FROM editorial_scheduler WHERE id=1").fetchone())
            row["last_result"] = json.loads(row["last_result"]) if row["last_result"] else None
            row["paused"] = bool(conn.execute("SELECT paused FROM editorial_control WHERE id=1").fetchone()[0])
            row["queue_counts"] = {item["status"]: item["total"] for item in conn.execute("SELECT status,COUNT(*) AS total FROM editorial_posts GROUP BY status")}
            cutoff = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
            row["due_within_window"] = conn.execute("SELECT COUNT(*) FROM editorial_posts WHERE status='scheduled' AND approved_at IS NOT NULL AND publish_at BETWEEN ? AND ?", (cutoff, now())).fetchone()[0]
            row["overdue_for_review"] = conn.execute("SELECT COUNT(*) FROM editorial_posts WHERE status='scheduled' AND publish_at<?", (cutoff,)).fetchone()[0]
        return row

    def success(self, post_id, external_id):
        with self.connect() as conn:
            conn.execute("UPDATE editorial_posts SET status='published',external_id=?,published_at=?,last_error=NULL WHERE id=? AND status='publishing'", (external_id, now(), post_id))

    def link(self, post_id, permalink):
        with self.connect() as conn:
            conn.execute("UPDATE editorial_posts SET permalink=? WHERE id=? AND status='published'", (permalink, post_id))

    def failure(self, post_id, error, status="needs_review"):
        with self.connect() as conn:
            conn.execute("UPDATE editorial_posts SET status=?,last_error=? WHERE id=? AND status='publishing'", (status, error, post_id))

    def comment(self, event, category, reply):
        with self.connect() as conn:
            cur = conn.execute("INSERT OR IGNORE INTO editorial_comments(event_key,platform,comment_id,payload_json,category,suggested_reply,created_at) VALUES(?,?,?,?,?,?,?)",
                               (f"{event.platform}:{event.comment_id}", event.platform, event.comment_id, json.dumps(event.model_dump()), category, reply, now()))
            return cur.rowcount == 1

    def comments(self):
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM editorial_comments ORDER BY id DESC LIMIT 200").fetchall()
        return [self.record(row) for row in rows]
