# Auditoría de paridad funcional — 8 octubre 2026

## Evidencia y límites

Auditoría inicial creada **antes de modificar código de aplicación**. Base de trabajo: `405f423fd79419700346c743eb90005e6bbbab82`, rama desplegada `agent/stabilize-architecture-20261006`. Recuperación aislada: `agent/restore-functional-parity-20261008`. Referencia histórica: `41d0599a45dda1edca13b1c253a68524e3567ad2` y su historial Git.

Se inspeccionó el tutorial aportado `Tutorial_Suite_ecommerce_Cliente(3).mp4` (555.029 s, 20 secciones, SHA256 `efd9a912cad44985bde344b694a5f22fb49574285d67a932b018a875699ab696`). Es una guía narrada con pantallas ilustrativas; acredita los flujos descritos, no una ejecución del deployment actual. Los requisitos posteriores al video proceden del texto del usuario y del código histórico de `catalog_capture.py`/`product_capture.py`.

Render comprobado mediante lectura de servicios y deploys. Frontend, API y worker separados, todos `free`, todos en `405f423`. Dos servicios históricos intactos, en `41d0599`. La interfaz real abre y ofrece login; esta sesión del navegador aún no está autenticada. No se ha generado con un proveedor real ni escrito en WooCommerce. La ausencia de errores en los últimos logs consultados no demuestra aceptación funcional.

| Servicio | ID | Deploy inicial observado | Estado |
|---|---|---|---|
| Frontend | srv-db2mlb2j9qps73eob7og | dep-db2mrmbrjlhs73fl00fg | live, free |
| API | srv-db2mlqij9qps73eobrg0 | dep-db3hfpd9fdbs73dqqgf0 | live, free |
| Worker | srv-db2mlqqj9qps73eobsk0 | dep-db2rgh2d0e5s73e5jru0 | live, free |
| Histórico IA | srv-da3841gae00c73aaour0 | dep-db0m3orm8hqs73d8rj70 | live, free, rama histórica |
| Histórico principal | srv-d9kc2lvavr4c73am1rug | dep-db0m3orm8hqs73d8ris0 | live, free, rama histórica |

## Matriz del tutorial

El estado siguiente describe el código inicial. «Presente» significa implementación localizada, **no** prueba real aprobada. No se afirma que una herramienta desapareció por estar bloqueada por login, rol o modo solo Drive.

| # / funcionalidad anterior | Archivo y función original | Implementación actual / endpoint | Acceso actual | Estado / causa | Corrección propuesta | Aceptación |
|---|---|---|---|---|---|---|
| 1–2 Navegación y herramientas | `app.py`, interfaz Gradio / `static/tutorial.js` | `frontend/app/page.tsx`, cinco menús | Visible en deployment | Presente; herramientas de captura dependen de `!ready` | Añadir acceso permanente a captura y herramientas conservadas | Cinco menús y captura accesibles a 360/390/430 px |
| 3 Conexión Google Drive | `app.py::login`, `auth_callback` | `/login`, `/auth/callback`, `/api/session` | Visible | Presente; validación real pendiente de sesión | Conservar OAuth y carpetas | Login y lectura del inventario con cuenta autorizada |
| 4 Gemini y carpeta | `app.py::guardar_api_key`, `guardar_carpeta_personalizada` | `studio_api.py::settings`, `session_status`; `/api/settings` | Más → Ajustes | Defectuosa: clave en diccionario; fallback `AI_API_KEY`; no borrar/probar | Persistir cifrada por tienda/usuario y resolver también en worker | Logout, reinicio, cambio, borrado y aislamiento sin secretos en respuesta |
| 5 Fotografía frontal y reverso | `app.py`, imágenes Gradio | `CaptureStudio::PhotoUpload`, `/api/uploads`, `/api/capture` | Generar solo si catálogo no listo | Oculta por condición `!ready`; sin eliminar foto individual | Productos → Nuevo producto con IA y Generar → Capturar producto; cámara/galería/eliminar | Foto vertical/EXIF, frontal obligatoria, reverso opcional, errores claros |
| 6 Análisis con IA | `app.py::modulo_extraer_textos` | `studio_api.py::analyze`, `/api/analyze` | Dentro de captura oculta | Desconectada de navegación; clasificación y dudas no estructuradas | Reutilizar modelo/reglas; autollenado editable y coincidencias | Foto conocida identifica campos; desconocidos vacíos/señalados |
| 7 Textos, precio y SKU | `generar_sku_logica`, `recalcular_precio_ui` | `/api/draft`, `/api/research-price`, CaptureStudio | En captura | Presente; precio se investiga por separado | Mantener edición y cálculo SKU original | Todos los campos editables antes de guardar |
| 8 Simple, variación y portada FULL | `ProductCapture::load_parents`, `cover`, `save` | `/api/parents`, `/api/family-cover`, `/api/save` | En captura | Presente pero oculta; padres y datos solo Sheets | Exponer recomendaciones y guardar relaciones en maestro | Padre sin stock/precio; variación con SKU/atributo propios |
| 9 Otras presentaciones | `app.py::buscar_variantes_por_imagen` | `/api/find-variants` | En captura | Presente pero oculta; recomendación solo texto y tipo retornado ignorado | Algoritmos primero; IA complementaria explícita; aplicar decisión manual | Duplicado no llama IA; variantes y padre explicados con origen |
| 10 Tres imágenes | `modulo_generar_todo`, `generar_foto_individual` | `studio_api::make_image`, `creative_pipeline::generate`, `/api/generate`; `/api/platform/generation/jobs` | Generar masivo sí; captura oculta | Presente; aceptación real pendiente | Conservar prompts/modelos/referencias/nombres y contrato | Limpio/lifestyle/comercial en mocks y prueba real mínima autorizada |
| 11 Corrección individual | `rehacer_hd`, `rehacer_life`, `rehacer_comercial` | `/api/images/{slot}/correct`, `/api/platform/assets/{id}/correct` | Revisión y captura | Presente; no hay prueba real de este turno | Mantener slot, historial, demás imágenes e idempotencia | Corregir una imagen conserva otras dos |
| 12 Guardado en inventario | `ProductCapture::save`, `_agregar_fila_google_sheet` | `/api/save`, escritura padre+hijo en Sheets | En captura | Desconectada del maestro; `record_saved` solo anota jobs | Sheets conserva compatibilidad; mirror SQL atómico y reparación visible | Producto aparece en maestro; fallo secundario no repite guardado |
| 13 Catálogo y existencias | `_cargar_df`, `inventory_web` | `/api/catalog`, `/api/platform/products` | Productos/Inventario | Presente; dos fuentes sin unificar captura | Incorporar capturas al maestro y ofrecer catálogo Drive | Buscar por nombre/SKU/barcode, stock de hijo separado |
| 14 Conteo físico inicial | `inventory_operations`, `inventory_web` | `/inventory-count-bulk`; `/api/platform/products/{id}/stock` | Maestro permite ajuste; herramienta Drive no enlazada por proxy | Oculta parcialmente en nueva navegación | Conservar acceso a herramienta histórica y permisos | Conteo sintético no cambia stock real; FULL excluido |
| 15 Movimientos e historial | `inventory_operations`, `inventory_web` | `/inventory-movement`, `/inventory-history`; ficha maestro | Historial maestro sí | Presente; acceso a herramientas Drive incompleto | Enlazar herramientas conservadas y proxy por mismo origen | Entrada/salida/merma/devolución identificadas en historial |
| 16 Comparación Sheets–Woo | `publication_web::inventory_review` | `/inventory-review`, operaciones maestro | Herramienta Drive no enlazada | Oculta/condicionada por `SUITE_DRIVE_ONLY`, no ausente | Acceso explícito, lectura y errores de conexión | Comparación sin escrituras remotas |
| 17 Drive–WordPress imágenes | `media_web`, `woocommerce_image_sync` | `/woocommerce-image-preview`, `/wp-media-health`, `/image-sync-one` | Herramienta no enlazada; revisión maestro sí | Oculta parcialmente y conexión condicionada | Enlazar herramienta conservada; publicar requiere revisión | Archivos/mappings comprobados sin publicar automáticamente |
| 18 Publicación masiva | `batch_web_v2`, `woocommerce_batch_sync` | `/woocommerce-batch-sync`, `/batch-create`; jobs maestro | Maestro parcial; original sin enlace/proxy | Presente pero acceso histórico incompleto | Exponer herramienta conservada, misma confirmación | Preview y confirmación; pruebas con dobles, sin productos reales |
| 19 Pausa/reanuda/verifica | `batch_web_v2`, `queue` | `/batch-step`, `/batch-resume`, `/batch-status`; `/api/platform/jobs/{id}/…` | Trabajos maestro sí | Presente; paridad de estados requiere prueba | Conservar ambos flujos, incertidumbre y resultados por producto | Pausar al acabar operación en vuelo, reanudar sin duplicados |
| 20 Rutina recomendada | `static/tutorial.js` | Más → Ayuda | Visible | Defectuosa: guía prioriza ficha manual y omite captura inteligente | Explicar Capturar → Analizar → Coincidencias → Revisar → Generar → Guardar/Publicar | Usuario completa flujo sin otra app ni publicación implícita |

## Ampliaciones posteriores obligatorias

1. `catalog_capture::find_duplicate/review_product`: existen GTIN válido, SKU, marca/nombre/presentación y atributos, pero solo consultan Sheets. Extender a maestro SQL y lectura Woo cuando la conexión esté activa. Mostrar registro, origen, SKU, atributos, precio e imagen; abrir ficha existente. Evitar familias creadas solo por marca compartida.
2. `ProductCapture::load_parents/cover`: existen propuestas SKU FULL, padres y composición con fotos reales. Conservar estas funciones y explicar si solo hay una variante. La recomendación no decide por el usuario.
3. `IntegrationAccount`, `accounts.persist/load`, `security.seal/unseal`: infraestructura existente; el guardado en Ajustes no la usa. El worker carga conexiones cifradas, pero la clave solo llega al persistir trabajos y puede proceder del fallback global. Separar credencial personal de la conexión Google y evitar que un worker sobrescriba una clave recién cambiada.
4. `CaptureStudio::ensureCapture`: ignora cambios de observaciones cuando las imágenes no cambian. Actualizar notas sin descartar datos editados o imágenes.
5. Borrador: depende de RAM, salvo recuperación de jobs de imágenes; navegación desmonta el componente. Conservar componente durante navegación y documentar/probar recuperación de borradores persistidos.

## Orden y barreras

Auditoría → restauración de accesos → credencial persistente → análisis/coincidencias/familias → guardado unificado → pruebas automáticas y móvil → staging. No promover a producción si fallan captura, Gemini, familias o generación. No cambiar planes, secretos Render actuales, servicios históricos, modelos ni prompts del generador. No generar con Gemini real sin presupuesto autorizado ni modificar stock/productos reales durante pruebas.

Los resultados posteriores deben registrarse por prueba en `TEST_PLAN.md` y `docs/VERIFICATION.md`. Una prueba sintética en Chromium/WebKit no se presenta como prueba en teléfono físico ni en una PWA instalada.
