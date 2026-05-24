# SOCIALMEDIAAUTOMATION

Backend en FastAPI para automatizar Facebook e Instagram con Make.com:
- Responder comentarios automáticamente según clasificación.
- Preparar payload de publicación (inmediata o programada).
- Validar webhook de Meta.

## Ejecutar local

```bash
pip install -r requirements.txt
uvicorn SOCIALMEDIAAUTOMATION:app --host 0.0.0.0 --port 8000
```

## Endpoints

- `GET /health`
- `GET /webhook` (verificación Meta)
- `POST /webhook` (comentarios + publicaciones)

## Datos que necesitas configurar (checklist)

1. `META_VERIFY_TOKEN` (Railway env var).
2. `MAKE_SECRET` (opcional pero recomendado).
3. `FACEBOOK_PAGE_ID`.
4. `INSTAGRAM_BUSINESS_ACCOUNT_ID`.
5. `META_LONG_LIVED_ACCESS_TOKEN`.
6. Permisos de app: `pages_manage_posts`, `pages_read_engagement`, `instagram_basic`, `instagram_content_publish`, `pages_manage_metadata`.
7. Escenarios de Make.com:
   - Escenario A: recibir comentario -> llamar backend -> si `action=auto_reply`, publicar respuesta.
   - Escenario B: crear publicación -> llamar backend -> enviar `publish_payload` a Graph API.

## Ejemplo: comentario

```json
{
  "platform": "instagram",
  "comment_id": "1789",
  "comment_text": "quiero precio",
  "user_name": "Carlos",
  "timestamp": "2026-05-24T18:00:00Z",
  "post_id": "998877"
}
```

## Ejemplo: publicación

```json
{
  "event_type": "publish_post",
  "platform": "facebook",
  "caption": "Nuevo lanzamiento RoyalShield",
  "image_url": "https://example.com/image.jpg",
  "publish_at": "2026-05-30T15:00:00Z"
}
```
