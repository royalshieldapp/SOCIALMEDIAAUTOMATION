"""
RoyalShield Automation Backend

FastAPI backend for Meta / Make.com / Railway.

What it does:
1. Verifies Meta/Facebook/Instagram webhooks with GET /webhook.
2. Receives POST webhook requests from Meta or Make.com.
3. Classifies Facebook/Instagram comments and returns a suggested reply + action.
4. Validates publish requests and returns a normalized payload for automation modules.
5. Includes /health and /config for Railway checks and setup verification.

Local run:
    pip install -r requirements.txt
    uvicorn SOCIALMEDIAAUTOMATION:app --host 0.0.0.0 --port 8000
"""

import hashlib
import hmac
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

import httpx
from fastapi import (
    BackgroundTasks,
    FastAPI,
    Header,
    HTTPException,
    Path,
    Query,
    Request,
)
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field, ValidationError, field_validator

APP_VERSION = "2.0.0"
DEFAULT_META_GRAPH_API_VERSION = "v25.0"
META_REQUEST_TIMEOUT_SECONDS = 20.0
META_ID_PATTERN = r"^[A-Za-z0-9_-]+$"
logger = logging.getLogger("socialmediaautomation")
app = FastAPI(title="SOCIALMEDIAAUTOMATION", version=APP_VERSION)


Category = Literal[
    "urgent",
    "lead",
    "soporte",
    "comentario_publico",
    "spam",
    "irrelevante",
    "media_post",
    "meta_event",
]

Action = Literal["auto_reply", "manual_review", "ignore"]


class CommentPayload(BaseModel):
    """Schema for incoming comment payloads from Make."""

    platform: Literal["facebook", "instagram"]
    comment_id: str
    comment_text: str
    user_name: str
    timestamp: Optional[str] = Field(
        default=None,
        description="Optional ISO timestamp when the comment was created.",
    )
    post_id: Optional[str] = Field(
        default=None,
        description="Optional ID of the publication that received the comment.",
    )
    post_id_default: Optional[str] = Field(
        default_factory=lambda: os.getenv("POST_ID"),
        description=(
            "Fallback post ID sourced from POST_ID when post_id is not " "supplied."
        ),
    )


class PublishPayload(BaseModel):
    """Schema for publish payloads sent by Make.com."""

    platform: Literal["facebook", "instagram"] = Field(
        ..., description="Target platform for publishing."
    )
    caption: str = Field(..., min_length=1, max_length=2200)
    image_url: Optional[str] = Field(default=None)
    video_url: Optional[str] = Field(default=None)
    publish_at: Optional[str] = Field(
        default=None,
        description="Optional ISO timestamp for scheduling.",
    )
    media_id: Optional[str] = Field(
        default_factory=lambda: os.getenv("MEDIA_ID"),
        description="Optional media container ID supplied by Make or MEDIA_ID.",
    )

    @field_validator("image_url", "video_url")
    @classmethod
    def validate_media_urls(cls, value: Optional[str]) -> Optional[str]:
        if value is None or value == "":
            return None
        if not re.match(r"^https?://", value):
            raise ValueError("media URLs must start with http:// or https://")
        return value

    @field_validator("video_url")
    @classmethod
    def only_video_for_facebook(cls, value: Optional[str], info):
        platform = info.data.get("platform")
        if value and platform == "instagram":
            raise ValueError(
                "video_url is currently supported only for facebook in this backend"
            )
        return value

    @field_validator("publish_at")
    @classmethod
    def validate_publish_date(cls, value: Optional[str]) -> Optional[str]:
        if value is None or value == "":
            return None
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value

    @field_validator("caption")
    @classmethod
    def validate_caption(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("caption cannot be empty")
        return cleaned


class FacebookCommentReplyPayload(BaseModel):
    """Message sent as a reply to an existing Facebook comment."""

    message: str = Field(..., min_length=1, max_length=2000)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("message cannot be empty")
        return cleaned


class ClassificationResponse(BaseModel):
    ok: bool = True
    category: Category
    action: Action
    reply: str
    tags: List[str]
    make_next_step: str
    received_at: str


class PublishResponse(BaseModel):
    ok: bool = True
    category: Category = "media_post"
    action: Literal["publish_now", "schedule_post"]
    platform: Literal["facebook", "instagram"]
    publish_payload: Dict[str, Any]
    checklist: List[str]
    received_at: str


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def env_is_set(name: str) -> bool:
    value = os.getenv(name)
    return bool(value and value.strip())


def get_meta_verify_token() -> Optional[str]:
    return os.getenv("META_VERIFY_TOKEN")


def get_meta_graph_api_version() -> str:
    version = os.getenv(
        "META_GRAPH_API_VERSION", DEFAULT_META_GRAPH_API_VERSION
    ).strip()
    if not re.fullmatch(r"v\d+\.\d+", version):
        raise HTTPException(
            status_code=503,
            detail="META_GRAPH_API_VERSION has an invalid format",
        )
    return version


def get_facebook_page_access_token() -> Optional[str]:
    return os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN") or os.getenv(
        "META_LONG_LIVED_ACCESS_TOKEN"
    )


def validation_error_response(exc: ValidationError) -> HTTPException:
    errors = [
        {
            "loc": error.get("loc", []),
            "msg": error.get("msg", "Invalid value"),
            "type": error.get("type", "value_error"),
        }
        for error in exc.errors()
    ]
    return HTTPException(status_code=422, detail=errors)


def verify_make_secret(
    secret_from_body: Optional[str], x_make_secret: Optional[str]
) -> None:
    expected_secret = os.getenv("MAKE_SECRET")
    if not expected_secret:
        if os.getenv("ENVIRONMENT", "development").lower() == "production":
            raise HTTPException(status_code=503, detail="MAKE_SECRET is not configured")
        return
    received_secret = x_make_secret or secret_from_body
    if not received_secret or not hmac.compare_digest(received_secret, expected_secret):
        raise HTTPException(status_code=401, detail="Unauthorized")


def verify_meta_signature(raw_body: bytes, signature: Optional[str]) -> None:
    """Verify that a native webhook POST was signed by the configured Meta app."""

    app_secret = os.getenv("META_APP_SECRET")
    if not app_secret:
        raise HTTPException(status_code=503, detail="META_APP_SECRET is not configured")
    if not signature or not signature.startswith("sha256="):
        raise HTTPException(status_code=401, detail="Invalid Meta webhook signature")

    expected = (
        "sha256="
        + hmac.new(
            app_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
    )
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="Invalid Meta webhook signature")


def facebook_auto_reply_enabled() -> bool:
    return os.getenv("FACEBOOK_AUTO_REPLY_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def require_facebook_config() -> tuple[str, str]:
    page_id = os.getenv("FACEBOOK_PAGE_ID", "").strip()
    access_token = (get_facebook_page_access_token() or "").strip()
    if not page_id or not re.fullmatch(META_ID_PATTERN, page_id):
        raise HTTPException(
            status_code=503, detail="FACEBOOK_PAGE_ID is not configured"
        )
    if not access_token:
        raise HTTPException(
            status_code=503,
            detail="FACEBOOK_PAGE_ACCESS_TOKEN is not configured",
        )
    return page_id, access_token


def app_secret_proof(access_token: str) -> Optional[str]:
    app_secret = os.getenv("META_APP_SECRET")
    if not app_secret:
        return None
    return hmac.new(
        app_secret.encode("utf-8"),
        access_token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


async def facebook_graph_request(
    edge: str,
    data: Dict[str, Any],
) -> Dict[str, Any]:
    """Send a server-side POST to Meta without exposing access tokens in URLs."""

    _, access_token = require_facebook_config()
    version = get_meta_graph_api_version()
    request_data = {**data, "access_token": access_token}
    proof = app_secret_proof(access_token)
    if proof:
        request_data["appsecret_proof"] = proof

    url = f"https://graph.facebook.com/{version}/{edge.lstrip('/')}"
    try:
        async with httpx.AsyncClient(
            timeout=META_REQUEST_TIMEOUT_SECONDS,
            follow_redirects=False,
        ) as client:
            response = await client.post(url, data=request_data)
    except httpx.RequestError as exc:
        logger.warning("Meta Graph API request failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=502,
            detail="Meta Graph API is temporarily unavailable",
        ) from exc

    try:
        result = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="Meta Graph API returned an invalid response",
        ) from exc

    if not isinstance(result, dict):
        raise HTTPException(
            status_code=502,
            detail="Meta Graph API returned an unexpected response",
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
    if payload.image_url and payload.video_url:
        raise HTTPException(
            status_code=422,
            detail="Provide only one of image_url or video_url",
        )
    if payload.publish_at:
        raise HTTPException(
            status_code=422,
            detail=(
                "Direct Facebook publishing expects Make to call this endpoint "
                "at the scheduled time; omit publish_at"
            ),
        )

    page_id, _ = require_facebook_config()
    if payload.video_url:
        edge = f"{page_id}/videos"
        data = {"file_url": payload.video_url, "description": payload.caption}
    elif payload.image_url:
        edge = f"{page_id}/photos"
        data = {"url": payload.image_url, "caption": payload.caption}
    else:
        edge = f"{page_id}/feed"
        data = {"message": payload.caption}
    return await facebook_graph_request(edge=edge, data=data)


async def reply_to_facebook_comment(comment_id: str, message: str) -> Dict[str, Any]:
    require_facebook_config()
    if not re.fullmatch(META_ID_PATTERN, comment_id):
        raise HTTPException(status_code=422, detail="Invalid Facebook comment ID")
    return await facebook_graph_request(
        edge=f"{comment_id}/comments",
        data={"message": message},
    )


def extract_facebook_comment_events(body: Dict[str, Any]) -> List[CommentPayload]:
    """Normalize Page feed comment events delivered by Meta webhooks."""

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
            if (
                value.get("item") != "comment"
                or value.get("verb") != "add"
                or str(actor.get("id", "")) == page_id
            ):
                continue
            try:
                events.append(
                    CommentPayload(
                        platform="facebook",
                        comment_id=str(value["comment_id"]),
                        comment_text=str(value.get("message", "")),
                        user_name=str(actor.get("name", "Facebook user")),
                        timestamp=(
                            str(value["created_time"])
                            if value.get("created_time") is not None
                            else None
                        ),
                        post_id=(
                            str(value["post_id"])
                            if value.get("post_id") is not None
                            else None
                        ),
                    )
                )
            except (KeyError, ValidationError):
                continue
    return events


async def process_facebook_comment_events(events: List[CommentPayload]) -> None:
    """Auto-reply after Meta has received a fast webhook acknowledgement."""

    for event in events:
        category = classify_comment(event.comment_text)
        if action_for_category(category) != "auto_reply":
            continue
        try:
            await reply_to_facebook_comment(
                comment_id=event.comment_id,
                message=generate_reply(category, event),
            )
        except HTTPException as exc:
            logger.warning(
                "Facebook auto-reply failed for comment %s with status %s",
                event.comment_id,
                exc.status_code,
            )


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


def tags_for_category(category: Category) -> List[str]:
    mapping = {
        "urgent": ["prioridad_alta", "atencion_inmediata"],
        "lead": ["posible_cliente", "ventas"],
        "soporte": ["ticket_soporte"],
        "comentario_publico": ["engagement"],
        "spam": ["seguridad", "revision"],
        "irrelevante": ["sin_accion"],
    }
    return mapping.get(category, ["sin_accion"])


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


def build_publish_payload(payload: PublishPayload) -> Dict[str, Any]:
    media_type = (
        "image" if payload.image_url else "video" if payload.video_url else "text"
    )

    result: Dict[str, Any] = {
        "platform": payload.platform,
        "caption": payload.caption,
        "media_type": media_type,
        "image_url": payload.image_url,
        "video_url": payload.video_url,
        "publish_at": payload.publish_at,
    }

    if payload.media_id:
        result["media_id"] = payload.media_id

    return result


@app.get("/")
async def root() -> Dict[str, Any]:
    return {
        "ok": True,
        "service": "SOCIALMEDIAAUTOMATION",
        "version": APP_VERSION,
        "health": "/health",
        "config": "/config",
        "webhook": "/webhook",
        "make_webhook": "/webhook/make",
        "required_publish_fields": [
            "platform",
            "caption",
            "image_url or video_url (optional for text posts)",
            "publish_at (optional)",
            "media_id (optional; overrides MEDIA_ID env var)",
        ],
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
        "endpoints": {
            "health": "/health",
            "meta_verify": "/webhook",
            "make_webhook": "/webhook/make",
            "docs": "/docs",
        },
        "configured": {
            "META_VERIFY_TOKEN": bool(get_meta_verify_token()),
            "META_APP_SECRET": env_is_set("META_APP_SECRET"),
            "META_LONG_LIVED_ACCESS_TOKEN": env_is_set("META_LONG_LIVED_ACCESS_TOKEN"),
            "FACEBOOK_PAGE_ACCESS_TOKEN": bool(get_facebook_page_access_token()),
            "MAKE_SECRET": env_is_set("MAKE_SECRET"),
            "META_GRAPH_API_VERSION": get_meta_graph_api_version(),
            "FACEBOOK_AUTO_REPLY_ENABLED": facebook_auto_reply_enabled(),
            "META_APP_ID": env_is_set("META_APP_ID"),
            "INSTAGRAM_APP_ID": env_is_set("INSTAGRAM_APP_ID"),
            "META_BUSINESS_ID": env_is_set("META_BUSINESS_ID"),
            "FACEBOOK_PAGE_ID": env_is_set("FACEBOOK_PAGE_ID"),
            "INSTAGRAM_BUSINESS_ACCOUNT_ID": env_is_set(
                "INSTAGRAM_BUSINESS_ACCOUNT_ID"
            ),
            "GOOGLE_SHEET_ID": env_is_set("GOOGLE_SHEET_ID"),
            "POST_ID": env_is_set("POST_ID"),
            "MEDIA_ID": env_is_set("MEDIA_ID"),
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


@app.post("/facebook/posts")
async def create_facebook_post(
    payload: PublishPayload,
    x_make_secret: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """Publish text, image, or video content directly to the configured Page."""

    verify_make_secret(secret_from_body=None, x_make_secret=x_make_secret)
    meta_result = await publish_facebook_post(payload)
    return {
        "ok": True,
        "platform": "facebook",
        "action": "published",
        "meta_result": meta_result,
        "received_at": now_iso(),
    }


@app.post("/facebook/comments/{comment_id}/reply")
async def create_facebook_comment_reply(
    payload: FacebookCommentReplyPayload,
    comment_id: str = Path(..., pattern=META_ID_PATTERN),
    x_make_secret: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """Reply directly to a Facebook Page comment through Graph API."""

    verify_make_secret(secret_from_body=None, x_make_secret=x_make_secret)
    meta_result = await reply_to_facebook_comment(comment_id, payload.message)
    return {
        "ok": True,
        "platform": "facebook",
        "action": "replied",
        "comment_id": comment_id,
        "meta_result": meta_result,
        "received_at": now_iso(),
    }


@app.post("/webhook")
@app.post("/webhook/make")
async def handle_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_make_secret: Optional[str] = Header(default=None),
    x_hub_signature_256: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    raw_body = await request.body()
    if len(raw_body) > 1_000_000:
        raise HTTPException(status_code=413, detail="Webhook payload is too large")

    try:
        body = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc

    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON body must be an object")

    if "object" in body and "entry" in body:
        verify_meta_signature(raw_body, x_hub_signature_256)
        facebook_events = extract_facebook_comment_events(body)
        auto_reply_queued = facebook_auto_reply_enabled() and bool(facebook_events)
        if auto_reply_queued:
            background_tasks.add_task(
                process_facebook_comment_events,
                facebook_events,
            )
        return {
            "ok": True,
            "category": "meta_event",
            "message": "Meta webhook event verified.",
            "facebook_comment_events": len(facebook_events),
            "auto_reply_queued": auto_reply_queued,
            "received_at": now_iso(),
        }

    secret_from_body = body.get("secret")
    verify_make_secret(secret_from_body=secret_from_body, x_make_secret=x_make_secret)

    if body.get("event_type") == "publish_post" or "caption" in body:
        try:
            publish_payload = PublishPayload(**body)
        except ValidationError as exc:
            raise validation_error_response(exc) from exc

        normalized_payload = build_publish_payload(publish_payload)
        action = "schedule_post" if publish_payload.publish_at else "publish_now"

        return PublishResponse(
            action=action,
            platform=publish_payload.platform,
            publish_payload=normalized_payload,
            checklist=[
                "Verificar token activo de Facebook/Instagram.",
                (
                    "Confirmar permisos: pages_manage_posts, pages_read_engagement, "
                    "instagram_basic, instagram_content_publish."
                ),
                "Enviar publish_payload al módulo Make que ejecuta Graph API.",
            ],
            received_at=now_iso(),
        ).model_dump()

    try:
        comment_payload = CommentPayload(**body)
    except ValidationError as exc:
        raise validation_error_response(exc) from exc

    category = classify_comment(comment_payload.comment_text)
    action = action_for_category(category)
    reply = generate_reply(category, comment_payload)

    return ClassificationResponse(
        category=category,
        action=action,
        reply=reply,
        tags=tags_for_category(category),
        make_next_step=(
            "Publicar reply con módulo 'Create Comment Reply' de Make"
            if action == "auto_reply"
            else "Enviar a revisión manual"
        ),
        received_at=now_iso(),
    ).model_dump()
