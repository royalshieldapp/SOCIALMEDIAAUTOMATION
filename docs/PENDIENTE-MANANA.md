# Pausa solicitada por el usuario — 2026-09-13

## Continuación P0 — 2026-09-23 America/New_York

**Estado: BLOQUEADA para activación externa; implementación corregida y verificada
localmente. No confundir con automatización activada.** Esta sección prevalece
sobre los estados históricos conservados debajo.

### Trabajo recuperado y preservado

- `D:/APPS/SOCIALMEDIAAUTOMATION`: `main` en `c9e9271`, cambios anteriores de
  código/configuración/pruebas conservados. Sin cambiar de rama ni copiar árboles.
- Esta continuación usa rutas explícitas del worktree `social-approval`, rama
  `codex/social-approval`, base `28827fe`. El flujo editorial ya existía aquí.
- Se leyeron las notas originales de Antigravity en
  `C:/Users/Anonymous/.gemini/antigravity-ide/brain/ed688f29-72a5-4a03-9548-35ae393f1b6e/pending_notes.md`
  y `meta_linking_resolution.md`, junto con `D:/APPS/SOCIALMEDIAAUTOMATION/PENDING_NOTES.md`.
  Las notas del 21 de septiembre afirman token System User y destinos configurados;
  el comentario real no recibió respuesta. No aportan ID de publicación ni prueba
  Graph de vinculación. Compartir portfolio y configurar IDs no valida la relación
  exigida por Facebook Login. Referencia de Meta:
  https://www.postman.com/meta/instagram/folder/u4g5a2a/instagram-api-with-facebook-login
- Las dos pruebas antiguamente fallidas ya estaban corregidas: 26 pruebas
  editoriales pasaron antes de los cambios. No se repitieron esas correcciones.

### Cambios de esta continuación

- `editorial.py`: trabajos con más de 15 minutos de retraso pasan a `needs_review`;
  contenedor Instagram persistido mediante migración aditiva; registro durable de
  ciclos y resumen de cola para supervisión. Sin borrar cola anterior ni contenido.
- `SOCIALMEDIAAUTOMATION.py`: worker existente gestionado por lifespan, comprobación
  de worker en `/health`, `GET /scheduler/status` autenticado, ciclos registrados,
  errores de ciclo sanitizados, API version visible, zona por defecto
  `America/New_York`, espera de preparación de imágenes y vídeos de Instagram y
  guardado del contenedor antes de publicar. Resultado ambiguo conserva revisión.
- `scheduler_daemon.py`: espera el ciclo completo sin timeout de lectura que
  pudiera solapar ejecuciones; no usa proxies ambientales para localhost;
  registra fallos HTTP sin cuerpos ni claves.
- `Dockerfile` y `railway.toml`: solo Uvicorn como proceso principal; lifespan
  arranca el compañero. Revisar cualquier override del comando en Railway.
- `tests/test_editorial.py`, `tests/test_backend.py`, `tests/test_runtime.py`:
  regresiones de vencidos, zona, contenedores, límites/token, migración, supervisión
  y reinicio real local. Tests de proveedor utilizan dobles explícitos.
- `RAILWAY_SETUP.md`: procedimiento vigente de cola, activación, pausa, recuperación
  y rollback; retiradas instrucciones obsoletas de publicación sin aprobación.

### Evidencia ejecutada

- `.venv/Scripts/python.exe -m pytest -q`: **49 passed**, usando las versiones
  exactas de `requirements.txt`, sin actualizar ese archivo. Entorno de pruebas
  aislado; pytest/tzdata adicionales para Windows. `pip check`: sin incompatibilidades.
- `.venv/Scripts/python.exe -m compileall -q SOCIALMEDIAAUTOMATION.py editorial.py scheduler_daemon.py tests`: PASS.
- `git diff --check`: PASS (avisos de conversión LF/CRLF, sin errores de whitespace).
- Siete regresiones nuevas fallaron antes del parche y pasaron después. Cobertura
  adicional de migración preservando aprobaciones y errores Meta 4/190 sin reintento.
- `test_runtime.py` inicia Uvicorn real dos veces con SQLite temporal de prueba,
  sin tokens Meta: ciclos HTTP reales del worker, pausa persistente, programación
  aprobada conservada y trabajo interrumpido recuperado como `needs_review` con
  contenedor. Esto prueba reinicio **local**, no volumen/deployment Railway.
- Consultas públicas HTTPS reales a
  `https://socialmediaautomation-production.up.railway.app`, 23/09 alrededor de
  20:44 America/New_York: `/health` 200, `/config` 200, versión **3.0.1**, entorno
  PRODUCTION, scheduler **false**, DB `social_scheduler.db`, Graph host
  `graph.facebook.com`. Secretos declarados presentes: no demuestra validez.
  `/studio` **404**, `/media/demo-privacy-en.jpg` **404**. El flujo editorial local
  no está disponible en ese despliegue. SHA desplegado y versión Graph no comprobados.
- Python/httpx local rechazó inicialmente el certificado por cadena local; las
  consultas públicas se hicieron con la confianza del sistema mediante PowerShell.
  La instalación aislada usó `pip --use-feature=truststore`; nunca se deshabilitó TLS.
- Publicaciones reales Facebook: **ninguna**. Instagram: **ninguna**.
  Comentarios/respuestas reales: **ninguno enviado**. Scheduler producción:
  **no activado**. Persistencia Railway tras reinicio: **no verificada**.

### Bloqueo exacto y siguiente paso

Railway pide login y la sesión GitHub del navegador conectado tampoco está activa.
No hay CLI Railway disponible ni credenciales de servicio en el entorno local.
Se dejó una pestaña para que el usuario inicie sesión y se solicitó el acceso
mientras continuaban las pruebas. No pedir ni guardar contraseñas/tokens en el chat.

Tras el login: identificar servicio/entorno/SHA y comando reales, volumen y DB;
leer cola completa antes de activarla; validar con GET los tokens, permisos, Page,
Instagram y vinculación requerida con la versión Graph configurada. Los bloqueos
de token del 13/09 son históricos, no se declaran vigentes sin consulta nueva.
No reemplazar credenciales, cambiar destinos o crear almacenamiento de pago.

Desplegar este trabajo únicamente por el procedimiento del servicio existente,
con scheduler deshabilitado y pausa editorial, tras reconciliar los cambios de
ambos árboles sin sobrescribirlos. Sin commit, push, deploy o cambio remoto en
esta continuación. No existe una prueba real aprobada documentada con horario en
las notas recuperadas: inspeccionar la cola autenticada y, si no hay una, solicitar
contenido/destinos/horario concretos antes de publicar. La imagen demo sigue siendo
un recurso local no autorizado por sí mismo para publicación.

### Pausa / rollback

`POST /editorial/control` con `{"paused":true}` bloquea reclamos nuevos;
una llamada a Meta ya en vuelo puede terminar y debe reconciliarse. Para detener
ciclos tras redeploy: `SCHEDULER_ENABLED=false`. Conservar/respaldar el volumen.
Nunca reintentar `needs_review` por timeout sin verificar Meta. Recuperar enlaces
con `/editorial/posts/{id}/refresh-link` solo para IDs publicados conocidos.
No volver a una imagen anterior a la aprobación editorial con scheduler o
auto-replies activos; sus rutas antiguas omiten aprobación. Ver guía Railway.

## Continuación del 13 de septiembre

El usuario reanudó el trabajo de Facebook/Instagram. Las dos pruebas fallidas descritas abajo ya se corrigieron; validación actual: 37 passed, compilación y diff check correctos. El historial de pausa se conserva sin reescribir. Leer el estado actualizado y bloqueos verificados en [META-VALIDACION-2026-09-13.md](META-VALIDACION-2026-09-13.md): token Railway malformado, token Explorer sin permisos necesarios, IDs configurados no validados, imagen pública 404 y persistencia /tmp. Sin publicaciones ni deployment.

El usuario pidió dejar pendiente para mañana. No reanudar acciones externas automáticamente.

## Dónde continuar

- Proyecto original: D:/APPS/SOCIALMEDIAAUTOMATION, main atrasado y con cambios anteriores; no se modificó su código.
- Trabajo nuevo: C:/Users/Anonymous/.codex/worktrees/social-approval/SOCIALMEDIAAUTOMATION, rama codex/social-approval, base origin/main 28827fe.
- Sin commits, pushes, deploys adicionales, publicaciones ni respuestas reales.
- Los posts y su imagen deben estar en INGLÉS. Interfaz y explicaciones en español.

## Avance local

Se añadieron editorial.py, studio.html, tests/test_editorial.py y content/demo-privacy-en.jpg. Integración del flujo borrador/aprobación/programación/pausa, reclamo SQLite atómico, estados por plataforma, captura de IDs, recuperación GET de enlaces, revisión de resultados ambiguos y bandeja de comentarios sin respuestas automáticas. Rutas antiguas de publicación/respuesta bloqueadas para evitar saltarse aprobación. Docker incluye los archivos nuevos. Producción requiere volumen Railway; la cola antigua se conserva pero no se ejecuta automáticamente.

Studio verificado por navegador local en puerto 8766: login con credencial ficticia de prueba, creación y visualización de borrador real en inglés, automatización pausada. Sin tokens Meta en el servidor local y scheduler desactivado. Eso NO prueba producción.

## Validación exacta al pausar

- Última suite completa: 31 passed, 1 warning de deprecación de Starlette/httpx.
- Después se añadió una prueba de credenciales fuera de URLs Graph; falló, se corrigió el envío con Authorization y pasó individualmente.
- Últimas DOS pruebas añadidas siguen FALLANDO y todavía NO se implementaron sus correcciones:
  - test_malformed_signed_webhook_returns_validation_error: entry o changes null produce TypeError; validar estructura tras verificar firma y devolver 422.
  - test_administration_rate_limit_bounds_repeated_requests: falta admin_requests y limitador de rutas administrativas. Implementar límite acotado y verificable o ajustar diseño y prueba de forma justificada.
- No declarar suite completa en verde al reanudar. Ejecutar primero esas pruebas, corregir, luego suite completa y compilación.
- Compilación Python y git diff --check pasaron antes de las últimas pruebas.
- node --check sobre JS de studio.html pasó.
- black no está instalado; no se ejecutó formateo.

## Bloqueos reales externos

- Railway: deployment 7a136db7-7994-433f-887b-2866c6404028 activo, versión 3.0.1, programador false, SCHEDULE_DB_PATH=/tmp/socialmediaautomation.db. Config muestra secretos presentes, no demuestra validez.
- Token largo generado en Meta: válido hasta 2026-11-11; User, app Royalshieldsocial 1376291581275332. Scopes reales: pages_show_list, ads_management, pages_read_engagement, public_profile. Faltan los permisos de publicación e Instagram.
- El valor mostrado privadamente en Railway META_LONG_LIVED_ACCESS_TOKEN difiere del token largo. Se verificó el valor visible en Access Token Debugger: Meta respondió Malformed access token. No se modificó la variable. No almacenar ni imprimir su valor.
- GET me/accounts?fields=id,name,tasks,instagram_business_account devolvió data vacía.
- GET 620119344509460?fields=id,name,instagram_business_account devolvió página Royal Shield pero sin instagram_business_account. Vinculación con @royalshieldsecure todavía NO verificada; no deducir desconexión definitiva mientras falten permisos.
- Consultas del Graph Explorer usaron el token largo válido, no el valor inválido de Railway.
- Se pidió al usuario comprobar control total y acceso de Royalshieldsocial a la página; respuesta aún pendiente.
- Suscripciones de la app actual, evento firmado real y publicación en ambas plataformas siguen NO verificados.

## Próximos pasos ordenados

1. Corregir las dos pruebas pendientes, revisar el diff y ejecutar suite/compilación.
2. Añadir guía final de aprobación/programación/pausa/recuperación y comprobar empaquetado, límites, persistencia y visualización.
3. Completar permisos y vinculación de Meta con participación del usuario cuando se requiera consentimiento. Corregir variable de Railway solo con autorización para el cambio concreto y deploy adicional.
4. Preparar autorización agrupada de commit/push/deploy y volumen real; no inferirla del pedido inicial.
5. Presentar publicación e imagen en inglés, cuentas exactas y horario futuro explícito America/New_York. Aún NO hay horario aprobado. El asset JPEG está local; el endpoint /media/demo-privacy-en.jpg NO está desplegado.
6. Tras aprobación específica, prueba real de publicación en Facebook e Instagram con enlaces verificados, después comentario real recibido y respuesta sugerida sin enviarla.

## Texto borrador inglés

Your privacy starts with your permissions.

Take a moment to review which apps can access your location, camera and microphone. Keep only the permissions you need, and revisit them when your habits change.

Save this reminder for your next privacy check.

#RoyalShield #DigitalPrivacy #OnlineSafety

Imagen: content/demo-privacy-en.jpg. Arte original generado en inglés, convertido a JPEG sin alterar su contenido visual; no publicado.
