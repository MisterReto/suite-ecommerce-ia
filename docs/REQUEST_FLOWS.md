# Solicitudes del proyecto, paso a paso

Estas rutas pertenecen a la rama de plataforma. Next las envía por el proxy
definido en `frontend/next.config.ts`. Las funciones `api` de `page.tsx` y
`CaptureStudio.tsx` leen JSON y presentan errores; el backend comprueba permisos
aunque alguien llame sin usar React.

## 1. Abrir la lista de productos

| Paso | Archivo / función | Endpoint / entrada | Salida / siguiente componente |
| --- | --- | --- | --- |
| Abrir Productos | `frontend/app/page.tsx`, `Platform`, `loadProducts` | búsqueda, filtro, offset | llamada `api` |
| Autorizar | `catalog_platform/api.py`, `context` | cookie de sesión | email, tenant y rol |
| Consultar | `api.products` | `GET /api/platform/products?q=...&filter=...` | SQL filtrado por tenant, nombre/SKU/barcode |
| Responder | `catalog_platform/catalog.py`, `serialize` | filas `Product` | `items`, total; React muestra cards |

Sin DB configurada, la UI ofrece catálogo histórico mediante `CaptureStudio`
y `/api/catalog`; no simula que el catálogo SQL ya está importado.

## 2. Abrir un producto

| Paso | Archivo / función | Endpoint / entrada | Salida / siguiente componente |
| --- | --- | --- | --- |
| Tocar card | `frontend/app/page.tsx`, `openProduct` | UUID interno | `api` |
| Leer ficha | `api.get_product`, `catalog.product_for` | `GET /api/platform/products/{product_id}` | ficha, imágenes, assets, jobs, variantes, movimientos e historial |
| Ver imagen | `api.image` + `DriveService` | `GET /api/platform/images/{image_id}` | archivo privado autorizado; no URL con credenciales |
| Guardar cambios | `api.update_product` | `PUT /api/platform/products/{id}`, campos + version | nueva versión y AuditLog; otra acción publica ecommerce |

## 3. Generar una imagen o un lote

### Catálogo

| Paso | Archivo / función | Endpoint / entrada | Salida / siguiente componente |
| --- | --- | --- | --- |
| Preparar selección | `frontend/app/page.tsx`, estimación/confirmación | productos, slots, cantidad | muestra modelo, total y USD estimado |
| Cotizar | `api.generation_estimate`, `estimate` | `POST /api/platform/generation/estimate` | token ligado a selección/modelo/versiones; no llamada de imagen |
| Confirmar | `api.enqueue` | `POST /api/platform/generation/jobs`, confirm, request_key, estimate_token | 202, batch_id, jobs queued |
| Confirmar SQL | `database.transaction`, `queue.dispatch` | un job por producto | IDs listos para entrega después del commit |
| Entregar | `redis_broker.publish_one` | ID SQL | RQ JSON; ninguna imagen o credencial |
| Reclamar | `worker.execute_job`, `queue.claim` | ID RQ | lease y `processing` |
| Generar | `worker.generation`, `ImageGenerationService` | snapshot producto + IDs de originales | pipeline protegido; Gemini actual |
| Guardar candidatos | `DriveService.upload`, worker | JPEG/raw en `/tmp` | IDs Drive, ProductImage, GeneratedAsset, checkpoint |
| Mostrar | `api.jobs`, `api.assets`, `api.image` | consultas autenticadas | estado, preview y revisión; no publicación automática |

### Captura individual

`CaptureStudio.run` envía `POST /api/generate` a `studio_api.generate_images`.
Con `STUDIO_IMAGE_JOBS=worker`, `studio_jobs.enqueue_capture` valida confirmación,
snapshot y duplicados; sube referencias de esa captura, crea SQL y entrega el ID
a Redis. `worker.process` llama `studio_jobs.process_capture`, que reutiliza
`ImageGenerationService` y el pipeline anterior. `GET /api/jobs/{id}` llama
`studio_jobs.get_job`: lee SQL y recupera candidatos por Drive ID para el
borrador. Una sesión nueva puede recuperar el último job propio después de login.

Sin ese flag sigue disponible la orquestación anterior `start_job` local para
compatibilidad. Esa modalidad no cumple aislamiento RAM y no es la configuración
de los tres servicios. Los jobs de análisis de texto y guardado histórico siguen
usando el executor local; los jobs pesados de imagen no lo usan en modo worker.

## 4. Regenerar, corregir, aprobar y guardar

| Acción | Archivo / función | Endpoint / entrada | Resultado |
| --- | --- | --- | --- |
| Regenerar catálogo | `api.regenerate` → `enqueue_operation` | `/api/platform/assets/{id}/regenerate`, request_key/confirm_cost | nuevo candidato con originales; conserva asset previo |
| Corregir catálogo | `api.correct` → `worker.generation` | `/api/platform/assets/{id}/correct`, feedback/confirm_cost | nuevo job con raw previo e historial |
| Corregir captura | `studio_api.correct_image` → `studio_jobs.enqueue_capture` | `/api/images/{slot}/correct`, feedback/errors | mismo pipeline y brief, anterior conservado |
| Regenerar captura | `studio_api.generate_images` | `/api/generate`, slot seleccionado | nueva imagen de esa revisión, anteriores archivadas en el job |
| Aprobar catálogo | `api.review` | `/api/platform/assets/{id}/review`, status/role | AuditLog, estado de asset/imagen/job |
| Aprobar captura | `studio_api.approve`, `studio_jobs.record_approval` | `/api/images/{slot}/approve`, approved | UI y payload SQL actualizados |
| Guardar catálogo | `api.save_generated_asset` → `worker.save_asset` | `/api/platform/assets/{id}/save`, confirm | guardado explícito en generadas, backup de existente antes de reemplazar |
| Guardar captura | `studio_api.save` → `ProductCapture.save` | `/api/save`, confirm | flujo original Drive/Sheet; `record_saved` impide recuperación como borrador sin guardar |

Un error del proveedor se registra como job failed; no convierte una imagen
anterior en pérdida. Las llamadas inciertas tras reinicio no se repiten solas.

## 5. Leer inventario_completo

| Paso | Archivo / función | Entrada | Salida / siguiente componente |
| --- | --- | --- | --- |
| Pedir catálogo compatible | `studio_api.catalog` | `GET /api/catalog`, sesión | `ProductCapture.snapshot` |
| Localizar fuentes | `product_capture.py`, `snapshot`; `app._preparar_estructura` | carpeta real / GOOGLE_SHEET_ID opcional | folder IDs y Sheet nativo, sin reordenar |
| Leer | `app._get_sheets_service` → `SheetsService.spreadsheets` | Lista completa, rango existente | SDK compatible y registros por encabezados |
| Buscar con servicio nuevo | `SheetsService.find_sku`, `columns`, `read_range` | SKU + pestaña | fila única o error; no escritura |

La auditoría externa solo leyó metadata, encabezados y muestras. Una lectura
correcta de muestra no prueba que todas las filas estén completas o sin duplicados.

## 6. Actualizar WooCommerce

| Paso | Archivo / función | Endpoint / entrada | Salida / siguiente componente |
| --- | --- | --- | --- |
| Revisar y confirmar | `frontend/app/page.tsx` | ficha/galería aprobada | petición de publicación |
| Encolar | `api.publish` | `POST /api/platform/products/{id}/publish` | job publication; requiere admin y flags de escritura |
| Validar versión | `worker.publication` | snapshot/version | rechaza ficha o imágenes cambiadas |
| Crear/reutilizar medios | `WordPressMediaService`, `wordpress_media.WordPressMediaClient` | JPEG + metadata | IDs/URLs WordPress persistidos |
| Publicar producto | `WooCommerceService`, `woocommerce_client.WooCommerceClient` | UUID/mappings/IDs externos | producto o variación; SyncEvent y AuditLog |

Escrituras reales solo sobre `TEST-INTEGRATION-*` durante validación. Un timeout
remoto exige consultar el mapping/objeto antes de repetir; no se publica por
haber terminado una generación.

## 7. Recibir webhook

| Paso | Archivo / función | Endpoint / entrada | Salida / siguiente componente |
| --- | --- | --- | --- |
| Recibir | `webhooks.woocommerce`, `receive` | `POST /api/webhooks/woocommerce`; cuerpo crudo, firma, delivery ID, topic | validación HMAC SHA256 y límites |
| Deduplicar y registrar | `WebhookEvent`, `seal`, transacción | event_id y payload_hash | evento cifrado; 409 si el mismo ID cambia de contenido |
| Encolar | `queue.dispatch`, `redis_broker` | job kind webhook | 202 rápido después de registro durable |
| Procesar | `worker.process` → `webhooks.process_event` | event_id SQL | snapshot producto/pedido; movimiento idempotente e historial |

`/webhooks/woocommerce` permanece como alias. `/api/webhooks/loyverse` y su
alias existen, pero responden 503 mientras no se valide la firma/cuenta real.
No se descuenta stock por volver a recibir un evento de pedido.
