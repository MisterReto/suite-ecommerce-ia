# Cómo viaja una solicitud

Un botón React inicia una petición HTTP. FastAPI recibe el JSON y verifica permisos. Una respuesta 202 significa que el trabajo fue aceptado; el resultado de IA llegará después mediante el worker.

## Consultar productos

| Paso | Código | Resultado |
| --- | --- | --- |
| Escribir una búsqueda | `frontend/app/page.tsx` | Solicita `GET /api/platform/products`. |
| Validar usuario y carpeta | `catalog_platform.api.context` | Determina el tenant autorizado. |
| Consultar SQL | `catalog_platform.api.products` | Filtra por tenant, búsqueda y paginación. |
| Pintar la lista | React | Usa el JSON recibido; no consulta Drive directamente. |

## Generar un lote persistente

1. La UI solicita `POST /api/platform/generation/estimate`; la API calcula selección y coste estimado sin generar imágenes.
2. Después de la confirmación, `POST /api/platform/generation/jobs` verifica el presupuesto, referencias, rol, worker disponible y `request_key`.
3. La transacción crea filas `rincon_generation_jobs` y persiste la conexión cifrada. Devuelve 202.
4. `catalog_platform.queue.claim` adquiere un trabajo mediante un lease; otro worker no debe adquirir la misma fila.
5. `catalog_platform.worker.generation` descarga referencias, llama a `ImageGenerationService` y guarda cada resultado con un checkpoint.
6. `GET /api/platform/jobs` y `GET /api/platform/assets` muestran progreso y resultados en la UI.

El identificador del producto, la carpeta autorizada y el job se validan en el servidor. Cambiar un ID en el navegador no autoriza acceder a otra carpeta.

## Corregir una imagen

`POST /api/platform/assets/{asset_id}/correct` crea un nuevo job con feedback, historial e ID de la imagen anterior sin marca. El worker usa esa imagen y los originales. Un fallo conserva la imagen previa. Ver [IMAGE_GENERATION_FLOW.md](IMAGE_GENERATION_FLOW.md).

## Aprobar y publicar

`POST /api/platform/assets/{asset_id}/review` registra aprobación o rechazo. Publicar requiere otra solicitud: `POST /api/platform/products/{product_id}/publish`, rol admin y confirmación explícita. El worker utiliza los clientes existentes y relee los IDs de medios/producto para comprobar el destino.

## Importar el inventario histórico

`POST /api/platform/import/sheets` o `/import/file` prepara una vista previa. `/import/commit` confirma el trabajo con respaldo previo. La fuente histórica se conserva; no se vacía la hoja ni se publican fichas por el hecho de importar.

## Captura compatible sin catálogo SQL

Los endpoints `/api/uploads`, `/api/capture`, `/api/analyze`, `/api/draft`, `/api/generate`, `/api/images/{slot}/correct` y `/api/save` viven en `studio_api.py`. Sus jobs usan memoria de sesión/proceso. El guardado confirmado conserva el flujo Sheets/Drive. Esta modalidad no ofrece la durabilidad del lote SQL.

## Autenticación en servicios separados

`/login` y `/auth/callback` pasan del frontend a la API. Google usa `GOOGLE_REDIRECT_URI` en el dominio del frontend. Las cookies Secure, HttpOnly y SameSite=Lax regresan al navegador por ese mismo dominio. `/logout` también se envía a la API.

## Encontrar una falla

| Síntoma | Primer lugar que revisar |
| --- | --- |
| No aparece una pantalla | Componentes React y `frontend/app/page.tsx`. |
| HTTP 400/403 al enviar | Host, `APP_PUBLIC_ORIGIN`, sesión y roles. |
| Un lote devuelve 503 | Base configurada, esquema inicial y heartbeat del worker. |
| Job detenido | Estado, lease, `in_flight`, mensaje y checkpoint en SQL. |
| Falta una foto | `ProductImage.drive_file_id`, propiedad de carpeta y conexión Drive. |
| No se publica | Aprobación, permisos, flags de escritura y IDs externos. |

No pruebes una falla de generación repitiendo automáticamente una llamada pagada incierta.
