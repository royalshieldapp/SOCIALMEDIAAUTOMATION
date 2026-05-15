"""
RoyalShield Automation Backend

FastAPI backend for Make.com / Railway.

What it does:
1. Receives webhook requests from Make.com.
2. Supports two payload styles:
   - Instagram/Facebook comments for classification and reply generation.
   - Image/caption payloads for publishing or forwarding logic.
3. Returns a fast JSON response so Make does not wait too long.
4. Includes /health for Railway health checks.

Local run:
    pip install -r requirements.txt
    uvicorn backendautomation:app --host 0.0.0.0 --port 8000

Railway endpoint examples:
    GET  https://YOUR-APP.up.railway.app/health
    POST https://YOUR-APP.up.railway.app/webhook
"""

import os
from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field


app = FastAPI(title="RoyalShield Automation Backend", version="1.1.0")


Category = Literal[
    "urgent",
    "lead",
    "soporte",
    "comentario_publico",
    "spam",
    "irrelevante",
    "media_post",
]


class CommentPayload(BaseModel):
    """Schema for incoming comment or message payloads."""

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


def verify_make_secret(secret_from_body: Optional[str], x_make_secret: Optional[str]) -> None:
    """
    Optional protection for Make.com requests.

    If MAKE_SECRET is not configured in Railway, this check is skipped.
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

    if any(word in lower for word in ["precio", "cotización", "cotizacion", "quote", "suscripción", "suscripcion", "plan", "costo"]):
        return "lead"

    if any(word in lower for word in ["soporte", "error", "fallo", "bug", "no funciona"]):
        return "soporte"

    if any(word in lower for word in ["http://", "https://", "compra aquí", "compra aqui", "haz clic", "click aquí", "click aqui"]):
        return "spam"

    if any(word in lower for word in ["royalshield", "royal shield", "gracias", "excelente", "buen trabajo", "me gusta"]):
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
        "service": "RoyalShield Automation Backend",
        "version": "1.1.0",
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


@app.post("/webhook")
async def handle_webhook(
    request: Request,
    x_make_secret: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """
    Endpoint triggered by Make.com.

    Supported JSON formats:

    Comment classification:
    {
      "platform": "instagram",
      "comment_id": "123",
      "comment_text": "quiero precio",
      "user_name": "Carlos",
      "timestamp": "2026-05-14T12:00:00Z"
    }

    Media/caption payload:
    {
      "image_url": "https://example.com/image.png",
      "caption": "Royal Shield App..."
    }
    """

    body = await request.json()

    secret_from_body = body.get("secret") if isinstance(body, dict) else None
    verify_make_secret(secret_from_body=secret_from_body, x_make_secret=x_make_secret)

    if "image_url" in body and "caption" in body:
        media_payload = MediaPayload(**body)

        # Keep this response fast. Add publishing, queueing, or database logic later.
        return MediaResponse(
            message="Media payload received by RoyalShield backend.",
            image_url=media_payload.image_url,
            caption=media_payload.caption,
            received_at=now_iso(),
        ).model_dump()

    comment_payload = CommentPayload(**body)
    category = classify_comment(comment_payload.comment_text)
    reply = generate_reply(category, comment_payload)

    return ClassificationResponse(
        category=category,
        reply=reply,
        received_at=now_iso(),
    ).model_dump()
