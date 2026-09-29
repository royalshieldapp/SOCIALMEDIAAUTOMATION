# Continuación Meta — 13 de septiembre de 2026

Decisión: **BLOCKED**. Alcance exclusivo Facebook e Instagram. Sin publicaciones, respuestas, mensajes privados, cambios de credenciales, commits, pushes ni deployments durante esta continuación.

## Estado recuperado

El checkpoint más reciente es `docs/PENDIENTE-MANANA.md`, en el worktree `C:/Users/Anonymous/.codex/worktrees/social-approval/SOCIALMEDIAAUTOMATION`, rama `codex/social-approval`, base `28827fe`. El checkout `D:/APPS/SOCIALMEDIAAUTOMATION` está adelantado 1 y atrasado 8 frente a su referencia origin/main local; conserva sus modificaciones anteriores. No se hizo fetch ni merge.

Ya existían el cliente Graph directo, publicación separada Facebook/Instagram, aprobación editorial, SQLite, reclamo atómico, estados por plataforma, recuperación de enlaces mediante GET y bandeja de comentarios. El diseño aprobado exige pausa inicial y prohíbe reintentos automáticos ante resultados ambiguos. Make ya se había eliminado en esta base; el README del checkout principal es anterior.

Al retomar fallaban dos tests: estructura nula de webhook firmado y ausencia del limitador administrativo. Se reprodujeron ambos antes de corregir. También se reprodujo la pérdida de `error.type` en un nuevo test.

## Diagnóstico inicial antes de modificar implementación

| COMPONENTE | ESTADO | EVIDENCIA | ACCIÓN |
|---|---|---|---|
| Aplicación Meta | INCOMPLETO | Royalshieldsocial existe; Unpublished, revisión Not submitted | Resolver acceso de prueba |
| Versión Graph | COMPLETO | Código y ejemplo v25.0 | Contrastar deployment |
| Access token | BLOQUEADO | Sin credenciales locales; checkpoint de token Railway inválido | Debugger oficial |
| Tipo de token | BLOQUEADO | Anterior User, estado actual pendiente | Debugger oficial |
| Validez y expiración | BLOQUEADO | Evidencia anterior no basta | Validación actual |
| Permisos | BLOQUEADO | Solicitudes no equivalen a concesión | GET me/permissions |
| Facebook Page ID | BLOQUEADO | Destino actual no validado | Consultar ID configurado |
| Page Access Token | BLOQUEADO | Sin token de página validado | Revisar fallback |
| Instagram Business Account ID | BLOQUEADO | Objetivo histórico royalshieldsecure | Consultar cuenta y relación |
| Vinculación | BLOQUEADO | Sin relación demostrada mediante API | Validar desde página |
| Publicación Facebook | INCOMPLETO | Código existente, sin prueba externa | Tests y prueba condicionada |
| Container Instagram | INCOMPLETO | Código existente, sin prueba externa | Tests y prueba condicionada |
| Publicación container | INCOMPLETO | Código existente, sin prueba externa | Tests y prueba condicionada |
| Errores Meta | INCOMPLETO | Faltan tipo y trace | Conservar datos sanitizados |
| Webhooks | INCOMPLETO | Firma y deduplicación; estructura nula falla | Devolver 422 |
| Duplicados | INCOMPLETO | Reclamo SQLite; persistencia productiva pendiente | Tests y volumen |
| Variables deployment | BLOQUEADO | Presencia anterior no demuestra validez | Lectura actual |
| Servicio correcto | INCOMPLETO | Configuración apunta a Railway | Confirmar fuente y deployment |

## Evidencia actual de Meta

Se usaron exclusivamente consultas GET en Graph Explorer y Access Token Debugger de Meta. No se generó, extendió ni reemplazó ningún token. Las consultas de Explorer se ejecutaron en **v26.0**, que seleccionó la interfaz; el backend conserva su default **v25.0**. No confundir estos dos contextos.

- App actual: **Royalshieldsocial**, ID `1376291581275332`. UI: **Unpublished** y solicitudes de App Review **Not submitted**. Esto no demuestra concesión de permisos al token ni implica por sí solo imposibilidad de pruebas con roles autorizados.
- Token abierto actualmente en Explorer: **User**, **Valid True**, vence `2026-09-13T15:00:00Z` (11:00 America/New_York), acceso a datos hasta timestamp `1797081629`. Es corto, no el token largo registrado en el checkpoint.
- Scopes concedidos de ese token: `public_profile` y dos scopes de WhatsApp. Estos últimos solo se observaron al diagnosticar el token; WhatsApp no se implementó ni se operó.
- `GET me/permissions`: `pages_show_list`, `pages_read_engagement` e `instagram_basic` **declined**. `pages_manage_posts` e `instagram_content_publish` no aparecen concedidos. Los permisos que faltan deben limitarse a los necesarios para Facebook/Instagram.
- `GET me/accounts?fields=id,name,tasks,instagram_business_account`: **data vacía**. No prueba ausencia de páginas; el token no tiene los permisos necesarios.
- Valor actual de Railway `META_LONG_LIVED_ACCESS_TOKEN`: el Debugger devuelve **Malformed access token**. No se imprimió ni se cambió. No se puede atribuir tipo, expiración ni scopes válidos.
- No existen variables llamadas `FACEBOOK_PAGE_ACCESS_TOKEN` ni `INSTAGRAM_ACCESS_TOKEN` en el filtro del servicio. El código hace fallback a `META_LONG_LIVED_ACCESS_TOKEN`. Por eso `/config` devuelve true para ambas: significa disponibilidad de un valor, no validez.
- `FACEBOOK_PAGE_ID` configurado termina en **6229** y coincide con el portfolio documentado previamente. La consulta de ese ID con `fields=id,name,instagram_business_account` devuelve **OAuthException, code 100**, campo no existente; trace `ADQJvJ0WmeLphXFUuL0VMrA`. No está validado como Page ID. No se sustituyó por un ID histórico.
- `INSTAGRAM_BUSINESS_ACCOUNT_ID` configurado termina en **6469**, diferente al objetivo histórico que terminaba en **8411**. Consulta `fields=id,username,account_type`: **GraphMethodException, code 100, error_subcode 33**, trace `AFmU3ryCDg9Ncq1x4W35t6b`. No permite identificar la cuenta ni concluir si el motivo es inexistencia o permisos.
- Objetivos históricos: página **Royal Shield** terminada en **9460**, Instagram **@royalshieldsecure**. No confirmados hoy mediante la API; no habilitan publicación.

La relación Page → instagram_business_account sigue pendiente. Para Facebook Login, esta relación es requisito del flujo documentado por Meta: [Instagram API with Facebook Login, colección oficial Meta](https://www.postman.com/meta/instagram/folder/u4g5a2a/instagram-api-with-facebook-login).

## Servicio y configuración

Verificado en Railway UI: **Automation → production → SOCIALMEDIAAUTOMATION**. Servicio `62290bd7-e097-41ab-addb-f47569f966ba`, proyecto `58e437cf-e376-4391-8cd2-0db0c68566be`. Source Repo `royalshieldapp/SOCIALMEDIAAUTOMATION`; enlace de configuración apunta al commit `28827fe9f2b0560349b0e47ea4decb17d3635628`. Deployment activo `7a136db7-7994-433f-887b-2866c6404028`. No corresponde a los otros server-backend de Render/Railway.

- `GET https://socialmediaautomation-production.up.railway.app/health`: **200**.
- `GET /config`: **200**, versión **3.0.1**, scheduler **false**, host Instagram **graph.facebook.com**, DB **/tmp/socialmediaautomation.db**.
- Presencia reportada por config: `META_VERIFY_TOKEN`, `META_APP_SECRET`, `AUTOMATION_API_KEY`, `FACEBOOK_PAGE_ID`, `INSTAGRAM_BUSINESS_ACCOUNT_ID` y tokens por fallback. No demuestra que App Secret corresponda a la app ni firma de un evento real.
- `META_GRAPH_API_VERSION` no existe en el filtro de variables: el código usa default v25.0. Existe otro nombre `GRAPH_API_VERSION` en la lista; no lo consume este cliente.
- `GET /media/demo-privacy-en.jpg`: **404**. Existe imagen JPEG local, pero no una URL de prueba validada para Meta.
- Settings muestra advertencia: región **us-west2 inválida, bloquea deployments**. Se registra como advertencia de plataforma observada, sin alterar región.
- Dashboard mostró uso computacional **9.97/10 USD**, cerca del límite. No se modificaron límites ni plan.
- El flujo local 3.1.0 requiere DB dentro del volumen Railway real; el deployment actual usa `/tmp`, por lo que la durabilidad no está cerrada.

Nombres necesarios para el runtime: `META_VERIFY_TOKEN`, `META_APP_SECRET`, `META_GRAPH_API_VERSION`, `AUTOMATION_API_KEY`, `FACEBOOK_PAGE_ID`, `FACEBOOK_PAGE_ACCESS_TOKEN`, `INSTAGRAM_BUSINESS_ACCOUNT_ID`, `INSTAGRAM_GRAPH_HOST`, `INSTAGRAM_ACCESS_TOKEN` (opcional si se reutiliza Page token), `SCHEDULE_DB_PATH`, `RAILWAY_VOLUME_MOUNT_PATH` (lo proporciona Railway), `SCHEDULER_ENABLED`, `SCHEDULER_POLL_SECONDS`, `ENVIRONMENT`, `PORT`. Compatibilidad existente: `META_LONG_LIVED_ACCESS_TOKEN`. Flags existentes `FACEBOOK_AUTO_REPLY_ENABLED` e `INSTAGRAM_AUTO_REPLY_ENABLED` no autorizan respuestas automáticas en el flujo editorial local. No se añadieron variables ni secretos.

## Cambios de esta continuación

1. `SOCIALMEDIAAUTOMATION.py`: valida arrays de entrada/cambios del webhook después de verificar firma; devuelve 422 en vez de TypeError. Limitador administrativo de 120 solicitudes por 60 segundos, con presupuestos separados para autenticadas e inválidas, memoria acotada y Retry-After. Límite por proceso, no distribuido; se reinicia con el proceso. Errores Graph conservan message, type, code, error_subcode y fbtrace_id, redactando token y secretos configurados, sin escribirlos en logs.
2. `tests/test_editorial.py`: cobertura Facebook e Instagram de estructuras malformadas, recuperación del límite y aislamiento de credenciales inválidas; conservación de diagnósticos sin credenciales.
3. Este informe y actualización del encabezado del checkpoint para evitar repetir los fallos ya corregidos.

Se conserva la deduplicación existente: clave por plataforma, reclamo SQLite atómico, persistencia del ID y estado needs_review ante timeout o resultado ambiguo. No se creó otro backend ni se modificaron pantallas, automatizaciones o rutas de WhatsApp.

## Validación final

| CHECK | RESULT | EVIDENCE |
|---|---|---|
| Recuperación de trabajo y Git | PASS | Checkpoint más reciente localizado; cambios originales preservados |
| Tests relacionados Meta/Facebook/Instagram/editorial | PASS | `python -m pytest -q --tb=short`: 37 passed, 1 warning |
| Compilación mínima backend | PASS | `python -m py_compile SOCIALMEDIAAUTOMATION.py editorial.py scheduler_daemon.py`: exit 0 |
| Diff whitespace | PASS | `git diff --check`: exit 0; avisos LF/CRLF |
| Secretos en diff y archivos revisados | PASS | Búsqueda por patrones y revisión; cero coincidencias de credenciales reales detectadas |
| Servicio correcto | PASS | Source Repo y commit en UI; deployment activo; health/config 200 |
| Token Railway | FAIL | Debugger oficial: Malformed access token |
| Token Explorer para Facebook/Instagram | FAIL | User corto; permisos necesarios declined o no concedidos |
| Facebook Page ID | FAIL | ID configurado no validado como Page; Graph code 100 |
| Instagram y vinculación | BLOCKED | ID configurado: 100/33; me/accounts vacío; relación no confirmada |
| Webhook local | PASS | Firma, deduplicación y estructura cubiertas por tests |
| Webhook real y suscripciones app actual | BLOCKED | Sin evento firmado real ni suscripciones verificadas en esta continuación |
| Durabilidad productiva | FAIL | DB activa en /tmp; volumen requerido para flujo local |
| Publicación Facebook | BLOCKED | Token inválido, permisos y destino pendientes; cero escrituras Meta |
| Container y publicación Instagram | BLOCKED | Cuenta no validada; imagen pública 404; cero containers creados |
| Próximo deployment | BLOCKED | No autorizado; permisos/cuentas pendientes y warning de región |

Tests con dobles HTTP verifican el comportamiento local, no representan publicaciones reales. Advertencia única de tests: deprecación Starlette/httpx. No se instalaron dependencias.

## Prueba preparada, no enviada

Contenido exclusivamente de prueba, en inglés, una publicación por plataforma con clave única separada:

> Royal Shield integration test — checking our Facebook and Instagram publishing connection. This is test content. Reference: RS-META-20260913-01.

Destinos actualmente configurados: Facebook **…6229**, Instagram **…6469**; ambos no validados. Destinos esperados históricos: Royal Shield y @royalshieldsecure, pendientes de comprobación. No publicar en ninguno mientras no coincidan configuración y respuesta de Graph. Claves propuestas: `RS-META-20260913-01-facebook` y `RS-META-20260913-01-instagram`; no insertadas ni programadas. Antes de cualquier escritura debe comprobarse que no existen en la cola ni en Meta. No se aprobaron horario ni imagen pública.

Facebook: cero publicaciones, ningún ID generado. Instagram: cero containers, cero publicaciones, ningún ID generado. La imagen local `content/demo-privacy-en.jpg` no habilita publicación: la ruta pública comprobada responde 404. No inventar otra URL.

## Pasos manuales pendientes y orden de cierre

1. En Royalshieldsocial, revisar acceso del usuario a la página real Royal Shield y autorización de Facebook Login para esa página. Resolver scopes declined. Permisos mínimos a verificar: pages_show_list, pages_read_engagement, pages_manage_posts, instagram_basic e instagram_content_publish. Añadir permisos al panel no equivale a otorgarlos al token; no solicitar scopes de anuncios, mensajes ni WhatsApp para esta prueba.
2. Con consentimiento del usuario cuando Meta requiera ampliar permisos, validar token con Debugger; consultar me/permissions y me/accounts. Confirmar Page ID, derivar Page token válido y resolver instagram_business_account → id,username,account_type. No usar un ID histórico como sustitución automática.
3. Preparar corrección concreta de credenciales e IDs en Railway, pero no aplicarla sin autorización específica: el pedido prohíbe reemplazar secretos y desplegar. No renovar por costumbre el token largo anterior; su estado actual no se comprobó.
4. Verificar volumen durable, warning de región y suscripciones de la app actual. No cambiar META_VERIFY_TOKEN. Capturar un evento real firmado antes de declarar webhook productivo.
5. Tras validaciones y autorización del cambio productivo, comprobar URL pública de la imagen y presentar contenido/destinos correctos. Publicar una sola vez por plataforma; ante timeout, revisar Meta y no reenviar.

## Comandos locales reproducibles

```powershell
Set-Location 'C:\Users\Anonymous\.codex\worktrees\social-approval\SOCIALMEDIAAUTOMATION'
git status --short --branch
git diff --check
python -m pytest -q tests/test_editorial.py -k 'malformed_signed or administration_rate or admin_limit or graph_error' --tb=short
python -m pytest -q --tb=short
python -m py_compile SOCIALMEDIAAUTOMATION.py editorial.py scheduler_daemon.py
```

Para confirmar nombres sin imprimir valores locales:

```powershell
Get-ChildItem Env: | Where-Object Name -match '^(META|FACEBOOK|INSTAGRAM|AUTOMATION|SCHEDULE|SCHEDULER|RAILWAY)' | Select-Object Name
```

La validación oficial de credenciales se realizó en [Access Token Debugger](https://developers.facebook.com/tools/debug/accesstoken/). No incluir tokens en comandos, enlaces compartidos, logs o capturas. Las salidas de herramientas se sanitizaron antes de mostrarse; no se guardaron credenciales en archivos.

**BLOCKED**
