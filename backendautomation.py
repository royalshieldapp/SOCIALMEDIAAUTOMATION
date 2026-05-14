"""
Backend for RoyalShield Facebook and Instagram automation.

This small FastAPI server provides an endpoint (`/webhook`) that receives
JSON payloads from Make.com (or any other webhook provider) whenever a new
comment, message or mention is detected on Facebook or Instagram.

Upon receiving a request it will:
1. Validate the incoming data structure.
2. Classify the comment based on simple keyword rules into one of the
   categories defined by the user: "urgent", "lead", "soporte",
   "comentario_publico", "spam", or "irrelevante".
3. Generate a brief, human and professional reply in Spanish, following
   RoyalShield's tone. If classification suggests a sales opportunity
   ("lead"), the reply invites the user to learn more about RoyalShield.
4. Return a JSON response containing the classification and the proposed
   reply. Make.com can then use these values in subsequent modules to
   add rows to a spreadsheet, post a response, or route the comment.

The classification logic here is deliberately simple. For a production
system you may want to replace it with a call to a more advanced
language model or integrate it with RoyalShield's CRM to personalise
responses. This script can serve as a starting point.

To run this server locally:
```bash
pip install fastapi uvicorn
uvicorn backend:app --host 0.0.0.0 --port 8000
```

Then configure your Make.com HTTP module to send POST requests to
`http://<server-ip>:8000/webhook` with a JSON body like the example below.
"""

from typing import Literal
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="RoyalShield Automation Backend", version="1.0.0")


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


class ClassificationResponse(BaseModel):
    """Schema for the response returned to Make.com."""
    category: Literal[
        "urgent",
        "lead",
        "soporte",
        "comentario_publico",
        "spam",
        "irrelevante",
    ]
    reply: str


def classify_comment(text: str) -> str:
    """Simple rule-based classification for demonstration purposes.

    Args:
        text: The comment text.

    Returns:
        A string indicating the category.
    """
    lower = text.lower()
    # Basic heuristic rules based on keywords
    if any(word in lower for word in ["urgent", "inmediato", "ayuda", "problema"]):
        return "urgent"
    if any(word in lower for word in ["precio", "cotización", "quote", "suscripción"]):
        return "lead"
    if any(word in lower for word in ["soporte", "error", "fallo", "bug"]):
        return "soporte"
    if any(word in lower for word in ["http://", "https://", "compra aquí", "haz clic"]):
        return "spam"
    # Comments that mention the product or brand but are positive or neutral
    if any(word in lower for word in ["royalshield", "gracias", "excelente", "buen trabajo"]):
        return "comentario_publico"
    # Default to irrelevante if nothing matches
    return "irrelevante"


def generate_reply(category: str, payload: CommentPayload) -> str:
    """Generate a brief reply based on classification.

    Args:
        category: The classification category.
        payload: The original payload with comment details.

    Returns:
        A Spanish reply string.
    """
    name = payload.user_name.split()[0] if payload.user_name else "Hola"
    if category == "urgent":
        return (
            f"Hola {name}, sentimos que estés teniendo dificultades. "
            "Por favor envíanos un mensaje privado o visita nuestra página de soporte para ayudarte de inmediato."
        )
    if category == "lead":
        return (
            f"Hola {name}, gracias por tu interés en RoyalShield. "
            "Visita nuestro sitio oficial para conocer más o envíanos un mensaje y te orientaremos con mucho gusto."
        )
    if category == "soporte":
        return (
            f"Hola {name}, lamentamos los inconvenientes. "
            "Nuestro equipo de soporte está listo para ayudarte. Por favor comunícate por nuestro canal oficial."
        )
    if category == "comentario_publico":
        return (
            f"¡Gracias {name}! Apreciamos tu comentario y tu apoyo. "
            "Si tienes preguntas o necesitas información adicional, estamos aquí para ayudarte."
        )
    if category == "spam":
        return (
            f"Hola {name}, tu mensaje contiene enlaces o contenido sospechoso y ha sido marcado como spam. "
            "Si esto es un error, por favor contáctanos directamente para revisarlo."
        )
    # irrelevante or default
    return (
        f"Hola {name}, gracias por tu mensaje. "
        "Actualmente no se requiere ninguna acción. ¡Que tengas un excelente día!"
    )


@app.post("/webhook", response_model=ClassificationResponse)
async def handle_webhook(payload: CommentPayload) -> ClassificationResponse:
    """Endpoint triggered by Make.com with comment data.

    This endpoint classifies the incoming comment, generates a reply, and
    returns both values.
    """
    category = classify_comment(payload.comment_text)
    reply = generate_reply(category, payload)
    return ClassificationResponse(category=category, reply=reply)
