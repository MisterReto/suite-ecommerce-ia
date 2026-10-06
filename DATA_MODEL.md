# Modelo de datos

Las definiciones reales están en `catalog_platform/models.py`. SQL guarda metadata; los binarios de fotos permanecen en Drive.

| Entidad | Tabla | Relación y regla |
| --- | --- | --- |
| Producto | `rincon_products` | ID interno estable; SKU único por tenant; versionado. |
| Variante | `rincon_product_variants` | Padre y producto hijo; atributos de la variante. |
| Imagen | `rincon_product_images` | Producto, ID Drive, rol, estado, checksum y dimensiones. |
| Trabajo | `rincon_generation_jobs` | Producto opcional, tipo, request_key, payload, progreso y lease. |
| Resultado generado | `rincon_generated_assets` | Job, producto, imagen, raw, slot, muestra e historial. |
| Cuenta de integración | `rincon_integration_accounts` | Credenciales cifradas por tenant/proveedor/actor. |
| Identidad externa | `rincon_integration_mappings` | Relaciona IDs de WooCommerce/WordPress/POS con producto interno. |
| Movimiento | `rincon_inventory_movements` | Cantidad antes/después, delta, origen e ID de evento. |
| Evento de sincronización | `rincon_sync_events` | Destino, operación, estado y mensaje. |
| Webhook recibido | `rincon_webhook_events` | Firma validada, ID/hash deduplicados y payload cifrado. |
| Auditoría | `rincon_audit_logs` | Actor, acción, producto, antes/después y resultado. |
| Heartbeat | `rincon_worker_heartbeats` | Indica si hay un worker reciente. |
| Pedido consultado | `rincon_order_snapshots` | ID WooCommerce, estado, total, moneda y fecha. |

## Identificadores

SKU identifica comercialmente el producto; el ID SQL identifica la fila interna; el ID Drive identifica el archivo; los IDs externos identifican ficha, variación o medio en la tienda. No son intercambiables. Las sincronizaciones reutilizan mappings permanentes; no deben volver a buscar por SKU para elegir otro destino.

`tenant_id` delimita la carpeta/catálogo autorizado. Las consultas de productos, imágenes y jobs deben incluirlo. `request_key` evita duplicar una confirmación HTTP; no garantiza exactamente una llamada entre todos los proveedores.

## Inventario

Los padres FULL no tienen precio ni stock propios. El stock se actualiza con versión e ID de evento; un cambio externo inesperado detiene la sincronización. `STOCK_AUTHORITY=loyverse` bloquea modificaciones de stock físico desde el catálogo.

## Inicializar y respaldar

`python -m catalog_platform.migrate` crea el esquema inicial de forma aditiva. El servidor web no hace migraciones al arrancar. Esta herramienta no sustituye migraciones versionadas para cambios futuros. Antes de cambiar un esquema con datos, generar y comprobar un dump. Ver [ROLLBACK.md](ROLLBACK.md).
