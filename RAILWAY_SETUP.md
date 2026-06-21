# 🚂 Configuracion Railway + GitHub

Esta guia deja `royalshieldapp/SOCIALMEDIAAUTOMATION` corriendo en Railway con una URL publica HTTPS para Meta y Make.com.

## 1. Crear proyecto en Railway

1. Entra a [railway.app](https://railway.app).
2. Crea un proyecto nuevo.
3. Selecciona **Deploy from GitHub repo**.
4. Escoge `royalshieldapp/SOCIALMEDIAAUTOMATION`.
5. Railway usara el `Dockerfile` del repo.

El repo incluye `railway.json` con health check en `/health`.

## 2. Configurar variables de entorno

En Railway, abre tu servicio y ve a **Variables**. Agrega:

```env
META_APP_ID=614438388426527
INSTAGRAM_APP_ID=1280603234240148
META_BUSINESS_ID=2640495129436229
META_VERIFY_TOKEN=pon_aqui_un_token_seguro
META_LONG_LIVED_ACCESS_TOKEN=pon_aqui_tu_token_largo_de_meta

MAKE_WEBHOOK_ID=2322427
MAKE_SECRET=pon_aqui_un_secreto_para_make
MAKE_FACEBOOK_CONNECTION_1=8998683
MAKE_FACEBOOK_CONNECTION_2=8947884
MAKE_FACEBOOK_CONNECTION_3=8998792
MAKE_GOOGLE_CONNECTION=8924705

FACEBOOK_PAGE_ID=tu_facebook_page_id
INSTAGRAM_BUSINESS_ACCOUNT_ID=tu_instagram_business_account_id
GOOGLE_SHEET_ID=10yqUf1Ch-EoTB97UVdfs4TFb4WPw8KXb22nEWaXp7bs

ENVIRONMENT=production
DEBUG=False
```

No es necesario configurar `PORT` manualmente en Railway. Railway lo inyecta y el `Dockerfile` ya lo usa.

Variables opcionales:

```env
POST_ID=
MEDIA_ID=
```

## 3. Verificar deploy

Cuando Railway termine el deploy, copia la URL publica. Debe verse similar a:

```text
https://socialmediaautomation-production.up.railway.app
```

Prueba estos endpoints:

```bash
curl https://tu-url-railway/health
curl https://tu-url-railway/config
```

`/config` solo muestra si las variables estan configuradas. No expone tokens.

## 4. Configurar webhook en Meta

En Facebook Developers / Meta App Dashboard:

1. Ve a **Webhooks**.
2. Agrega o edita el webhook.
3. Usa esta URL:

```text
https://tu-url-railway/webhook
```

4. En **Verify Token**, pon exactamente el mismo valor que `META_VERIFY_TOKEN` en Railway.
5. Guarda y verifica.

Campos sugeridos segun el producto activado en tu app:

- `feed`
- `comments`
- `messages`
- Instagram comments si tu app tiene Instagram Graph API habilitado

## 5. Conectar Make.com

Make debe enviar payloads normalizados al backend.

Para comentarios:

```text
POST https://tu-url-railway/webhook
Header: x-make-secret: TU_MAKE_SECRET
```

Para publicaciones:

```text
POST https://tu-url-railway/webhook/make
Header: x-make-secret: TU_MAKE_SECRET
```

La guia completa esta en [`MAKE_SETUP.md`](./MAKE_SETUP.md).

## 6. Obtener token largo de Meta

Necesitas un token largo con permisos suficientes para los modulos de Meta que usara Make.

Permisos comunes:

- `pages_show_list`
- `pages_read_engagement`
- `pages_manage_posts`
- `instagram_basic`
- `instagram_manage_comments`
- `instagram_content_publish`

El token debe pertenecer a una cuenta con acceso a la Facebook Page y a la cuenta de Instagram profesional conectada.

## 7. Prueba final

1. Publica un comentario real en Instagram/Facebook.
2. Confirma que Make lo detecta.
3. Confirma que Make llama al backend.
4. Confirma que el backend responde con `action` y `reply`.
5. Confirma que Make publica la respuesta con el modulo de Meta.

Para publicaciones programadas:

1. Crea una fila en Google Sheets.
2. Make envia el payload a `/webhook/make`.
3. El backend devuelve `publish_payload`.
4. Make publica o programa en Meta.
5. Make actualiza `Status` en Google Sheets.

## Troubleshooting

### `Invalid Meta verify token`

`META_VERIFY_TOKEN` en Railway no coincide con el token configurado en Meta.

### `META_VERIFY_TOKEN is not configured`

Falta configurar `META_VERIFY_TOKEN` en Railway o el deploy no fue reiniciado despues de agregarlo.

### `401 Unauthorized` desde Make

`MAKE_SECRET` esta configurado en Railway, pero Make no envio el header `x-make-secret` correcto.

### `422` desde Make

El JSON no cumple el formato esperado. Revisa `platform`, `comment_text`, `caption`, `image_url`, `video_url` y `publish_at`.

### Railway no responde

Revisa:

- Deploy logs en Railway.
- `https://tu-url-railway/health`.
- Que Railway este construyendo desde el `Dockerfile`.
- Que no hayas sobrescrito `PORT` con un valor incorrecto.
