"""Royal Shield standalone social-media automation backend."""

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

APP_VERSION = "3.0.1"
DEFAULT_META_GRAPH_API_VERSION = "v25.0"
META_TIMEOUT = 20.0
META_ID_PATTERN = r"^[A-Za-z0-9_-]+$"
MAX_WEBHOOK_BYTES = 1_000_000
Platform = Literal["facebook", "instagram"]
Category = Literal[
    "urgent", "lead", "soporte", "comentario_publico", "spam", "irrelevante"
]
logger = logging.getLogger("socialmediaautomation")
app = FastAPI(title="SOCIALMEDIAAUTOMATION", version=APP_VERSION)


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
    def validate_url(cls, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        if not value.startswith("https://"):
            raise ValueError("media URLs must start with https://")
        return value

    @field_validator("caption")
    @classmethod
    def clean_caption(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("caption cannot be empty")
        return value

    @field_validator("publish_at")
    @classmethod
    def normalize_publish_at(cls, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("publish_at must include a timezone")
        return parsed.astimezone(timezone.utc).isoformat()

    @model_validator(mode="after")
    def validate_media(self):
        if self.image_url and self.video_url:
            raise ValueError("provide only one of image_url or video_url")
        if self.platform == "instagram" and not (self.image_url or self.video_url):
            raise ValueError("Instagram publishing requires image_url or video_url")
        return self


class ReplyPayload(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)

    @field_validator("message")
    @classmethod
    def clean_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message cannot be empty")
        return value


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    return (
        default
        if value is None
        else value.strip().lower() in {"1", "true", "yes", "on"}
    )


def env_set(name: str) -> bool:
    return bool((os.getenv(name) or "").strip())


def meta_version() -> str:
    version = os.getenv(
        "META_GRAPH_API_VERSION", DEFAULT_META_GRAPH_API_VERSION
    ).strip()
    if not re.fullmatch(r"v\d+\.\d+", version):
        raise HTTPException(503, "META_GRAPH_API_VERSION has an invalid format")
    return version


def instagram_host() -> str:
    host = os.getenv("INSTAGRAM_GRAPH_HOST", "graph.facebook.com").strip().lower()
    if host not in {"graph.facebook.com", "graph.instagram.com"}:
        raise HTTPException(503, "INSTAGRAM_GRAPH_HOST is invalid")
    return host


def facebook_token() -> str:
    token = (
        os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN")
        or os.getenv("META_LONG_LIVED_ACCESS_TOKEN")
        or ""
    ).strip()
    if not token:
        raise HTTPException(503, "FACEBOOK_PAGE_ACCESS_TOKEN is not configured")
    return token


def instagram_token() -> str:
    token = (
        os.getenv("INSTAGRAM_ACCESS_TOKEN")
        or os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN")
        or os.getenv("META_LONG_LIVED_ACCESS_TOKEN")
        or ""
    ).strip()
    if not token:
        raise HTTPException(503, "Instagram access token is not configured")
    return token


def require_id(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value or not re.fullmatch(META_ID_PATTERN, value):
        raise HTTPException(503, f"{name} is not configured")
    return value


def require_automation_key(received: Optional[str]) -> None:
    expected = (os.getenv("AUTOMATION_API_KEY") or "").strip()
    if not expected:
        raise HTTPException(503, "AUTOMATION_API_KEY is not configured")
    if not received or not hmac.compare_digest(received, expected):
        raise HTTPException(401, "Unauthorized")


def verify_meta_signature(raw: bytes, signature: Optional[str]) -> None:
    secret = (os.getenv("META_APP_SECRET") or "").strip()
    if not secret:
        raise HTTPException(503, "META_APP_SECRET is not configured")
    if not signature or not signature.startswith("sha256="):
        raise HTTPException(401, "Invalid Meta webhook signature")
    expected = "sha256=" + hmac.new(
        secret.encode(), raw, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(401, "Invalid Meta webhook signature")


def appsecret_proof(token: str, host: str) -> Optional[str]:
    secret = (os.getenv("META_APP_SECRET") or "").strip()
    if not secret or host != "graph.facebook.com":
        return None
    return hmac.new(secret.encode(), token.encode(), hashlib.sha256).hexdigest()


async def graph_request(
    edge: str,
    token: str,
    data: Optional[Dict[str, Any]] = None,
    *,
    method: Literal["GET", "POST"] = "POST",
    host: str = "graph.facebook.com",
) -> Dict[str, Any]:
    payload = dict(data or {})
    payload["access_token"] = token
    proof = appsecret_proof(token, host)
    if proof:
        payload["appsecret_proof"] = proof
    url = f"https://{host}/{meta_version()}/{edge.lstrip('/')}"
    try:
        async with httpx.AsyncClient(
            timeout=META_TIMEOUT, follow_redirects=False
        ) as client:
            response = await (
                client.get(url, params=payload)
                if method == "GET"
                else client.post(url, data=payload)
            )
    except httpx.RequestError as exc:
        raise HTTPException(
            502, "Meta Graph API is temporarily unavailable"
        ) from exc
    try:
        body = response.json()
    except ValueError as exc:
        raise HTTPException(502, "Meta Graph API returned invalid JSON") from exc
    if not isinstance(body, dict):
        raise HTTPException(502, "Meta Graph API returned an unexpected response")
    if response.is_error or "error" in body:
        error = body.get("error") if isinstance(body.get("error"), dict) else {}
        raise HTTPException(
            502,
            {
                "message": "Meta Graph API rejected the request",
                "code": error.get("code"),
                "error_subcode": error.get("error_subcode"),
            },
        )
    return body


async def publish_facebook(payload: PublishPayload) -> Dict[str, Any]:
    page_id = require_id("FACEBOOK_PAGE_ID")
    token = facebook_token()
    if payload.video_url:
        return await graph_request(
            f"{page_id}/videos",
            token,
            {"file_url": payload.video_url, "description": payload.caption},
        )
    if payload.image_url:
        return await graph_request(
            f"{page_id}/photos",
            token,
            {"url": payload.image_url, "caption": payload.caption},
        )
    return await graph_request(f"{page_id}/feed", token, {"message": payload.caption})


async def publish_instagram(payload: PublishPayload) -> Dict[str, Any]:
    account_id = require_id("INSTAGRAM_BUSINESS_ACCOUNT_ID")
    token = instagram_token()
    host = instagram_host()
    create: Dict[str, Any] = {"caption": payload.caption}
    if payload.video_url:
        create.update({"media_type": "REELS", "video_url": payload.video_url})
    else:
        create["image_url"] = payload.image_url
    container = await graph_request(
        f"{account_id}/media", token, create, host=host
    )
    creation_id = str(container.get("id") or "")
    if not creation_id or not re.fullmatch(META_ID_PATTERN, creation_id):
        raise HTTPException(
            502, "Instagram did not return a valid media container ID"
        )
    if payload.video_url:
        for attempt in range(10):
            status = await graph_request(
                creation_id,
                token,
                {"fields": "status_code,status"},
                method="GET",
                host=host,
            )
            code = str(status.get("status_code") or "").upper()
            if code == "FINISHED":
                break
            if code in {"ERROR", "EXPIRED"}:
                raise HTTPException(502, "Instagram media processing failed")
            if attempt == 9:
                raise HTTPException(504, "Instagram media container is not ready")
            await asyncio.sleep(2)
    media = await graph_request(
        f"{account_id}/media_publish",
        token,
        {"creation_id": creation_id},
        host=host,
    )
    return {"container_id": creation_id, "media": media}


async def publish(payload: PublishPayload) -> Dict[str, Any]:
    immediate = payload.model_copy(update={"publish_at": None})
    return await (
        publish_facebook(immediate)
        if payload.platform == "facebook"
        else publish_instagram(immediate)
    )


async def reply_comment(
    platform: Platform, comment_id: str, message: str
) -> Dict[str, Any]:
    if not re.fullmatch(META_ID_PATTERN, comment_id):
        raise HTTPException(422, "Invalid comment ID")
    if platform == "facebook":
        return await graph_request(
            f"{comment_id}/comments", facebook_token(), {"message": message}
        )
    return await graph_request(
        f"{comment_id}/replies",
        instagram_token(),
        {"message": message},
        host=instagram_host(),
    )


class StateStore:
    def __init__(self) -> None:
        self.lock = threading.Lock()

    @property
    def path(self) -> str:
        return os.getenv("SCHEDULE_DB_PATH", "/tmp/socialmediaautomation.db")

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def schema(self) -> None:
        with self.lock, self.connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS processed_events "
                "(event_key TEXT PRIMARY KEY, processed_at TEXT NOT NULL)"
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS scheduled_posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    payload_json TEXT NOT NULL,
                    publish_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    published_at TEXT
                )"""
            )
            conn.commit()

    def claim_event(self, key: str) -> bool:
        self.schema()
        try:
            with self.lock, self.connect() as conn:
                conn.execute(
                    "INSERT INTO processed_events VALUES (?, ?)", (key, now_iso())
                )
                conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def schedule(self, payload: PublishPayload) -> int:
        self.schema()
        with self.lock, self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO scheduled_posts(payload_json,publish_at,created_at) "
                "VALUES (?,?,?)",
                (json.dumps(payload.model_dump()), payload.publish_at, now_iso()),
            )
            conn.commit()
            return int(cur.lastrowid)

    def due(self, limit: int = 20) -> List[sqlite3.Row]:
        self.schema()
        with self.lock, self.connect() as conn:
            return list(
                conn.execute(
                    "SELECT * FROM scheduled_posts WHERE status='pending' "
                    "AND publish_at<=? ORDER BY publish_at LIMIT ?",
                    (now_iso(), limit),
                ).fetchall()
            )

    def success(self, post_id: int) -> None:
        with self.lock, self.connect() as conn:
            conn.execute(
                "UPDATE scheduled_posts SET status='published',published_at=?,"
                "last_error=NULL WHERE id=?",
                (now_iso(), post_id),
            )
            conn.commit()

    def failure(self, post_id: int, error: str) -> None:
        with self.lock, self.connect() as conn:
            row = conn.execute(
                "SELECT attempts FROM scheduled_posts WHERE id=?", (post_id,)
            ).fetchone()
            attempts = (int(row["attempts"]) if row else 0) + 1
            conn.execute(
                "UPDATE scheduled_posts SET attempts=?,status=?,last_error=? "
                "WHERE id=?",
                (
                    attempts,
                    "failed" if attempts >= 5 else "pending",
                    error[:500],
                    post_id,
                ),
            )
            conn.commit()


state = StateStore()


def classify(text: str) -> Category:
    text = text.lower()
    if any(
        x in text for x in ["urgent", "urgente", "inmediato", "ayuda", "problema"]
    ):
        return "urgent"
    if any(
        x in text
        for x in [
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
    if any(x in text for x in ["soporte", "error", "fallo", "bug", "no funciona"]):
        return "soporte"
    if any(
        x in text
        for x in ["http://", "https://", "compra aquí", "compra aqui", "haz clic"]
    ):
        return "spam"
    if any(
        x in text
        for x in [
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


def reply_text(category: Category, event: CommentPayload) -> str:
    name = event.user_name.split()[0] if event.user_name else "Hola"
    messages = {
        "urgent": (
            f"Hola {name}, sentimos que estés teniendo dificultades. "
            "Por favor envíanos un mensaje privado para ayudarte de inmediato."
        ),
        "lead": (
            f"Hola {name}, gracias por tu interés. Envíanos un mensaje privado "
            "y te compartimos precios y planes disponibles."
        ),
        "soporte": (
            f"Hola {name}, gracias por reportarlo. Te ayudamos por mensaje privado "
            "para revisar tu caso paso a paso."
        ),
        "comentario_publico": f"¡Gracias {name}! Valoramos mucho tu comentario.",
        "spam": f"Hola {name}, tu comentario fue marcado para revisión de seguridad.",
        "irrelevante": f"Hola {name}, gracias por comentar.",
    }
    return messages[category]


def should_auto_reply(category: Category) -> bool:
    return category in {"urgent", "lead", "soporte", "comentario_publico"}


def facebook_events(body: Dict[str, Any]) -> List[CommentPayload]:
    if body.get("object") != "page":
        return []
    result: List[CommentPayload] = []
    for entry in body.get("entry", []):
        if not isinstance(entry, dict):
            continue
        page_id = str(entry.get("id", ""))
        for change in entry.get("changes", []):
            value = (
                change.get("value")
                if isinstance(change, dict) and change.get("field") == "feed"
                else None
            )
            if (
                not isinstance(value, dict)
                or value.get("item") != "comment"
                or value.get("verb") != "add"
            ):
                continue
            actor = value.get("from") if isinstance(value.get("from"), dict) else {}
            if str(actor.get("id", "")) == page_id or not value.get("comment_id"):
                continue
            try:
                result.append(
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
            except ValidationError:
                continue
    return result


def instagram_events(body: Dict[str, Any]) -> List[CommentPayload]:
    if body.get("object") != "instagram":
        return []
    result: List[CommentPayload] = []
    for entry in body.get("entry", []):
        if not isinstance(entry, dict):
            continue
        changes = (
            [entry] if entry.get("field") in {"comments", "live_comments"} else []
        )
        changes += [c for c in entry.get("changes", []) if isinstance(c, dict)]
        for change in changes:
            if change.get("field") not in {"comments", "live_comments"}:
                continue
            value = change.get("value")
            if not isinstance(value, dict) or not value.get("id"):
                continue
            actor = value.get("from") if isinstance(value.get("from"), dict) else {}
            media = value.get("media") if isinstance(value.get("media"), dict) else {}
            result.append(
                CommentPayload(
                    platform="instagram",
                    comment_id=str(value["id"]),
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
    return result


async def process_event(event: CommentPayload) -> None:
    category = classify(event.comment_text)
    if not should_auto_reply(category):
        return
    try:
        await reply_comment(
            event.platform, event.comment_id, reply_text(category, event)
        )
    except HTTPException as exc:
        logger.warning(
            "%s auto-reply failed for %s: %s",
            event.platform,
            event.comment_id,
            exc.status_code,
        )


async def run_due_posts() -> Dict[str, Any]:
    rows = state.due()
    published = failed = 0
    for row in rows:
        try:
            await publish(PublishPayload(**json.loads(row["payload_json"])))
            state.success(int(row["id"]))
            published += 1
        except Exception as exc:
            state.failure(int(row["id"]), type(exc).__name__)
            failed += 1
    return {
        "ok": True,
        "checked": len(rows),
        "published": published,
        "failed": failed,
        "received_at": now_iso(),
    }


@app.get("/")
async def root() -> Dict[str, Any]:
    return {
        "ok": True,
        "service": "SOCIALMEDIAAUTOMATION",
        "version": APP_VERSION,
        "architecture": "standalone-meta-graph-api",
        "webhook": "/webhook",
        "publish": "/posts",
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
        "version": APP_VERSION,
        "configured": {
            "META_VERIFY_TOKEN": env_set("META_VERIFY_TOKEN"),
            "META_APP_SECRET": env_set("META_APP_SECRET"),
            "AUTOMATION_API_KEY": env_set("AUTOMATION_API_KEY"),
            "FACEBOOK_PAGE_ID": env_set("FACEBOOK_PAGE_ID"),
            "FACEBOOK_PAGE_ACCESS_TOKEN": (
                env_set("FACEBOOK_PAGE_ACCESS_TOKEN")
                or env_set("META_LONG_LIVED_ACCESS_TOKEN")
            ),
            "INSTAGRAM_BUSINESS_ACCOUNT_ID": env_set(
                "INSTAGRAM_BUSINESS_ACCOUNT_ID"
            ),
            "INSTAGRAM_ACCESS_TOKEN": (
                env_set("INSTAGRAM_ACCESS_TOKEN")
                or env_set("FACEBOOK_PAGE_ACCESS_TOKEN")
                or env_set("META_LONG_LIVED_ACCESS_TOKEN")
            ),
            "INSTAGRAM_GRAPH_HOST": instagram_host(),
            "SCHEDULE_DB_PATH": state.path,
            "SCHEDULER_ENABLED": env_bool("SCHEDULER_ENABLED", True),
        },
    }


@app.get("/webhook")
async def verify_webhook(
    hub_mode: Optional[str] = Query(default=None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(default=None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(default=None, alias="hub.challenge"),
):
    expected = (os.getenv("META_VERIFY_TOKEN") or "").strip()
    if not expected:
        raise HTTPException(403, "META_VERIFY_TOKEN is not configured")
    if hub_mode == "subscribe" and hub_verify_token == expected:
        return PlainTextResponse(hub_challenge or "")
    raise HTTPException(403, "Invalid Meta verify token")


@app.post("/posts")
async def create_post(
    payload: PublishPayload,
    x_automation_key: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    require_automation_key(x_automation_key)
    if (
        payload.publish_at
        and datetime.fromisoformat(payload.publish_at) > datetime.now(timezone.utc)
    ):
        schedule_id = state.schedule(payload)
        return {
            "ok": True,
            "action": "scheduled",
            "schedule_id": schedule_id,
            "platform": payload.platform,
            "publish_at": payload.publish_at,
        }
    return {
        "ok": True,
        "action": "published",
        "platform": payload.platform,
        "meta_result": await publish(payload),
        "received_at": now_iso(),
    }


@app.post("/facebook/posts")
async def create_facebook_post(
    payload: PublishPayload,
    x_automation_key: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    if payload.platform != "facebook":
        raise HTTPException(422, "platform must be facebook")
    return await create_post(payload, x_automation_key)


@app.post("/instagram/posts")
async def create_instagram_post(
    payload: PublishPayload,
    x_automation_key: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    if payload.platform != "instagram":
        raise HTTPException(422, "platform must be instagram")
    return await create_post(payload, x_automation_key)


@app.post("/facebook/comments/{comment_id}/reply")
async def facebook_reply(
    payload: ReplyPayload,
    comment_id: str = Path(..., pattern=META_ID_PATTERN),
    x_automation_key: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    require_automation_key(x_automation_key)
    return {
        "ok": True,
        "platform": "facebook",
        "action": "replied",
        "meta_result": await reply_comment("facebook", comment_id, payload.message),
    }


@app.post("/instagram/comments/{comment_id}/reply")
async def instagram_reply(
    payload: ReplyPayload,
    comment_id: str = Path(..., pattern=META_ID_PATTERN),
    x_automation_key: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    require_automation_key(x_automation_key)
    return {
        "ok": True,
        "platform": "instagram",
        "action": "replied",
        "meta_result": await reply_comment("instagram", comment_id, payload.message),
    }


@app.post("/scheduler/run")
async def scheduler_run(
    x_automation_key: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    require_automation_key(x_automation_key)
    return await run_due_posts()


@app.post("/webhook")
async def webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    raw = await request.body()
    if len(raw) > MAX_WEBHOOK_BYTES:
        raise HTTPException(413, "Webhook payload is too large")
    try:
        body = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(400, "Invalid JSON body") from exc
    if not isinstance(body, dict):
        raise HTTPException(400, "JSON body must be an object")
    verify_meta_signature(raw, x_hub_signature_256)
    fb = facebook_events(body)
    ig = instagram_events(body)
    queued = duplicates = 0
    for event in [*fb, *ig]:
        enabled = (
            env_bool("FACEBOOK_AUTO_REPLY_ENABLED")
            if event.platform == "facebook"
            else env_bool("INSTAGRAM_AUTO_REPLY_ENABLED")
        )
        if not enabled:
            continue
        if not state.claim_event(f"{event.platform}:comment:{event.comment_id}"):
            duplicates += 1
            continue
        background_tasks.add_task(process_event, event)
        queued += 1
    return {
        "ok": True,
        "category": "meta_event",
        "facebook_comment_events": len(fb),
        "instagram_comment_events": len(ig),
        "auto_reply_queued": queued,
        "duplicates_ignored": duplicates,
        "received_at": now_iso(),
    }
