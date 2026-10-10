# Archivos que conviene conocer

**Lectura actual:** [guía de reparación del 10 de octubre](CODE_GUIDE.md) e
[índice de funciones y objetos](FUNCTION_INDEX.md). Este mapa inicial conserva
referencias históricas; la guía distingue el estado actual de sesiones, cola,
WooCommerce y controles del catálogo.

No hay carpetas nuevas `backend/routers` ficticias: este proyecto mantiene
módulos Python en raíz y agrupa el catálogo nuevo en `catalog_platform/`.

| Área / archivo | Responsabilidad |
| --- | --- |
| frontend/app/page.tsx | Platform: Inicio, catálogo, inventario, selección de generación, revisión, configuración y confirmaciones |
| frontend/components/CaptureStudio.tsx | captura de producto y flujo probado de fotos/análisis/IA/guardado |
| funciones api en page.tsx y CaptureStudio.tsx | cliente HTTP con cookies y errores |
| frontend/app/layout.tsx, globals.css | layout, estilos móvil/desktop |
| frontend/next.config.ts | export compatible o standalone; proxy API y headers |
| frontend/public/manifest.webmanifest, sw.js, icons/ | PWA y cache de carcasa pública |
| service_entrypoint.py | elige API main/sync, registra routers, health y middleware |
| studio_api.py | endpoints de captura; make_image/creative_plan protegidos; orquestación compatible |
| app.py, ai_app.py | runtime histórico: OAuth, sesiones, descubrimiento Drive/Sheets y funciones existentes |
| creative_pipeline.py | prompts, planificación creativa, referencias y generación Gemini protegida |
| gemini_gateway.py | cliente IA, límites y medición/estimación existente |
| image_generation_service.py | ImageProvider y adaptador al pipeline aceptado; otros proveedores inactivos |
| product_generation.py | marca oficial y limpieza de descripciones |
| product_capture.py, catalog_capture.py | captura, duplicados, variantes, portada y guardado histórico en Sheet |
| drive_service.py | ownership, búsqueda, metadata, streaming, uploads y backup previo a guardado aprobado |
| sheets_service.py | lectura por rango/SKU y escritura precisa; compatibilidad SDK |
| app_security.py, oauth_guard.py | límites, origen/Host, errores redactados, OAuth state y allowlist |
| google_credentials.py | service account opcional por entorno, sin cambiar credenciales automáticamente |
| catalog_platform/api.py | endpoints del catálogo, jobs, review, publicación, import/export, stock, conexión e historial |
| catalog_platform/models.py, database.py, migrate.py | entidades SQL, transacciones y esquema aditivo |
| catalog_platform/catalog.py | producto por tenant, auditoría, movimientos y serialización |
| catalog_platform/security.py, rbac.py, accounts.py | roles, cifrado y conexiones durables para worker |
| catalog_platform/queue.py | idempotencia, claim, lease, checkpoint y resultado incierto |
| catalog_platform/redis_broker.py | entrega RQ JSON después del commit; reconciliación desde SQL |
| catalog_platform/redis_worker.py, rq_settings.py | supervisor del pool RQ, concurrencia, heartbeat y conexión privada |
| catalog_platform/worker_web.py, worker_wakeup.py | health mínimo para web free; wake HTTP por trabajo real después de commit |
| catalog_platform/initialize.py | opt-in de esquema en base nueva vacía; rechaza DDL automático sobre esquemas existentes incompletos |
| catalog_platform/render_config.py | deriva el callback staging del origen público frontend; conserva un callback explícito |
| catalog_platform/worker.py | ejecuta un ID; generación, publicación, guardado aprobado y limpieza temporal |
| catalog_platform/studio_jobs.py | adaptador durable para captura, corrección, recuperación y aprobación |
| catalog_platform/imports.py | importar explícitamente con respaldo y asociar históricos por naming |
| catalog_platform/ecommerce.py, inventory.py, enrichment.py | snapshots ecommerce, sincronización stock y enriquecimiento en jobs |
| catalog_platform/webhooks.py | firma WooCommerce, registro/dedupe y procesamiento; Loyverse inactivo |
| catalog_platform/backup.py | pg_dump privado; debe exportarse antes de perder /tmp |
| ecommerce_services.py | WooCommerceService y WordPressMediaService sobre clientes existentes |
| woocommerce_client.py, wordpress_media.py | transporte HTTP, autenticación, límites y errores de ecommerce |
| sync_bridge_protocol.py, sync_gateway.py, sync_service.py | compatibilidad con servicio histórico de sincronización |
| pos_provider.py, loyverse_client.py, loyverse_sync.py, loyverse_jobs.py | contrato POS y módulos históricos; no activados como autoridad nueva |
| Dockerfile.frontend, Dockerfile.api, Dockerfile.worker | imágenes independientes de los tres procesos |
| deploy/render-platform.yaml | propuesta aditiva con tres servicios, PostgreSQL y Key Value |
| .env.example | nombres y valores de ejemplo sin secretos |
| .github/workflows/validate-drive-client.yml | builds, seguridad de dependencias, pruebas Redis/PostgreSQL y contrato IA |

Para proteger generación, empieza por `test_generation_contract.py`,
`test_creative_pipeline.py`, `test_studio_api.py`, `test_catalog_platform.py`
y `test_stabilization.py`. Las pruebas históricas permanecen: no se borran para
hacer pasar una migración. Los índices y documentos operativos están enlazados
en README y [TEST_PLAN](../TEST_PLAN.md).
