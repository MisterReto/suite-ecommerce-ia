# Captura recuperada

Referencia: tutorial de 555 s entregado por el usuario y auditoría previa en
`FUNCTIONAL_PARITY_AUDIT.md`. Base del cambio: `405f423`; commit de auditoría
publicado antes del código: `ef1b756`. La aceptación con teléfonos y proveedor
real se registra por separado en `../TEST_PLAN.md`.

## Desde la interfaz

Productos → **Nuevo producto con IA** y Generar → **Capturar producto** abren
el mismo estudio, aunque PostgreSQL ya esté listo. `frontend/app/page.tsx`
mantiene una sola instancia de `CaptureStudio`, oculta durante otros menús.
Cambiar de menú conserva fotos y edición; recargar recupera el checkpoint del
servidor. El catálogo, generación masiva, revisión y trabajos conservan sus entradas.

Frente obligatorio; reverso opcional. Cada foto ofrece cámara trasera y
galería/archivos, vista previa, reemplazo y eliminación. No hace falta crear
antes una ficha en el maestro. Notas y campos se guardan después de editar;
**Nuevo producto** descarta únicamente el borrador activo.

El celular es el dispositivo principal. Hasta 480 px, fotos y ficha utilizan
una sola columna. Cámara y galería tienen texto visible y áreas de 48 px;
las acciones y correcciones tienen al menos 44 px. Los campos usan texto de
16 px, teclado decimal para precio y numérico para barcode; SKU no aplica
autocorrección. La navegación inferior y los diálogos respetan las áreas
seguras del teléfono. El diálogo de corrección puede desplazarse en una
pantalla corta. La prueba de navegador usa perfiles táctiles Pixel/iPhone
en Chromium/WebKit; cámara nativa, teclado del sistema, HEIC y PWA instalada
requieren además un pase en dispositivos físicos.

`CaptureStudio::PhotoUpload` usa dos inputs nativos. `capture="environment"`
sugiere cámara trasera; el selector concreto depende del teléfono. La API
comprueba bytes, 12 MB y 24 millones de píxeles, corrige EXIF, convierte a RGB y
limita a 2400 px. HEIC/HEIF requiere el decoder opcional `pillow_heif`; sin él
devuelve un error que solicita JPG/PNG. No se afirma soporte HEIC instalado.

## React y FastAPI para quien conoce Python

El estado de React (`product`, `front`, `back`, `context`) equivale a variables
del formulario. Un botón llama a `api`, que envía JSON o `FormData` a FastAPI.
Pydantic valida ese objeto antes de entrar a la función Python. `applyDraft`
actualiza la pantalla con la respuesta; un debounce de 800 ms persiste cambios
sin publicar el producto. La comparación normalizada evita escrituras repetidas
por el orden de claves JSON o un reverso nulo.

| Acción | Archivo / función | Endpoint |
|---|---|---|
| Subir imagen | `CaptureStudio::upload`; `studio_api::upload`, `asset` | `POST /api/uploads` |
| Crear borrador | `ensureCapture`; `studio_api::capture` | `POST /api/capture` |
| Editar datos / notas | `persist`; `update_product`, `capture_notes` | `PUT /api/draft`, `PUT /api/capture-notes` |
| Analizar | `studio_api::analyze`, `read_barcodes`, `GeminiClient` | `POST /api/analyze` |
| Coincidencias | `studio_api::check`, `capture_bridge::check` | `POST /api/check-product` |
| Otras presentaciones | `studio_api::find_variants`, `app::buscar_variantes_por_imagen` | `POST /api/find-variants` |
| Familias / portada | `studio_api::parents`, `family_cover`; `ProductCapture` | `GET /api/parents`, `POST /api/family-cover` |
| Generar / corregir | `generate_images`, `correct_image`; `studio_jobs` | `POST /api/generate`, `POST /api/images/{slot}/correct` |
| Aprobar | `studio_api::approve` | `POST /api/images/{slot}/approve` |
| Guardar / reparar | `studio_api::save`, `repair_capture`; `capture_bridge` | `POST /api/save`, `POST /api/capture-sync` |
| Recuperar / descartar | `session_status`, `get_draft`, `clear_draft` | `GET /api/session`, `GET /api/draft`, `DELETE /api/draft` |

## Análisis y decisión

Primero se leen códigos EAN/UPC/GTIN válidos. Un código ya registrado recupera
la ficha y bloquea crear una copia sin llamar a Gemini. Para una foto nueva se
conserva el modelo de texto actual y las reglas comerciales existentes. Nombre,
marca, presentación, tipo reconocido, variante, atributos, categoría, textos,
etiquetas y barcode son editables. Los datos desconocidos quedan vacíos y en
`uncertain_fields`; no se selecciona automáticamente la primera categoría.

Las coincidencias muestran origen, SKU, marca, precio, atributos, diferencias
e imagen cuando está disponible. La decisión final es del operador: abrir
existente, utilizar padre, crear padre o guardar como simple. El análisis con
IA no garantiza por sí mismo que una etiqueta esté bien leída; la prueba real
debe comparar los campos con la fotografía.

## Persistencia y guardado

`capture_bridge::checkpoint` guarda metadata cifrada en `IntegrationAccount`,
por tienda y actor, provider `capture_draft`. Los archivos se suben a
`Rincon_de_Asia_App/capturas_temporales/<actor_hash>/<revision>`; un checksum
evita volver a subir la misma imagen. `restore` descarga a un namespace nuevo
y entrega IDs opacos nuevos. No se guardan rutas privadas ni claves en el navegador.

La recuperación incorpora resultados del worker para la revisión vigente aunque
terminaran mientras el cliente estaba desconectado; conserva los campos editados
del borrador. Descartar una captura deja una marca que impide recuperarla desde
jobs antiguos. `studio_jobs::record_saved` confirma la marca de guardado de los
jobs y del borrador cifrado en la misma transacción, sin volver a subir archivos
ni escribir Sheets. Así no se pierde el guardado si el proceso termina antes
del checkpoint final.

El guardado mantiene la escritura original de `inventario_completo` / Lista
completa y la carpeta `imagenes_generadas`. A:N y las fórmulas O:R permanecen;
S:T contienen el atributo de variación y U el barcode. Los atributos adicionales,
presentación y tipo reconocido se conservan también en el maestro SQL. La
compatibilidad histórica de Sheets tiene un atributo principal por variación.
Las referencias se guardan como `<SKU>_referencia_frente.jpg` y reverso, además
de los nombres originales de resultados y portadas.

Un lock PostgreSQL por tienda serializa lectura fresca y escritura Sheets entre
procesos API. Padre e hijo se escriben en un `values.batchUpdate` de Sheets y
se incorporan juntos en una transacción SQL con su relación e imágenes. Estas
dos transacciones no son una transacción distribuida: Sheets es la escritura
operativa primaria durante esta etapa. Si falla SQL, la UI muestra
`pending_repair`; reparar no vuelve a escribir Sheets.

El checkpoint `save_phase=saving` se crea inmediatamente antes de intentar
escribir Sheets, después de validar datos y preparar imágenes. Si la respuesta
se pierde, el siguiente intento verifica SKU, nombre, marca, padre, código y
atributo mediante lectura. Un resultado incierto nunca se repite a ciegas.
Una validación fallida antes de escribir permite corregir los campos y reintentar.

Guardar no publica en WooCommerce ni modifica stock remoto. El stock inicial
de la captura nueva es cero y se administra desde el inventario del maestro.
Los accesos a conteo, comparación y publicación originales están en Más →
Herramientas de Drive y usan el proxy del frontend.
