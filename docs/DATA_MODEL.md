# Modelo de datos conservado

catalog_platform/models.py no cambia en esta entrega. No se ejecutan migraciones. PostgreSQL sigue almacenando productos, variantes, imágenes, lotes/jobs, credenciales cifradas, sesiones, movimientos y auditorías.

| Objeto | Uso actual |
|---|---|
| Product | UUID interno, SKU/barcode, padre/tipo, marca/categoría, precio, stock local, versión y estado |
| ProductImage | Referencias y galería asociadas al producto; ID Drive, rol y estado |
| GenerationBatch / GenerationJob | Confirmación, actor/tenant, coste/modelo, lease, checkpoints y cancelación |
| GeneratedAsset | Candidatos generados, raw, slot, revisión y vínculo con producto/job |
| IntegrationAccount | OAuth Google y Gemini personales cifrados; actor + tenant + proveedor |
| AuditLog | Cambios del catálogo, stock y estados; no se borra con soft delete |
| Browser session / heartbeat | Recuperación de sesión y disponibilidad del worker |
| Registros de movimientos/import | Operaciones locales y trazabilidad |

Tenant es la carpeta raíz autorizada; actor es el correo normalizado. UUID, SKU y barcode no son equivalentes. Las variantes tienen parent_id y atributos; el padre variable no recibe stock físico agregado mediante una escritura externa.

Las columnas woocommerce_*, wordpress_media_ids, loyverse_* y last_*_sync permanecen **históricas y sin uso operativo**. La serialización de Product no las muestra. OrderSnapshot, WebhookEvent y SyncEvent permanecen por integridad/historial: no hay receptores ni handlers activos que las alimenten. Los jobs antiguos de esos proveedores tampoco se eliminan; su ejecución/retry se bloquea.

Archivar/restaurar usa Product.status existente, incrementa version y añade AuditLog. Un padre archiva sus variantes activas; restaurar recupera las que fueron archivadas con ese mismo evento, sin resucitar variantes archivadas por separado. Stock, imágenes y filas permanecen. La eliminación local continúa siendo un soft delete confirmado y protegido por versión.

No hay DROP, TRUNCATE, ALTER ni limpieza de registros históricos. Una eventual migración a Supabase es un proyecto independiente.
