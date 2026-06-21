# ⚙️ Configuracion Make.com

Esta guia conecta Make.com con el backend de RoyalShield en Railway.

El backend no reemplaza a los modulos de Meta. Su papel es recibir datos normalizados, decidir que hacer y devolver una respuesta clara para que Make ejecute la accion final.

## Datos base

Reemplaza estos valores:

```text
RAILWAY_URL=https://tu-url-railway
MAKE_SECRET=el_mismo_valor_configurado_en_railway
```

Headers para todas las llamadas desde Make al backend:

```text
Content-Type: application/json
x-make-secret: MAKE_SECRET
```

## Escenario A: Auto-responder comentarios

Flujo recomendado:

```text
Meta/Facebook/Instagram trigger en Make
  -> HTTP POST al backend
  -> Router por action/category
  -> Modulo Meta para responder comentario
  -> Registro opcional en Google Sheets
```

### 1. Trigger

Usa el modulo de Facebook Pages o Instagram for Business que detecte comentarios nuevos. El nombre exacto puede variar segun tu conexion de Make.

### 2. HTTP POST al backend

URL:

```text
POST https://tu-url-railway/webhook
```

Body:

```json
{
  "platform": "instagram",
  "comment_id": "{{comment_id}}",
  "comment_text": "{{comment_text}}",
  "user_name": "{{user_name}}",
  "post_id": "{{post_id}}",
  "timestamp": "{{timestamp}}"
}
```

Campos importantes:

- `platform`: `instagram` o `facebook`.
- `comment_id`: ID real del comentario, necesario para responder.
- `comment_text`: texto que se clasificara.
- `user_name`: nombre visible para personalizar la respuesta.
- `post_id`: opcional, pero util para auditoria.
- `timestamp`: opcional, pero recomendado.

### 3. Router en Make

Usa la respuesta del backend:

```json
{
  "ok": true,
  "category": "lead",
  "action": "auto_reply",
  "reply": "Hola Carlos, gracias por tu interes...",
  "tags": ["posible_cliente", "ventas"],
  "make_next_step": "Publicar reply con modulo 'Create Comment Reply' de Make"
}
```

Rutas recomendadas:

- Si `action = auto_reply`: publicar `reply` como respuesta al comentario.
- Si `action = manual_review`: mandar a Slack/email/Sheet para revision.
- Si `action = ignore`: no publicar respuesta; solo registrar si quieres.

### 4. Responder en Meta

Usa el modulo de Make para responder comentarios o un HTTP request a Graph API.

Para Instagram Graph API, el patron comun es responder al comentario con el `comment_id` y un campo `message` igual a `reply`. Verifica el endpoint exacto en tu modulo/conexion de Make.

## Escenario B: Publicar desde Google Sheets

Flujo recomendado:

```text
Google Sheets row
  -> HTTP POST al backend /webhook/make
  -> Modulo Meta publica o programa
  -> Google Sheets actualiza Status
```

### 1. Columnas sugeridas en Google Sheets

| Platform | Caption | Image URL | Video URL | Publish At | Status | Meta ID |
|----------|---------|-----------|-----------|------------|--------|---------|
| instagram | Nuevo lanzamiento | https://... | | 2026-06-20T15:00:00Z | pending | |
| facebook | Promo semanal | https://... | | | pending | |

### 2. Filtrar filas pendientes

En Make, procesa solo filas donde:

```text
Status = pending
```

### 3. HTTP POST al backend

URL:

```text
POST https://tu-url-railway/webhook/make
```

Body:

```json
{
  "event_type": "publish_post",
  "platform": "{{Platform}}",
  "caption": "{{Caption}}",
  "image_url": "{{Image URL}}",
  "video_url": "{{Video URL}}",
  "publish_at": "{{Publish At}}"
}
```

Notas:

- `caption` es obligatorio.
- `image_url` y `video_url` deben empezar con `http://` o `https://`.
- `publish_at` debe ser ISO, por ejemplo `2026-06-20T15:00:00Z`.
- Para Instagram, este backend no acepta `video_url`; usa imagen o un `media_id` ya preparado.

### 4. Usar `publish_payload`

El backend responde algo como:

```json
{
  "ok": true,
  "category": "media_post",
  "action": "schedule_post",
  "platform": "instagram",
  "publish_payload": {
    "platform": "instagram",
    "caption": "Nuevo lanzamiento",
    "media_type": "image",
    "image_url": "https://example.com/image.jpg",
    "video_url": null,
    "publish_at": "2026-06-20T15:00:00Z"
  }
}
```

Make debe tomar `publish_payload` y enviarlo al modulo correspondiente de Meta.

### 5. Actualizar Google Sheets

Despues de publicar:

- `Status = published` si Meta responde bien.
- `Status = failed` si hubo error.
- `Meta ID = id devuelto por Meta`, si existe.

## Pruebas rapidas

### Probar comentario

```bash
curl -X POST https://tu-url-railway/webhook \
  -H "Content-Type: application/json" \
  -H "x-make-secret: TU_MAKE_SECRET" \
  -d '{
    "platform":"instagram",
    "comment_id":"1",
    "comment_text":"quiero precio",
    "user_name":"Carlos",
    "timestamp":"2026-06-20T10:00:00Z",
    "post_id":"post_1"
  }'
```

### Probar publicacion

```bash
curl -X POST https://tu-url-railway/webhook/make \
  -H "Content-Type: application/json" \
  -H "x-make-secret: TU_MAKE_SECRET" \
  -d '{
    "event_type":"publish_post",
    "platform":"instagram",
    "caption":"Post test",
    "image_url":"https://example.com/image.jpg"
  }'
```

## Errores comunes

### `401 Unauthorized`

Make no esta enviando `x-make-secret`, o el valor no coincide con `MAKE_SECRET` en Railway.

### `422`

El body no cumple el formato esperado. Revisa si falta `platform`, `comment_id`, `comment_text`, `user_name` o `caption`.

### El backend responde bien pero no se publica nada

Eso significa que el backend hizo su parte. Falta revisar el modulo de Meta en Make, permisos del token, Page ID, Instagram Business Account ID o el estado de la fila en Google Sheets.
