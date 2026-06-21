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

import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field, ValidationError, field_validator


APP_VERSION = "2.1.0"
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
        description="Fallback post ID sourced from POST_ID when post_id is not supplied.",
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
            raise ValueError("video_url is currently supported only for facebook in this backend")
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
    # The legacy key is kept only so old Railway projects do not break abruptly.
    return os.getenv("META_VERIFY_TOKEN") or os.getenv("royalshield_verify_2026")


def validation_error_response(exc: ValidationError) -> HTTPException:
    return HTTPException(status_code=422, detail=exc.errors())


def verify_make_secret(secret_from_body: Optional[str], x_make_secret: Optional[str]) -> None:
    expected_secret = os.getenv("MAKE_SECRET")
    if not expected_secret:
        return
    received_secret = x_make_secret or secret_from_body
    if received_secret != expected_secret:
        raise HTTPException(status_code=401, detail="Unauthorized")


def classify_comment(text: str) -> Category:
    lower = text.lower()

    if any(word in lower for word in ["urgent", "urgente", "inmediato", "ayuda", "problema"]):
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

    if any(word in lower for word in ["soporte", "error", "fallo", "bug", "no funciona"]):
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
    media_type = "image" if payload.image_url else "video" if payload.video_url else "text"

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
            "META_LONG_LIVED_ACCESS_TOKEN": env_is_set("META_LONG_LIVED_ACCESS_TOKEN"),
            "MAKE_SECRET": env_is_set("MAKE_SECRET"),
            "META_APP_ID": env_is_set("META_APP_ID"),
            "INSTAGRAM_APP_ID": env_is_set("INSTAGRAM_APP_ID"),
            "META_BUSINESS_ID": env_is_set("META_BUSINESS_ID"),
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
        raise HTTPException(status_code=500, detail="META_VERIFY_TOKEN is not configured")

    if hub_mode == "subscribe" and hub_verify_token == expected_token:
        return PlainTextResponse(content=hub_challenge or "", status_code=200)

    raise HTTPException(status_code=403, detail="Invalid Meta verify token")


@app.post("/webhook")
@app.post("/webhook/make")
async def handle_webhook(request: Request, x_make_secret: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc

    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON body must be an object")

    if "object" in body and "entry" in body:
        return {
            "ok": True,
            "category": "meta_event",
            "message": "Meta webhook event received.",
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
                "Confirmar permisos: pages_manage_posts, pages_read_engagement, instagram_basic, instagram_content_publish.",
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
