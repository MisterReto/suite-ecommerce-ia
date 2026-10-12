# Auditoría de retirada de integraciones

Fecha: 2026-10-12. Alcance: código de los tres servicios actuales, sin modificar los dos servicios históricos ni datos externos.

## Base real y respaldos

La lectura de servicios y deploys de Render, workspace ProyectoInventario, confirmó:

| Servicio | Rama desplegada | Commit live |
|---|---|---|
| rincon-frontend | feature/woocommerce-and-product-removal-20261009 | b4aa4051cd2d1b897cc7a582e67ee8b938cfcc2b |
| rincon-catalog-api | feature/woocommerce-and-product-removal-20261009 | b4aa4051cd2d1b897cc7a582e67ee8b938cfcc2b |
| rincon-catalog-worker | feature/woocommerce-and-product-removal-20261009 | b4aa4051cd2d1b897cc7a582e67ee8b938cfcc2b |
| suite-ecommerce-ia, histórico | agent/woocommerce-inventory-foundation | 1a1c3bc9c9e56422c290fb59247a6dff2602d315 |
| suite-ecommerce-ia-ai, histórico | agent/woocommerce-inventory-foundation | 1a1c3bc9c9e56422c290fb59247a6dff2602d315 |

Respaldos creados en GitHub: backup/pre-integration-cleanup-20261012 y backup/historical-before-cleanup-20261012, respectivamente. La limpieza se desarrolla en cleanup/remove-store-integrations-20261012. El árbol remoto final se construye sobre el árbol del commit desplegado, con ese commit como padre; el snapshot de trabajo local no se publica como historial alternativo.

## Dependencias retiradas

| Módulos | Consumidores anteriores | Retirada |
|---|---|---|
| woocommerce_client, ecommerce_services, catalog_platform/ecommerce | api, worker, sincronizadores, conexión | Cliente REST, imports, dispatch, publicación, pedidos, refresh/import y métricas externos |
| woocommerce_inventory, woocommerce_stock, catalog_platform/inventory | stock, comparaciones, webhook | Operaciones remotas y autoridad externa; stock local conservado |
| woocommerce_product_sync, batch_sync, catalog_light, publish_preview | batch_web, publication_web, product_web | Publicación/sincronización/importación ecommerce y herramientas antiguas |
| wordpress_media, woocommerce_image_sync, woocommerce_media_prepare, media_web | imágenes/publicación/import local | Publicación externa eliminada; naming/resolución Drive extraídos a drive_image_index |
| loyverse_client, loyverse_sync, loyverse_jobs, loyverse_web, pos_provider | studio_api, frontend, inventario histórico | APIs, jobs, OAuth/config, herramientas y estados activos retirados |
| catalog_platform/webhooks | service_entrypoint / worker | Receptores y handlers Woo/Loyverse retirados; SQL histórico conservado |
| store_connection | arranque, status, clientes | Sin conexión automática ni estado de tienda |
| sync_bridge_protocol, sync_gateway, sync_service, sync_lite_app | native_tools / herramientas históricas | Puente firmado y endpoints eliminados |
| inventory_web / inventory_hub | native_tools / HTML histórico | Extracción de lectura/conteos/movimientos a sheet_inventory; HTML/comparaciones retirados |
| product_web_ai | captura/tests y UI histórica | Consumidores conservados usan ai_app; interfaz heredada retirada |
| frontend controles/componentes exclusivos | Productos, Más, Captura, dashboard | Sin Woo/Loyverse, ventas/pedidos externos, webhooks, IDs visibles ni publicación |
| requirements-sync.txt / gradio_security | servicio sync antiguo | Eliminados de esta rama; dependencias comunes siguen en requirements.txt |

La lista exacta de cambios se obtiene con `git diff --name-status b4aa4051..HEAD` y está en [CHANGESET.md](CHANGESET.md).

## Lógica compartida protegida

- Resolución de imágenes Drive: extracción de funciones puras, mismo naming y fallback, sin cliente HTTP ecommerce.
- Inventario Sheet: lectura de Lista completa, conteos, movimientos e historial conservados; no sobrescritura completa.
- Captura/coincidencias: catálogo local y Sheet permanecen; se retiran únicamente las consultas de tiendas.
- Logs: eventos locales ahora leen AuditLog, sin estados/controles de sincronización. SyncEvent histórico permanece en SQL. Inicio cuenta solo jobs conservados.
- Worker: generación, planificación, correcciones, import local y asset_save permanecen. Las credenciales históricas no se cargan para jobs retirados.
- PostgreSQL: models.py sin cambios, columnas/OrderSnapshot/WebhookEvent/SyncEvent y credenciales históricas conservados. No se ejecuta migrate ni ALTER/DROP.
- Archivar/restaurar: no existía en la base desplegada. Se añade con estado existente, auditoría, control de versión y tratamiento de familia; no modifica archivos o stock. Los jobs activos bloquean el cambio.
- Prompts/modelos: módulos creativos y funciones protegidas sin cambios; contrato automatizado verde.

## Puente histórico

El puente hacia suite-ecommerce-ia-ai solo servía las herramientas ecommerce retiradas. inventory/history/counts/movement ahora llaman a sheet_inventory directamente en la API autenticada. RQ, Redis, la base SQL y IMAGE_WORKER_ORIGIN son la comunicación del Image Worker; **no usan SYNC_SERVICE_URL ni SYNC_SERVICE_SHARED_KEY**.

Por tanto, las variables del puente son eliminables del entorno de los tres servicios **después** de desplegar y verificar esta rama. No se confirma que puedan eliminarse de los históricos: su commit conserva ese código, y sus variables actuales no pudieron enumerarse con el conector. Permanecen intactas.

## Entorno: evidencia y límites

Se auditó cada lector de variables del código y cada entrada del Blueprint, incluidos nombres/aliases de módulos retirados. La captura de configuración aportada confirma nueve nombres de variables, pero no sustituye el inventario de los cinco servicios. El conector Render permite leer servicios/deploys y modificar variables, pero no enumerar el entorno; no se usó la operación de escritura para intentar inferirlo.

No se quitaron variables reales, no se movieron credenciales, no se alteró ningún servicio histórico y no se desplegó esta rama. La ubicación real y presencia de los nueve secretos WC/WP solicitados requiere revisión privada de los nombres/orígenes en Render. El Blueprint original apunta a suite-ecommerce-ia; no prueba que todos los alias estén configurados.

## Secreto del puente expuesto

SYNC_SERVICE_SHARED_KEY aparece expuesto en la captura aportada y en una salida de auditoría anterior. Su valor no se copia a archivos, Git, documentación o pruebas. Su vigencia no se comprobó ni se utilizó.

Plan: comprobar por nombre qué consumidores históricos siguen activos; preparar una nueva clave en almacenamiento seguro; coordinar el cambio de ambos extremos históricos y una comprobación de firma sin datos externos; retirar la clave antigua de los procesos actuales cuando el puente quede eliminado. Si los históricos ya no necesitan puente, retirarlo solo mediante un cambio independiente autorizado. No rotar CREDENTIAL_ENCRYPTION_KEY ni las credenciales WC/WP por este incidente.

## Aceptación y reversión

Pruebas automatizadas con red externa bloqueada; no consumo real Gemini. La matriz de aceptación y pendientes está en [REGRESSION_RESULTS.md](REGRESSION_RESULTS.md). El despliegue y el archivado físico de credenciales siguen pendientes. Rollback exacto en [ROLLBACK.md](../ROLLBACK.md).
