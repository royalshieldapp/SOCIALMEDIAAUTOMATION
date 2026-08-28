"""Royal Shield social media automation backend.

Standalone FastAPI service for Meta, Facebook, Instagram, and Railway.
Make.com is not required.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import re
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

import httpx
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Path, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

APP_VERSION = "3.0.0"
DEFAULT_META_GRAPH_API_VERSION = "v25.0"
META_REQUEST_TIMEOUT_SECONDS = 20.0
META_ID_PATTERN = r"^[A-Za-z0-9_-]+$"
MAX_WEBHOOK_BYTES = 1_000_000
logger = logging.getLogger("socialmediaautomation")
app = FastAPI(title="SOCIALMEDIAAUTOMATION", version=APP_VERSION)

Category = Literal[
    "urgent",
    "lead",
    "soporte",
    "comentario_publico",
    "spam",
    "irrelevante",
    "meta_event",
]
Action = Literal["auto_reply", "manual_review", "ignore"]
Platform = Literal["facebook", "instagram"]


class CommentPayload(BaseModel):
    platform: Platform
    comment_id: str
    comment_text: str
    user_name: str
    timestamp: Optional[str] = None
    post_id: Optional[str] = None


class PublishPayload(BaseModel):
    platform: Platform
    caption: str = Field(..., min_length=1, max_length=2200)
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    publish_at: Optional[str] = None

    @field_validator("image_url", "video_url")
    @classmethod
    def validate_media_urls(cls, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        if not re.match(r"^https://", value):
            raise ValueError("media URLs must start with https://")
        return value

    @field_validator("caption")
    @classmethod
    def validate_caption(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("caption cannot be empty")
        return cleaned

    @field_validator("publish_at")
    @classmethod
    def validate_publish_at(cls, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("publish_at must include a timezone")
        return parsed.astimezone(timezone.utc).isoformat()

    @model_validator(mode="after")
    def validate_platform_media(self):
        if self.image_url and self.video_url:
            raise ValueError("provide only one of image_url or video_url")
        if self.platform == "instagram" and not (self.image_url or self.video_url):
            raise ValueError("Instagram publishing requires image_url or video_url")
        return self


class CommentReplyPayload(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("message cannot be empty")
        return cleaned


class StateStore:
    """SQLite state store for idempotency and scheduled posts."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    @property
    def path(self) -> str:
        return os.getenv("SCHEDULE_DB_PATH", "/tmp/socialmediaautomation.db")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def ensure_schema(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS processed_events (
                    event_key TEXT PRIMARY KEY,
                    processed_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS scheduled_posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    payload_json TEXT NOT NULL,
                    publish_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    published_at TEXT
                )
                """
            )
            conn.commit()

    def claim_event(self, event_key: str) -> bool:
        self.ensure_schema()
        try:
            with self._lock, self._connect() as conn:
                conn.execute(
                    "INSERT INTO processed_events(event_key, processed_at) VALUES (?, ?)",
                    (event_key, now_iso()),
                )
                conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def schedule(self, payload: PublishPayload) -> int:
        if not payload.publish_at:
            raise ValueError("publish_at is required")
        self.ensure_schema()
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO scheduled_posts(payload_json, publish_at, created_at)
                VALUES (?, ?, ?)
                """,
                (json.dumps(payload.model_dump()), payload.publish_at, now_iso()),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def due_posts(self, limit: int = 20) -> List[sqlite3.Row]:
        self.ensure_schema()
        with self._lock, self._connect() as conn:
            return list(
                conn.execute(
                    """
                    SELECT * FROM scheduled_posts
                    WHERE status = 'pending' AND publish_at <= ?
                    ORDER BY publish_at ASC
                    LIMIT ?
                    """,
                    (now_iso(), limit),
                ).fetchall()
            )

    def mark_published(self, post_id: int) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE scheduled_posts
                SET status='published', published_at=?, last_error=NULL
                WHERE id=?
                """,
                (now_iso(), post_id),
            )
            conn.commit()

    def mark_failed(self, post_id: int, error: str) -> None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT attempts FROM scheduled_posts WHERE id=?", (post_id,)
            ).fetchone()
            attempts = (int(row["attempts"]) if row else 0) + 1
            status = "failed" if attempts >= 5 else "pending"
            conn.execute(
                """
                UPDATE scheduled_posts
                SET attempts=?, status=?, last_error=?
                WHERE id=?
                """,
                (attempts, status, error[:500], post_id),
            )
            conn.commit()


state_store = StateStore()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def env_is_set(name: str) -> bool:
    value = os.getenv(name)
    return bool(value and value.strip())


def bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_meta_verify_token() -> Optional[str]:
    return os.getenv("META_VERIFY_TOKEN")


def get_meta_graph_api_version() -> str:
    version = os.getenv("META_GRAPH_API_VERSION", DEFAULT_META_GRAPH_API_VERSION).strip()
    if not re.fullmatch(r"v\d+\.\d+", version):
        raise HTTPException(
            status_code=503, detail="META_GRAPH_API_VERSION has an invalid format"
        )
    return version


def get_facebook_page_access_token() -> Optional[str]:
    return os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN") or os.getenv(
        "META_LONG_LIVED_ACCESS_TOKEN"
    )


def get_instagram_access_token() -> Optional[str]:
    return (
        os.getenv("INSTAGRAM_ACCESS_TOKEN")
        or os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN")
        or os.getenv("META_LONG_LIVED_ACCESS_TOKEN")
    )


def require_automation_key(x_automation_key: Optional[str]) -> None:
    expected = (os.getenv("AUTOMATION_API_KEY") or "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="AUTOMATION_API_KEY is not configured")
    if not x_automation_key or not hmac.compare_digest(x_automation_key, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")


def verify_meta_signature(raw_body: bytes, signature: Optional[str]) -> None:
    app_secret = (os.getenv("META_APP_SECRET") or "").strip()
    if not app_secret:
        raise HTTPException(status_code=503, detail="META_APP_SECRET is not configured")
    if not signature or not signature.startswith("sha256="):
        raise HTTPException(status_code=401, detail="Invalid Meta webhook signature")
    expected = "sha256=" + hmac.new(
        app_secret.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="Invalid Meta webhook signature")


def app_secret_proof(access_token: str) -> Optional[str]:
    app_secret = (os.getenv("META_APP_SECRET") or "").strip()
    if not app_secret:
        return None
    return hmac.new(
        app_secret.encode(), access_token.encode(), hashlib.sha256
    ).hexdigest()


def require_facebook_config() -> tuple[str, str]:
    page_id = (os.getenv("FACEBOOK_PAGE_ID") or "").strip()
    token = (get_facebook_page_access_token() or "").strip()
    if not page_id or not re.fullmatch(META_ID_PATTERN, page_id):
        raise HTTPException(status_code=503, detail="FACEBOOK_PAGE_ID is not configured")
    if not token:
        raise HTTPException(
            status_code=503, detail="FACEBOOK_PAGE_ACCESS_TOKEN is not configured"
        )
    return page_id, token


def require_instagram_config() -> tuple[str, str]:
    account_id = (os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID") or "").strip()
    token = (get_instagram_access_token() or "").strip()
    if not account_id or not re.fullmatch(META_ID_PATTERN, account_id):
        raise HTTPException(
            status_code=503, detail="INSTAGRAM_BUSINESS_ACCOUNT_ID is not configured"
        )
    if not token:
        raise HTTPException(status_code=503, detail="INSTAGRAM_ACCESS_TOKEN is not configured")
    return account_id, token


async def meta_graph_request(
    *,
    edge: str,
    access_token: str,
    method: Literal["GET", "POST"] = "POST",
    data: Optional[Dict[str, Any]] = None,
    host: str = "graph.facebook.com",
) -> Dict[str, Any]:
    version = get_meta_graph_api_version()
    request_data: Dict[str, Any] = dict(data or {})
    request_data["access_token"] = access_token
    proof = app_secret_proof(access_token)
    if proof and host == "graph.facebook.com":
        request_data["appsecret_proof"] = proof
    url = f"https://{host}/{version}/{edge.lstrip('/')}"
    try:
        async with httpx.AsyncClient(
            timeout=META_REQUEST_TIMEOUT_SECONDS, follow_redirects=False
        ) as client:
            if method == "GET":
                response = await client.get(url, params=request_data)
            else:
                response = await client.post(url, data=request_data)
    except httpx.RequestError as exc:
        logger.warning("Meta Graph API request failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=502, detail="Meta Graph API is temporarily unavailable"
        ) from exc

    try:
        result = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=502, detail="Meta Graph API returned an invalid response"
        ) from exc
    if not isinstance(result, dict):
        raise HTTPException(
            status_code=502, detail="Meta Graph API returned an unexpected response"
        )
    if response.is_error or "error" in result:
        error = result.get("error")
        safe_detail = {
            "message": "Meta Graph API rejected the request",
            "code": error.get("code") if isinstance(error, dict) else None,
            "error_subcode": (
                error.get("error_subcode") if isinstance(error, dict) else None
            ),
        }
        raise HTTPException(status_code=502, detail=safe_detail)
    return result


async def publish_facebook_post(payload: PublishPayload) -> Dict[str, Any]:
    if payload.platform != "facebook":
        raise HTTPException(status_code=422, detail="platform must be facebook")
    page_id, token = require_facebook_config()
    if payload.video_url:
        edge = f"{page_id}/videos"
        data = {"file_url": payload.video_url, "description": payload.caption}
    elif payload.image_url:
        edge = f"{page_id}/photos"
        data = {"url": payload.image_url, "caption": payload.caption}
    else:
        edge = f"{page_id}/feed"
        data = {"message": payload.caption}
    return await meta_graph_request(edge=edge, access_token=token, data=data)


async def publish_instagram_post(payload: PublishPayload) -> Dict[str, Any]:
    if payload.platform != "instagram":
        raise HTTPException(status_code=422, detail="platform must be instagram")
    account_id, token = require_instagram_config()
    container_data: Dict[str, Any] = {"caption": payload.caption}
    is_video = bool(payload.video_url)
    if payload.video_url:
        container_data.update({"media_type": "REELS", "video_url": payload.video_url})
    elif payload.image_url:
        container_data["image_url"] = payload.image_url
    else:
        raise HTTPException(
            status_code=422, detail="Instagram requires image_url or video_url"
        )

    container = await meta_graph_request(
        edge=f"{account_id}/media", access_token=token, data=container_data
    )
    creation_id = str(container.get("id") or "")
    if not creation_id or not re.fullmatch(META_ID_PATTERN, creation_id):
        raise HTTPException(
            status_code=502, detail="Instagram did not return a valid media container ID"
        )

    if is_video:
        for attempt in range(10):
            status = await meta_graph_request(
                edge=creation_id,
                access_token=token,
                method="GET",
                data={"fields": "status_code,status"},
            )
            status_code = str(status.get("status_code") or "").upper()
            if status_code == "FINISHED":
                break
            if status_code in {"ERROR", "EXPIRED"}:
                raise HTTPException(
                    status_code=502,
                    detail="Instagram media container processing failed",
                )
            if attempt == 9:
                raise HTTPException(
                    status_code=504,
                    detail="Instagram media container is not ready yet",
                )
            await asyncio.sleep(2)

    published = await meta_graph_request(
        edge=f"{account_id}/media_publish",
        access_token=token,
        data={"creation_id": creation_id},
    )
    return {"container_id": creation_id, "media": published}


async def publish_to_platform(payload: PublishPayload) -> Dict[str, Any]:
    immediate = payload.model_copy(update={"publish_at": None})
    if payload.platform == "facebook":
        return await publish_facebook_post(immediate)
    return await publish_instagram_post(immediate)


async def reply_to_facebook_comment(comment_id: str, message: str) -> Dict[str, Any]:
    _, token = require_facebook_config()
    if not re.fullmatch(META_ID_PATTERN, comment_id):
        raise HTTPException(status_code=422, detail="Invalid Facebook comment ID")
    return await meta_graph_request(
        edge=f"{comment_id}/comments",
        access_token=token,
        data={"message": message},
    )


async def reply_to_instagram_comment(comment_id: str, message: str) -> Dict[str, Any]:
    _, token = require_instagram_config()
    if not re.fullmatch(META_ID_PATTERN, comment_id):
        raise HTTPException(status_code=422, detail="Invalid Instagram comment ID")
    return await meta_graph_request(
        edge=f"{comment_id}/replies",
        access_token=token,
        data={"message": message},
        host="graph.instagram.com",
    )


def extract_facebook_comment_events(body: Dict[str, Any]) -> List[CommentPayload]:
    if body.get("object") != "page":
        return []
    events: List[CommentPayload] = []
    for entry in body.get("entry", []):
        if not isinstance(entry, dict):
            continue
        page_id = str(entry.get("id", ""))
        for change in entry.get("changes", []):
            if not isinstance(change, dict) or change.get("field") != "feed":
                continue
            value = change.get("value")
            if not isinstance(value, dict):
                continue
            actor = value.get("from") if isinstance(value.get("from"), dict) else {}
            if value.get("item") != "comment" or value.get("verb") != "add":
                continue
            if str(actor.get("id", "")) == page_id:
                continue
            try:
                events.append(
                    CommentPayload(
                        platform="facebook",
                        comment_id=str(value["comment_id"]),
                        comment_text=str(value.get("message", "")),
                        user_name=str(actor.get("name", "Facebook user")),
                        timestamp=(
                            str(value.get("created_time"))
                            if value.get("created_time") is not None
                            else None
                        ),
                        post_id=(
                            str(value.get("post_id"))
                            if value.get("post_id") is not None
                            else None
                        ),
                    )
                )
            except (KeyError, ValidationError):
                continue
    return events


def extract_instagram_comment_events(body: Dict[str, Any]) -> List[CommentPayload]:
    if body.get("object") != "instagram":
        return []
    events: List[CommentPayload] = []
    for entry in body.get("entry", []):
        if not isinstance(entry, dict):
            continue
        candidates: List[Dict[str, Any]] = []
        if entry.get("field") in {"comments", "live_comments"}:
            candidates.append(entry)
        candidates.extend(
            c for c in entry.get("changes", []) if isinstance(c, dict)
        )
        for change in candidates:
            if change.get("field") not in {"comments", "live_comments"}:
                continue
            value = change.get("value")
            if not isinstance(value, dict):
                continue
            actor = value.get("from") if isinstance(value.get("from"), dict) else {}
            media = value.get("media") if isinstance(value.get("media"), dict) else {}
            comment_id = value.get("id")
            if not comment_id:
                continue
            try:
                events.append(
                    CommentPayload(
                        platform="instagram",
                        comment_id=str(comment_id),
                        comment_text=str(value.get("text", "")),
                        user_name=str(actor.get("username") or "Instagram user"),
                        timestamp=(
                            str(entry.get("time"))
                            if entry.get("time") is not None
                            else None
                        ),
                        post_id=(
                            str(media.get("id")) if media.get("id") is not None else None
                        ),
                    )
                )
            except ValidationError:
                continue
    return events


def classify_comment(text: str) -> Category:
    lower = text.lower()
    if any(
        word in lower
        for word in ["urgent", "urgente", "inmediato", "ayuda", "problema"]
    ):
        return "urgent"
    if any(
        word in lower
        for word in [
            "precio",
            "cotización",
            "cotizacion",
            "quote",
            "suscripción",
            "suscripcion",
            "plan",
            "costo",
        ]
    ):
        return "lead"
    if any(
        word in lower for word in ["soporte", "error", "fallo", "bug", "no funciona"]
    ):
        return "soporte"
    if any(
        word in lower
        for word in [
            "http://",
            "https://",
            "compra aquí",
            "compra aqui",
            "haz clic",
            "click aquí",
            "click aqui",
        ]
    ):
        return "spam"
    if any(
        word in lower
        for word in [
            "royalshield",
            "royal shield",
            "gracias",
            "excelente",
            "buen trabajo",
            "me gusta",
        ]
    ):
        return "comentario_publico"
    return "irrelevante"


def action_for_category(category: Category) -> Action:
    if category in {"urgent", "lead", "soporte", "comentario_publico"}:
        return "auto_reply"
    if category == "spam":
        return "manual_review"
    return "ignore"


def generate_reply(category: Category, payload: CommentPayload) -> str:
    name = payload.user_name.split()[0] if payload.user_name else "Hola"
    if category == "urgent":
        return (
            f"Hola {name}, sentimos que estés teniendo dificultades. "
            "Por favor envíanos un mensaje privado para ayudarte de inmediato."
        )
    if category == "lead":
        return (
            f"Hola {name}, gracias por tu interés. "
            "Envíanos un mensaje privado y te compartimos precios y planes disponibles."
        )
    if category == "soporte":
        return (
            f"Hola {name}, gracias por reportarlo. "
            "Te ayudamos por mensaje privado para revisar tu caso paso a paso."
        )
    if category == "comentario_publico":
        return f"¡Gracias {name}! Valoramos mucho tu comentario."
    if category == "spam":
        return (
            f"Hola {name}, tu comentario fue marcado para revisión de seguridad. "
            "Si necesitas ayuda real, escríbenos por nuestros canales oficiales."
        )
    return f"Hola {name}, gracias por comentar."


async def process_comment_event(event: CommentPayload) -> None:
    category = classify_comment(event.comment_text)
    if action_for_category(category) != "auto_reply":
        return
    try:
        if event.platform == "facebook":
            await reply_to_facebook_comment(
                event.comment_id, generate_reply(category, event)
            )
        else:
            await reply_to_instagram_comment(
                event.comment_id, generate_reply(category, event)
            )
    except HTTPException as exc:
        logger.warning(
            "%s auto-reply failed for %s with status %s",
            event.platform,
            event.comment_id,
            exc.status_code,
        )


def schedule_or_due(payload: PublishPayload) -> tuple[bool, Optional[int]]:
    if not payload.publish_at:
        return False, None
    when = datetime.fromisoformat(payload.publish_at)
    if when <= datetime.now(timezone.utc):
        return False, None
    return True, state_store.schedule(payload)


@app.get("/")
async def root() -> Dict[str, Any]:
    return {
        "ok": True,
        "service": "SOCIALMEDIAAUTOMATION",
        "version": APP_VERSION,
        "architecture": "standalone-meta-graph-api",
        "health": "/health",
        "config": "/config",
        "webhook": "/webhook",
        "publish": "/posts",
        "scheduler": "/scheduler/run",
    }


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "status": "healthy",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "received_at": now_iso(),
    }


@app.get("/config")
async def config() -> Dict[str, Any]:
    return {
        "ok": True,
        "service": "SOCIALMEDIAAUTOMATION",
        "version": APP_VERSION,
        "environment": os.getenv("ENVIRONMENT", "development"),
        "configured": {
            "META_VERIFY_TOKEN": bool(get_meta_verify_token()),
            "META_APP_SECRET": env_is_set("META_APP_SECRET"),
            "META_GRAPH_API_VERSION": get_meta_graph_api_version(),
            "AUTOMATION_API_KEY": env_is_set("AUTOMATION_API_KEY"),
            "FACEBOOK_PAGE_ID": env_is_set("FACEBOOK_PAGE_ID"),
            "FACEBOOK_PAGE_ACCESS_TOKEN": bool(get_facebook_page_access_token()),
            "FACEBOOK_AUTO_REPLY_ENABLED": bool_env("FACEBOOK_AUTO_REPLY_ENABLED"),
            "INSTAGRAM_BUSINESS_ACCOUNT_ID": env_is_set(
                "INSTAGRAM_BUSINESS_ACCOUNT_ID"
            ),
            "INSTAGRAM_ACCESS_TOKEN": bool(get_instagram_access_token()),
            "INSTAGRAM_AUTO_REPLY_ENABLED": bool_env("INSTAGRAM_AUTO_REPLY_ENABLED"),
            "SCHEDULE_DB_PATH": state_store.path,
        },
    }


@app.get("/webhook")
async def verify_meta_webhook(
    hub_mode: Optional[str] = Query(default=None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(default=None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(default=None, alias="hub.challenge"),
):
    expected_token = get_meta_verify_token()
    if not expected_token:
        raise HTTPException(
            status_code=403, detail="META_VERIFY_TOKEN is not configured"
        )
    if hub_mode == "subscribe" and hub_verify_token == expected_token:
        return PlainTextResponse(content=hub_challenge or "", status_code=200)
    raise HTTPException(status_code=403, detail="Invalid Meta verify token")


@app.post("/posts")
async def create_post(
    payload: PublishPayload,
    x_automation_key: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    require_automation_key(x_automation_key)
    scheduled, schedule_id = schedule_or_due(payload)
    if scheduled:
        return {
            "ok": True,
            "action": "scheduled",
            "schedule_id": schedule_id,
            "publish_at": payload.publish_at,
            "platform": payload.platform,
        }
    result = await publish_to_platform(payload)
    return {
        "ok": True,
        "action": "published",
        "platform": payload.platform,
        "meta_result": result,
        "received_at": now_iso(),
    }


@app.post("/facebook/posts")
async def create_facebook_post(
    payload: PublishPayload,
    x_automation_key: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    require_automation_key(x_automation_key)
    if payload.platform != "facebook":
        raise HTTPException(status_code=422, detail="platform must be facebook")
    scheduled, schedule_id = schedule_or_due(payload)
    if scheduled:
        return {
            "ok": True,
            "action": "scheduled",
            "schedule_id": schedule_id,
            "publish_at": payload.publish_at,
            "platform": "facebook",
        }
    result = await publish_facebook_post(payload.model_copy(update={"publish_at": None}))
    return {
        "ok": True,
        "action": "published",
        "platform": "facebook",
        "meta_result": result,
        "received_at": now_iso(),
    }


@app.post("/instagram/posts")
async def create_instagram_post(
    payload: PublishPayload,
    x_automation_key: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    require_automation_key(x_automation_key)
    if payload.platform != "instagram":
        raise HTTPException(status_code=422, detail="platform must be instagram")
    scheduled, schedule_id = schedule_or_due(payload)
    if scheduled:
        return {
            "ok": True,
            "action": "scheduled",
            "schedule_id": schedule_id,
            "publish_at": payload.publish_at,
            "platform": "instagram",
        }
    result = await publish_instagram_post(
        payload.model_copy(update={"publish_at": None})
    )
    return {
        "ok": True,
        "action": "published",
        "platform": "instagram",
        "meta_result": result,
        "received_at": now_iso(),
    }


@app.post("/facebook/comments/{comment_id}/reply")
async def create_facebook_comment_reply(
    payload: CommentReplyPayload,
    comment_id: str = Path(..., pattern=META_ID_PATTERN),
    x_automation_key: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    require_automation_key(x_automation_key)
    result = await reply_to_facebook_comment(comment_id, payload.message)
    return {
        "ok": True,
        "platform": "facebook",
        "action": "replied",
        "comment_id": comment_id,
        "meta_result": result,
        "received_at": now_iso(),
    }


@app.post("/instagram/comments/{comment_id}/reply")
async def create_instagram_comment_reply(
    payload: CommentReplyPayload,
    comment_id: str = Path(..., pattern=META_ID_PATTERN),
    x_automation_key: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    require_automation_key(x_automation_key)
    result = await reply_to_instagram_comment(comment_id, payload.message)
    return {
        "ok": True,
        "platform": "instagram",
        "action": "replied",
        "comment_id": comment_id,
        "meta_result": result,
        "received_at": now_iso(),
    }


@app.post("/scheduler/run")
async def run_scheduler(
    x_automation_key: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    require_automation_key(x_automation_key)
    due = state_store.due_posts()
    published = 0
    failed = 0
    for row in due:
        post_id = int(row["id"])
        try:
            payload = PublishPayload(**json.loads(row["payload_json"]))
            await publish_to_platform(payload)
            state_store.mark_published(post_id)
            published += 1
        except Exception as exc:
            state_store.mark_failed(post_id, type(exc).__name__)
            failed += 1
            logger.exception("Scheduled post %s failed", post_id)
    return {
        "ok": True,
        "checked": len(due),
        "published": published,
        "failed": failed,
        "received_at": now_iso(),
    }


@app.post("/webhook")
async def handle_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    raw_body = await request.body()
    if len(raw_body) > MAX_WEBHOOK_BYTES:
        raise HTTPException(status_code=413, detail="Webhook payload is too large")
    try:
        body = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON body must be an object")

    verify_meta_signature(raw_body, x_hub_signature_256)
    facebook_events = extract_facebook_comment_events(body)
    instagram_events = extract_instagram_comment_events(body)
    queued = 0
    duplicates = 0

    for event in [*facebook_events, *instagram_events]:
        enabled = (
            bool_env("FACEBOOK_AUTO_REPLY_ENABLED")
            if event.platform == "facebook"
            else bool_env("INSTAGRAM_AUTO_REPLY_ENABLED")
        )
        if not enabled:
            continue
        event_key = f"{event.platform}:comment:{event.comment_id}"
        if not state_store.claim_event(event_key):
            duplicates += 1
            continue
        background_tasks.add_task(process_comment_event, event)
        queued += 1

    return {
        "ok": True,
        "category": "meta_event",
        "message": "Meta webhook event verified.",
        "facebook_comment_events": len(facebook_events),
        "instagram_comment_events": len(instagram_events),
        "auto_reply_queued": queued,
        "duplicates_ignored": duplicates,
        "received_at": now_iso(),
    }
