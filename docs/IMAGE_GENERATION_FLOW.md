# Flujo de generación de imágenes

El flujo principal se conserva: **capturar → analizar con Gemini → detectar coincidencias → clasificar → generar → revisar → guardar en Drive y catálogo**.

| Paso | Código | Comportamiento conservado |
|---|---|---|
| Fotografía / cámara | CaptureStudio, studio_api, product_capture | Cámara móvil y upload, validación de imagen, referencias originales |
| Análisis | ProductCapture / gemini_gateway | Gemini con la clave personal configurada; extracción y clasificación simple/variable |
| Coincidencias | catalog_capture / capture_bridge | Búsqueda por SKU/barcode y similitud en catálogo local y Sheet; ya no consulta tiendas externas |
| Familia | product_generation / capture_bridge | Padres y variantes, atributos, marca/categoría, portada del padre |
| Preparación | creative_pipeline / ImageGenerationService | Prompt HD y brief lifestyle/comercial, referencias y estilos actuales |
| Confirmación | studio_api / catalog_platform.api | Slots, cantidad, estimación, modelo/versiones e idempotencia |
| Encolado | studio_jobs / queue / redis_broker | SQL confirma el job y Redis entrega su ID; no transporta API keys ni fotos |
| Ejecución | worker.process / generation / studio_generation | Credenciales vigentes del actor, checkpoints, imágenes individuales y masivas |
| Revisión | GeneratedAsset / CaptureStudio | Candidato, original/raw, QA, aprobación/rechazo, corrección y regeneración |
| Guardado | ProductCapture.save / asset_save | Drive, catálogo y escritura puntual existente del Sheet; conserva backups y naming |

`app.py`, `creative_pipeline.py`, `gemini_gateway.py`, `product_capture.py`, `product_generation.py` e `image_generation_service.py` permanecen idénticos a la base desplegada. Las funciones creativas protegidas de studio_api mantienen el contrato aceptado en `3ba6a2f9aeb65265a6165ee6c48b7ab273256d7f`.

No se cambian automáticamente los modelos: los defaults existentes son `gemini-2.5-flash` para texto y `gemini-3.1-flash-image` para imágenes. Los overrides de modelo deben seguir siendo iguales entre API y worker; un job que confirmó otro modelo se rechaza antes de generar.

Los tres slots conservan su significado y nombres:

| Slot | Imagen | Naming existente |
|---|---|---|
| `1_hd` | Producto limpio / portada | `SKU_1_hd.jpg` |
| `2_uso` | Lifestyle | `SKU_2_uso.jpg` |
| `3_comercial` | Comercial | `SKU_3_comercial.jpg` |

Las carpetas `imagenes_generadas`, candidatos temporales, originales/raw, ejemplos de estilo y respaldos mantienen su lógica. La limpieza no mueve carpetas, renombra imágenes ni sobrescribe el Sheet completo. Un guardado confirmado puede crear el respaldo y reemplazar el canónico según el comportamiento ya existente.

Regenerar conserva el resultado anterior y las referencias. Corregir utiliza el raw anterior y el feedback individual. La cancelación y el cierre de navegador no eliminan el historial. Un checkpoint marcado incierto impide repetir automáticamente una llamada pagada.

Más → Ajustes guarda la API key Gemini con Fernet en PostgreSQL, por actor y carpeta. `accounts.persist` guarda Google por separado; `accounts.load` recupera Google y consulta la clave Gemini vigente. No usa AI_API_KEY global como fallback ni requiere una clave personal en Render.

Las pruebas automatizadas emplean dobles del proveedor y bloquean conexiones externas. La aceptación con Gemini real está pendiente y requiere autorización de gasto. Consultar [REGRESSION_RESULTS.md](REGRESSION_RESULTS.md).
