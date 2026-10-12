# Mapa de código

| Archivo o directorio | Qué conserva / dónde intervenir |
|---|---|
| `frontend/app/page.tsx` | Cinco menús, catálogo local, archivado/restauración, inventario, revisión, ajustes y logs |
| `frontend/components/CaptureStudio.tsx` | Cámara, fotografía, análisis, coincidencias, familia/variantes, tres imágenes y corrección |
| `frontend/components/InventoryTools.tsx` | Conteos, ajustes, movimientos e historial del Sheet |
| `frontend/next.config.ts` | Proxy API/OAuth y cabeceras; sin proxies de herramientas ecommerce |
| `frontend/lib/session-recovery.ts` | Recuperación de sesión, arranque y respuesta perdida |
| `service_entrypoint.py` | Ensambla FastAPI, catálogo, herramientas locales y middleware |
| `studio_api.py` | Sesión, ajustes Gemini, captura, generación, revisión y guardado; pipeline creativo preservado |
| `app.py`, `ai_app.py` | Runtime Google/Gemini y adaptador de captura; sin Gradio cargado |
| `product_capture.py`, `catalog_capture.py`, `product_generation.py` | Análisis, clasificación, coincidencias locales y gestión de familia |
| `creative_pipeline.py`, `gemini_gateway.py`, `image_generation_service.py` | Prompts, modelos, planificación, QA, coste y producción de imágenes; contrato congelado |
| `drive_service.py`, `sheets_service.py` | Acceso acotado a la carpeta y escritura existente en Google |
| `drive_image_index.py` | Resolución de imágenes por SKU y naming; lógica pura extraída del módulo ecommerce |
| `sheet_inventory.py` | Lectura del maestro y handlers de conteo/movimiento extraídos sin clientes externos |
| `native_tools.py` | JSON autenticado: inventory, history, counts, movement |
| `inventory_schema.py`, `inventory_operations.py`, `inventory_bulk.py` | Reglas de stock/padres, movimientos y conteos, conservadas |
| `catalog_taxonomy.py` | Marcas/categorías y clasificación Drive/Sheet |
| `catalog_platform/api.py` | Catálogo, import/export local, stock local, jobs, assets, conexiones Google/Gemini, archivar/restaurar |
| `catalog_platform/catalog.py` | Versiones, validación, serialización sin IDs externos y auditoría |
| `catalog_platform/models.py` | Esquema existente completo, incluidas columnas/tablas históricas; sin cambios |
| `catalog_platform/accounts.py`, `security.py` | Credenciales cifradas por usuario, clave Gemini vigente y roles |
| `catalog_platform/web_sessions.py`, `oauth_guard.py`, `app_security.py`, `rbac.py` | Sesión durable, OAuth/PKCE, límites, CSRF y permisos |
| `catalog_platform/capture_bridge.py` | Vincula captura, catálogo local y Sheet; no usa puente ecommerce |
| `catalog_platform/studio_jobs.py` | Convierte captura/guardado en jobs durables |
| `catalog_platform/worker.py`, `job_types.py` | Ejecuta únicamente operaciones conservadas; bloquea jobs retirados |
| `catalog_platform/queue.py`, `redis_broker.py`, `redis_worker.py`, `worker_web.py`, `worker_wakeup.py` | Lease/checkpoints, Redis/RQ, heartbeat y despertar el worker |
| `catalog_platform/imports.py` | Importación/exportación local y asociación de imágenes Drive |
| `catalog_platform/database.py`, `initialize.py`, `migrate.py`, `backup.py` | Acceso SQL y utilidades explícitas; esta entrega no ejecuta migraciones ni backups externos |
| `retired_service.py`, `Dockerfile.retired` | Retiro/redirect genérico, sin activar un servicio de sincronización |
| `deploy/render-platform.yaml` | Propuesta para los tres servicios existentes; autodeploy desactivado, no aplicada |
| `test_integration_removal.py` | Rutas retiradas, credenciales, jobs históricos bloqueados, stock local, naming y archive/restore |
| `test_generation_contract.py` | Comparación de funciones creativas con el commit aceptado; modelos/prompts protegidos |

Para recuperar los módulos retirados, consultar la rama de respaldo indicada en [ROLLBACK.md](../ROLLBACK.md). No mantener copias cargables de esos clientes en el runtime. [FUNCTION_INDEX.md](FUNCTION_INDEX.md) enumera las funciones actuales.
