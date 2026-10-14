# Modelo de datos real y transición

Fuente: `catalog_platform/models.py`. Tablas con prefijo `rincon_`; PostgreSQL
operativo, SQLite exclusivamente como doble de pruebas (`APP_ENV=test`).
`tenant_id` es la carpeta raíz de trabajo; todas las consultas de catálogo se
acotan a ella. `id` es UUID interno, no SKU ni ID WooCommerce.

| Entidad / tabla | Función y relaciones |
| --- | --- |
| Product / rincon_products | producto maestro; SKU único por tenant, barcode, nombre, marca, categorías, descripciones, tags, atributos, tipo, precio/costo/stock/status |
| ProductVariant / rincon_product_variants | padre y child_product_id; atributos de la variante |
| ProductImage / rincon_product_images | product_id, Drive ID, URL, checksum SHA256, dimensiones, MIME, rol y estado; sin bytes |
| Category / rincon_categories | nombre único por tenant |
| Brand / rincon_brands | nombre único por tenant |
| InventoryMovement / rincon_inventory_movements | producto/variante/tienda, source/event_id, antes/después/delta y metadata |
| GenerationBatch / rincon_generation_batches | solicitud agrupada, actor, request_key, número de productos/imágenes, estimado USD |
| GenerationJob / rincon_generation_jobs | tipo, producto opcional, lote opcional, actor, request_key, estado, modelo/costo, payload, progreso, lease y fechas |
| GeneratedAsset / rincon_generated_assets | resultado candidato: job/product/image, raw Drive ID, slot/sample, modelo, estado, feedback y metadata |
| IntegrationAccount / rincon_integration_accounts | conexión por tenant/provider/actor, cifrada con Fernet |
| IntegrationMapping / rincon_integration_mappings | UUID interno ↔ ID permanente externo/provider/tipo/padre |
| SyncEvent / rincon_sync_events | origen/destino, acción, estado, mensaje y job asociado |
| WebhookEvent / rincon_webhook_events | provider, event_id, tipo, hash, recibido/procesado, estado, payload cifrado |
| AuditLog / rincon_audit_logs | actor, acción, producto opcional, system, before/after, result, created_at |
| WorkerHeartbeat / rincon_worker_heartbeats | proceso, último heartbeat, versión |
| OrderSnapshot / rincon_order_snapshots | última lectura de pedido, ID WooCommerce, estado, total, moneda y fecha |

## Producto maestro e IDs

El campo solicitado `internal_product_id` corresponde a `Product.id`; no se
añade una segunda identidad redundante. Las relaciones usan ese UUID. Hay
`woocommerce_product_id`, `woocommerce_variation_id`, `wordpress_media_ids`,
`loyverse_item_id`, `loyverse_variant_id`, `loyverse_store_id`, fechas de sync y
`sync_status`. `version` implementa edición optimista: guardar con una versión
antigua provoca conflicto, no reemplaza silenciosamente una ficha actualizada.

`price`, `cost` y `stock` usan Float por compatibilidad con el modelo existente;
no constituyen un libro contable. Una futura precisión Decimal necesita migración
separada. Stock desconocido es nullable, diferente de cero. Hoy
`STOCK_AUTHORITY=app`; no cambiar a Loyverse antes de validar integración.

## Jobs y assets

Batch → un job por producto → varios assets por slot/sample. Los slots reales
son `1_hd`, `2_uso`, `3_comercial`. La unicidad `(job_id,slot,sample)` y
`completed_keys` impiden duplicar resultados confirmados. Redis contiene solo
el ID SQL. SQL conserva snapshot, IDs Drive, checkpoint e incertidumbre.

La captura compatible puede carecer aún de Product SQL: su job
`studio_generation` usa `product_id=null` y relaciona SKU + revisión en payload.
No se crea automáticamente un producto SQL para alterar el guardado probado
del Sheet. Aprobación y guardado de captura también se registran en ese payload.
Los assets del catálogo sí tienen claves foráneas a Product y ProductImage.

El worker registra contadores de llamadas/tokens por job en payload.usage y los
agrega en SQL para conservarlos al terminar sus procesos hijos. La API no carga
todos los payloads en RAM. estimated_cost es aproximado; actual_cost permanece
desconocido hasta conciliación con el proveedor. Los contadores no sustituyen
factura ni cubren una llamada incierta sin registro de uso confirmado.

Los estados del job incluyen queued/processing/completed/failed y revisión
approved/rejected/published. Un Batch no necesita otro estado independiente:
`GET /api/platform/generation/batches` agrega los estados de sus jobs. Reintentar
un producto fallido no vuelve a generar otros productos del lote.

## Integridad e inventario

Movimiento único por `(tenant_id,source,source_event_id,product_id)`. Guardar un
stock registra el valor anterior, nuevo y delta. Se reconcilian snapshots de
WooCommerce; el webhook de pedido no descuenta por su cuenta otra vez. La
entrada remota se relaciona por ID permanente y SKU verificado.

`WebhookEvent` es único por provider/event_id y tenant/provider/payload_hash.
Los payloads se cifran porque pueden contener información personal. AuditLog
utiliza actor/system/created_at y before/after como equivalente al esquema
solicitado user/source/timestamp/metadata; no se renombra una tabla funcional
solo para cambiar vocabulario. Un registro de auditoría no almacena tokens.

## Migración y fuentes

`python -m catalog_platform.migrate` crea tablas faltantes y añade `batch_id`
nullable si existe un esquema de plataforma anterior. No hace DROP/TRUNCATE,
no reemplaza Sheets y no corre al iniciar la API. Respaldar antes de aplicarlo
con datos; la herramienta no aporta downgrade destructivo automático.

`inventario_completo` mantiene la operación histórica. `imports.normalize` y
`execute_import` permiten una importación explícita con backup y revisión;
el catálogo SQL no se declara automáticamente fuente única. Resolver diferencias
de SKU, variantes, imágenes y stock es una fase posterior. Ninguna fila real
fue importada, actualizada o borrada durante esta auditoría.
