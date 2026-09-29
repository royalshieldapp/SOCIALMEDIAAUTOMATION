"""AI content generator and comment responder using NVIDIA NIM API."""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger("socialmediaautomation.ai")

DEFAULT_NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
DEFAULT_NVIDIA_MODEL = "meta/llama-3.2-11b-vision-instruct"
AI_TIMEOUT = 25.0

BRAND_SYSTEM_PROMPT = """Eres el estratega de contenido y director de redes sociales de Royal Shield.
Royal Shield es una plataforma y ecosistema tecnológico integral de seguridad personal, ciberseguridad, protección familiar y privacidad digital (con app móvil, monitoreo de riesgos, alertas de amenazas y VPN segura).

Tu tono de voz es:
- Experto, protector, confiable y accesible.
- Nunca alarmista sin solución: siempre planteas un riesgo o problema real y ofreces valor inmediato, prevención o la solución que brinda Royal Shield.
- Muy adaptado a redes sociales modernas: usas ganchos iniciales atractivos, párrafos cortos, formato visualmente limpio, emojis moderados y profesionales, y llamadas a la acción (CTA) directas.
- Respuestas siempre en español a menos que se indique lo contrario.
"""

TOPIC_IDEAS = [
    "Cómo identificar intentos de phishing y estafas bancarias por mensaje de texto",
    "Los peligros de conectarse a redes Wi-Fi públicas sin protección VPN",
    "Seguridad digital para toda la familia: protegiendo a niños y adultos mayores en internet",
    "Qué hacer de inmediato si sospechas que tu teléfono o cuenta fue vulnerada",
    "La importancia de la privacidad: cómo evitar que recopilen tus datos personales",
    "Alertas de seguridad en tiempo real en tu comunidad con la app Royal Shield"
]


def get_nvidia_key() -> str:
    return (os.getenv("NVIDIA_API_KEY") or "").strip()


def get_nvidia_model() -> str:
    return (os.getenv("NVIDIA_MODEL") or DEFAULT_NVIDIA_MODEL).strip()


async def call_nvidia_chat(messages: List[Dict[str, str]], *, temperature: float = 0.7, max_tokens: int = 1000) -> str:
    api_key = get_nvidia_key()
    if not api_key:
        raise ValueError("NVIDIA_API_KEY no está configurada")
    
    model = get_nvidia_model()
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    async with httpx.AsyncClient(timeout=AI_TIMEOUT) as client:
        response = await client.post(DEFAULT_NVIDIA_URL, json=payload, headers=headers)
        if response.status_code != 200:
            logger.error("NVIDIA API error %s: %s", response.status_code, response.text)
            raise RuntimeError(f"NVIDIA NIM error {response.status_code}: {response.text[:200]}")
        
        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("NVIDIA NIM no devolvió opciones")
        return str(choices[0].get("message", {}).get("content", "")).strip()


async def generate_post(
    topic: Optional[str] = None,
    platform: str = "instagram",
    tone: str = "profesional",
    language: str = "es"
) -> Dict[str, Any]:
    """Genera un post optimizado para Facebook o Instagram usando NVIDIA NIM."""
    api_key = get_nvidia_key()
    chosen_topic = (topic or "").strip()
    if not chosen_topic:
        import random
        chosen_topic = random.choice(TOPIC_IDEAS)
        
    if not api_key:
        # Fallback sin API key configurada
        return {
            "caption": (
                f"🛡️ {chosen_topic}\n\n"
                "La seguridad de tu información digital es la mejor inversión para tu tranquilidad y la de tu familia. "
                "Con Royal Shield, mantén tus dispositivos, tu privacidad y tus conexiones siempre protegidas.\n\n"
                "👉 Descarga la app y activa tu escudo de protección hoy mismo.\n\n"
                "#RoyalShield #Ciberseguridad #ProteccionDigital #Privacidad #SeguridadOnline"
            ),
            "topic": chosen_topic,
            "platform": platform,
            "provider": "fallback_template"
        }

    platform_instructions = (
        "Formato para Instagram: Gancho inicial impactante en la primera línea. Párrafos breves con saltos de línea limpios. "
        "Emojis seleccionados que den dinamismo. Llamada a la acción invitando a guardar el post o visitar el enlace del perfil. "
        "Incluye al final de 5 a 10 hashtags estratégicos relevantes."
        if platform == "instagram"
        else
        "Formato para Facebook: Titular llamativo. Texto explicativo de alto valor (2 a 3 párrafos concisos). "
        "Pregunta final o llamada a la acción para generar interacción en los comentarios. 3 a 5 hashtags al final."
    )

    prompt = f"""Escribe una publicación completa para {platform.upper()} sobre el siguiente tema de seguridad:
Tema: "{chosen_topic}"
Tono: {tone}
Idioma: {language}

{platform_instructions}

IMPORTANTE: Devuelve ÚNICAMENTE el texto listo para publicar (copy final). No agregues notas como 'Aquí tienes tu publicación:' ni títulos adicionales.
"""

    messages = [
        {"role": "system", "content": BRAND_SYSTEM_PROMPT},
        {"role": "user", "content": prompt}
    ]

    try:
        content = await call_nvidia_chat(messages, temperature=0.75, max_tokens=1000)
        # Limpieza básica si el modelo agregó preámbulo
        cleaned = re.sub(r"^(aquí tienes|a continuación|claro|por supuesto)[^\n]*\n+", "", content, flags=re.IGNORECASE).strip()
        return {
            "caption": cleaned or content,
            "topic": chosen_topic,
            "platform": platform,
            "provider": f"nvidia:{get_nvidia_model()}"
        }
    except Exception as exc:
        logger.warning("Fallo al llamar a NVIDIA NIM para generar post: %s", exc)
        return {
            "caption": (
                f"🛡️ {chosen_topic}\n\n"
                "La seguridad digital es vital en el día a día. "
                "En Royal Shield protegemos lo que más te importa con tecnología avanzada de monitoreo y privacidad.\n\n"
                "👉 Conoce más y activa tu protección hoy.\n\n"
                "#RoyalShield #Ciberseguridad #ProteccionDigital"
            ),
            "topic": chosen_topic,
            "platform": platform,
            "provider": "fallback_error",
            "error": str(exc)
        }


async def generate_smart_reply(comment_text: str, user_name: str, platform: str) -> Dict[str, Any]:
    """Genera una respuesta inteligente y contextual a un comentario usando NVIDIA NIM."""
    api_key = get_nvidia_key()
    clean_name = (user_name or "").split()[0] if user_name else "amigo"
    
    if not api_key:
        return {
            "reply": f"Hola {clean_name}, gracias por tu comentario. Para cualquier consulta o soporte con Royal Shield, contáctanos por mensaje privado.",
            "category": "comentario_publico",
            "provider": "fallback_template"
        }

    prompt = f"""Un usuario comentó en nuestra cuenta de {platform.upper()} de Royal Shield.
Nombre del usuario: {user_name}
Comentario recibido: "{comment_text}"

Instrucciones:
1. Analiza la intención del usuario.
2. Redacta una respuesta pública amigable, profesional, concisa (máximo 2 a 3 oraciones) y con el tono de Royal Shield.
3. Si el usuario pregunta por precios, planes o ventas, agradécele e indícale que le enviamos la información detallada por mensaje privado (DM).
4. Si el usuario reporta un problema técnico o duda urgente, dale tranquilidad e indícale que por privado revisamos su caso paso a paso.
5. Si es un saludo o felicitación, agradece con calidez.
6. Si parece spam publicitario o enlaces sospechosos, indica que es SPAM.

Responde ÚNICAMENTE en formato JSON estricto con esta estructura:
{{
  "category": "lead" | "soporte" | "urgent" | "comentario_publico" | "spam",
  "reply": "Texto exacto de la respuesta para el usuario"
}}
"""

    messages = [
        {"role": "system", "content": BRAND_SYSTEM_PROMPT},
        {"role": "user", "content": prompt}
    ]

    try:
        raw_output = await call_nvidia_chat(messages, temperature=0.3, max_tokens=300)
        # Extraer JSON si viene rodeado de markdown ```json ... ```
        json_match = re.search(r"\{[\s\S]*\}", raw_output)
        if json_match:
            parsed = json.loads(json_match.group(0))
            return {
                "reply": parsed.get("reply", f"Hola {clean_name}, ¡gracias por contactar a Royal Shield! Te escribimos por privado para darte más detalles."),
                "category": parsed.get("category", "comentario_publico"),
                "provider": f"nvidia:{get_nvidia_model()}"
            }
        return {
            "reply": raw_output.strip(),
            "category": "comentario_publico",
            "provider": f"nvidia:{get_nvidia_model()}"
        }
    except Exception as exc:
        logger.warning("Fallo al generar respuesta con NVIDIA: %s", exc)
        return {
            "reply": f"Hola {clean_name}, gracias por tu mensaje. Escríbenos por privado para poder orientarte mejor con Royal Shield.",
            "category": "comentario_publico",
            "provider": "fallback_error"
        }
