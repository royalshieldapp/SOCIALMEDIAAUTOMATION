"""
RoyalShield Automation Backend

FastAPI backend for Meta / Make.com / Railway.

What it does:
1. Verifies Meta/Facebook/Instagram webhooks with GET /webhook.
2. Receives POST webhook requests from Meta or Make.com.
3. Supports two Make.com payload styles:
   - Instagram/Facebook comments for classification and reply generation.
   - Image/caption payloads for publishing or forwarding logic.
4. Returns fast JSON responses so Make and Meta do not wait too long.
5. Includes /health for Railway health checks.

Local run:
    pip install -r requirements.txt
    uvicorn SOCIALMEDIAAUTOMATION:app --host 0.0.0.0 --port 8000

Railway endpoint examples:
    GET  https://socialmediaautomation-production.up.railway.app/health
    GET  https://socialmediaautomation-production.up.railway.app/webhook
    POST https://socialmediaautomation-production.up.railway.app/webhook
"""

import os
from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field


app = FastAPI(title="SOCIALMEDIAAUTOMATION", version="1.2.0")


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


class CommentPayload(BaseModel):
    """Schema for incoming comment or message payloads from Make."""

    platform: Literal["facebook", "instagram"] = Field(
        ..., description="Social media platform where the message originated."
    )
    comment_id: str = Field(
        ..., description="Unique identifier of the comment or message."
    )
    comment_text: str = Field(
        ..., description="Raw text content of the comment or message."
    )
    user_name: str = Field(
        ..., description="Display name of the user who left the comment."
    )
    timestamp: str = Field(
        ..., description="ISO timestamp when the comment was created."
    )


class MediaPayload(BaseModel):
    """Schema for image/caption payloads sent by Make.com."""

    image_url: str = Field(..., description="Public image URL.")
    caption: str = Field(..., description="Caption text to publish or process.")
    platform: Optional[Literal["facebook", "instagram"]] = Field(
        default="instagram", description="Target social media platform."
    )
    timestamp: Optional[str] = Field(
        default=None, description="Optional ISO timestamp."
    )


class ClassificationResponse(BaseModel):
    """Response returned to Make.com."""

    ok: bool = True
    category: Category
    reply: str
    received_at: str


class MediaResponse(BaseModel):
    """Response returned when Make.com sends image_url and caption."""

    ok: bool = True
    category: Category = "media_post"
    message: str
    image_url: str
    caption: str
    received_at: str


def now_iso() -> str:
    """Return current UTC time in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def verify_make_secret(
    secret_from_body: Optional[str],
    x_make_secret: Optional[str],
) -> None:
    """
    Optional protection for Make.com requests.

    In Railway, set:
        MAKE_SECRET=your_private_secret

    If MAKE_SECRET is not configured, this check is skipped.
    If MAKE_SECRET exists, Make must send the same secret either:
    - in the JSON body as "secret"
    - or in the request header as "x-make-secret"
    """

    expected_secret = os.getenv("MAKE_SECRET")

    if not expected_secret:
        return

    received_secret = x_make_secret or secret_from_body

    if received_secret != expected_secret:
        raise HTTPException(status_code=401, detail="Unauthorized")


def classify_comment(text: str) -> Category:
    """Simple rule-based classification for RoyalShield comments."""

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


def generate_reply(category: Category, payload: CommentPayload) -> str:
    """Generate a brief reply based on classification."""

    name = payload.user_name.split()[0] if payload.user_name else "Hola"

    if category == "urgent":
        return (
            f"Hola {name}, sentimos que estés teniendo dificultades. "
            "Por favor envíanos un mensaje privado o visita nuestro canal oficial de soporte para ayudarte de inmediato."
        )

    if category == "lead":
        return (
            f"Hola {name}, gracias por tu interés en RoyalShield. "
            "Envíanos un mensaje privado y con gusto te orientamos sobre planes, funciones y próximos pasos."
        )

    if category == "soporte":
        return (
            f"Hola {name}, lamentamos los inconvenientes. "
            "Nuestro equipo de soporte puede ayudarte; por favor comunícate por nuestro canal oficial."
        )

    if category == "comentario_publico":
        return (
            f"¡Gracias {name}! Apreciamos mucho tu comentario y tu apoyo. "
            "Estamos aquí para ayudarte si necesitas más información."
        )

    if category == "spam":
        return (
            f"Hola {name}, tu mensaje contiene enlaces o contenido sospechoso y fue marcado para revisión. "
            "Si esto es un error, contáctanos directamente por nuestros canales oficiales."
        )

    return (
        f"Hola {name}, gracias por tu mensaje. "
        "Por ahora no se requiere ninguna acción adicional. ¡Que tengas un excelente día!"
    )


@app.get("/")
async def root() -> Dict[str, Any]:
    """Basic service info."""

    return {
        "ok": True,
        "service": "SOCIALMEDIAAUTOMATION",
        "version": "1.2.0",
        "health": "/health",
        "webhook": "/webhook",
    }


@app.get("/health")
async def health() -> Dict[str, Any]:
    """Railway health check endpoint."""

    return {
        "ok": True,
        "status": "healthy",
        "received_at": now_iso(),
    }


@app.get("/webhook")
async def verify_meta_webhook(
    hub_mode: Optional[str] = Query(default=None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(default=None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(default=None, alias="hub.challenge"),
):
    """
    Meta/Facebook/Instagram webhook verification endpoint.

    Meta sends:
        hub.mode=subscribe
        hub.verify_token=<your token>
        hub.challenge=<number/string>

    This endpoint must return only hub.challenge as plain text.
    """

    expected_token = os.getenv("META_VERIFY_TOKEN", "royalshield_verify_2026")

    if hub_mode == "subscribe" and hub_verify_token == expected_token:
        return PlainTextResponse(content=hub_challenge or "", status_code=200)

    raise HTTPException(status_code=403, detail="Invalid Meta verify token")


@app.post("/webhook")
async def handle_webhook(
    request: Request,
    x_make_secret: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """
    Main webhook endpoint.

    Receives:
    - Meta webhook events
    - Make.com image/caption payloads
    - Make.com comment classification payloads
    """

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON body must be an object")

    # Meta webhook events usually include "object" and "entry".
    # Return 200 fast so Meta does not mark the webhook as failing.
    if "object" in body and "entry" in body:
        print("META WEBHOOK EVENT:", body)
        return {
            "ok": True,
            "category": "meta_event",
            "message": "Meta webhook event received.",
            "received_at": now_iso(),
        }

    # Optional Make.com protection.
    secret_from_body = body.get("secret")
    verify_make_secret(secret_from_body=secret_from_body, x_make_secret=x_make_secret)

    # Make.com media payload.
    if "image_url" in body and "caption" in body:
        media_payload = MediaPayload(**body)

        return MediaResponse(
            message="Media payload received by RoyalShield backend.",
            image_url=media_payload.image_url,
            caption=media_payload.caption,
            received_at=now_iso(),
        ).model_dump()

    # Make.com comment/message payload.
    comment_payload = CommentPayload(**body)
    category = classify_comment(comment_payload.comment_text)
    reply = generate_reply(category, comment_payload)

    return ClassificationResponse(
        category=category,
        reply=reply,
        received_at=now_iso(),
    ).model_dump()
