# 🚂 Configuración Railway + GitHub para RoyalShield Social Media Automation

## Paso 1: Crear proyecto en Railway

1. Ve a [railway.app](https://railway.app)
2. Haz clic en **"New Project"**
3. Selecciona **"Deploy from GitHub"**
4. Conecta tu cuenta de GitHub y selecciona: `royalshieldapp/SOCIALMEDIAAUTOMATION`
5. Railway auto-detectará que es una app Python/FastAPI

## Paso 2: Configurar variables de entorno en Railway

En tu proyecto de Railway, ve a **Variables** y añade:

```
META_APP_ID=614438388426527
INSTAGRAM_APP_ID=1280603234240148
META_BUSINESS_ID=2640495129436229
META_VERIFY_TOKEN=your_secure_random_token_here_abc123xyz
META_LONG_LIVED_ACCESS_TOKEN=YOUR_META_ACCESS_TOKEN_HERE

MAKE_WEBHOOK_ID=2322427
MAKE_SECRET=your_make_secret_token_here
MAKE_FACEBOOK_CONNECTION_1=8998683
MAKE_FACEBOOK_CONNECTION_2=8947884
MAKE_FACEBOOK_CONNECTION_3=8998792
MAKE_GOOGLE_CONNECTION=8924705

GOOGLE_SHEET_ID=10yqUf1Ch-EoTB97UVdfs4TFb4WPw8KXb22nEWaXp7bs

PORT=8000
ENVIRONMENT=production
DEBUG=False
```

### ⚠️ IMPORTANTE: Obtener `META_LONG_LIVED_ACCESS_TOKEN`

1. Ve a [Facebook Developers](https://developers.facebook.com)
2. App Settings → Tools → Access Token Debugger
3. Genera un token corto desde Graph API Explorer
4. Canjéalo por uno de larga duración:

```bash
# Reemplaza los valores:
curl -i -X GET "https://graph.instagram.com/oauth/access_token?grant_type=fb_exchange_token&client_id=614438388426527&client_secret=YOUR_APP_SECRET&fb_exchange_token=SHORT_TOKEN"
```

## Paso 3: Obtener URL desplegada en Railway

Una vez desplegado, Railway te mostrará una URL como:
```
https://socialmediaautomation-production.up.railway.app
```

**Guarda esta URL**, la necesitarás para los webhooks.

## Paso 4: Configurar Webhooks de Meta

### 4.1 En Facebook App Dashboard

1. Ve a **Settings** → **Basic** (copia App ID y App Secret)
2. Ve a **Settings** → **Webhooks**
3. Haz clic en **Edit Webhooks**

### 4.2 Añadir URL de webhook

- **Callback URL**: `https://tu-railway-url/webhook`
- **Verify Token**: El mismo que pusiste en `META_VERIFY_TOKEN`
- **Subscription Fields**: Selecciona:
  - ✅ `feed`
  - ✅ `comments`
  - ✅ `messages`
  - ✅ `message_reads`

4. Haz clic en **Verify and Save**

### 4.3 Suscribir a eventos

En la misma sección, bajo "Webhooks", haz clic en **"Manage Subscriptions"**:

- ✅ Page Feed
- ✅ Conversations  
- ✅ Instagram Comments
- ✅ Instagram Stories Comments

## Paso 5: Configurar Make.com (Scenarios)

### Scenario A: Auto-responder comentarios

```
[Webhook Trigger]
    ↓
[HTTP POST] → https://tu-railway-url/webhook
Body:
{
  "platform": "instagram",
  "comment_id": "{{86.id}}",
  "comment_text": "{{86.message}}",
  "user_name": "{{86.from.name}}",
  "timestamp": "now",
  "post_id": "{{86.object}}",
  "action": "auto_reply"
}
    ↓
[Meta API] → Reply to comment
```

### Scenario B: Publicar posts programados

```
[Google Sheets] Nueva fila
    ↓
[HTTP POST] → https://tu-railway-url/webhook/make
Body:
{
  "event_type": "publish_post",
  "platform": "{{1.Platform}}",
  "caption": "{{1.Caption}}",
  "image_url": "{{1.Image URL}}",
  "publish_at": "{{1.Scheduled Time}}"
}
    ↓
[FastAPI] → Meta Graph API
    ↓
Post published! 🎉
```

## Paso 6: GitHub Secrets (para CI/CD automático)

Ve a **Settings** → **Secrets and variables** → **Actions** en tu repo de GitHub:

```
RAILWAY_TOKEN = your-railway-api-token
RAILWAY_PROJECT_ID = your-project-id
```

Para obtener estos:
1. En Railway, haz clic en tu perfil → **Tokens**
2. Crea un nuevo token y cópialo como `RAILWAY_TOKEN`
3. En tu proyecto, copia el **Project ID** desde la URL

## Paso 7: Desplegar cambios

Una vez todo esté configurado:

```bash
git add .
git commit -m "Setup Railway + GitHub Actions deployment"
git push origin main
```

GitHub Actions ejecutará automáticamente y desplegará en Railway. ¡Listo! 🚀

## Verificar que funciona

```bash
# Health check
curl https://tu-railway-url/health

# Ver config (sin datos sensibles)
curl https://tu-railway-url/config

# Ver logs en Railway
# Dashboard → Deployments → Logs
```

## Troubleshooting

### "Invalid verify token" en webhook

- ✅ Asegúrate de que `META_VERIFY_TOKEN` en Railway coincide con el que pusiste en Meta App
- ✅ Espera 5 minutos después de cambiar variables en Railway

### Webhook no se ejecuta

- ✅ Verifica que la URL es correcta en Meta App Dashboard
- ✅ Revisa los logs en Railway: **Deployments** → **Logs**
- ✅ Asegúrate de que el `META_LONG_LIVED_ACCESS_TOKEN` no ha expirado

### Error "Unsupported platform"

- ✅ En Make.com, verifica que `platform` sea `"instagram"` o `"facebook"` (minúsculas)

## Recursos útiles

- 📚 [Meta Graph API Docs](https://developers.facebook.com/docs/graph-api)
- 🚂 [Railway Docs](https://docs.railway.app)
- ⚙️ [Make.com Integration](https://make.com)
- 📊 [Google Sheets API](https://developers.google.com/sheets/api)
