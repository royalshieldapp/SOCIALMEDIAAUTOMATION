# SOCIALMEDIAAUTOMATION

Backend en FastAPI para automatizar Facebook e Instagram con Make.com:
- Responder comentarios automáticamente según clasificación.
- Preparar payload de publicación (inmediata o programada).
- Validar webhook de Meta.

## Despliegue activo (Railway)

- Base URL: `https://socialmediaautomation-production.up.railway.app`
- Health: `GET https://socialmediaautomation-production.up.railway.app/health`
- Webhook verify: `GET https://socialmediaautomation-production.up.railway.app/webhook`
- Webhook eventos: `POST https://socialmediaautomation-production.up.railway.app/webhook`

## IDs que ya me compartiste

- `PAGE_ID=61573434707140`
- `INSTAGRAM_BUSINESS_ID=2640495129436229`
- `POST_ID=18068953853001463`
- `MEDIA_ID=1184853931369329`

> Recomendación: guárdalos también como variables en Railway:
> - `DEFAULT_POST_ID=18068953853001463`
> - `DEFAULT_MEDIA_ID=1184853931369329`

## Confirmación de IDs operativos

- POST_ID activo: `18068953853001463`
- MEDIA_ID activo: `1184853931369329`
- Fecha de confirmación: `2026-05-25`

## Ejecutar local

```bash
pip install -r requirements.txt
uvicorn SOCIALMEDIAAUTOMATION:app --host 0.0.0.0 --port 8000
```

## Endpoints

- `GET /health`
- `GET /webhook` (verificación Meta)
- `POST /webhook` (comentarios + publicaciones)

## Formato recomendado de eventos en Make.com

### 1) Responder comentarios (Facebook / Instagram)
Envía este payload al webhook:

```json
{
  "platform": "instagram",
  "comment_id": "1789",
  "comment_text": "quiero precio",
  "user_name": "Carlos",
  "timestamp": "2026-05-24T18:00:00Z",
  "post_id": "18068953853001463"
}
```

### 2) Crear publicación
Para publicaciones, **incluye** `event_type: "publish_post"`:

```json
{
  "event_type": "publish_post",
  "platform": "facebook",
  "caption": "Nuevo lanzamiento RoyalShield",
  "image_url": "https://example.com/image.jpg",
  "publish_at": "2026-05-30T15:00:00Z",
  "media_id": "18002500652607734"
}
```

> Nota: `media_id` puede viajar en tu escenario de Make para trazabilidad aunque el backend no lo exige para validar.

## Datos que necesito de tu lado (lista)

1. `META_VERIFY_TOKEN` (Railway env var).
2. `MAKE_SECRET` (opcional pero recomendado).
3. `FACEBOOK_PAGE_ID` (confirmado: `61573434707140`).
4. `INSTAGRAM_BUSINESS_ACCOUNT_ID` (confirmado: `2640495129436229`).
5. `META_LONG_LIVED_ACCESS_TOKEN`.
6. Permisos de app: `pages_manage_posts`, `pages_read_engagement`, `instagram_basic`, `instagram_content_publish`, `pages_manage_metadata`.
7. Qué tipo de respuesta quieres por categoría (ej: `lead`, `soporte`, `urgent`) para personalizar los mensajes automáticos.
8. Horarios / zona horaria de publicación para posts programados.

## Flujo Make.com sugerido

- Escenario A: recibir comentario -> llamar backend -> si `action=auto_reply`, publicar respuesta.
- Escenario B: crear publicación -> llamar backend con `event_type=publish_post` -> enviar `publish_payload` a Graph API.
