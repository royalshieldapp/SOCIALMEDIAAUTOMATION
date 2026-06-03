<!-- markdownlint-disable MD033 MD041 -->

# 🎯 RoyalShield Social Media Automation

Backend en **FastAPI** para automatizar publicaciones en Facebook e Instagram con **Make.com** + **Railway**.

![Python](https://img.shields.io/badge/Python-3.11+-3776ab?style=flat-square&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688?style=flat-square&logo=fastapi)
![Railway](https://img.shields.io/badge/Railway-✓-0B0D0E?style=flat-square&logo=railway)

---

## ✨ Características

- ✅ **Auto-responder comentarios** en Instagram y Facebook
- ✅ **Publicar posts** inmediatos o programados
- ✅ **Integración Make.com** para workflows avanzados
- ✅ **Google Sheets** como base de datos de posts
- ✅ **Webhooks validados** de Meta
- ✅ **Deploy automático** con GitHub Actions + Railway
- ✅ **Documentación interactiva** en `/docs` (Swagger UI)

---

## 🚀 Quick Start

### 1. Clonar repositorio

```bash
git clone https://github.com/royalshieldapp/SOCIALMEDIAAUTOMATION.git
cd SOCIALMEDIAAUTOMATION
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
# Edita .env con tus credenciales
nano .env
```

Variables requeridas:
```env
META_VERIFY_TOKEN=tu_token_seguro_aqui
META_LONG_LIVED_ACCESS_TOKEN=tu_access_token_aqui
MAKE_SECRET=tu_make_secret
# ... ver .env.example para todas las variables
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Ejecutar localmente

```bash
uvicorn SOCIALMEDIAAUTOMATION:app --host 0.0.0.0 --port 8000 --reload
```

Accede a: http://localhost:8000/docs

---

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────┐
│          Meta Webhooks (Facebook/IG)        │
│   (comentarios, publicaciones, eventos)     │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
    ┌──────────────────────────────┐
    │   RoyalShield FastAPI App    │
    │   (Railway Container)        │
    │                              │
    │  POST /webhook               │
    │  POST /webhook/make          │
    │  GET  /health                │
    │  GET  /config                │
    └──────────────────────────────┘
         ▲              ▼
         │              │
    ┌────┴──┐      ┌────┴────────────┐
    │ Meta   │      │  Make.com       │
    │ API    │      │  Scenarios      │
    └────────┘      └────┬───────────┘
                         │
                    ┌────▼─────┐
                    │ Google    │
                    │ Sheets    │
                    └──────────┘
```

---

## 📝 Endpoints

### Health Check
```bash
GET /health
```
Respuesta:
```json
{
  "status": "healthy",
  "timestamp": "2026-06-03T10:15:30.123456",
  "environment": "production"
}
```

### Webhook Verification (Meta)
```bash
GET /webhook?hub.mode=subscribe&hub.challenge=CHALLENGE&hub.verify_token=TOKEN
```

### Webhook Events
```bash
POST /webhook
Content-Type: application/json

{
  "event_type": "comment",
  "platform": "instagram",
  "comment_id": "1234567890",
  "comment_text": "¿Cuál es el precio?",
  "user_name": "juanpedro92",
  "post_id": "998877665544",
  "timestamp": "2026-06-03T10:00:00Z",
  "action": "auto_reply"
}
```

### Make.com Webhook
```bash
POST /webhook/make
Content-Type: application/json

{
  "event_type": "publish_post",
  "platform": "instagram",
  "caption": "Nuevo lanzamiento RoyalShield 🎉",
  "image_url": "https://example.com/image.jpg",
  "publish_at": "2026-06-03T15:00:00Z"
}
```

---

## 🔐 Credenciales Meta

### Obtener `META_LONG_LIVED_ACCESS_TOKEN`

1. Ve a [Facebook Developers](https://developers.facebook.com)
2. App → Tools → **Graph API Explorer**
3. Genera token (válido 2 horas)
4. Canjéalo por token largo:

```bash
curl -i -X GET \
  "https://graph.instagram.com/oauth/access_token?
   grant_type=fb_exchange_token&
   client_id=614438388426527&
   client_secret=YOUR_APP_SECRET&
   fb_exchange_token=SHORT_TOKEN"
```

---

## 🔧 Configuración Railway

Ver: [`RAILWAY_SETUP.md`](./RAILWAY_SETUP.md)

**Resumen rápido:**

1. Conectar GitHub repo
2. Añadir variables de entorno
3. Habilitar auto-deploy
4. Copiar URL de webhook
5. Configurar en Meta App Dashboard

---

## ⚙️ Configuración Make.com

Ver: [`MAKE_SETUP.md`](./MAKE_SETUP.md)

**Escenarios disponibles:**

### Escenario A: Auto-responder comentarios
```
Instagram/Facebook → Webhook → Backend → Meta API → Respuesta automática
```

### Escenario B: Publicar desde Google Sheets
```
Google Sheets → Webhook → Backend → Meta API → Post publicado
```

---

## 📊 Google Sheets Integration

Tu Google Sheet debe tener estas columnas:

| Platform | Caption | Image URL | Video URL | Publish At | Status |
|----------|---------|-----------|-----------|-----------|--------|
| instagram | Nuevo lanzamiento 🎉 | https://... | - | 2026-06-03T15:00:00Z | pending |
| facebook | Únete a nosotros | https://... | - | 2026-06-03T15:30:00Z | published |

**Sheet ID:** `10yqUf1Ch-EoTB97UVdfs4TFb4WPw8KXb22nEWaXp7bs`

---

## 🧪 Testing

### Test local

```bash
# Health check
curl http://localhost:8000/health

# Webhook verification
curl "http://localhost:8000/webhook?hub.mode=subscribe&hub.challenge=test123&hub.verify_token=tu_token"

# Enviar comentario de prueba
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "comment",
    "platform": "instagram",
    "comment_id": "123",
    "comment_text": "¡Excelente!",
    "user_name": "test_user",
    "post_id": "456",
    "action": "auto_reply"
  }'
```

### Test en Railway

```bash
# Ver logs
railway logs -f

# Health check
curl https://tu-railway-url/health

# Webhook test
curl -X POST https://tu-railway-url/webhook/make \
  -H "Content-Type: application/json" \
  -d '{"event_type":"publish_post","platform":"instagram","caption":"Test","publish_at":"2026-06-03T15:00:00Z"}'
```

---

## 📋 Checklist de Configuración

- [ ] Variables de entorno en `.env`
- [ ] Meta App ID y App Secret en mano
- [ ] `META_LONG_LIVED_ACCESS_TOKEN` generado
- [ ] Repo conectado a Railway
- [ ] Variables de entorno en Railway dashboard
- [ ] Webhook URL configurado en Meta App Dashboard
- [ ] Make.com scenarios creados y testados
- [ ] Google Sheet preparada
- [ ] GitHub Secrets configurados para CI/CD

---

## 🐛 Troubleshooting

### Webhook no se ejecuta

```bash
# Verificar logs en Railway
railway logs -f

# Confirmar variables de entorno
curl https://tu-railway-url/config

# Probar manualmente
curl -X POST https://tu-railway-url/webhook \
  -H "Content-Type: application/json" \
  -d '{...}'
```

### "Invalid verify token"

- Verifica que `META_VERIFY_TOKEN` en Railway coincide con el de Meta App
- Espera 5 minutos después de actualizar variables

### Meta API errors

- Confirma que `META_LONG_LIVED_ACCESS_TOKEN` no ha expirado
- Verifica permisos: `pages_manage_posts`, `instagram_content_publish`
- Revisa que IDs de página/cuenta son correctos

---

## 📚 Documentación Adicional

- [**RAILWAY_SETUP.md**](./RAILWAY_SETUP.md) - Guía completa de Railway
- [**MAKE_SETUP.md**](./MAKE_SETUP.md) - Guía completa de Make.com
- [Meta Graph API](https://developers.facebook.com/docs/graph-api)
- [Instagram API](https://developers.facebook.com/docs/instagram-api)
- [Railway Docs](https://docs.railway.app)
- [Make.com Docs](https://www.make.com/en/help)

---

## 🤝 Contribuir

Reporta issues o sugiere features: [GitHub Issues](https://github.com/royalshieldapp/SOCIALMEDIAAUTOMATION/issues)

---

## 📄 Licencia

MIT License - Ver [LICENSE](./LICENSE) para detalles

---

## 🎉 Créditos

Desarrollado por **RoyalShield** para automatizar Social Media Marketing.

**Stack:**
- 🐍 Python 3.11+
- ⚡ FastAPI
- 🚂 Railway
- ⚙️ Make.com
- 📊 Google Sheets
- 🔵 Meta Graph API

---

**¿Preguntas?** Revisa los docs o abre un issue en GitHub.

Happy automating! 🚀
