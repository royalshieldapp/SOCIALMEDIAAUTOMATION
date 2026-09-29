# Diseño: automatización y crecimiento orgánico de @royalshieldsecure

**Fecha:** 2026-08-01  
**Estado:** aprobado en conversación; pendiente de revisión del documento  
**Servicio:** `royalshieldapp/SOCIALMEDIAAUTOMATION`, separado del producto Royal Shield

## 1. Objetivo

Configurar la cuenta nueva de Instagram `@royalshieldsecure` como presencia oficial de Royal Shield y conectarla con la página existente de Facebook, Meta Business, Make y el backend desplegado en Railway. El sistema deberá:

- programar y publicar contenido en inglés;
- responder automáticamente comentarios de bajo riesgo;
- escalar comentarios sensibles a revisión humana;
- atraer seguidores reales mediante contenido útil y crecimiento orgánico;
- registrar resultados reales y fallar de forma explícita cuando Meta, Make o Railway no completen una acción.

No se usarán anuncios pagados, seguidores comprados, follow/unfollow automático, likes masivos, spam, scraping no autorizado ni mensajes directos masivos.

## 2. Alcance

### Incluido

- Conversión de la cuenta de Instagram a tipo profesional **Business**.
- Vinculación con la página existente de Facebook de Royal Shield.
- Incorporación o verificación dentro del portafolio correcto de Meta Business.
- Conexión de Instagram en Make mediante la sesión autenticada del usuario.
- Configuración de identificadores y secretos únicamente en Meta, Make y Railway.
- Publicaciones programadas de imágenes, carruseles y, después de ampliar y validar el flujo actual, Reels.
- Clasificación y respuesta a comentarios.
- Calendario editorial en inglés para público general segmentado.
- Métricas orgánicas y revisión semanal.
- Pruebas reales de publicación, comentario, respuesta y registro del resultado.

### Fuera de alcance

- Campañas publicitarias o gasto en Meta Ads.
- Automatización de seguidores, likes, follows, unfollows o comentarios promocionales en cuentas ajenas.
- Mensajes directos masivos o no solicitados.
- Promesas de protección total o claims de seguridad no verificados.
- Modificar el producto Android Royal Shield u otros repositorios.

## 3. Enfoques considerados

### A. Flujo híbrido: backend + Make + Meta — seleccionado

El backend valida y clasifica; Make programa/orquesta; Meta publica y responde. Reutiliza la arquitectura existente, mantiene controles visibles y reduce cambios innecesarios.

### B. Graph API directa

Ofrece mayor control y menos dependencia de Make, pero exige más desarrollo, gestión de tokens, observabilidad, revisión de permisos y mantenimiento. Puede evaluarse después de estabilizar el flujo híbrido.

### C. Solo Meta Business Suite

Permite una puesta en marcha rápida, pero no satisface la lógica personalizada de clasificación, aprobación, registro y respuestas automáticas requerida.

## 4. Arquitectura propuesta

### 4.1 Identidad y permisos

- `@royalshieldsecure` será una cuenta Business pública.
- La cuenta se vinculará a la página oficial existente de Facebook.
- Meta Business deberá mostrar ambos activos bajo el portafolio correcto.
- El usuario conservará control administrativo y realizará directamente cualquier inicio de sesión, desafío MFA o consentimiento.
- Los permisos efectivos se comprobarán desde las conexiones reales; no se asumirán por nombre ni se codificarán identificadores sin verificarlos.

### 4.2 Calendario editorial

Google Sheets será la cola editorial inicial. Cada registro tendrá, como mínimo:

- `Content ID`
- `Audience Segment`
- `Content Pillar`
- `Format`
- `Caption`
- `Media URL`
- `Publish At`
- `Approval Status`
- `Publish Status`
- `Meta Media ID`
- `Published At`
- `Error Summary`

Estados válidos: `draft`, `pending_review`, `approved`, `publishing`, `published`, `failed` y `cancelled`. Solo `approved` puede entrar al flujo de publicación.

### 4.3 Publicación

1. Make consulta únicamente filas `approved` cuya fecha programada haya llegado.
2. Make envía el payload al endpoint protegido del backend con `x-make-secret`.
3. El backend valida plataforma, formato, texto, URL multimedia y campos obligatorios.
4. El backend devuelve un payload normalizado o un error explícito.
5. Make publica mediante la conexión oficial de Instagram/Meta.
6. Make guarda el identificador real devuelto por Meta y cambia el estado a `published`.
7. Si Meta no confirma la publicación, el estado será `failed`; nunca se registrará éxito basándose solo en una respuesta local.

El backend actual rechaza `video_url` para Instagram. Reels se activará solamente después de implementar el formato correcto, agregar pruebas y completar una publicación real de validación.

### 4.4 Comentarios

1. Meta o Make entrega el comentario y su identificador real.
2. El backend valida autenticidad, normaliza el evento y clasifica el contenido.
3. Se aplica una política de riesgo:

   - **Bajo:** agradecimientos, preguntas generales y consultas informativas verificables. Puede responderse automáticamente.
   - **Medio:** problemas de producto, precios, compatibilidad o troubleshooting. Se genera borrador para revisión.
   - **Alto:** pagos, cuentas comprometidas, amenazas, menores, privacidad, datos personales, vulnerabilidades o reclamaciones legales. No se responde automáticamente; se escala.

4. La publicación de la respuesta debe devolver evidencia de Meta. Un fallo de token, permiso o red queda registrado como error y no como éxito.

Las respuestas automáticas serán breves, variadas, en inglés y limitadas a hechos confirmados. No solicitarán contraseñas, tokens, información bancaria completa ni datos sensibles.

## 5. Estrategia orgánica de contenido

### 5.1 Audiencias

El público será general, pero cada pieza se enfocará en un segmento principal:

- familias y padres;
- jóvenes y estudiantes;
- adultos mayores;
- profesionales y trabajadores remotos;
- pequeños negocios.

### 5.2 Pilares editoriales

- Scam alerts y señales de fraude.
- Privacy tips prácticos.
- Seguridad digital familiar.
- Protección de dispositivos y cuentas.
- Educación sobre Wi-Fi público y VPN sin promesas absolutas.
- Explicación de capacidades reales de Royal Shield.
- Checklists rápidos y errores comunes.

### 5.3 Cadencia inicial

- Cuatro publicaciones semanales.
- Dos Reels semanales una vez validado el flujo de video.
- Stories frecuentes reutilizando material aprobado.
- Revisión semanal de rendimiento y ajuste mensual del calendario.

La cadencia es un punto de partida, no una garantía de crecimiento. Se ajustará con datos reales de Insights.

### 5.4 Voz y llamadas a la acción

La voz será premium, clara, útil y confiable. Evitará miedo exagerado y afirmaciones no demostradas. Las llamadas a la acción pedirán, según el contenido, seguir, guardar, compartir o comentar de forma natural; no condicionarán premios o dinero a métricas de engagement.

## 6. Perfil inicial

Antes de automatizar publicaciones se configurarán:

- nombre visible coherente con Royal Shield;
- categoría de negocio apropiada;
- biografía en inglés que explique el beneficio real sin promesas absolutas;
- enlace oficial verificado;
- logo aprobado y legible en formato circular;
- información de contacto mínima y no sensible;
- autenticación de dos factores y revisión de sesiones activas.

El texto final de bio, CTA y enlace se aprobará antes de publicarlo.

## 7. Seguridad y privacidad

- No se compartirán contraseñas, tokens completos ni App Secret en el chat.
- Secretos y tokens vivirán solo en almacenes protegidos de Railway, Make y Meta.
- Los logs no incluirán tokens, firmas completas, comentarios privados ni datos personales innecesarios.
- Los webhooks directos de Meta exigirán firma válida.
- Las llamadas de Make exigirán `x-make-secret`.
- Endpoints sensibles tendrán validación, límites de tasa y errores sanitizados.
- Los permisos se limitarán a publicación, lectura/gestión de comentarios e Insights necesarios.
- Las conexiones y tokens tendrán un procedimiento de rotación y revocación.

## 8. Manejo de errores

- Token vencido o permiso ausente: detener la acción, registrar error sanitizado y solicitar reconexión.
- Cuenta no vinculada o identificador incorrecto: bloquear publicación y mostrar el activo que falta verificar.
- Medio inaccesible o formato inválido: marcar `failed` sin enviar a Meta.
- Respuesta duplicada o webhook repetido: usar identificadores de evento para evitar doble publicación.
- Rate limit de Meta: reintento controlado con espera y número máximo de intentos.
- Error parcial entre Meta y Sheets: consultar el identificador real antes de reintentar para evitar duplicados.
- Contenido sensible: escalar a humano y conservar estado `pending_review`.

## 9. Pruebas y criterios de aceptación

### 9.1 Cuenta y conexión

- Instagram muestra tipo Business.
- Facebook y Meta Business muestran la cuenta correcta vinculada.
- Make puede enumerar el activo correcto sin exponer credenciales.
- Railway muestra únicamente flags de configuración, no valores secretos.

### 9.2 Publicación real

- Una fila aprobada produce una publicación visible en `@royalshieldoficial`.
- Sheets guarda el ID real de Meta y la hora de publicación.
- Una fila no aprobada no se publica.
- Un error de permisos termina en `failed`, no en `published`.

### 9.3 Comentario real

- Un comentario de prueba llega al backend con ID verificable.
- Una consulta de bajo riesgo recibe una respuesta visible en Instagram.
- Un comentario sensible queda en revisión sin respuesta automática.
- Un webhook duplicado no genera una segunda respuesta.

### 9.4 Crecimiento y analítica

- Insights registra alcance, interacciones, visitas al perfil, nuevos seguidores, guardados y compartidos.
- Se genera una revisión semanal basada en datos reales.
- No se atribuye crecimiento a la automatización sin comparar períodos y contenido.

## 10. Rollout y rollback

### Fase 1: preparación

Vincular activos, asegurar la cuenta, completar perfil y verificar permisos sin publicar automáticamente.

### Fase 2: publicación supervisada

Publicar un lote pequeño aprobado manualmente y validar imágenes, captions, horarios y registros.

### Fase 3: comentarios supervisados

Generar borradores y confirmar clasificación antes de activar respuestas automáticas de bajo riesgo.

### Fase 4: automatización gradual

Activar publicaciones programadas y respuestas de bajo riesgo con monitoreo diario inicial.

### Fase 5: Reels y optimización

Implementar el soporte faltante de video, hacer una prueba real y optimizar según Insights.

Rollback: desactivar escenarios de Make y flags de auto-respuesta, revocar la conexión si fuera necesario y conservar el historial. No se eliminarán publicaciones ni datos sin autorización explícita.

## 11. Restricciones de implementación

- Antes de editar código se reconciliarán los siete commits remotos pendientes con el commit local y los cambios no confirmados en `railway.toml`, `tests/test_backend.py` y `.codex/`.
- Se preservarán todos los cambios existentes del usuario.
- No habrá commits, pushes, deploys ni acciones destructivas sin autorización explícita.
- No se cambiarán secretos ni cuentas sin que el usuario complete directamente los pasos de autenticación.
- Las pruebas locales, `/health` y `/config` no cuentan como prueba de automatización end-to-end.

## 12. Resultado esperado

La tarea estará completa únicamente cuando la cuenta esté vinculada y asegurada, una publicación programada aparezca realmente en Instagram, un comentario de bajo riesgo reciba una respuesta real, un comentario sensible quede bloqueado para revisión y los resultados se registren sin falsos positivos.
