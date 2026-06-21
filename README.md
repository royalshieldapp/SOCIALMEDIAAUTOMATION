<!-- markdownlint-disable MD033 MD041 -->

# 🎯 RoyalShield Social Media Automation

Backend en **FastAPI** para conectar Meta/Facebook/Instagram con **Make.com** y **Railway**.

El backend funciona como motor de decision: valida webhooks, clasifica comentarios, genera respuestas sugeridas y normaliza payloads de publicacion. La publicacion real y las respuestas en Meta las ejecuta Make.com con sus modulos de Facebook/Instagram o HTTP Graph API.

![Python](https://img.shields.io/badge/Python-3.11+-3776ab?style=flat-square&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688?style=flat-square&logo=fastapi)
![Railway](https://img.shields.io/badge/Railway-ready-0B0D0E?style=flat-square&logo=railway)

---

## Estado actual

- ✅ `GET /webhook` verifica el webhook de Meta usando `META_VERIFY_TOKEN`.
- ✅ `POST /webhook` recibe eventos de Meta o payloads normalizados de Make.
- ✅ `POST /webhook/make` existe como alias para escenarios de Make.
- ✅ `GET /health` sirve como health check de Railway.
- ✅ `GET /config` confirma variables configuradas sin mostrar secretos.
- ✅ Docker usa el puerto asignado por Railway con `PORT`.
- ✅ CI de GitHub compila el backend y corre smoke tests.

---

## Quick Start local

```bash
git clone https://github.com/royalshieldapp/SOCIALMEDIAAUTOMATION.git
cd SOCIALMEDIAAUTOMATION
cp .env.example .env
pip install -r requirements.txt
uvicorn SOCIALMEDIAAUTOMATION:app --host 0.0.0.0 --port 8000 --reload
```

Abre:

- `http://localhost:8000/health`
- `http://localhost:8000/config`
- `http://localhost:8000/docs`

---

## Variables requeridas

En Railway configura como minimo:

```env
META_VERIFY_TOKEN=un_token_seguro_que_tambien_usaras_en_meta
MAKE_SECRET=un_secreto_para_proteger_llamadas_de_make
META_LONG_LIVED_ACCESS_TOKEN=token_largo_de_meta
ENVIRONMENT=production
```

Variables utiles para Make o modulos Meta:

```env
META_APP_ID=614438388426527
INSTAGRAM_APP_ID=1280603234240148
META_BUSINESS_ID=2640495129436229
FACEBOOK_PAGE_ID=tu_page_id
INSTAGRAM_BUSINESS_ACCOUNT_ID=tu_ig_business_account_id
GOOGLE_SHEET_ID=10yqUf1Ch-EoTB97UVdfs4TFb4WPw8KXb22nEWaXp7bs
POST_ID=
MEDIA_ID=
```

No guardes tokens reales en el repo. Ponlos solo en Railway, Meta y Make.

---

## Endpoints

### Health check

```http
GET /health
```

Respuesta esperada:

```json
{
  "ok": true,
  "status": "healthy",
  "environment": "production",
  "received_at": "2026-06-20T10:15:30.123456+00:00"
}
```

### Config segura

```http
GET /config
```

Devuelve banderas `true/false` para confirmar si las variables existen, sin exponer los valores secretos.

### Verificacion de Meta

```http
GET /webhook?hub.mode=subscribe&hub.challenge=CHALLENGE&hub.verify_token=META_VERIFY_TOKEN
```

Meta debe recibir el `hub.challenge` como texto plano.

### Comentarios desde Make

```http
POST /webhook
Content-Type: application/json
x-make-secret: MAKE_SECRET

{
  "platform": "instagram",
  "comment_id": "1234567890",
  "comment_text": "Quiero precio",
  "user_name": "Carlos",
  "post_id": "998877665544",
  "timestamp": "2026-06-20T10:00:00Z"
}
```

El backend responde con `category`, `action`, `reply`, `tags` y `make_next_step`.

### Publicaciones desde Make

```http
POST /webhook/make
Content-Type: application/json
x-make-secret: MAKE_SECRET

{
  "event_type": "publish_post",
  "platform": "instagram",
  "caption": "Nuevo lanzamiento RoyalShield",
  "image_url": "https://example.com/image.jpg",
  "publish_at": "2026-06-20T15:00:00Z"
}
```

El backend devuelve un `publish_payload` normalizado. Make debe usar ese payload para ejecutar el modulo de Meta/Graph API.

---

## Deploy en Railway

Ver la guia completa: [`RAILWAY_SETUP.md`](./RAILWAY_SETUP.md)

Resumen:

1. Crea un proyecto en Railway desde GitHub.
2. Selecciona `royalshieldapp/SOCIALMEDIAAUTOMATION`.
3. Configura las variables de entorno.
4. Railway construira con `Dockerfile` y le pasara `PORT` al contenedor.
5. Copia la URL publica de Railway.
6. Configura en Meta el callback `https://tu-url-railway/webhook`.
7. Configura Make para llamar a `https://tu-url-railway/webhook` o `/webhook/make`.

---

## Make.com

Ver la guia completa: [`MAKE_SETUP.md`](./MAKE_SETUP.md)

Escenarios recomendados:

- Comentarios: Meta/Instagram trigger en Make -> backend -> modulo de respuesta en Meta.
- Publicaciones: Google Sheets -> backend -> modulo de publicacion en Meta -> actualizar estado en Sheets.

---

## Testing

```bash
python -m py_compile SOCIALMEDIAAUTOMATION.py
python -m unittest discover -s tests
```

GitHub Actions ejecuta estos checks en cada push a `main` y en pull requests.

---

## Checklist final

- [ ] Railway conectado al repo.
- [ ] Variables reales configuradas en Railway.
- [ ] `META_VERIFY_TOKEN` coincide en Railway y Meta.
- [ ] Webhook de Meta verificado con `https://tu-url-railway/webhook`.
- [ ] Escenarios de Make creados con `x-make-secret`.
- [ ] Token largo de Meta vigente y con permisos correctos.
- [ ] Cuenta Instagram profesional conectada a una Facebook Page.
- [ ] Prueba real: comentario en Instagram/Facebook -> Make -> backend -> respuesta.

---

## Troubleshooting

### `Invalid Meta verify token`

Confirma que `META_VERIFY_TOKEN` en Railway es exactamente el mismo token usado en Meta App Dashboard.

### Make recibe `401 Unauthorized`

Si `MAKE_SECRET` esta configurado en Railway, Make debe enviar el header `x-make-secret` con el mismo valor.

### Make recibe `422`

El JSON esta incompleto o tiene valores invalidos. Revisa `platform`, `caption`, `image_url`, `video_url` y `publish_at`.

### Railway no abre la app

Revisa `/health`, logs del deploy y que el contenedor este usando la variable `PORT`.

---

## Recursos

- [Meta Graph API](https://developers.facebook.com/docs/graph-api)
- [Instagram API](https://developers.facebook.com/docs/instagram-api)
- [Railway Docs](https://docs.railway.app)
- [Make.com Docs](https://www.make.com/en/help)
