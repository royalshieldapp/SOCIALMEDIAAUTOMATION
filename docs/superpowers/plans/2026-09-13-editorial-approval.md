# Flujo editorial con aprobación

Objetivo aprobado por el usuario: borrador → aprobación → programación persistente → Meta → resultados por plataforma; comentarios para revisión, nunca respuesta automática.

Base: origin/main 28827fe, FastAPI + SQLite + Graph API directa, sin Make. Worktree separado para conservar ambos árboles sucios existentes.

## Diseño y decisiones

Reutilizar los adaptadores Graph y añadir un módulo editorial, tablas nuevas sin borrar la cola antigua y una interfaz /studio. SQLite requiere un volumen Railway y una réplica. No añadir PostgreSQL ni Make: requerirían infraestructura adicional no necesaria para este servicio.

Cada plataforma tiene un registro independiente y una clave de idempotencia. El borrador guarda contenido, medio, destino y zona horaria. Aprobar solo permite programar esa versión. Los registros son inmutables tras aprobar: un cambio requiere un nuevo borrador. El trabajador reclama una fila atómicamente; los resultados ambiguos nunca se reintentan automáticamente. La pausa persistente empieza activada. La cola anterior no se ejecuta sin aprobación.

## Pasos

- [ ] Pruebas de aprobación, persistencia, pausa, concurrencia, resultados incompletos, errores y bandeja de comentarios.
- [ ] Implementar almacén editorial y rutas autenticadas; bloquear rutas antiguas que omiten aprobación.
- [ ] Integrar despacho existente y guardar IDs antes de consultar enlaces.
- [ ] Interfaz de revisión y programación, clave solo en memoria del navegador.
- [ ] Pruebas completas, compilación, revisión del diff y guía operativa.
- [ ] Preparar demostración sin publicar. Evidencia real requiere permisos Meta, aprobación del contenido y autorización para desplegar.

## Evidencia inicial

Railway deployment 7a136db7-7994-433f-887b-2866c6404028 activo, versión 3.0.1. Configuración: secretos presentes, scheduler false, DB /tmp/socialmediaautomation.db. Token extendido de Royalshieldsocial válido hasta 2026-11-11, tipo User; scopes pages_show_list, ads_management, pages_read_engagement, public_profile. GET me/accounts devolvió data vacía: vinculación y publicación bloqueadas. No se guardan secretos.
