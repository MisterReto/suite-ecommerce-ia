# Índice de funciones y objetos

Actualizado el 11 de octubre de 2026 (UTC). Complementa [CODE_GUIDE](CODE_GUIDE.md).
Base funcional: `ba19067`. Rama: `feature/woocommerce-and-product-removal-20261009`.

Inventario completo de definiciones propias: **83 módulos Python, 744 funciones/métodos y 71 clases** (incluye el handler HTTP anidado del worker); **127 definiciones nombradas del frontend** entre funciones, componentes, tipos, clases y constructores. Se documentan diez archivos frontend, incluido el service worker sin funciones nombradas propias.

La descripción procede de los comentarios de esta entrega y de las docstrings existentes. Las docstrings históricas se conservan cuando ya explican la función. Los campos de las clases se obtienen del código; los campos heredados se explican en su clase base. Las firmas son referencias del contrato, nunca valores de configuración reales. No contiene credenciales ni datos del inventario.

Los enlaces apuntan a la rama de trabajo; los números de línea corresponden a esta entrega. En un commit posterior buscar por nombre. Los nombres cualificados como `start_job.work` identifican un helper dentro de otra función. Las dependencias, callbacks anónimos y variables locales no se enumeran como funciones de negocio.

**Protección:** documentar `creative_pipeline`, `make_image`, `creative_plan` o las herramientas históricas no autoriza reescribirlas ni activar integraciones. Usar primero la tabla de síntomas de la guía y sus pruebas.

# Frontend: pantallas y controles

Sección del índice del código de la aplicación. Las rutas y números de línea corresponden a esta entrega documental; buscar por nombre en una versión posterior. Una función compatible/histórica no implica que su integración esté activada.

## frontend/app/connect-google/page.tsx

Pantalla local de espera de /login; funciona con script inline aunque los chunks React no carguen.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/connect-google/page.tsx)

- `bootstrap` — Inserta en el HTML una espera autocontenida y un botón Reintentar; no depende de que hidrate React. [Código, línea 10](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/connect-google/page.tsx#L10)

- `ConnectGoogle` — Renderiza Iniciando servidor y el script que decide volver al inicio o empezar OAuth tras validar sesión. [Código, línea 60](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/connect-google/page.tsx#L60)

## frontend/app/layout.tsx

Layout, fuentes y metadata global de la interfaz/PWA.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/layout.tsx)

- `RootLayout` — Aplica idioma/layout, tipografía y metadata compartida; no guarda datos del catálogo. [Código, línea 23](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/layout.tsx#L23)

## frontend/app/page.tsx

Pantalla principal Platform: navegación, catálogo SQL, trabajos, inventario, conexiones y confirmaciones.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx)

- `Section` — Nombres de las cinco secciones de navegación; no son permisos del servidor. [Código, línea 41](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L41)

- `Product` — Copia JSON de Product SQL para la interfaz; version debe enviarse en las escrituras correspondientes. [Código, línea 44](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L44)
  Campos declarados: `id`, `sku`, `barcode`, `name`, `brand`, `category`, `subcategory`, `short_description`, `long_description`, `tags`, `attributes`, `product_type`, `parent_id`, `price`, `cost`, `stock`, `woocommerce_stock`, `loyverse_stock`, `status`, `sync_status`, `version`, `image_id`, `woocommerce_product_id`, `woocommerce_variation_id`, `loyverse_item_id`, `last_woocommerce_sync`.

- `Picture` — Metadata y referencia Drive de una imagen del catálogo. [Código, línea 73](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L73)
  Campos declarados: `id`, `drive_file_id`, `role`, `status`, `metadata_json`.

- `Brief` — Plan creativo y fuentes de investigación mostrados junto al candidato. [Código, línea 81](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L81)
  Campos declarados: `lifestyle`, `comercial`, `note`, `sources`, `search_suggestions`.

- `Asset` — Candidato generado, estado de revisión, slot e historial de correcciones. [Código, línea 89](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L89)
  Campos declarados: `provider`, `model`, `id`, `image_id`, `product_id`, `job_id`, `sku`, `product_name`, `slot`, `estimated_correction_usd`, `status`, `history`, `metadata_json`.

- `Job` — Trabajo durable con actor, estado, progreso y payload; cancelling sigue siendo activo. [Código, línea 110](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L110)
  Campos declarados: `id`, `actor`, `kind`, `product_id`, `status`, `progress`, `message`, `estimated_cost`, `created_at`, `payload`.

- `Event` — Evento de sincronización mostrado en el historial. [Código, línea 128](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L128)
  Campos declarados: `id`, `product_id`, `action`, `source`, `destination`, `status`, `message`, `created_at`, `job_id`.

- `Detail` — Respuesta compuesta de ficha, variantes, imágenes, movimientos y trabajos. [Código, línea 140](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L140)
  Campos declarados: `product`, `images`, `assets`, `jobs`, `movements`, `sync_events`, `variants`.

- `Session` — Estado público de sesión; no contiene tokens Google ni la clave Gemini. [Código, línea 158](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L158)
  Campos declarados: `authenticated`, `email`, `gemini_configured`, `folder`, `folder_id`, `image_model`, `estimated_image_usd`.

- `Status` — Configuración, rol y readiness de plataforma/worker para habilitar controles. [Código, línea 168](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L168)
  Campos declarados: `ready`, `configured`, `worker_ready`, `worker_can_queue`, `role`, `message`.

- `Dashboard` — Datos agregados de Inicio basados en registros/snapshots reales. [Código, línea 177](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L177)
  Campos declarados: `stats`, `activity`, `ecommerce`.

- `Quote` — Selección/coste cotizados antes de confirmar generación. [Código, línea 193](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L193)
  Campos declarados: `products`, `images`, `provider`, `model`, `estimated_usd`, `estimate_token`, `note`.

- `Preview` — Resultado de previsualización que debe revisarse antes de importar. [Código, línea 203](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L203)
  Campos declarados: `preview_id`, `rows`, `errors`, `sample`, `note`.

- `Confirm` — Datos y acción del modal de confirmación; abrirlo todavía no ejecuta la escritura. [Código, línea 211](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L211)
  Campos declarados: `title`, `text`, `label`, `uncertain`, `action`.

- `currency` — Formatea importes para mostrar al usuario. [Código, línea 253](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L253)

- `date` — Formatea fechas operativas según el navegador. [Código, línea 261](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L261)

- `pictureUrl` — Construye la URL privada de imagen servida por la API. [Código, línea 271](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L271)

- `active` — Considera queued, processing y cancelling como trabajos todavía activos. [Código, línea 274](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L274)

- `blank` — Crea la ficha vacía del formulario de producto sin persistirla. [Código, línea 276](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L276)

- `ApiError` — Error HTTP con estado e información de respuesta perdida/incertidumbre. [Código, línea 300](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L300)

- `ApiError.constructor` — Conserva estado HTTP y datos de respuesta perdida en el error que recibe la pantalla. [Código, línea 301](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L301)

- `api` — Envía solicitudes con cookie de mismo origen y timeout; no reintenta automáticamente escrituras o generaciones. [Código, línea 310](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L310)

- `Badge` — Muestra la etiqueta visual de un estado existente. [Código, línea 359](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L359)

- `Empty` — Muestra una explicación cuando una lista/pantalla no tiene elementos. [Código, línea 365](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L365)

- `Platform` — Organiza estado, carga, navegación y acciones de la app; la autorización efectiva vive en la API. [Código, línea 377](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L377)

- `Platform.go` — Cambia sección/tab y referencia de navegación del navegador. [Código, línea 441](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L441)

- `Platform.attempt` — Conserva una clave request_key por intención confirmada para recuperar envíos sin duplicarlos. [Código, línea 450](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L450)

- `Platform.durablePost` — Envía una operación durable con la misma clave idempotente si debe resolverse una respuesta perdida. [Código, línea 469](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L469)

- `Platform.reloadBase` — Recupera sesión y configuración base antes de cargar operaciones privadas. [Código, línea 485](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L485)

- `Platform.reloadOperations` — Actualiza trabajos, imágenes y resumen operativo desde SQL. [Código, línea 494](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L494)

- `Platform.loadProducts` — Carga la página/selección/filtros actuales del catálogo. [Código, línea 507](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L507)

- `Platform.change` — Interpreta el hash de navegación para recuperar la sección seleccionada. [Código, línea 516](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L516)

- `Platform.disconnected` — Refleja falta de conexión del navegador en la interfaz. [Código, línea 531](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L531)

- `Platform.connected` — Recupera sesión al volver conexión/foco, agrupando solicitudes simultáneas. [Código, línea 534](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L534)

- `Platform.resumed` — Solicita reconexión cuando la pestaña vuelve a estar visible y hay red. [Código, línea 545](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L545)

- `Platform.run` — Callback de polling que actualiza trabajos y trata un 401 como sesión no autenticada. [Código, línea 578](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L578)

- `Platform.keys` — Gestiona Escape y foco del modal para teclado/accesibilidad. [Código, línea 614](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L614)

- `Platform.openProduct` — Obtiene la ficha completa por UUID antes de abrirla o editarla. [Código, línea 644](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L644)

- `Platform.ask` — Abre confirmación y limpia la aceptación previa de incertidumbre. [Código, línea 653](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L653)

- `Platform.deleteProduct` — Confirma retirada de la app y envía UUID/version; no borra archivos Drive, hojas ni tienda. [Código, línea 659](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L659)

- `Platform.stopJobs` — Confirma los IDs visibles: uno o lote; trabajos creados después no quedan incluidos. [Código, línea 676](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L676)

- `Platform.operation` — Envía una operación durable confirmada y actualiza su progreso. [Código, línea 691](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L691)

- `Platform.saveProduct` — Valida atributos de formulario y guarda la ficha con el contrato/versionado de API. [Código, línea 701](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L701)

- `Platform.uploadReference` — Sube y asocia una referencia al producto autorizado. [Código, línea 720](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L720)

- `Platform.scan` — Pide lectura de código de barras de la foto elegida. [Código, línea 736](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L736)

- `Platform.batch` — Cotiza/confirma o encola el lote de generación seleccionado con deduplicación de intención. [Código, línea 756](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L756)

- `Platform.reviewAsset` — Abre los datos de un candidato para revisar o corregir. [Código, línea 766](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L766)

- `Platform.approve` — Persiste aprobación/rechazo y actualiza la lista de candidatos. [Código, línea 781](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L781)

- `Platform.retry` — Confirma expresamente el reintento del trabajo y conserva controles de coste/incertidumbre. [Código, línea 797](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/app/page.tsx#L797)

## frontend/components/CaptureStudio.tsx

Captura de producto: fotos, borrador, análisis, familia, generación, revisión y guardado compatible.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/CaptureStudio.tsx)

- `Product` — Ficha de borrador de captura; sus campos se traducen al contrato de studio_api, no al formulario SQL directamente. [Código, línea 37](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/CaptureStudio.tsx#L37)
  Campos declarados: `sku`, `name`, `brand`, `size`, `kind`, `price`, `category`, `subcategory`, `tags`, `short_description`, `description`, `barcode`, `parent_sku`, `parent_name`, `parent_mode`, `attribute`, `attribute_value`, `product_type`, `variant`, `attributes`, `uncertain_fields`.

- `Match` — Coincidencia de inventario/tienda que el usuario debe revisar antes de guardar. [Código, línea 61](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/CaptureStudio.tsx#L61)
  Campos declarados: `sku`, `nombre_producto`, `Marca`, `precio`, `atributo_nombre`, `atributo_valor`, `sku_padre`, `product_id`, `image_url`, `_source`, `attributes`, `matching_attributes`, `different_attributes`.

- `IdentityReview` — Resultado de coincidencias, padres posibles y recomendación de familia. [Código, línea 66](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/CaptureStudio.tsx#L66)
  Campos declarados: `status`, `case`, `message`, `recommendation`, `suggested`, `duplicate`, `parents`, `candidates`, `sources`.

- `Picture` — Slot/imagen de borrador con estado de aprobación y referencia propia. [Código, línea 69](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/CaptureStudio.tsx#L69)
  Campos declarados: `id`, `approved`, `message`, `history`, `qa`.

- `Brief` — Investigación creativa asociada a las imágenes del borrador. [Código, línea 77](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/CaptureStudio.tsx#L77)
  Campos declarados: `lifestyle`, `comercial`, `note`, `style_count`, `sources`, `search_suggestions`.

- `Draft` — Producto, fotos, contexto, brief, aprobación e historial de la captura actual. [Código, línea 86](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/CaptureStudio.tsx#L86)
  Campos declarados: `revision`, `front_id`, `back_id`, `context`, `product`, `images`, `brief`, `cover_id`, `cover_message`, `saved`, `variant_report`, `variant_recommendation`, `identity_review`, `sync_status`, `sync_error`, `master_product_id`.

- `Job` — Respuesta compatible del job local/durable de captura. [Código, línea 105](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/CaptureStudio.tsx#L105)
  Campos declarados: `id`, `status`, `label`, `progress`, `message`.

- `Session` — Estado público de cuenta, carpeta, Gemini y borrador recuperado. [Código, línea 113](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/CaptureStudio.tsx#L113)
  Campos declarados: `authenticated`, `email`, `gemini_configured`, `folder`, `folder_id`, `image_model`, `image_provider`, `estimated_image_usd`, `text_model`, `errors`, `usage`, `draft`, `job`, `loyverse`.

- `CatalogRow` — Fila del inventario histórico que se muestra en consultas de captura. [Código, línea 134](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/CaptureStudio.tsx#L134)

- `LoyRow` — Fila de coincidencia de las herramientas Loyverse compatibles. [Código, línea 136](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/CaptureStudio.tsx#L136)
  Campos declarados: `sku`, `name`, `drive`, `loyverse`, `price`, `status`, `detail`, `eligible`.

- `LoyJob` — Progreso de un trabajo compatible Loyverse, separado de la cola SQL de imágenes. [Código, línea 147](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/CaptureStudio.tsx#L147)
  Campos declarados: `id`, `state`, `done`, `total`, `phase`, `current`, `error`, `uncertain`, `created`, `completed`.

- `sameProduct` — Compara campos normalizados de dos borradores para no reemplazar una edición más reciente con una respuesta vieja. [Código, línea 186](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/CaptureStudio.tsx#L186)

- `sameProduct.normalize` — Normaliza un valor de campo para comparar versiones del borrador. [Código, línea 188](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/CaptureStudio.tsx#L188)

- `fileUrl` — Construye la URL de un temporal propio o una imagen privada recuperada. [Código, línea 217](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/CaptureStudio.tsx#L217)

- `activeJob` — Incluye Deteniendo entre trabajos activos para evitar otra generación mientras termina la llamada actual. [Código, línea 220](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/CaptureStudio.tsx#L220)

- `ApiError` — Error del cliente HTTP de captura con estado/resultado incierto. [Código, línea 224](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/CaptureStudio.tsx#L224)

- `ApiError.constructor` — Conserva estado HTTP y resultado incierto de una operación de captura. [Código, línea 225](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/CaptureStudio.tsx#L225)

- `api` — Envía JSON o fotos con cookies y timeout; conserva errores de sesión y no repite llamadas pagadas. [Código, línea 235](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/CaptureStudio.tsx#L235)

- `Field` — Renderiza un campo etiquetado con el control de formulario que recibe. [Código, línea 286](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/CaptureStudio.tsx#L286)

- `PhotoUpload` — Selector/preview de foto con interacción móvil y borrado del borrador. [Código, línea 307](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/CaptureStudio.tsx#L307)

- `CaptureStudio` — Conserva la secuencia capturar, identificar, revisar, generar y guardar del flujo aceptado. [Código, línea 375](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/CaptureStudio.tsx#L375)

- `CaptureStudio.applyDraft` — Aplica una respuesta de borrador sin sobreescribir una edición más reciente. [Código, línea 445](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/CaptureStudio.tsx#L445)

- `CaptureStudio.refresh` — Recupera sesión/borrador después de arranque en frío o reconexión. [Código, línea 458](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/CaptureStudio.tsx#L458)

- `CaptureStudio.change` — Notifica cambios del borrador a los controles de captura. [Código, línea 475](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/CaptureStudio.tsx#L475)

- `CaptureStudio.attempt` — Conserva la clave idempotente de la intención de generación/corrección. [Código, línea 558](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/CaptureStudio.tsx#L558)

- `CaptureStudio.edit` — Actualiza un campo local y marca que falta persistir la edición. [Código, línea 574](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/CaptureStudio.tsx#L574)

- `CaptureStudio.ensureCapture` — Guarda fotos/contexto necesarios para que la API conozca la captura actual. [Código, línea 577](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/CaptureStudio.tsx#L577)

- `CaptureStudio.persist` — Guarda el producto editado antes de analizar, generar o enviar otra operación. [Código, línea 594](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/CaptureStudio.tsx#L594)

- `CaptureStudio.run` — Inicia una acción de captura y observa el job resultante, usando confirmación/idempotencia cuando procede. [Código, línea 603](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/CaptureStudio.tsx#L603)

- `CaptureStudio.upload` — Sube frente/reverso y actualiza la captura sin mezclar respuestas de una foto anterior. [Código, línea 625](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/CaptureStudio.tsx#L625)

- `CaptureStudio.loadCatalog` — Consulta el inventario conectado para revisar fichas existentes. [Código, línea 644](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/CaptureStudio.tsx#L644)

- `CaptureStudio.removePhoto` — Retira una foto del borrador local/captura; no elimina un archivo de producto guardado en Drive. [Código, línea 655](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/CaptureStudio.tsx#L655)

- `CaptureStudio.loadParents` — Consulta padres existentes y propuestas de relación de familia. [Código, línea 668](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/CaptureStudio.tsx#L668)

- `CaptureStudio.chooseFamily` — Aplica una familia elegida por el usuario al borrador y la persiste. [Código, línea 686](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/CaptureStudio.tsx#L686)

- `CaptureStudio.go` — Cambia el paso visible de la captura. [Código, línea 698](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/CaptureStudio.tsx#L698)

## frontend/components/DriveClassification.tsx

Selectores de categoría/subcategoría y etiquetas tomadas de Drive, con búsqueda y reintento visible.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/DriveClassification.tsx)

- `Choices` — Vocabulario leído: categorías, subcategorías por categoría y etiquetas, con origen drive/defaults. [Código, línea 9](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/DriveClassification.tsx#L9)
  Campos declarados: `source`, `categories`, `subcategories`, `tags`.

- `Value` — Clasificación seleccionada por el usuario; escribir en búsqueda no crea una etiqueta. [Código, línea 16](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/DriveClassification.tsx#L16)
  Campos declarados: `category`, `subcategory`, `tags`.

- `DriveClassification` — Lee opciones con timeout/reintento, limpia subcategorías incompatibles y muestra las etiquetas en fila desplazable. [Código, línea 20](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/DriveClassification.tsx#L20)

## frontend/lib/generation-sounds.ts

Avisos de inicio, éxito y fallo de imagen con Web Audio, consentimiento por gesto y deduplicación.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/lib/generation-sounds.ts)

- `ImageJob` — Identidad/estado/etiqueta del job de imagen que se observará para un aviso sonoro. [Código, línea 4](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/lib/generation-sounds.ts#L4)
  Campos declarados: `id`, `status`, `label`.

- `GenerationSounds` — Controlador de avisos de imagen; evita repetir sonidos en cada polling y permite silenciarlos. [Código, línea 15](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/lib/generation-sounds.ts#L15)
  Campos declarados: `context`, `output`, `nextAt`, `enabled`, `jobs`.

- `GenerationSounds.constructor` — Recibe la creación de AudioContext y deja el audio pendiente de un gesto; no inicia una generación. [Código, línea 22](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/lib/generation-sounds.ts#L22)

- `GenerationSounds.setEnabled` — Actualiza la preferencia en memoria y el volumen; la persistencia del ajuste pertenece al componente que lo utiliza. [Código, línea 31](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/lib/generation-sounds.ts#L31)

- `GenerationSounds.unlock` — Desbloquea Web Audio desde un gesto del usuario para que funcione en móvil. [Código, línea 38](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/lib/generation-sounds.ts#L38)

- `GenerationSounds.observe` — Compara la transición del job y emite inicio, fin o fallo una sola vez. [Código, línea 53](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/lib/generation-sounds.ts#L53)

- `GenerationSounds.play` — Programa tonos breves por tipo de aviso; no llama a proveedores ni descarga un audio externo. [Código, línea 78](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/lib/generation-sounds.ts#L78)

- `GenerationSounds.play.schedule` — Agenda notas en AudioContext después de asegurar que está operativo. [Código, línea 82](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/lib/generation-sounds.ts#L82)

- `GenerationSounds.dispose` — Cierra el contexto de audio y limpia recursos al desmontar el componente. [Código, línea 111](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/lib/generation-sounds.ts#L111)

## frontend/lib/session-recovery.ts

Arranque de API y recuperación acotada de sesión: solo reintenta lecturas GET.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/lib/session-recovery.ts)

- `recoverSession` — Despierta API sin credenciales y verifica health/sesión por proxy durante un máximo de tres minutos; solo reintenta GET. [Código, línea 8](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/lib/session-recovery.ts#L8)

- `recoverSession.cancelWake` — Aborta el aviso de arranque directo cuando vence su plazo o se cancela la recuperación. [Código, línea 19](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/lib/session-recovery.ts#L19)

- `recoverSession.aborted` — Crea el error AbortError usado al abandonar/cambiar un intento. [Código, línea 38](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/lib/session-recovery.ts#L38)

- `recoverSession.read` — Lee JSON válido por el dominio frontend con cookie y plazo acotado por petición. [Código, línea 41](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/lib/session-recovery.ts#L41)

- `recoverSession.read.cancel` — Aborta una lectura cuyo plazo ha vencido o cuya recuperación fue cancelada. [Código, línea 45](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/lib/session-recovery.ts#L45)

- `recoverSession.pause` — Espera entre lecturas conservando la posibilidad de cancelar el intento. [Código, línea 62](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/lib/session-recovery.ts#L62)

- `recoverSession.pause.finish` — Resuelve la espera y limpia el listener de cancelación. [Código, línea 66](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/lib/session-recovery.ts#L66)

- `recoverSession.pause.cancel` — Cancela el temporizador y rechaza la espera si el usuario abandona el intento. [Código, línea 69](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/lib/session-recovery.ts#L69)

## frontend/next.config.ts

Modo standalone/export y proxy al origen API validado; conserva cookies y sirve /login localmente.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/next.config.ts)

- `rewrites` — Sirve /login localmente, dirige /auth/start al login de FastAPI y conserva el proxy de API/callback con el origen validado. [Código, línea 30](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/next.config.ts#L30)

- `headers` — Aplica políticas HTTP y no-store al login; la CSP permite únicamente el origen API público configurado para arranque. [Código, línea 49](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/next.config.ts#L49)

## frontend/public/sw.js

Caché PWA de la carcasa pública; no guarda sesión, datos privados ni operaciones de API.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/public/sw.js)

Este módulo configura/importa componentes o registra callbacks anónimos; no declara funciones o clases nombradas propias.


# API: login, sesiones y permisos

Sección del índice del código de la aplicación. Las rutas y números de línea corresponden a esta entrega documental; buscar por nombre en una versión posterior. Una función compatible/histórica no implica que su integración esté activada.

## app.py

Runtime compartido de OAuth, sesiones, Drive/Sheets y funciones históricas; contiene partes del generador protegidas.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py)

- `field_update` — Structured field values used by catalog adapters, independent of the UI. [Código, línea 45](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L45)
  Firma: `field_update(**values)`.

- `_env_requerida` — Exige una variable de arranque y falla sin mostrar su valor secreto. [Código, línea 63](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L63)
  Firma: `_env_requerida(nombre)`.

- `_construir_correccion` — Arma el bloque de retroalimentación que se le manda al modelo explicándole POR QUÉ estamos rehaciendo la imagen y qué debe corregir. [Código, línea 187](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L187)
  Firma: `_construir_correccion(errores_seleccionados, texto_libre, historial)`.

- `_nueva_session_id` — Genera el identificador aleatorio que recibirá la cookie de sesión. [Código, línea 250](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L250)
  Firma: `_nueva_session_id()`.

- `_eliminar_sesion` — Revoca la sesión SQL, retira su copia local y limpia solo temporales de esa sesión. [Código, línea 255](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L255)
  Firma: `_eliminar_sesion(session_id)`.

- `_guardar_sesion` — Actualiza el registro en memoria y persiste la sesión cuando el almacén durable está disponible. [Código, línea 268](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L268)
  Firma: `_guardar_sesion(clave_sesion, **kwargs)`.

- `_obtener_sesion` — Obtiene la sesión validada desde la cookie y retira sesiones caducadas. [Código, línea 293](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L293)
  Firma: `_obtener_sesion(request: FastAPIRequest)`.

- `_validar_sesion` — Devuelve sesión o error de acceso para las funciones compatibles. [Código, línea 307](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L307)
  Firma: `_validar_sesion(request: FastAPIRequest, requiere_api_key=True)`.

- `login` — Emite estado/PKCE y redirige a Google; el frontend actual llega aquí por /auth/start después de comprobar salud. [Código, línea 327](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L327)
  Firma: `login()`.
  Rutas/decoradores HTTP: `fastapi_app.get('/login')`.

- `auth_callback` — Consume estado una vez, intercambia el código, valida cuenta y crea cookie/sesión segura antes de volver al frontend. [Código, línea 352](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L352)
  Firma: `auth_callback(request: FastAPIRequest)`.
  Rutas/decoradores HTTP: `fastapi_app.get('/auth/callback')`.

- `logout` — Revoca la sesión y elimina la cookie mediante una solicitud explícita. [Código, línea 412](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L412)
  Firma: `logout(request: FastAPIRequest)`.
  Rutas/decoradores HTTP: `fastapi_app.post('/logout')`.

- `_get_drive_service` — Construye el cliente Drive con las credenciales del usuario autenticado. [Código, línea 424](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L424)
  Firma: `_get_drive_service(sesion)`.

- `_get_sheets_service` — Construye el cliente Sheets con la misma conexión Google de la sesión. [Código, línea 439](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L439)
  Firma: `_get_sheets_service(sesion)`.

- `_buscar_o_crear_carpeta` — Resuelve o crea una carpeta en el flujo histórico de preparación; no usar como lectura de taxonomía. [Código, línea 451](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L451)
  Firma: `_buscar_o_crear_carpeta(service, nombre, parent_id=None)`.

- `_buscar_archivo` — Busca un archivo existente por nombre, carpeta y tipo MIME. [Código, línea 466](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L466)
  Firma: `_buscar_archivo(service, nombre, parent_id, mime_type=None)`.

- `_buscar_inventario_importable` — Encuentra el XLSX/ODS/CSV entregado dentro de la carpeta del cliente. [Código, línea 475](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L475)
  Firma: `_buscar_inventario_importable(service, parent_id)`.

- `_convertir_inventario_importable` — Convierte el archivo subido a una hoja nativa sin borrar el original. [Código, línea 501](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L501)
  Firma: `_convertir_inventario_importable(service, carpeta_raiz_id)`.

- `_validar_inventario_preparado` — Verifica la tabla canónica antes de permitir que la carpeta quede activa. [Código, línea 530](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L530)
  Firma: `_validar_inventario_preparado(sheets_service, spreadsheet_id)`.

- `_obtener_gid_inventario` — Devuelve el sheetId de 'Gabo nueva'; crea o renombra la pestaña si hace falta. [Código, línea 552](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L552)
  Firma: `_obtener_gid_inventario(sheets_service, spreadsheet_id)`.

- `_aplicar_formato_base` — Replica la estructura visual principal de la pestaña 'Gabo nueva'. [Código, línea 587](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L587)
  Firma: `_aplicar_formato_base(sheets_service, spreadsheet_id, sheet_gid, agregar_reglas=False)`.

- `_aplicar_formato_filas` — Formatea únicamente las filas pobladas; inicio/fin son índices base cero. [Código, línea 695](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L695)
  Firma: `_aplicar_formato_filas(sheets_service, spreadsheet_id, sheet_gid, inicio, fin)`.

- `_limpiar_valor_sheet` — Convierte celdas vacías/NaN y valores escalares al formato compatible con Sheets. [Código, línea 784](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L784)
  Firma: `_limpiar_valor_sheet(valor)`.

- `_fila_formato_gabo` — Convierte un diccionario/Series al orden exacto de 'Gabo nueva'. [Código, línea 798](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L798)
  Firma: `_fila_formato_gabo(registro)`.

- `_obtener_o_crear_gid_lista_variable` — Resuelve la pestaña canónica 'Lista Variable' sin duplicar variantes de mayúsculas. [Código, línea 821](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L821)
  Firma: `_obtener_o_crear_gid_lista_variable(sheets_service, spreadsheet_id)`.

- `_variante_desde_nombre` — Fallback conservador para nuevas variantes; nunca modifica el nombre o descripciones. [Código, línea 859](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L859)
  Firma: `_variante_desde_nombre(nombre)`.

- `_normalizar_fila_variable` — Ajusta una fila de variantes al número/orden de columnas aceptados. [Código, línea 876](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L876)
  Firma: `_normalizar_fila_variable(fila)`.

- `_fila_variable_desde_gabo` — Mapea campos por posición, sin resumir ni alterar nombres o descripciones. [Código, línea 882](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L882)
  Firma: `_fila_variable_desde_gabo(fila_gabo, variante='')`.

- `_aplicar_formato_lista_variable` — Extiende el formato existente a la columna etiquetas y a filas recién añadidas. [Código, línea 902](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L902)
  Firma: `_aplicar_formato_lista_variable(sheets_service, spreadsheet_id, sheet_gid, filas_pobladas, hoja_nueva=False)`.

- `_sincronizar_lista_variable` — Sincroniza por SKU desde 'Gabo nueva'. [Código, línea 993](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L993)
  Firma: `_sincronizar_lista_variable(sheets_service, spreadsheet_id, registro_nuevo=None, crear_desde_variables=False)`.

- `_crear_o_encontrar_inventario` — Resuelve la hoja existente o la prepara explícitamente en el flujo histórico de selección de carpeta. [Código, línea 1096](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L1096)
  Firma: `_crear_o_encontrar_inventario(service, sheets_service, carpeta_raiz_id)`.

- `_leer_csv_legacy` — Descarga y lee el CSV histórico como tabla; no es el lector actual de taxonomía. [Código, línea 1130](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L1130)
  Firma: `_leer_csv_legacy(service, csv_id)`.

- `_migrar_csv_legacy` — Copia una vez el CSV anterior al nuevo Sheet; conserva el CSV como respaldo. [Código, línea 1146](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L1146)
  Firma: `_migrar_csv_legacy(service, sheets_service, carpeta_raiz_id, spreadsheet_id, sheet_gid)`.

- `_preparar_estructura` — Prepara la estructura histórica Drive/Sheets; puede escribir, por eso la clasificación usa un lector separado. [Código, línea 1165](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L1165)
  Firma: `_preparar_estructura(service, sesion=None)`.

- `_extraer_folder_id` — Extrae un ID de carpeta de una URL Drive o de un ID introducido por el usuario. [Código, línea 1218](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L1218)
  Firma: `_extraer_folder_id(texto)`.

- `_leer_google_sheet` — Lee filas de la hoja canónica mediante Sheets y las devuelve como tabla por encabezados. [Código, línea 1233](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L1233)
  Firma: `_leer_google_sheet(sheets_service, spreadsheet_id)`.

- `_agregar_fila_google_sheet` — Añade una fila del guardado histórico respetando columnas y sincronización existente. [Código, línea 1251](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L1251)
  Firma: `_agregar_fila_google_sheet(sesion, spreadsheet_id, registro)`.

- `_cargar_df` — Obtiene el inventario compatible de la sesión; puede preparar estructura, no sirve para una lectura sin escrituras. [Código, línea 1279](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L1279)
  Firma: `_cargar_df(sesion)`.

- `_subir_imagen_drive` — Sube/actualiza una imagen identificada en la carpeta prevista y conserva su checksum. [Código, línea 1286](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L1286)
  Firma: `_subir_imagen_drive(service, carpeta_imagenes_id, nombre_archivo, ruta_local)`.

- `_cargar_logo_marca` — Descarga y prepara la marca oficial usada por la composición de imágenes. [Código, línea 1308](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L1308)
  Firma: `_cargar_logo_marca(service, logo_id)`.

- `limpiar_texto_sku` — Normaliza caracteres de un segmento del SKU histórico de respaldo. [Código, línea 1329](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L1329)
  Firma: `limpiar_texto_sku(texto)`.

- `generar_sku_logica` — Respaldo aceptado de diez caracteres: marca 3, nombre 3 y gramaje 4; se usa cuando no hay código válido. [Código, línea 1338](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L1338)
  Firma: `generar_sku_logica(nombre, marca, gramaje)`.

- `comprimir_imagen` — Corrige orientación y reduce la foto al límite del flujo compatible. [Código, línea 1351](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L1351)
  Firma: `comprimir_imagen(img_array, max_size=1024)`.

- `estampar_logo` — Aplica la marca mediante la composición aceptada y guarda el resultado. [Código, línea 1358](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L1358)
  Firma: `estampar_logo(ruta_imagen, service, logo_id)`.

- `_extraer_json` — Extrae JSON de una respuesta de texto del flujo histórico. [Código, línea 1368](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L1368)
  Firma: `_extraer_json(texto_raw)`.

- `_extraer_imagen_bytes` — Saca los bytes de la imagen de la respuesta del modelo. (response.parts no existe: hay que recorrer candidates -> content -> parts) [Código, línea 1376](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L1376)
  Firma: `_extraer_imagen_bytes(response)`.

- `_imagen_para_ia` — Small inline reference: avoids an extra Files API upload per call. [Código, línea 1391](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L1391)
  Firma: `_imagen_para_ia(path)`.

- `estimar_precio_producto` — Usa Gemini + Búsqueda de Google (con la API key del usuario) para investigar el precio real de mercado del producto y sugerir un precio de venta. [Código, línea 1399](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L1399)
  Firma: `estimar_precio_producto(nombre, marca, gramaje, categoria, api_key)`.

- `_obtener_vocabulario_etiquetas` — Junta todas las etiquetas ya usadas en el inventario (la columna guarda varias por celda, separadas por coma) en una lista única, sin repetidos. [Código, línea 1426](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L1426)
  Firma: `_obtener_vocabulario_etiquetas(df)`.

- `_vocabulario_relevante` — Selecciona etiquetas del vocabulario existente relevantes al contexto del producto. [Código, línea 1440](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L1440)
  Firma: `_vocabulario_relevante(vocabulario, contexto, limite=80)`.

- `estimar_etiquetas_producto` — Si ya existen etiquetas en el catálogo, la IA SOLO puede elegir entre esas (nada de inventar nuevas). Si el catálogo todavía no tiene ninguna, la IA propone unas pocas para empezar a construir el vocabulario. [Código, línea 1445](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L1445)
  Firma: `estimar_etiquetas_producto(nombre, marca, categoria, subcategoria, descripcion, vocabulario, api_key)`.

- `recalcular_etiquetas_ui` — Recalcula la propuesta de etiquetas desde el inventario y los campos actuales. [Código, línea 1487](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L1487)
  Firma: `recalcular_etiquetas_ui(nombre, marca, categoria, subcategoria, descripcion, request: FastAPIRequest)`.

- `buscar_variantes_por_imagen` — Búsqueda tipo Google Lens: sube la foto del producto y usa Gemini (visión + Búsqueda de Google) para detectar si el MISMO producto existe en otros gramajes/tamaños en el mercado. [Código, línea 1497](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L1497)
  Firma: `buscar_variantes_por_imagen(imagen, nombre_actual, marca_actual, request: FastAPIRequest)`.

- `investigar_prompts` — Delega la investigación creativa al pipeline y conserva su brief de respaldo. [Código, línea 1571](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L1571)
  Firma: `investigar_prompts(producto, marca, desc, api_key)`.

- `_rutas_referencia` — Acepta una foto (versiones anteriores) o frontal+reverso (versión actual). [Código, línea 1580](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L1580)
  Firma: `_rutas_referencia(ruta_base)`.

- `_configuracion_imagen_cuadrada` — Fuerza 1:1 en la API; conserva compatibilidad con SDKs antiguos. [Código, línea 1587](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L1587)
  Firma: `_configuracion_imagen_cuadrada()`.

- `_contrato_visual` — Resuelve las reglas visuales del slot de imagen existente. [Código, línea 1598](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L1598)
  Firma: `_contrato_visual(slot)`.

- `_validacion_local_imagen` — Comprueba formato/contenido local de una imagen antes de aceptarla. [Código, línea 1608](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L1608)
  Firma: `_validacion_local_imagen(ruta_imagen)`.

- `_validar_con_vision` — Un segundo pase de visión actúa como control de calidad antes de subir a Drive. [Código, línea 1628](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L1628)
  Firma: `_validar_con_vision(client, archivos_referencia, ruta_generada, slot)`.

- `generar_foto_individual` — Genera, compara contra la referencia y reintenta antes de guardar una imagen. [Código, línea 1671](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L1671)
  Firma: `generar_foto_individual(prompt, ruta_base, ruta_salida_local, api_key, service, logo_id, slot, correccion='')`.

- `modulo_extraer_textos` — Analiza fotos para extraer ficha, código y clasificación en el flujo compatible. [Código, línea 1773](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L1773)
  Firma: `modulo_extraer_textos(imagen_1, imagen_2, descripcion_breve, request: FastAPIRequest)`.

- `_rehacer_generico` — Núcleo compartido: arma la corrección, genera un borrador y devuelve (ruta_imagen, historial_actualizado, mensaje). [Código, línea 1876](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L1876)
  Firma: `_rehacer_generico(slot, prompt, ruta_base, sku, errores, feedback, historial, sesion)`.

- `rehacer_hd` — Corrige el slot limpio HD usando el prompt protegido y el feedback histórico. [Código, línea 1918](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L1918)
  Firma: `rehacer_hd(ruta_base, sku, errores, feedback, historial, request: FastAPIRequest)`.

- `rehacer_life` — Corrige el slot de uso/lifestyle con brief y feedback existentes. [Código, línea 1927](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L1927)
  Firma: `rehacer_life(ruta_base, sku, nombre, marca, desc, errores, feedback, historial, request: FastAPIRequest)`.

- `rehacer_comercial` — Corrige el slot comercial con brief y feedback existentes. [Código, línea 1937](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L1937)
  Firma: `rehacer_comercial(ruta_base, sku, nombre, marca, desc, errores, feedback, historial, request: FastAPIRequest)`.

- `modulo_generar_todo` — Primera pasada: sin correcciones y reseteando el historial de feedback. [Código, línea 1947](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L1947)
  Firma: `modulo_generar_todo(ruta_base, sku, nombre, marca, desc, request: FastAPIRequest)`.

- `guardar_producto_sheet` — Guarda la ficha confirmada con su tipo, padre y campos en el inventario histórico. [Código, línea 1976](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L1976)
  Firma: `guardar_producto_sheet(sku, tipo, sku_padre, nombre, marca, gramaje, atributo_nombre, atributo_valor, precio, cat, subcat, etiquetas, desc_corta, desc_larga, request: FastAPIRequest)`.

- `detectar_padre` — Busca en TU inventario ya guardado (no en internet) un producto existente parecido a este, para detectar de cuál SKU es variante. Si primero filtramos por la misma marca, la comparación de nombres es más precisa (dos productos de marcas distintas con nombres parecidos ya no se confunden entre sí). [Código, línea 2026](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L2026)
  Firma: `detectar_padre(nombre_actual, marca_actual, request: FastAPIRequest)`.

- `cambio_tipo_ui` — Actualiza campos de relación simple/variante y consulta padres cuando corresponde. [Código, línea 2067](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L2067)
  Firma: `cambio_tipo_ui(tipo_seleccionado, nombre_actual, marca_actual, request: FastAPIRequest)`.

- `aplicar_recomendacion_tipo` — Se dispara directo desde el botón 'Aplicar recomendación' de la pestaña Lens. A diferencia de antes, esto YA busca el SKU padre de inmediato en vez de esperar a que el cambio de valor de in_tipo dispare otro evento por su cuenta. [Código, línea 2074](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L2074)
  Firma: `aplicar_recomendacion_tipo(tipo_recomendado, nombre_actual, marca_actual, request: FastAPIRequest)`.

- `recalcular_sku_ui` — Recalcula el respaldo de SKU con generar_sku_logica, sin cambiar su algoritmo. [Código, línea 2084](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L2084)
  Firma: `recalcular_sku_ui(nombre, marca, gramaje)`.

- `recalcular_precio_ui` — Obtiene la propuesta de precio desde los campos y clave personal vigentes. [Código, línea 2088](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L2088)
  Firma: `recalcular_precio_ui(nombre, marca, gramaje, categoria, request: FastAPIRequest)`.

- `obtener_categorias` — Lee categorías del inventario para el flujo histórico; el selector React actual usa catalog_taxonomy. [Código, línea 2096](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L2096)
  Firma: `obtener_categorias(request: FastAPIRequest)`.

- `obtener_subcategorias` — Lee subcategorías del inventario para el flujo histórico. [Código, línea 2108](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L2108)
  Firma: `obtener_subcategorias(request: FastAPIRequest)`.

- `_estado_login_html` — Construye el estado de acceso/configuración de las herramientas históricas. [Código, línea 2123](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L2123)
  Firma: `_estado_login_html(request: FastAPIRequest)`.

- `cargar_estado_inicial` — Carga sesión, clasificación y controles iniciales del flujo compatible. [Código, línea 2149](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L2149)
  Firma: `cargar_estado_inicial(request: FastAPIRequest)`.

- `guardar_api_key` — Guarda la clave Gemini en la sesión/configuración compatible sin imprimirla. [Código, línea 2164](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L2164)
  Firma: `guardar_api_key(api_key_input, request: FastAPIRequest)`.

- `refrescar_categorias` — Actualiza los controles históricos con categorías/subcategorías leídas. [Código, línea 2187](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L2187)
  Firma: `refrescar_categorias(request: FastAPIRequest)`.

- `guardar_carpeta_personalizada` — Valida y selecciona la carpeta de proyecto con preparación histórica explícita. [Código, línea 2191](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L2191)
  Firma: `guardar_carpeta_personalizada(texto_carpeta, request: FastAPIRequest)`.

- `limpiar_feedback` — Después de mandar el feedback, limpia los checkboxes y el texto libre (el historial se conserva en el State). [Código, línea 2260](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app.py#L2260)
  Firma: `limpiar_feedback()`.

## app_security.py

Protección HTTP: Host/origen, sesión, límites de solicitudes y errores sin secretos.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app_security.py)

- `clean_html` — Sanea HTML de textos de producto antes de publicarlos o mostrarlos. [Código, línea 22](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app_security.py#L22)
  Firma: `clean_html(value)`.

- `validate_service_url` — Valida destinos de servicio para evitar enviar credenciales a un origen no autorizado. [Código, línea 28](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app_security.py#L28)
  Firma: `validate_service_url(url)`.

- `checked_image_type` — Comprueba contenido y tipo real de imagen, independientemente del nombre del archivo. [Código, línea 46](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app_security.py#L46)
  Firma: `checked_image_type(filename, data)`.

- `public_error` — Resume errores externos y elimina URLs/tokens/datos que no deben exponerse al usuario. [Código, línea 72](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app_security.py#L72)
  Firma: `public_error(exc)`.

- `WindowLimiter` — Contador local por ventana temporal para limitar solicitudes de un mismo ámbito. [Código, línea 85](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app_security.py#L85)

- `WindowLimiter.__init__` — Configura ventana y estructura de conteo local del proceso. [Código, línea 87](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app_security.py#L87)
  Firma: `WindowLimiter.__init__(self, maximum=4096)`.

- `WindowLimiter.allow` — Decide si la solicitud cabe en el límite vigente. [Código, línea 93](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app_security.py#L93)
  Firma: `WindowLimiter.allow(self, key, limit, seconds=60)`.

- `SecurityMiddleware` — Valida Host/origen y límites, restaura sesión fuera del bucle asíncrono y aplica cabeceras sin caché privada. [Código, línea 110](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app_security.py#L110)

- `SecurityMiddleware.__init__` — Recibe almacén de sesiones, revocación y restauración durable. [Código, línea 112](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app_security.py#L112)
  Firma: `SecurityMiddleware.__init__(self, app, sessions=lambda: {}, expire=None, restore=None)`.

- `SecurityMiddleware.__call__` — Protege cada solicitud; un fallo temporal al restaurar SQL devuelve 503 sin cerrar la sesión del navegador. [Código, línea 121](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app_security.py#L121)
  Firma: `SecurityMiddleware.__call__(self, scope, receive, send)`.

- `SecurityMiddleware.__call__.secure_send` — Añade cabeceras de seguridad y no-store a las respuestas privadas. [Código, línea 135](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app_security.py#L135)
  Firma: `SecurityMiddleware.__call__.secure_send(message)`.

- `SecurityMiddleware.__call__.buffered` — Entrega al siguiente componente el cuerpo HTTP ya recibido y limitado. [Código, línea 212](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/app_security.py#L212)
  Firma: `SecurityMiddleware.__call__.buffered()`.

## catalog_platform/accounts.py

Conexiones cifradas por carpeta y usuario, preferencias personales y clave Gemini del usuario.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/accounts.py)

- `account` — Busca una conexión por tenant, correo normalizado y proveedor. [Código, línea 13](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/accounts.py#L13)
  Firma: `account(db, tenant, actor, provider)`.

- `put` — Serializa la actualización de conexión y cifra sus datos antes de almacenarlos. [Código, línea 21](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/accounts.py#L21)
  Firma: `put(db, tenant, actor, provider, data, status='connected')`.

- `gemini_for` — Devuelve únicamente la clave Gemini personal de una conexión vigente del usuario. [Código, línea 33](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/accounts.py#L33)
  Firma: `gemini_for(db, tenant, actor)`.

- `profile_tenant` — Deriva una clave estable de preferencias personales a partir del correo normalizado. [Código, línea 41](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/accounts.py#L41)
  Firma: `profile_tenant(actor)`.

- `save_gemini` — Guarda la clave personal en la carpeta seleccionada y conserva esa carpeta en el perfil. [Código, línea 46](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/accounts.py#L46)
  Firma: `save_gemini(db, tenant, actor, key, folder_name='')`.

- `save_profile` — Persiste la carpeta elegida por el usuario para restaurarla en una sesión posterior. [Código, línea 54](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/accounts.py#L54)
  Firma: `save_profile(db, tenant, actor, folder_name='')`.

- `delete_gemini` — Marca la conexión como desconectada; un snapshot antiguo no debe recuperar una clave eliminada. [Código, línea 61](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/accounts.py#L61)
  Firma: `delete_gemini(db, tenant, actor)`.

- `restore` — Relee perfil y clave personal en cada solicitud; no utiliza una clave global como respaldo. [Código, línea 67](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/accounts.py#L67)
  Firma: `restore(value)`.

- `persist` — Guarda las credenciales Drive cifradas para que el worker pueda actuar sin el navegador. [Código, línea 102](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/accounts.py#L102)
  Firma: `persist(db, tenant, actor, value)`.

- `load` — Reconstruye la conexión del actor para un trabajo; excluye claves globales presentes en snapshots antiguos. [Código, línea 115](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/accounts.py#L115)
  Firma: `load(db, tenant, actor)`.

## catalog_platform/api.py

Rutas del catálogo SQL, inventario, generación, cancelación, revisión, importación y publicación.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py)

- `context` — Resuelve sesión, conexión, credenciales personales y carpeta autorizada antes de operar el catálogo. [Código, línea 41](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L41)
  Firma: `context(request: Request)`.

- `tenant` — Obtiene la carpeta que delimita los datos de esta solicitud. [Código, línea 91](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L91)
  Firma: `tenant(value)`.

- `actor` — Obtiene el correo autenticado que queda en trabajos y auditoría. [Código, línea 96](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L96)
  Firma: `actor(value)`.

- `edit` — Exige rol admin o editor para una escritura. [Código, línea 101](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L101)
  Firma: `edit(value)`.

- `admin` — Exige rol administrador para operaciones sensibles como eliminar o publicar. [Código, línea 106](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L106)
  Firma: `admin(value)`.

- `ProductInput` — Contrato de ficha editable; limita texto, atributos, etiquetas y versión recibidos por la API. [Código, línea 112](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L112)
  Campos declarados: `sku: str`, `barcode: str`, `name: str`, `brand: str`, `category: str`, `subcategory: str`, `short_description: str`, `long_description: str`, `tags: list[str]`, `attributes: dict`, `product_type: str`, `parent_id: str | None`, `price: float | None`, `cost: float | None`, `stock: float | None`, `version: int | None`.

- `ProductInput.bounded_attributes` — Limita la estructura y tamaño de atributos para evitar payloads descontrolados. [Código, línea 135](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L135)
  Firma: `ProductInput.bounded_attributes(cls, value)`.

- `ProductInput.bounded_tags` — Limita cantidad y longitud de etiquetas del producto. [Código, línea 153](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L153)
  Firma: `ProductInput.bounded_tags(cls, value)`.

- `BatchInput` — Selección de productos, slots, cantidad y revisión automática para una cotización/lote. [Código, línea 160](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L160)
  Campos declarados: `product_ids: list[str]`, `category: str | None`, `pending: bool`, `slots: list[str]`, `quantity: int`, `quality: str`, `automatic_review: bool`.

- `EnqueueInput` — Añade confirmación, request_key y token de estimación a la selección que se enviará al worker. [Código, línea 176](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L176)
  Campos declarados: `request_key: str`, `estimate_token: str`, `confirm: bool`.

- `ReviewInput` — Contrato del estado/rol de imagen que el usuario revisa. [Código, línea 183](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L183)
  Campos declarados: `status: str`, `role: str`.

- `CorrectionInput` — Feedback y autorización de coste para corregir un candidato. [Código, línea 191](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L191)
  Campos declarados: `feedback: str`, `confirm_cost: bool`, `request_key: str`.

- `StockInput` — Cantidad y datos de un movimiento de inventario. [Código, línea 198](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L198)
  Campos declarados: `quantity: float`, `event_id: str`, `version: int`, `reason: str`.

- `ConfirmInput` — Confirmación explícita requerida para una operación. [Código, línea 206](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L206)
  Campos declarados: `confirm: bool`.

- `DeleteProductInput` — Confirmación y versión esperada de la ficha que se va a retirar. [Código, línea 211](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L211)
  Campos declarados: `version: int`.

- `CancelJobsInput` — Confirmación y lista limitada a 100 IDs; no interpreta Detener todos como una consulta abierta. [Código, línea 217](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L217)
  Campos declarados: `job_ids: list[str]`.

- `status` — Describe configuración, rol y disponibilidad real/capacidad de cola; distingue worker activo de worker despertable. [Código, línea 224](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L224)
  Firma: `status(request: Request)`.
  Rutas/decoradores HTTP: `router.get('/status')`.

- `products` — Lista y filtra fichas visibles por tenant con paginación; omite eliminadas. [Código, línea 265](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L265)
  Firma: `products(q: str='', filter: str='all', offset: int=0, limit: int=50, value=Depends(context))`.
  Rutas/decoradores HTTP: `router.get('/products')`.

- `create_product` — Crea una ficha validada en SQL y registra su auditoría; no publica automáticamente en WooCommerce. [Código, línea 323](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L323)
  Firma: `create_product(data: ProductInput, value=Depends(context))`.
  Rutas/decoradores HTTP: `router.post('/products', status_code=201)`.

- `get_product` — Devuelve ficha, variantes, imágenes, trabajos, movimientos y eventos del producto autorizado. [Código, línea 346](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L346)
  Firma: `get_product(product_id: str, value=Depends(context))`.
  Rutas/decoradores HTTP: `router.get('/products/{product_id}')`.

- `get_product.related` — Consulta registros relacionados del producto dentro del mismo tenant para construir su ficha. [Código, línea 350](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L350)
  Firma: `get_product.related(model)`.

- `update_product` — Guarda cambios de ficha con versión esperada y auditoría; no reemplaza una edición concurrente. [Código, línea 386](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L386)
  Firma: `update_product(product_id: str, data: ProductInput, value=Depends(context))`.
  Rutas/decoradores HTTP: `router.put('/products/{product_id}')`.

- `delete_product` — Retira solo la ficha de la app: bloquea fila, valida versión/familia/trabajos, guarda tombstone y libera SKU sin borrar Drive o WooCommerce. [Código, línea 408](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L408)
  Firma: `delete_product(product_id: str, data: DeleteProductInput, value=Depends(context))`.
  Rutas/decoradores HTTP: `router.delete('/products/{product_id}')`.

- `inventory_change` — Registra un movimiento local identificado y su auditoría. [Código, línea 451](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L451)
  Firma: `inventory_change(product_id: str, data: StockInput, value=Depends(context))`.
  Rutas/decoradores HTTP: `router.post('/products/{product_id}/stock')`.

- `ReferenceInput` — Identifica un upload temporal propio que se usará como referencia o para leer un código. [Código, línea 496](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L496)
  Campos declarados: `upload_id: str`.

- `reference` — Asocia una referencia de imagen autorizada al producto; valida pertenencia y límites. [Código, línea 502](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L502)
  Firma: `reference(product_id: str, data: ReferenceInput, value=Depends(context))`.
  Rutas/decoradores HTTP: `router.post('/products/{product_id}/reference')`.

- `image` — Sirve una imagen privada del producto desde Drive mediante la sesión autorizada. [Código, línea 557](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L557)
  Firma: `image(image_id: str, download: bool=False, value=Depends(context))`.
  Rutas/decoradores HTTP: `router.get('/images/{image_id}')`.

- `selection` — Resuelve exactamente los productos y variantes que se van a cotizar; excluye padres y eliminados. [Código, línea 588](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L588)
  Firma: `selection(db, value, data, lock=False)`.

- `image_unit` — Obtiene el coste estimado por imagen del modelo configurado. [Código, línea 643](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L643)
  Firma: `image_unit(model)`.

- `estimate` — Calcula cantidad/coste y vincula la cotización a selección, modelo y versiones. [Código, línea 661](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L661)
  Firma: `estimate(db, value, data, lock=False)`.

- `guard_cost` — Valida confirmación, límites y token de cotización antes de aceptar una operación pagada. [Código, línea 693](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L693)
  Firma: `guard_cost(cost)`.

- `generation_estimate` — Devuelve una cotización para revisión; no genera imágenes. [Código, línea 711](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L711)
  Firma: `generation_estimate(data: BatchInput, value=Depends(context))`.
  Rutas/decoradores HTTP: `router.post('/generation/estimate')`.

- `enqueue` — Crea lote y trabajos durables con idempotencia, snapshot y confirmación de gasto. [Código, línea 719](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L719)
  Firma: `enqueue(data: EnqueueInput, value=Depends(context))`.
  Rutas/decoradores HTTP: `router.post('/generation/jobs', status_code=202)`.

- `batches` — Lista los lotes de generación del catálogo autorizado. [Código, línea 809](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L809)
  Firma: `batches(value=Depends(context))`.
  Rutas/decoradores HTTP: `router.get('/generation/batches')`.

- `jobs` — Lista estados y progreso de trabajos; incluye actor para mostrar permisos de cancelación. [Código, línea 825](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L825)
  Firma: `jobs(value=Depends(context))`.
  Rutas/decoradores HTTP: `router.get('/jobs')`.

- `cancel_locked` — Valida permisos del actor y aplica la cancelación de una fila bloqueada con una sola entrada de auditoría. [Código, línea 842](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L842)
  Firma: `cancel_locked(db, job, value)`.

- `cancel_job` — Detiene un trabajo confirmado del tenant; una solicitud repetida conserva el mismo resultado. [Código, línea 859](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L859)
  Firma: `cancel_job(job_id: str, data: ConfirmInput, value=Depends(context))`.
  Rutas/decoradores HTTP: `router.post('/jobs/{job_id}/cancel')`.

- `cancel_jobs` — Detiene únicamente los IDs confirmados y revierte el lote entero si falla alguna autorización. [Código, línea 877](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L877)
  Firma: `cancel_jobs(data: CancelJobsInput, value=Depends(context))`.
  Rutas/decoradores HTTP: `router.post('/jobs/cancel')`.

- `assets` — Lista candidatos de imagen y estados de revisión de fichas visibles. [Código, línea 893](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L893)
  Firma: `assets(value=Depends(context))`.
  Rutas/decoradores HTTP: `router.get('/assets')`.

- `review` — Cambia la aprobación/rechazo del candidato y registra auditoría; conserva un job Cancelado o Deteniendo. [Código, línea 918](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L918)
  Firma: `review(asset_id: str, data: ReviewInput, value=Depends(context))`.
  Rutas/decoradores HTTP: `router.post('/assets/{asset_id}/review')`.

- `correct` — Encola una corrección con feedback, referencia anterior y confirmación de coste; conserva el asset previo. [Código, línea 990](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L990)
  Firma: `correct(asset_id: str, data: CorrectionInput, value=Depends(context))`.
  Rutas/decoradores HTTP: `router.post('/assets/{asset_id}/correct', status_code=202)`.

- `RegenerationInput` — Clave idempotente y confirmación de coste para una regeneración. [Código, línea 1062](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L1062)
  Campos declarados: `confirm_cost: bool`, `request_key: str`.

- `regenerate` — Encola un nuevo candidato con referencias del producto y coste confirmado. [Código, línea 1069](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L1069)
  Firma: `regenerate(asset_id: str, data: RegenerationInput, value=Depends(context))`.
  Rutas/decoradores HTTP: `router.post('/assets/{asset_id}/regenerate', status_code=202)`.

- `PublishInput` — Confirmación y request_key idempotente de publicación/operación. [Código, línea 1093](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L1093)
  Campos declarados: `confirm: bool`, `request_key: str`.

- `save_generated_asset` — Encola el guardado explícito de un candidato aprobado; no lo publica por sí solo en la tienda. [Código, línea 1101](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L1101)
  Firma: `save_generated_asset(asset_id: str, data: PublishInput, value=Depends(context))`.
  Rutas/decoradores HTTP: `router.post('/assets/{asset_id}/save', status_code=202)`.

- `publish` — Encola publicación WooCommerce con permisos, flags y snapshot/versiones comprobados. [Código, línea 1118](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L1118)
  Firma: `publish(product_id: str, data: PublishInput, value=Depends(context))`.
  Rutas/decoradores HTTP: `router.post('/products/{product_id}/publish', status_code=202)`.

- `dashboard` — Resume catálogo visible, trabajos, actividad y últimos snapshots reales de pedidos. [Código, línea 1179](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L1179)
  Firma: `dashboard(value=Depends(context))`.
  Rutas/decoradores HTTP: `router.get('/dashboard')`.

- `dashboard.count` — Cuenta registros bajo filtros del dashboard sin mezclar tenants o productos retirados. [Código, línea 1182](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L1182)
  Firma: `dashboard.count(model, *rules)`.

- `events` — Lista historial de sincronizaciones del tenant. [Código, línea 1259](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L1259)
  Firma: `events(value=Depends(context))`.
  Rutas/decoradores HTTP: `router.get('/events')`.

- `connections` — Describe estados de integración sin exponer credenciales. [Código, línea 1276](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L1276)
  Firma: `connections(value=Depends(context))`.
  Rutas/decoradores HTTP: `router.get('/connections')`.

- `ecommerce_refresh` — Encola una consulta de tienda, diferenciada de una importación completa. [Código, línea 1335](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L1335)
  Firma: `ecommerce_refresh(data: PublishInput, value=Depends(context))`.
  Rutas/decoradores HTTP: `router.post('/ecommerce/refresh', status_code=202)`.

- `import_woocommerce` — Encola una importación explícita WooCommerce con confirmación y respaldo. [Código, línea 1344](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L1344)
  Firma: `import_woocommerce(data: PublishInput, value=Depends(context))`.
  Rutas/decoradores HTTP: `router.post('/import/woocommerce', status_code=202)`.

- `enqueue_operation` — Crea una operación durable e idempotente y persiste la conexión del actor antes de entregarla. [Código, línea 1355](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L1355)
  Firma: `enqueue_operation(value, kind, request_key, payload, product_id=None, model='', estimated_cost=None)`.

- `preview_sheet` — Previsualiza filas de inventario Sheets sin confirmar su importación al catálogo. [Código, línea 1419](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L1419)
  Firma: `preview_sheet(value=Depends(context))`.
  Rutas/decoradores HTTP: `router.post('/import/sheets')`.

- `preview_file` — Valida y previsualiza un CSV/XLSX recibido antes de autorizar la importación. [Código, línea 1449](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L1449)
  Firma: `preview_file(source: UploadFile=File(), value=Depends(context))`.
  Rutas/decoradores HTTP: `router.post('/import/file')`.

- `ImportConfirm` — Referencia de la previsualización/importación que el usuario confirma. [Código, línea 1483](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L1483)
  Campos declarados: `preview_id: str`.

- `commit_import` — Confirma la importación revisada y crea el trabajo correspondiente. [Código, línea 1489](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L1489)
  Firma: `commit_import(data: ImportConfirm, value=Depends(context))`.
  Rutas/decoradores HTTP: `router.post('/import/commit', status_code=202)`.

- `RetryInput` — Confirmación explícita del reintento de un trabajo existente. [Código, línea 1544](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L1544)
  Campos declarados: `uncertainty_reviewed: bool`.

- `retry` — Exige una decisión explícita antes de repetir un fallo; conserva protección de resultados inciertos y deduplicación. [Código, línea 1551](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L1551)
  Firma: `retry(job_id: str, data: RetryInput, value=Depends(context))`.
  Rutas/decoradores HTTP: `router.post('/jobs/{job_id}/retry', status_code=202)`.

- `reference_from_image` — Convierte una imagen autorizada existente en referencia del producto. [Código, línea 1588](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L1588)
  Firma: `reference_from_image(product_id: str, image_id: str, value=Depends(context))`.
  Rutas/decoradores HTTP: `router.post('/products/{product_id}/reference-from-image/{image_id}')`.

- `export` — Entrega CSV o XLSX del catálogo visible; no modifica el inventario conectado. [Código, línea 1635](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L1635)
  Firma: `export(format: str='csv', value=Depends(context))`.
  Rutas/decoradores HTTP: `router.get('/export')`.

- `enrich_product` — Encola una propuesta IA de textos y clasificación para revisión. [Código, línea 1689](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L1689)
  Firma: `enrich_product(product_id: str, data: PublishInput, value=Depends(context))`.
  Rutas/decoradores HTTP: `router.post('/products/{product_id}/enrich', status_code=202)`.

- `barcode` — Lee códigos de una fotografía autorizada; no cambia un producto por sí solo. [Código, línea 1724](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L1724)
  Firma: `barcode(data: ReferenceInput, value=Depends(context))`.
  Rutas/decoradores HTTP: `router.post('/barcode')`.

- `sync_stock` — Encola una escritura de stock confirmada sobre la entidad remota identificada. [Código, línea 1732](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L1732)
  Firma: `sync_stock(product_id: str, data: PublishInput, value=Depends(context))`.
  Rutas/decoradores HTTP: `router.post('/products/{product_id}/sync-stock', status_code=202)`.

- `approve_original` — Marca como revisada una referencia original, conservando permisos y auditoría. [Código, línea 1761](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/api.py#L1761)
  Firma: `approve_original(product_id: str, image_id: str, data: PublishInput, value=Depends(context))`.
  Rutas/decoradores HTTP: `router.post('/products/{product_id}/images/{image_id}/approve-original')`.

## catalog_platform/rbac.py

Middleware de permisos de lectura/escritura para API y herramientas compatibles.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/rbac.py)

- `RoleMiddleware` — Aplica permisos a solicitudes HTTP; ocultar un botón en React no reemplaza este control. [Código, línea 11](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/rbac.py#L11)

- `RoleMiddleware.__init__` — Recibe la aplicación y el acceso al almacén de sesiones. [Código, línea 13](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/rbac.py#L13)
  Firma: `RoleMiddleware.__init__(self, app, sessions)`.

- `RoleMiddleware.__call__` — Rechaza cuentas no autorizadas y escrituras de usuarios viewer, conservando las rutas públicas definidas. [Código, línea 18](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/rbac.py#L18)
  Firma: `RoleMiddleware.__call__(self, scope, receive, send)`.

## catalog_platform/render_config.py

Derivación del callback Google desde el dominio público cuando no hay uno explícito.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/render_config.py)

- `configure_redirect` — Conserva GOOGLE_REDIRECT_URI explícita o la deriva del origen público del frontend; evita que Google vuelva al dominio de API. [Código, línea 11](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/render_config.py#L11)
  Firma: `configure_redirect()`.

## catalog_platform/security.py

Cifrado de conexiones y comprobación de pertenencia/rol del usuario.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/security.py)

- `cipher` — Valida la clave de cifrado compartida; cambiarla sin migración impediría leer conexiones existentes. [Código, línea 11](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/security.py#L11)
  Firma: `cipher()`.

- `seal` — Cifra un objeto JSON antes de guardarlo como credenciales. [Código, línea 26](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/security.py#L26)
  Firma: `seal(data)`.

- `unseal` — Descifra y reconstruye una conexión; informa el fallo sin revelar su contenido. [Código, línea 31](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/security.py#L31)
  Firma: `unseal(data)`.

- `role_for` — Resuelve admin, editor o viewer desde la configuración y valida el formato del mapa de roles. [Código, línea 42](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/security.py#L42)
  Firma: `role_for(email)`.

- `member` — Comprueba la pertenencia del correo al catálogo autorizado. [Código, línea 58](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/security.py#L58)
  Firma: `member(email)`.

- `require_role` — Rechaza en servidor una operación si el usuario no pertenece al catálogo o carece del rol requerido. [Código, línea 72](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/security.py#L72)
  Firma: `require_role(value, *roles)`.

## catalog_platform/web_sessions.py

Sesiones de navegador cifradas en PostgreSQL; permite restaurarlas tras reiniciar la API.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/web_sessions.py)

- `_tenant` — Valida el identificador aleatorio de cookie y deriva su clave SHA-256; no almacena el identificador original. [Código, línea 24](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/web_sessions.py#L24)
  Firma: `_tenant(sid)`.

- `save` — Persiste cifrados correo, credenciales, vencimiento y espacio de archivos; no amplía la caducidad de sesión. [Código, línea 32](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/web_sessions.py#L32)
  Firma: `save(sid, value)`.

- `revoke` — Borra la sesión durable al cerrar sesión para invalidar también las copias en memoria. [Código, línea 44](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/web_sessions.py#L44)
  Firma: `revoke(sid)`.

- `restore` — Recupera una sesión vigente después de reiniciar la API y revalida caducidad, pertenencia, allowlist y preferencias personales. [Código, línea 55](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/web_sessions.py#L55)
  Firma: `restore(sid)`.

## google_credentials.py

Credenciales de servicio opcionales configuradas por entorno; no sustituye automáticamente al usuario.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/google_credentials.py)

- `dedicated_credentials` — Resuelve las credenciales de servicio opcionales definidas por entorno y sus scopes. [Código, línea 8](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/google_credentials.py#L8)
  Firma: `dedicated_credentials()`.

## oauth_guard.py

Estado OAuth y PKCE de un solo uso, con caducidad y lista de correos autorizados.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/oauth_guard.py)

- `issue_oauth` — Registra estado y verificador PKCE durante diez minutos, con límite de solicitudes pendientes; el registro es local al proceso API. [Código, línea 16](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/oauth_guard.py#L16)
  Firma: `issue_oauth(state, verifier)`.

- `consume_oauth` — Compara cookie y estado, consume el verificador una sola vez y rechaza estados caducados o reutilizados. [Código, línea 29](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/oauth_guard.py#L29)
  Firma: `consume_oauth(cookie_state, state)`.

- `email_allowed` — Comprueba la lista de acceso y, cuando se exige, los correos con rol configurado. [Código, línea 40](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/oauth_guard.py#L40)
  Firma: `email_allowed(email)`.

## service_entrypoint.py

Arranque de FastAPI: selecciona el rol, registra rutas y ordena los controles de sesión y permisos.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/service_entrypoint.py)

- `service_health` — Informa rol, versión y almacén de sesión sin consultar Drive ni ejecutar generación; no sustituye el heartbeat del worker. [Código, línea 34](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/service_entrypoint.py#L34)
  Firma: `service_health()`.
  Rutas/decoradores HTTP: `fastapi_app.get('/service-health')`.

## studio_api.py

API de captura: borrador, fotos, análisis, revisión y guardado; delega imágenes durables al worker.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py)

- `Product` — Ficha de captura validada: usa nombres históricos como nombre_producto y Marca; difiere del Product SQL. [Código, línea 44](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L44)
  Campos declarados: `sku: str`, `name: str`, `brand: str`, `size: str`, `kind: str`, `price: float`, `category: str`, `subcategory: str`, `tags: str`, `short_description: str`, `description: str`, `barcode: str`, `parent_sku: str`, `parent_name: str`, `parent_mode: str`, `attribute: str`, `attribute_value: str`, `product_type: str`, `variant: str`, `attributes: dict[Annotated[str, Field(max_length=80)], Annotated[str, Field(max_length=160)]]`, `uncertain_fields: list[Annotated[str, Field(max_length=120)]]`.

- `Capture` — Fotos frente/reverso y contexto que inician un borrador. [Código, línea 69](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L69)
  Campos declarados: `front_id: str`, `back_id: str | None`, `context: str`.

- `CaptureNotes` — Datos de notas/contexto modificables de una captura. [Código, línea 76](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L76)
  Campos declarados: `context: str`.

- `Generation` — Selección de slots y confirmación de coste de generación. [Código, línea 81](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L81)
  Campos declarados: `slots: list[str]`, `automatic_review: bool`, `request_key: str | None`, `confirm_cost: bool`.

- `Correction` — Errores/feedback y autorización de corrección de una imagen. [Código, línea 89](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L89)
  Campos declarados: `feedback: str`, `errors: list[str]`, `automatic_review: bool`, `request_key: str | None`, `confirm_cost: bool`.

- `Approval` — Confirmación de aprobación de un slot propio. [Código, línea 98](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L98)
  Campos declarados: `approved: bool`.

- `Settings` — Carpeta Drive y configuración personal Gemini recibidas desde la interfaz. [Código, línea 103](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L103)
  Campos declarados: `api_key: SecretStr | None`, `folder: str | None`.

- `Save` — Datos y confirmación del guardado explícito de una captura. [Código, línea 109](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L109)
  Campos declarados: `confirm: bool`.

- `authenticated_session` — Valida/restaura la sesión antes de usar fotos, configuración o borrador. [Código, línea 114](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L114)
  Firma: `authenticated_session(request: Request)`.

- `session` — Dependencia de acceso que obtiene la sesión y sus preferencias personales actuales. [Código, línea 122](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L122)
  Firma: `session(request: Request)`.

- `editor` — Exige permiso de edición para modificar la captura o iniciar operaciones. [Código, línea 133](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L133)
  Firma: `editor(request: Request)`.

- `ready` — Comprueba conexión Google/carpeta y las condiciones necesarias para el flujo solicitado. [Código, línea 141](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L141)
  Firma: `ready(value)`.

- `draft` — Obtiene o crea el borrador propio de esta sesión. [Código, línea 147](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L147)
  Firma: `draft(value)`.

- `idle` — Impide una edición que colisionaría con el trabajo activo del borrador. [Código, línea 155](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L155)
  Firma: `idle(value)`.

- `asset` — Convierte un archivo temporal de la sesión en una referencia visible para su dueño. [Código, línea 165](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L165)
  Firma: `asset(value, path)`.

- `file_path` — Valida y localiza un archivo temporal dentro del espacio de la sesión. [Código, línea 181](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L181)
  Firma: `file_path(value, key)`.

- `view` — Serializa el borrador, productos, imágenes y estados para CaptureStudio. [Código, línea 191](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L191)
  Firma: `view(value)`.

- `error_message` — Convierte un error interno en mensaje público sin secretos. [Código, línea 208](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L208)
  Firma: `error_message(exc, value)`.

- `start_job` — Ejecuta trabajos locales compatibles de texto/guardado; imágenes durables utilizan studio_jobs cuando está habilitado. [Código, línea 229](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L229)
  Firma: `start_job(value, label, action)`.

- `start_job.update` — Actualiza progreso de un trabajo local comprobando que la sesión sigue disponible. [Código, línea 241](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L241)
  Firma: `start_job.update(progress, message)`.

- `start_job.work` — Ejecuta la acción local y conserva resultado/error, liberando la capacidad reservada al terminar. [Código, línea 246](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L246)
  Firma: `start_job.work()`.

- `session_status` — Informa autenticación, carpeta y configuración; auth_only evita descargar imágenes durante el login. [Código, línea 280](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L280)
  Firma: `session_status(request: Request, auth_only: bool=False)`.
  Rutas/decoradores HTTP: `app.get('/api/session')`.

- `catalog_taxonomy` — Devuelve opciones de clasificación leídas de la hoja existente sin crear o sincronizar Drive. [Código, línea 320](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L320)
  Firma: `catalog_taxonomy(value=Depends(authenticated_session))`.
  Rutas/decoradores HTTP: `app.get('/api/catalog-taxonomy')`.

- `settings` — Valida/guarda carpeta y clave Gemini personal; mantiene conexión cifrada y borrador del usuario. [Código, línea 333](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L333)
  Firma: `settings(data: Settings, request: Request, value=Depends(editor))`.
  Rutas/decoradores HTTP: `app.post('/api/settings')`.

- `remove_gemini` — Desconecta la clave personal y evita restaurarla desde snapshots antiguos. [Código, línea 387](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L387)
  Firma: `remove_gemini(value=Depends(editor))`.
  Rutas/decoradores HTTP: `app.delete('/api/settings/gemini')`.

- `test_gemini` — Comprueba la clave configurada mediante la operación de diagnóstico existente. [Código, línea 403](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L403)
  Firma: `test_gemini(value=Depends(editor))`.
  Rutas/decoradores HTTP: `app.post('/api/settings/gemini/test')`.

- `upload` — Valida foto recibida y la guarda en temporales del usuario con límites de formato/tamaño. [Código, línea 423](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L423)
  Firma: `upload(request: Request, image: UploadFile=File(), value=Depends(editor))`.
  Rutas/decoradores HTTP: `app.post('/api/uploads')`.

- `get_file` — Entrega únicamente un archivo perteneciente a la sesión autenticada. [Código, línea 442](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L442)
  Firma: `get_file(key: str, download: bool=False, value=Depends(session))`.
  Rutas/decoradores HTTP: `app.get('/api/files/{key}')`.

- `capture` — Crea el borrador a partir de frente/reverso y del contexto de captura. [Código, línea 450](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L450)
  Firma: `capture(data: Capture, value=Depends(editor))`.
  Rutas/decoradores HTTP: `app.post('/api/capture')`.

- `update_product` — Actualiza campos de borrador, valida barcode y recalcula SKU según la regla aceptada. [Código, línea 469](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L469)
  Firma: `update_product(data: Product, value=Depends(editor))`.
  Rutas/decoradores HTTP: `app.put('/api/draft')`.

- `capture_notes` — Actualiza las notas/contexto de la captura sin generar una imagen. [Código, línea 500](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L500)
  Firma: `capture_notes(data: CaptureNotes, value=Depends(editor))`.
  Rutas/decoradores HTTP: `app.put('/api/capture-notes')`.

- `clear_draft` — Descarta el borrador recuperable del usuario; conserva productos ya guardados. [Código, línea 511](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L511)
  Firma: `clear_draft(value=Depends(editor))`.
  Rutas/decoradores HTTP: `app.delete('/api/draft')`.

- `analyze` — Analiza fotos/texto, identidad y clasificación utilizando vocabulario disponible. [Código, línea 520](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L520)
  Firma: `analyze(request: Request, value=Depends(editor))`.
  Rutas/decoradores HTTP: `app.post('/api/analyze')`.

- `analyze.action` — Extrae ficha/clasificación de fotos y actualiza el borrador para revisión. [Código, línea 523](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L523)
  Firma: `analyze.action(update)`.

- `research_price` — Investiga una propuesta de precio, sin publicar una escritura automática de tienda. [Código, línea 595](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L595)
  Firma: `research_price(value=Depends(editor))`.
  Rutas/decoradores HTTP: `app.post('/api/research-price')`.

- `research_price.action` — Aplica al borrador la propuesta de precio investigada, conservando validaciones. [Código, línea 598](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L598)
  Firma: `research_price.action(update)`.

- `find_variants` — Busca posibles presentaciones/variantes para que el usuario revise la familia. [Código, línea 610](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L610)
  Firma: `find_variants(request: Request, value=Depends(editor))`.
  Rutas/decoradores HTTP: `app.post('/api/find-variants')`.

- `find_variants.action` — Guarda posibles variantes y revisa la recomendación de padre sin fusionar automáticamente. [Código, línea 612](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L612)
  Firma: `find_variants.action(update)`.

- `creative_plan` — Función protegida: prepara brief y referencias con el pipeline aceptado; documentar afuera sin cambiar prompts/modelos. [Código, línea 636](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L636)
  Firma: `creative_plan(value, current, update)`.

- `make_image` — Función protegida: genera, aplica marca y QA con el flujo aceptado; no sustituir por otro proveedor para corregir cola/login. [Código, línea 651](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L651)
  Firma: `make_image(value, current, slot, prompt, styles, *, feedback=(), automatic_review=False)`.

- `generate_images` — Valida selección y confirmación de coste; delega la generación durable al worker en el despliegue actual. [Código, línea 682](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L682)
  Firma: `generate_images(data: Generation, value=Depends(editor))`.
  Rutas/decoradores HTTP: `app.post('/api/generate')`.

- `generate_images.action` — Orquestación local compatible de slots; el despliegue worker usa la ruta durable en su lugar. [Código, línea 696](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L696)
  Firma: `generate_images.action(update)`.

- `correct_image` — Solicita una corrección de slot con feedback y conserva referencias/historial. [Código, línea 713](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L713)
  Firma: `correct_image(slot: str, data: Correction, value=Depends(editor))`.
  Rutas/decoradores HTTP: `app.post('/api/images/{slot}/correct')`.

- `correct_image.action` — Orquestación local compatible de corrección con el mismo plan y make_image. [Código, línea 729](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L729)
  Firma: `correct_image.action(update)`.

- `approve` — Guarda la aprobación de un candidato propio y la refleja en su trabajo durable. [Código, línea 739](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L739)
  Firma: `approve(slot: str, data: Approval, value=Depends(editor))`.
  Rutas/decoradores HTTP: `app.post('/api/images/{slot}/approve')`.

- `check` — Coteja código, duplicados y familia de la ficha actual. [Código, línea 758](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L758)
  Firma: `check(request: Request, value=Depends(editor))`.
  Rutas/decoradores HTTP: `app.post('/api/check-product')`.

- `parents` — Devuelve padres registrados para elegir una familia existente. [Código, línea 770](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L770)
  Firma: `parents(request: Request, value=Depends(session))`.
  Rutas/decoradores HTTP: `app.get('/api/parents')`.

- `family_cover` — Construye/revisa la portada de familia con la composición existente. [Código, línea 794](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L794)
  Firma: `family_cover(request: Request, value=Depends(editor))`.
  Rutas/decoradores HTTP: `app.post('/api/family-cover')`.

- `family_cover.action` — Compone y asocia la portada revisable de la familia seleccionada. [Código, línea 796](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L796)
  Firma: `family_cover.action(update)`.

- `save` — Guarda la captura confirmada con ProductCapture y registra el resultado durable para recuperar respuestas perdidas. [Código, línea 810](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L810)
  Firma: `save(data: Save, request: Request, value=Depends(editor))`.
  Rutas/decoradores HTTP: `app.post('/api/save')`.

- `save.write` — Ejecuta el guardado confirmado y concilia su espejo SQL sin repetir resultados ya confirmados. [Código, línea 818](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L818)
  Firma: `save.write(update)`.

- `save.action` — Serializa el guardado histórico y delega a write dentro del control de escritura. [Código, línea 856](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L856)
  Firma: `save.action(update)`.

- `match_image` — Busca una imagen asociada al registro identificado del inventario. [Código, línea 866](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L866)
  Firma: `match_image(sku: str, value=Depends(session))`.
  Rutas/decoradores HTTP: `app.get('/api/matches/{sku}/image')`.

- `repair_capture` — Concilia un guardado pendiente entre Sheets y SQL sin repetir una generación. [Código, línea 883](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L883)
  Firma: `repair_capture(value=Depends(editor))`.
  Rutas/decoradores HTTP: `app.post('/api/capture-sync')`.

- `get_job` — Devuelve progreso/resultado del job local o durable que pertenece al usuario. [Código, línea 893](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L893)
  Firma: `get_job(key: str, value=Depends(session))`.
  Rutas/decoradores HTTP: `app.get('/api/jobs/{key}')`.

- `catalog` — Devuelve el inventario compatible conectado a Drive/Sheets. [Código, línea 911](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L911)
  Firma: `catalog(value=Depends(session))`.
  Rutas/decoradores HTTP: `app.get('/api/catalog')`.

- `get_draft` — Recupera el borrador propio para continuar una captura. [Código, línea 918](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/studio_api.py#L918)
  Firma: `get_draft(value=Depends(session))`.
  Rutas/decoradores HTTP: `app.get('/api/draft')`.


# Datos: productos, captura, Drive y Sheets

Sección del índice del código de la aplicación. Las rutas y números de línea corresponden a esta entrega documental; buscar por nombre en una versión posterior. Una función compatible/histórica no implica que su integración esté activada.

## ai_app.py

Adaptación del runtime histórico a la hoja maestra canónica; conserva compatibilidad de llamadas.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/ai_app.py)

- `sheets_for_session` — Obtiene el cliente Sheets compatible correspondiente a la sesión. [Código, línea 13](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/ai_app.py#L13)
  Firma: `sheets_for_session(session)`.

- `_clean` — Normaliza celdas vacías/escalares antes de mapear la hoja maestra. [Código, línea 21](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/ai_app.py#L21)
  Firma: `_clean(value)`.

- `_canonical_row` — Traduce una fila a las columnas canónicas del inventario. [Código, línea 30](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/ai_app.py#L30)
  Firma: `_canonical_row(record)`.

- `_read_master` — Lee la pestaña maestra para el runtime adaptado. [Código, línea 84](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/ai_app.py#L84)
  Firma: `_read_master(sheets_service, spreadsheet_id)`.

- `_append_master_row` — Read fresh, reject duplicates, then write the parent and child atomically. [Código, línea 109](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/ai_app.py#L109)
  Firma: `_append_master_row(session, spreadsheet_id, record)`.

- `_no_variable_sync` — Adaptador que omite la sincronización legada de variantes en esta modalidad. [Código, línea 138](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/ai_app.py#L138)
  Firma: `_no_variable_sync(*args, **kwargs)`.

- `_no_legacy_format` — Adaptador que evita aplicar formato legado sobre la hoja canónica. [Código, línea 142](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/ai_app.py#L142)
  Firma: `_no_legacy_format(*args, **kwargs)`.

## catalog_capture.py

Identidad del producto: código de barras, coincidencias, familias y planificación de filas padre/variante.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_capture.py)

- `text` — Convierte vacíos/NaN a texto limpio sin transformar códigos en números. [Código, línea 15](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_capture.py#L15)
  Firma: `text(value)`.

- `normalized` — Normaliza acentos y separadores para comparar nombres/marcas. [Código, línea 22](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_capture.py#L22)
  Firma: `normalized(value)`.

- `barcode` — Valida EAN/UPC/GTIN y su dígito de control; conserva los ceros iniciales. [Código, línea 28](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_capture.py#L28)
  Firma: `barcode(value)`.

- `barcode_key` — Crea una clave GTIN de 14 dígitos para cotejar distintas representaciones del mismo código. [Código, línea 42](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_capture.py#L42)
  Firma: `barcode_key(value)`.

- `record_barcode` — Lee código o SKU numérico histórico; una máscara de padre no cuenta como código de barras. [Código, línea 50](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_capture.py#L50)
  Firma: `record_barcode(row)`.

- `family_name` — Quita presentación del nombre para comparar posibles familias. [Código, línea 68](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_capture.py#L68)
  Firma: `family_name(name)`.

- `presentation` — Identifica la presentación que diferencia variantes. [Código, línea 73](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_capture.py#L73)
  Firma: `presentation(value)`.

- `same_brand` — Compara marcas normalizadas antes de proponer una familia. [Código, línea 87](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_capture.py#L87)
  Firma: `same_brand(first, second)`.

- `family_label` — Produce una etiqueta legible para una posible familia sin alterar la ficha original. [Código, línea 99](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_capture.py#L99)
  Firma: `family_label(name)`.

- `family_score` — Mide similitud conservadora de familia considerando nombre y marca. [Código, línea 105](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_capture.py#L105)
  Firma: `family_score(name, brand, row)`.

- `find_duplicate` — Busca identidad exacta de código/SKU antes de sugerir otra familia. [Código, línea 117](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_capture.py#L117)
  Firma: `find_duplicate(rows, candidate)`.

- `review_product` — Devuelve coincidencia, padre sugerido y candidatos para revisión; no fusiona productos automáticamente. [Código, línea 157](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_capture.py#L157)
  Firma: `review_product(rows, candidate)`.

- `next_parent_sku` — Usa el prefijo común de GTIN distintos y enmascara el resto con x; sin variantes usa seis dígitos y rechaza colisiones. [Código, línea 184](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_capture.py#L184)
  Firma: `next_parent_sku(name, brand, rows, code='')`.

- `records_from_values` — Interpreta filas existentes respetando encabezados y columnas canónicas. [Código, línea 212](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_capture.py#L212)
  Firma: `records_from_values(values)`.

- `prepare_capture_updates` — Planifica la escritura de padre/variante y relaciones antes del guardado explícito. [Código, línea 224](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_capture.py#L224)
  Firma: `prepare_capture_updates(values, record)`.

## catalog_platform/backup.py

Comando de respaldo privado PostgreSQL; no se ejecuta como parte de una lectura de catálogo.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/backup.py)

- `main` — Genera un pg_dump privado; el archivo temporal debe exportarse antes de perder el contenedor. [Código, línea 13](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/backup.py#L13)
  Firma: `main()`.

## catalog_platform/capture_bridge.py

Puente entre captura/Sheets y catálogo SQL con recuperación de borrador y espejo por identidad.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/capture_bridge.py)

- `root_for` — Resuelve la carpeta seleccionada que limita el puente captura/SQL. [Código, línea 29](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/capture_bridge.py#L29)
  Firma: `root_for(value)`.

- `active` — Indica si el puente SQL está disponible para la sesión y carpeta actuales. [Código, línea 34](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/capture_bridge.py#L34)
  Firma: `active(value)`.

- `sheet_write_guard` — Serializa el guardado compatible de captura para evitar duplicar una operación sobre Sheets. [Código, línea 41](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/capture_bridge.py#L41)
  Firma: `sheet_write_guard(value)`.

- `candidate` — Normaliza el borrador de captura a una ficha que puede cotejarse en SQL. [Código, línea 52](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/capture_bridge.py#L52)
  Firma: `candidate(product)`.

- `master_rows` — Lee filas visibles del catálogo para coincidencias; excluye eliminadas. [Código, línea 59](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/capture_bridge.py#L59)
  Firma: `master_rows(value)`.

- `woo_rows` — Traduce relaciones WooCommerce registradas a filas compatibles de captura. [Código, línea 81](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/capture_bridge.py#L81)
  Firma: `woo_rows(value, product)`.

- `check` — Coteja el borrador con el catálogo existente y sus identidades remotas. [Código, línea 145](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/capture_bridge.py#L145)
  Firma: `check(value, product, include_woo=False)`.

- `checkpoint` — Guarda un borrador durable antes de una operación que deba recuperarse tras reinicio. [Código, línea 180](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/capture_bridge.py#L180)
  Firma: `checkpoint(value, current)`.

- `checkpoint.store_path` — Persiste una foto temporal por checksum en la carpeta privada de captura y reutiliza su ID. [Código, línea 193](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/capture_bridge.py#L193)
  Firma: `checkpoint.store_path(path)`.

- `mark_saved` — Registra que una captura ya quedó guardada y su resultado no debe enviarse dos veces. [Código, línea 223](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/capture_bridge.py#L223)
  Firma: `mark_saved(db, value, current)`.

- `restore` — Restaura el borrador durable propio al recuperar la sesión. [Código, línea 243](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/capture_bridge.py#L243)
  Firma: `restore(value)`.

- `restore.local` — Recupera el archivo identificado de un borrador durable a temporales autorizados. [Código, línea 260](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/capture_bridge.py#L260)
  Firma: `restore.local(key)`.

- `clear` — Limpia el borrador recuperable de captura sin eliminar productos ni imágenes guardados. [Código, línea 288](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/capture_bridge.py#L288)
  Firma: `clear(value)`.

- `recover_saved` — Recupera el resultado de un guardado ya confirmado para resolver una respuesta HTTP perdida. [Código, línea 299](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/capture_bridge.py#L299)
  Firma: `recover_saved(value, current)`.

- `event_id` — Deriva una identidad estable del evento de guardado para deduplicarlo. [Código, línea 318](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/capture_bridge.py#L318)
  Firma: `event_id(value, current)`.

- `mirror_records` — Refleja filas identificadas del guardado en SQL conservando padres y variantes. [Código, línea 323](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/capture_bridge.py#L323)
  Firma: `mirror_records(value, current, rows, images=None)`.

- `mirror` — Coordina el espejo del resultado de captura y registra su estado. [Código, línea 398](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/capture_bridge.py#L398)
  Firma: `mirror(value, current)`.

- `pending` — Describe una reconciliación de guardado pendiente para revisión. [Código, línea 422](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/capture_bridge.py#L422)
  Firma: `pending(value, current)`.

## catalog_platform/catalog.py

Operaciones del catálogo por tenant, versionado, movimientos, auditoría y exportación.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/catalog.py)

- `serialize` — Convierte columnas SQL en una respuesta JSON, conservando fechas e identificadores. [Código, línea 45](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/catalog.py#L45)
  Firma: `serialize(record)`.

- `product_for` — Busca el producto en el tenant y excluye fichas eliminadas; puede bloquear la fila para una escritura. [Código, línea 57](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/catalog.py#L57)
  Firma: `product_for(db, tenant, product_id, lock=False)`.

- `audit` — Registra actor, operación y valores antes/después dentro de la misma transacción. [Código, línea 68](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/catalog.py#L68)
  Firma: `audit(db, tenant, actor, action, product_id=None, before=None, after=None, result='completed', system='app')`.

- `move_stock` — Aplica un movimiento identificado de inventario y evita repetir el mismo evento. [Código, línea 94](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/catalog.py#L94)
  Firma: `move_stock(db, product, quantity, source, event_id, actor, metadata=None, store_id='')`.

- `save_product` — Valida versión, SKU y relación padre/variante antes de actualizar la ficha y su auditoría. [Código, línea 138](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/catalog.py#L138)
  Firma: `save_product(db, tenant, actor, data, product_id=None, expected_version=None, source='app', event_id=None)`.

- `csv_export` — Exporta el catálogo visible sin incluir productos eliminados. [Código, línea 272](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/catalog.py#L272)
  Firma: `csv_export(products)`.

## catalog_platform/database.py

Transacciones PostgreSQL y publicación de IDs de trabajos después del commit.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/database.py)

- `configured` — Indica si existe una dirección de base de datos configurada. [Código, línea 13](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/database.py#L13)
  Firma: `configured()`.

- `engine_for` — Reutiliza un pool pequeño y rechaza conexiones heredadas por fork; SQLite queda reservado a pruebas. [Código, línea 20](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/database.py#L20)
  Firma: `engine_for(url)`.

- `engine_for.mark_process` — Registra el PID propietario de cada conexión SQL nueva. [Código, línea 41](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/database.py#L41)
  Firma: `engine_for.mark_process(connection, record)`.

- `engine_for.require_own_connection` — Obliga al proceso hijo RQ a abrir su propio socket SQL en lugar de usar el del supervisor. [Código, línea 47](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/database.py#L47)
  Firma: `engine_for.require_own_connection(connection, record, proxy)`.

- `transaction` — Confirma o revierte la operación completa; despierta al worker y entrega IDs a Redis solo después del commit. [Código, línea 60](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/database.py#L60)
  Firma: `transaction()`.

## catalog_platform/imports.py

Importación revisada de CSV/XLSX/Sheets/WooCommerce, con respaldo y sin resucitar eliminados.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/imports.py)

- `normalize` — Convierte filas externas al contrato de producto sin inventar cantidades ausentes. [Código, línea 19](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/imports.py#L19)
  Firma: `normalize(rows)`.

- `normalize.number` — Interpreta un campo numérico de la fila de importación sin inventar un valor ausente. [Código, línea 64](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/imports.py#L64)
  Firma: `normalize.number(key, legacy, default=0)`.

- `parse_file` — Valida CSV/XLSX recibido y extrae filas con límites de tamaño/estructura. [Código, línea 112](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/imports.py#L112)
  Firma: `parse_file(filename, raw)`.

- `backup_catalog` — Guarda un respaldo explícito antes de aplicar una importación autorizada. [Código, línea 152](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/imports.py#L152)
  Firma: `backup_catalog(db, tenant, drive)`.

- `execute_import` — Procesa las filas confirmadas con checkpoints, identidad por tenant y auditoría. [Código, línea 176](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/imports.py#L176)
  Firma: `execute_import(job, value, drive, owner)`.

- `attach_historic_images` — Asocia imágenes existentes por el naming aceptado; no reorganiza originales en Drive. [Código, línea 262](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/imports.py#L262)
  Firma: `attach_historic_images(job, data, product_id, drive_index, drive, owner)`.

## catalog_platform/initialize.py

Inicialización optativa únicamente de una base vacía; no migra un esquema existente incompleto.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/initialize.py)

- `initialize_empty_database` — Con autorización del flag, crea tablas solo si la base está vacía; exige migración explícita si existe un esquema incompleto. [Código, línea 13](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/initialize.py#L13)
  Firma: `initialize_empty_database()`.

## catalog_platform/migrate.py

Comando explícito de preparación aditiva del esquema SQL.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/migrate.py)

- `main` — Ejecuta preparación aditiva del esquema desde un comando explícito; no es un downgrade ni un borrado de datos. [Código, línea 13](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/migrate.py#L13)
  Firma: `main()`.

## catalog_platform/models.py

Objetos SQL: catálogo, imágenes, trabajos, conexiones cifradas y auditoría; las fotos permanecen en Drive.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/models.py)

- `uid` — Crea el UUID interno; la identidad del registro no depende del SKU. [Código, línea 23](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/models.py#L23)
  Firma: `uid()`.

- `now` — Devuelve una fecha UTC con zona horaria para el historial. [Código, línea 28](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/models.py#L28)
  Firma: `now()`.

- `Base` — Registro declarativo de tablas SQLAlchemy; no representa un producto. [Código, línea 33](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/models.py#L33)

- `Record` — Campos compartidos id, tenant_id y created_at; tenant_id limita los datos a una carpeta/tienda. [Código, línea 39](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/models.py#L39)
  Campos declarados: `id: Mapped[str]`, `tenant_id: Mapped[str]`, `created_at: Mapped[datetime]`.

- `Product` — Ficha SQL con UUID, SKU, barcode, familia, precios/stock, IDs remotos y versión; deleted es una retirada lógica, no un borrado externo. [Código, línea 47](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/models.py#L47)
  Campos declarados: `sku: Mapped[str]`, `barcode: Mapped[str]`, `name: Mapped[str]`, `brand: Mapped[str]`, `category: Mapped[str]`, `subcategory: Mapped[str]`, `short_description: Mapped[str]`, `long_description: Mapped[str]`, `tags: Mapped[list]`, `attributes: Mapped[dict]`, `product_type: Mapped[str]`, `parent_id: Mapped[str | None]`, `price: Mapped[float | None]`, `cost: Mapped[float | None]`, `stock: Mapped[float | None]`, `woocommerce_stock: Mapped[float | None]`, `loyverse_stock: Mapped[float | None]`, `status: Mapped[str]`, `sync_status: Mapped[str]`, `woocommerce_product_id: Mapped[int | None]`, `woocommerce_variation_id: Mapped[int | None]`, `wordpress_media_ids: Mapped[list]`, `loyverse_item_id: Mapped[str | None]`, `loyverse_variant_id: Mapped[str | None]`, `loyverse_store_id: Mapped[str | None]`, `last_woocommerce_sync: Mapped[datetime | None]`, `woocommerce_updated_at: Mapped[datetime | None]`, `last_loyverse_sync: Mapped[datetime | None]`, `version: Mapped[int]`, `updated_at: Mapped[datetime]`.

- `ProductVariant` — Relaciona UUID padre e hijo y atributos de la variante dentro del mismo tenant. [Código, línea 93](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/models.py#L93)
  Campos declarados: `product_id: Mapped[str]`, `child_product_id: Mapped[str]`, `attributes: Mapped[dict]`.

- `ProductImage` — Metadata de una imagen y su Drive ID, rol, checksum y dimensiones; no almacena los bytes de la fotografía. [Código, línea 103](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/models.py#L103)
  Campos declarados: `product_id: Mapped[str]`, `drive_file_id: Mapped[str]`, `url: Mapped[str]`, `role: Mapped[str]`, `status: Mapped[str]`, `checksum: Mapped[str]`, `width: Mapped[int]`, `height: Mapped[int]`, `mime_type: Mapped[str]`, `metadata_json: Mapped[dict]`.

- `Category` — Entidad SQL de categoría; las opciones de captura actuales se leen de Drive mediante catalog_taxonomy. [Código, línea 121](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/models.py#L121)
  Campos declarados: `name: Mapped[str]`.

- `Brand` — Entidad SQL de marca única por tenant. [Código, línea 128](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/models.py#L128)
  Campos declarados: `name: Mapped[str]`.

- `InventoryMovement` — Historial de cantidades antes/después y evento origen, con unicidad para evitar aplicar un movimiento dos veces. [Código, línea 136](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/models.py#L136)
  Campos declarados: `product_id: Mapped[str]`, `variant_id: Mapped[str | None]`, `source: Mapped[str]`, `source_event_id: Mapped[str]`, `store_id: Mapped[str]`, `quantity_before: Mapped[float | None]`, `quantity_after: Mapped[float]`, `delta: Mapped[float]`, `metadata_json: Mapped[dict]`.

- `GenerationBatch` — Agrupa los trabajos confirmados de una selección y conserva su estimación de coste. [Código, línea 155](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/models.py#L155)
  Campos declarados: `actor: Mapped[str]`, `request_key: Mapped[str]`, `product_count: Mapped[int]`, `image_count: Mapped[int]`, `estimated_cost: Mapped[float | None]`.

- `GenerationJob` — Unidad durable de ejecución: actor, request_key, tipo, payload, progreso, lease y estado; in_flight impide repetir llamadas inciertas. [Código, línea 167](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/models.py#L167)
  Campos declarados: `product_id: Mapped[str | None]`, `batch_id: Mapped[str | None]`, `actor: Mapped[str]`, `kind: Mapped[str]`, `request_key: Mapped[str]`, `status: Mapped[str]`, `provider: Mapped[str]`, `model: Mapped[str]`, `estimated_cost: Mapped[float | None]`, `actual_cost: Mapped[float | None]`, `payload: Mapped[dict]`, `progress: Mapped[int]`, `message: Mapped[str]`, `lease_owner: Mapped[str | None]`, `lease_until: Mapped[float | None]`, `started_at: Mapped[datetime | None]`, `finished_at: Mapped[datetime | None]`.

- `GeneratedAsset` — Candidato generado asociado a producto, job e imagen; conserva slot, muestra, raw Drive ID, revisión e historial de correcciones. [Código, línea 202](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/models.py#L202)
  Campos declarados: `job_id: Mapped[str]`, `product_id: Mapped[str]`, `image_id: Mapped[str]`, `raw_drive_file_id: Mapped[str]`, `slot: Mapped[str]`, `sample: Mapped[int]`, `provider: Mapped[str]`, `model: Mapped[str]`, `status: Mapped[str]`, `history: Mapped[list]`, `metadata_json: Mapped[dict]`.

- `IntegrationAccount` — Conexión cifrada por tenant, proveedor y actor; también guarda sesiones web/perfil sin exponer secretos al navegador. [Código, línea 224](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/models.py#L224)
  Campos declarados: `provider: Mapped[str]`, `actor: Mapped[str]`, `encrypted_credentials: Mapped[str]`, `status: Mapped[str]`, `updated_at: Mapped[datetime]`.

- `IntegrationMapping` — Relación explícita entre UUID interno e ID externo de producto/variante; evita depender solo del SKU. [Código, línea 238](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/models.py#L238)
  Campos declarados: `internal_product_id: Mapped[str]`, `provider: Mapped[str]`, `entity_type: Mapped[str]`, `external_id: Mapped[str]`, `parent_external_id: Mapped[str | None]`.

- `SyncEvent` — Resultado trazable de una operación entre sistemas, con origen, destino y mensaje. [Código, línea 251](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/models.py#L251)
  Campos declarados: `product_id: Mapped[str | None]`, `source: Mapped[str]`, `destination: Mapped[str]`, `action: Mapped[str]`, `status: Mapped[str]`, `message: Mapped[str]`, `job_id: Mapped[str | None]`.

- `WebhookEvent` — Evento externo recibido y deduplicado, con payload cifrado y estado de procesamiento. [Código, línea 265](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/models.py#L265)
  Campos declarados: `provider: Mapped[str]`, `event_id: Mapped[str]`, `event_type: Mapped[str]`, `payload_hash: Mapped[str]`, `received_at: Mapped[datetime]`, `processed_at: Mapped[datetime | None]`, `status: Mapped[str]`, `encrypted_payload: Mapped[str]`.

- `AuditLog` — Registro de actor, acción y valores antes/después para revisar o conciliar una modificación. [Código, línea 285](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/models.py#L285)
  Campos declarados: `actor: Mapped[str]`, `action: Mapped[str]`, `product_id: Mapped[str | None]`, `system: Mapped[str]`, `before: Mapped[dict]`, `after: Mapped[dict]`, `result: Mapped[str]`.

- `WorkerHeartbeat` — Señal reciente del supervisor y su versión; un health HTTP disponible no prueba que el consumidor esté activo. [Código, línea 298](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/models.py#L298)
  Campos declarados: `id: Mapped[str]`, `updated: Mapped[float]`, `version: Mapped[str]`.

- `OrderSnapshot` — Copia local de un pedido WooCommerce para consultas y métricas, sin inventar ventas ni escribir el pedido remoto. [Código, línea 307](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/models.py#L307)
  Campos declarados: `woocommerce_id: Mapped[int]`, `status: Mapped[str]`, `total: Mapped[float]`, `currency: Mapped[str]`, `ordered_at: Mapped[datetime]`.

## catalog_taxonomy.py

Lectura de categorías, subcategorías y etiquetas del inventario conectado; no escribe ni crea archivos.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_taxonomy.py)

- `read_rows` — Descubre y lee el inventario existente dentro de la carpeta autorizada; evita el adaptador que crea/sincroniza hojas. [Código, línea 12](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_taxonomy.py#L12)
  Firma: `read_rows(runtime, value)`.

- `classification` — Extrae categoría/subcategoría tanto del camino combinado como de columnas históricas. [Código, línea 42](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_taxonomy.py#L42)
  Firma: `classification(row)`.

- `choices_from_rows` — Construye opciones únicas de Drive, conserva ortografía y relaciona subcategorías con su categoría; defaults solo para datos ausentes. [Código, línea 49](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_taxonomy.py#L49)
  Firma: `choices_from_rows(rows, default_categories=(), default_subcategories=())`.

## drive_service.py

Acceso a archivos dentro de la carpeta autorizada: lectura, subida y respaldo antes de reemplazar.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/drive_service.py)

- `DriveService` — Límite de acceso por carpeta: un Drive ID recibido del navegador no concede permiso por sí solo. [Código, línea 9](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/drive_service.py#L9)

- `DriveService.__init__` — Recibe cliente Google y carpeta raíz autorizada. [Código, línea 10](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/drive_service.py#L10)
  Firma: `DriveService.__init__(self, client, root_id=None)`.

- `DriveService.files` — Mantiene el acceso compatible al recurso files del SDK. [Código, línea 13](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/drive_service.py#L13)
  Firma: `DriveService.files(self)`.

- `DriveService.for_session` — Construye el adaptador con credenciales y carpeta de la sesión. [Código, línea 18](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/drive_service.py#L18)
  Firma: `DriveService.for_session(cls, runtime, value)`.

- `DriveService.list` — Lista archivos dentro del ámbito y pagina resultados del SDK. [Código, línea 25](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/drive_service.py#L25)
  Firma: `DriveService.list(self, folder=None, query='', fields='id,name,mimeType,parents', limit=5000)`.

- `DriveService.folder` — Busca/resuelve una carpeta dentro de la raíz autorizada. [Código, línea 53](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/drive_service.py#L53)
  Firma: `DriveService.folder(self, name, parent=None)`.

- `DriveService.working_folder` — Resuelve la carpeta de trabajo prevista para imágenes/borradores. [Código, línea 81](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/drive_service.py#L81)
  Firma: `DriveService.working_folder(self, *parts)`.

- `DriveService.owns` — Comprueba que un archivo pertenece a la raíz autorizada antes de leerlo o modificarlo. [Código, línea 87](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/drive_service.py#L87)
  Firma: `DriveService.owns(self, file_id)`.

- `DriveService.download` — Descarga un archivo autorizado y valida sus límites. [Código, línea 111](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/drive_service.py#L111)
  Firma: `DriveService.download(self, file_id)`.

- `DriveService._download` — Ejecuta la descarga por partes del SDK a un destino autorizado. [Código, línea 118](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/drive_service.py#L118)
  Firma: `DriveService._download(self, file_id, stream)`.

- `DriveService.download_to` — Descarga a una ruta temporal explícita del trabajo para no cargar todas las fotos en RAM. [Código, línea 128](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/drive_service.py#L128)
  Firma: `DriveService.download_to(self, file_id, destination)`.

- `DriveService.metadata` — Lee metadata de un archivo y su relación de pertenencia. [Código, línea 141](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/drive_service.py#L141)
  Firma: `DriveService.metadata(self, file_id)`.

- `DriveService.find` — Busca un archivo por nombre dentro de una carpeta autorizada. [Código, línea 147](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/drive_service.py#L147)
  Firma: `DriveService.find(self, name, folder=None)`.

- `DriveService.url` — Construye la referencia de un archivo identificado; no incluye credenciales. [Código, línea 152](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/drive_service.py#L152)
  Firma: `DriveService.url(file_id)`.

- `DriveService.save_approved` — Respalda el archivo existente antes de guardar el aprobado, conserva su ID y bloquea nombres duplicados. [Código, línea 157](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/drive_service.py#L157)
  Firma: `DriveService.save_approved(self, path, filename, folder, asset_id)`.

- `DriveService.upload` — Sube explícitamente un archivo de trabajo a su carpeta autorizada. [Código, línea 181](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/drive_service.py#L181)
  Firma: `DriveService.upload(self, path, filename, folder, properties=None)`.

- `DriveService.backup` — Crea respaldo del archivo identificado antes de una actualización explícita. [Código, línea 200](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/drive_service.py#L200)
  Firma: `DriveService.backup(self, file_id, label)`.

- `DriveService.upload_bytes` — Sube bytes validados con nombre y destino explícitos. [Código, línea 215](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/drive_service.py#L215)
  Firma: `DriveService.upload_bytes(self, data, filename, folder, mime_type)`.

- `DriveService.export` — Exporta un archivo Google nativo al formato solicitado. [Código, línea 231](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/drive_service.py#L231)
  Firma: `DriveService.export(self, file_id, mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')`.

## inventory_schema.py

Contrato de columnas del inventario histórico y clasificación simple/padre/variante.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_schema.py)

- `is_variable_parent` — Reconoce un padre variable a partir del tipo y relación guardados. [Código, línea 18](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_schema.py#L18)
  Firma: `is_variable_parent(row: Mapping[str, Any])`.

- `split_category_path` — Separa el camino de categoría/subcategoría del contrato histórico. [Código, línea 26](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_schema.py#L26)
  Firma: `split_category_path(value: Any)`.

- `join_category_path` — Construye el camino de clasificación conservando el texto de sus partes. [Código, línea 34](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_schema.py#L34)
  Firma: `join_category_path(parent: Any, child: Any)`.

- `normalize_product_row` — Adapta encabezados/campos históricos al contrato canónico de fila. [Código, línea 42](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_schema.py#L42)
  Firma: `normalize_product_row(row: Mapping[str, Any])`.

- `ProductKindIndex` — Índice de identidad padre/variante que evita tratar máscaras de familia como productos simples. [Código, línea 91](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_schema.py#L91)
  Campos declarados: `simple_skus: frozenset[str]`, `variable_skus: frozenset[str]`.

- `ProductKindIndex.from_rows` — Construye el índice a partir de filas existentes. [Código, línea 96](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_schema.py#L96)
  Firma: `ProductKindIndex.from_rows(cls, simple_rows, variable_rows)`.

- `ProductKindIndex.from_rows.collect` — Recopila identidades/relaciones de filas para construir el índice de tipos. [Código, línea 97](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_schema.py#L97)
  Firma: `ProductKindIndex.from_rows.collect(rows)`.

- `ProductKindIndex.kind_for` — Devuelve el tipo conocido de un SKU sin inventar una relación nueva. [Código, línea 105](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_schema.py#L105)
  Firma: `ProductKindIndex.kind_for(self, sku: str, fallback: str='Simple')`.

## product_capture.py

Adaptador de captura existente: fotografías, selección de padre, portada y guardado explícito.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/product_capture.py)

- `field_update` — Representa una actualización de campo compatible con las funciones históricas, independiente de React. [Código, línea 13](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/product_capture.py#L13)
  Firma: `field_update(**values)`.

- `read_barcodes` — Lee códigos de una foto y devuelve candidatos para validación de identidad. [Código, línea 27](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/product_capture.py#L27)
  Firma: `read_barcodes(image)`.

- `compose_family_cover` — Compone una portada con las referencias de familia sin generar otro producto por IA. [Código, línea 49](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/product_capture.py#L49)
  Firma: `compose_family_cover(pictures, title)`.

- `ProductCapture` — Adaptador por sesión que conserva el flujo probado de captura, coincidencias, padre e inventario. [Código, línea 72](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/product_capture.py#L72)

- `ProductCapture.__init__` — Recibe runtime y acceso a la sesión que delimita todas las operaciones de captura. [Código, línea 73](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/product_capture.py#L73)
  Firma: `ProductCapture.__init__(self, backend)`.

- `ProductCapture.session` — Obtiene y valida la sesión propia del adaptador. [Código, línea 77](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/product_capture.py#L77)
  Firma: `ProductCapture.session(self, request)`.

- `ProductCapture.snapshot` — Lee catálogo y relaciones disponibles del inventario conectado. [Código, línea 83](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/product_capture.py#L83)
  Firma: `ProductCapture.snapshot(self, session)`.

- `ProductCapture.check` — Compara una ficha con registros existentes y propone revisión de identidad/familia. [Código, línea 92](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/product_capture.py#L92)
  Firma: `ProductCapture.check(self, sku, name, brand, size, code, parent, attribute, value, request: Request)`.

- `ProductCapture.scan` — Extrae códigos de una fotografía para comprobar coincidencias. [Código, línea 114](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/product_capture.py#L114)
  Firma: `ProductCapture.scan(self, photo, current_code, request: Request)`.

- `ProductCapture.detect_from_product` — Resuelve identidad/parentesco desde campos y código del producto. [Código, línea 125](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/product_capture.py#L125)
  Firma: `ProductCapture.detect_from_product(self, front, back, current_code, request: Request)`.

- `ProductCapture.load_parents` — Lee padres existentes para seleccionar una familia ya guardada. [Código, línea 136](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/product_capture.py#L136)
  Firma: `ProductCapture.load_parents(self, kind, mode, name, brand, sku, selected, request: Request, code='')`.

- `ProductCapture.select_parent` — Aplica una selección de padre revisada a los campos del borrador. [Código, línea 163](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/product_capture.py#L163)
  Firma: `ProductCapture.select_parent(self, selected, request: Request)`.

- `ProductCapture._namespace` — Obtiene el espacio privado de temporales de la sesión. [Código, línea 171](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/product_capture.py#L171)
  Firma: `ProductCapture._namespace(self, session)`.

- `ProductCapture._references` — Resuelve fotos propias que servirán de referencias para captura/portada. [Código, línea 174](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/product_capture.py#L174)
  Firma: `ProductCapture._references(self, session, reference)`.

- `ProductCapture.stage_image` — Guarda una referencia temporal autorizada del usuario. [Código, línea 181](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/product_capture.py#L181)
  Firma: `ProductCapture.stage_image(self, session, sku, slot, path, revision)`.

- `ProductCapture.draft_images` — Recupera las imágenes de borrador vinculadas al producto/captura. [Código, línea 195](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/product_capture.py#L195)
  Firma: `ProductCapture.draft_images(self, session, sku)`.

- `ProductCapture._drive_picture` — Descarga una imagen Drive autorizada para mostrarla o componer portada. [Código, línea 209](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/product_capture.py#L209)
  Firma: `ProductCapture._drive_picture(self, service, folder, name)`.

- `ProductCapture.cover` — Compone la portada de la familia seleccionada usando sus imágenes existentes. [Código, línea 228](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/product_capture.py#L228)
  Firma: `ProductCapture.cover(self, kind, mode, parent, title, sku, reference, request: Request)`.

- `ProductCapture.regenerate_cover` — Vuelve a componer explícitamente una portada conservando el flujo de familia. [Código, línea 288](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/product_capture.py#L288)
  Firma: `ProductCapture.regenerate_cover(self, kind, mode, parent, title, sku, reference, request: Request)`.

- `ProductCapture.save` — Guarda la captura confirmada en Drive/Sheets con validación de identidad y relación padre/variante. [Código, línea 298](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/product_capture.py#L298)
  Firma: `ProductCapture.save(self, sku, kind, parent, name, brand, size, attribute, value, price, category, subcategory, tags, short, long, code, mode, title, cover_token, request: Request)`.

## sheets_service.py

Lectura y escritura puntual de Sheets con encabezados, SKU único y valor previo comprobados.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sheets_service.py)

- `column_name` — Convierte un índice de columna a la notación A1 de Sheets. [Código, línea 6](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sheets_service.py#L6)
  Firma: `column_name(number)`.

- `SheetsService` — Adaptador de Sheets que conserva estructura histórica y comprueba identidad antes de escribir. [Código, línea 14](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sheets_service.py#L14)

- `SheetsService.__init__` — Recibe cliente Google y límite Drive opcional para comprobar pertenencia de la hoja. [Código, línea 15](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sheets_service.py#L15)
  Firma: `SheetsService.__init__(self, client, spreadsheet_id=None, tab='Lista completa')`.

- `SheetsService.spreadsheets` — Mantiene el recurso compatible del SDK Sheets. [Código, línea 18](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sheets_service.py#L18)
  Firma: `SheetsService.spreadsheets(self)`.

- `SheetsService._id` — Valida el identificador de hoja antes de formar una consulta. [Código, línea 22](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sheets_service.py#L22)
  Firma: `SheetsService._id(self)`.

- `SheetsService._tab` — Escapa el nombre de pestaña para una referencia A1 segura. [Código, línea 27](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sheets_service.py#L27)
  Firma: `SheetsService._tab(self)`.

- `SheetsService.metadata` — Lee pestañas/metadata de la hoja identificada. [Código, línea 30](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sheets_service.py#L30)
  Firma: `SheetsService.metadata(self)`.

- `SheetsService.read_range` — Lee un rango preciso de una hoja autorizada. [Código, línea 34](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sheets_service.py#L34)
  Firma: `SheetsService.read_range(self, cells)`.

- `SheetsService.columns` — Obtiene los encabezados reales para resolver posiciones sin inventar columnas. [Código, línea 41](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sheets_service.py#L41)
  Firma: `SheetsService.columns(self, required=('sku',))`.

- `SheetsService.find_sku` — Busca una fila por SKU único; la ambigüedad bloquea una escritura. [Código, línea 57](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sheets_service.py#L57)
  Firma: `SheetsService.find_sku(self, sku, max_rows=5000)`.

- `SheetsService.update_cell` — Valida SKU, columna y valor previo antes de escribir solo la celda solicitada. [Código, línea 80](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sheets_service.py#L80)
  Firma: `SheetsService.update_cell(self, sku, column, value, expected=None)`.


# Procesos: cola, worker y generador protegido

Sección del índice del código de la aplicación. Las rutas y números de línea corresponden a esta entrega documental; buscar por nombre en una versión posterior. Una función compatible/histórica no implica que su integración esté activada.

## catalog_platform/queue.py

Estado durable de trabajos, locks, lease y cancelación segura entre operaciones.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/queue.py)

- `JobCancelled` — Excepción de control: detener un trabajo no equivale a fallo ni autoriza un reintento. [Código, línea 14](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/queue.py#L14)

- `mark_cancelled` — Finaliza como Cancelado, libera el lease y conserva resultados e incertidumbre de una operación iniciada. [Código, línea 20](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/queue.py#L20)
  Firma: `mark_cancelled(job)`.

- `request_cancel` — Con la fila bloqueada, cancela En cola al instante o marca Deteniendo si hay una llamada vigente; no requiere Redis. [Código, línea 34](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/queue.py#L34)
  Firma: `request_cancel(job)`.

- `request_lock` — Serializa solicitudes con la misma clave dentro del tenant mediante un lock PostgreSQL. [Código, línea 48](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/queue.py#L48)
  Firma: `request_lock(db, tenant, key)`.

- `heartbeat` — Registra que el supervisor sigue activo y la versión que ejecuta. [Código, línea 60](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/queue.py#L60)
  Firma: `heartbeat(owner)`.

- `worker_ready` — Comprueba Redis cuando corresponde y un heartbeat de menos de noventa segundos. [Código, línea 76](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/queue.py#L76)
  Firma: `worker_ready(db)`.

- `available` — Permite aceptar en SQL un trabajo para un worker gratuito que puede despertarse; no afirma que ya esté ejecutándose. [Código, línea 94](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/queue.py#L94)
  Firma: `available(db)`.

- `dispatch` — Registra el ID para su entrega posterior al commit; no ejecuta el trabajo dentro de la petición HTTP. [Código, línea 105](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/queue.py#L105)
  Firma: `dispatch(db, job)`.

- `recover_expired` — Recupera leases vencidos; nunca reencola cancelados ni repite automáticamente una operación con resultado incierto. [Código, línea 113](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/queue.py#L113)
  Firma: `recover_expired(db)`.

- `claim` — Reclama bajo lock un único trabajo En cola, le asigna propietario y lease de cinco minutos. [Código, línea 136](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/queue.py#L136)
  Firma: `claim(owner, job_id=None)`.

- `checkpoint` — Persiste progreso/resultado y comprueba propietario/cancelación antes del siguiente paso; confirma SQL antes de lanzar JobCancelled. [Código, línea 172](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/queue.py#L172)
  Firma: `checkpoint(job_id, owner, *, payload=None, progress=None, message=None)`.

- `renew` — Renueva el lease de una llamada en curso, incluso mientras se espera su cancelación. [Código, línea 207](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/queue.py#L207)
  Firma: `renew(job_id, owner)`.

- `finish` — Guarda el resultado final del propietario vigente; Deteniendo termina como Cancelado y conserva el historial. [Código, línea 218](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/queue.py#L218)
  Firma: `finish(job_id, owner, success, message)`.

## catalog_platform/redis_broker.py

Entrega de IDs SQL a RQ y reconciliación de trabajos si Redis no recibió una entrega.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/redis_broker.py)

- `connection_for` — Construye/reutiliza la conexión Redis correspondiente a la URL configurada. [Código, línea 24](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/redis_broker.py#L24)
  Firma: `connection_for(url)`.

- `connection` — Obtiene Redis desde el entorno del proceso. [Código, línea 32](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/redis_broker.py#L32)
  Firma: `connection()`.

- `reachable` — Comprueba disponibilidad de Redis sin consumir un trabajo. [Código, línea 40](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/redis_broker.py#L40)
  Firma: `reachable()`.

- `rq_queue` — Construye la cola RQ con serialización JSON. [Código, línea 48](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/redis_broker.py#L48)
  Firma: `rq_queue()`.

- `publish_one` — Entrega solo el UUID SQL, con deduplicación de despacho; no serializa fotos o credenciales. [Código, línea 53](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/redis_broker.py#L53)
  Firma: `publish_one(job_id)`.

- `publish_committed` — Publica IDs de una transacción ya confirmada y conserva SQL como respaldo si Redis falla. [Código, línea 85](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/redis_broker.py#L85)
  Firma: `publish_committed(ids)`.

- `reconcile` — Revisa la bandeja SQL En cola y recupera entregas pendientes; un trabajo Cancelado no vuelve a ejecutarse. [Código, línea 99](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/redis_broker.py#L99)
  Firma: `reconcile()`.

## catalog_platform/redis_worker.py

Supervisor de procesos RQ, heartbeat SQL y reconciliación periódica.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/redis_worker.py)

- `concurrency` — Valida el número de procesos de imagen entre 1 y 8; aumentar este valor puede aumentar RAM y gasto. [Código, línea 19](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/redis_worker.py#L19)
  Firma: `concurrency()`.

- `main` — Inicia el pool RQ, actualiza heartbeat y reconcilia SQL cada cinco segundos; un pool terminado provoca el reinicio del servicio. [Código, línea 31](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/redis_worker.py#L31)
  Firma: `main(ready=None)`.

- `main.shutdown` — Detiene el grupo de procesos y retira la señal de readiness al recibir una señal de apagado. [Código, línea 51](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/redis_worker.py#L51)
  Firma: `main.shutdown(*_)`.

## catalog_platform/rq_settings.py

Configuración de transporte RQ; los trabajos viajan por ID y con serialización JSON.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/rq_settings.py)

Este módulo configura/importa componentes o registra callbacks anónimos; no declara funciones o clases nombradas propias.

## catalog_platform/studio_jobs.py

Persistencia y recuperación de trabajos de captura que reutilizan el generador aceptado.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/studio_jobs.py)

- `enabled` — Selecciona la orquestación durable cuando STUDIO_IMAGE_JOBS=worker y existe SQL. [Código, línea 21](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/studio_jobs.py#L21)
  Firma: `enabled()`.

- `tenant_for` — Obtiene la carpeta autorizada de la captura que identifica el tenant del trabajo. [Código, línea 26](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/studio_jobs.py#L26)
  Firma: `tenant_for(value)`.

- `public_job` — Traduce el job SQL al contrato compatible de captura sin exponer conexión cifrada. [Código, línea 35](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/studio_jobs.py#L35)
  Firma: `public_job(job)`.

- `find_active` — Busca el trabajo activo del actor, incluyendo Deteniendo, para evitar duplicar una operación. [Código, línea 42](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/studio_jobs.py#L42)
  Firma: `find_active(value)`.

- `recorded_usage` — Lee el consumo ya registrado de la generación para comparar el incremento del trabajo. [Código, línea 57](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/studio_jobs.py#L57)
  Firma: `recorded_usage(value)`.

- `enqueue_capture` — Valida confirmación/snapshot, guarda referencias y encola una captura o corrección idempotente. [Código, línea 76](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/studio_jobs.py#L76)
  Firma: `enqueue_capture(value, current, slots, data, corrections=())`.

- `process_capture` — Ejecuta la captura durable con el generador existente, checkpoints y persistencia de cada candidato. [Código, línea 143](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/studio_jobs.py#L143)
  Firma: `process_capture(job, value, drive, owner)`.

- `restore` — Reconstruye el borrador y los candidatos de un trabajo con referencias Drive. [Código, línea 209](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/studio_jobs.py#L209)
  Firma: `restore(value, payload, job_id)`.

- `get_job` — Consulta un trabajo autorizado y recupera sus resultados para la interfaz de captura. [Código, línea 245](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/studio_jobs.py#L245)
  Firma: `get_job(value, job_id)`.

- `recover_latest` — Recupera el último trabajo propio después de iniciar una sesión nueva. [Código, línea 262](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/studio_jobs.py#L262)
  Firma: `recover_latest(value)`.

- `record_saved` — Marca el trabajo como guardado para no recuperarlo como un borrador pendiente. [Código, línea 286](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/studio_jobs.py#L286)
  Firma: `record_saved(value, current)`.

- `record_approval` — Persiste aprobación/rechazo de un slot conservando el estado de una cancelación. [Código, línea 307](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/studio_jobs.py#L307)
  Firma: `record_approval(value, slot, approved)`.

## catalog_platform/worker.py

Ejecución de un trabajo reclamado: imágenes, guardado, ecommerce y limpieza temporal.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/worker.py)

- `download_reference` — Descarga una referencia autorizada a un temporal del trabajo, sin compartir fotos entre usuarios. [Código, línea 39](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/worker.py#L39)
  Firma: `download_reference(drive, file_id, path)`.

- `file_checksum` — Calcula SHA-256 de un archivo para identificar el contenido de imagen. [Código, línea 48](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/worker.py#L48)
  Firma: `file_checksum(path)`.

- `candidate_folder` — Resuelve el destino temporal de candidatos del job conservando los nombres establecidos. [Código, línea 57](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/worker.py#L57)
  Firma: `candidate_folder(drive, job_id)`.

- `record_usage` — Guarda el uso/coste registrado, incluso si una cancelación ya liberó el lease. [Código, línea 62](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/worker.py#L62)
  Firma: `record_usage(job_id, api_key, initial)`.

- `generation` — Genera slots con el pipeline aceptado y persiste cada resultado; checkpoint y in_flight protegen cancelación y llamadas pagadas. [Código, línea 77](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/worker.py#L77)
  Firma: `generation(job, value, drive)`.

- `generation.progress` — Actualiza progreso mediante checkpoint para detectar cancelación entre pasos del pipeline. [Código, línea 107](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/worker.py#L107)
  Firma: `generation.progress(count, message)`.

- `publication` — Publica ficha y medios aprobados solo después de validar versiones, identidad remota y flags de escritura. [Código, línea 280](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/worker.py#L280)
  Firma: `publication(job, value, drive)`.

- `save_asset` — Guarda un candidato aprobado en Drive mediante respaldo previo y versionado; conserva IDs e historial. [Código, línea 447](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/worker.py#L447)
  Firma: `save_asset(job, value, drive)`.

- `process` — Despacha por kind con la conexión cifrada del actor; no trata JobCancelled como error de proveedor. [Código, línea 478](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/worker.py#L478)
  Firma: `process(job)`.

- `execute_job` — Reclama un ID SQL, renueva lease y ejecuta con checkpoints; cancelación y limpieza son independientes del cierre del navegador. [Código, línea 557](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/worker.py#L557)
  Firma: `execute_job(job_id)`.

- `execute_job.renew` — Mantiene el lease en un hilo mientras el worker espera una operación externa. [Código, línea 563](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/worker.py#L563)
  Firma: `execute_job.renew()`.

- `main` — Entrada compatible de worker; usa el supervisor RQ cuando está configurado y conserva el modo PostgreSQL anterior. [Código, línea 607](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/worker.py#L607)
  Firma: `main()`.

- `main.keeper` — Mantiene el heartbeat del worker compatible y solicita parada si falla su mantenimiento. [Código, línea 627](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/worker.py#L627)
  Firma: `main.keeper()`.

## catalog_platform/worker_wakeup.py

Aviso de arranque al worker gratuito mediante su health público, sin credenciales.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/worker_wakeup.py)

- `health_url` — Valida el origen HTTPS onrender.com del worker antes de construir la URL de salud. [Código, línea 20](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/worker_wakeup.py#L20)
  Firma: `health_url()`.

- `configured` — Indica si hay un worker gratuito configurado que pueda recibir el aviso de arranque. [Código, línea 35](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/worker_wakeup.py#L35)
  Firma: `configured()`.

- `notify` — Agrupa avisos concurrentes de trabajos confirmados en un hilo de arranque. [Código, línea 43](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/worker_wakeup.py#L43)
  Firma: `notify()`.

- `_wake` — Hace una lectura de salud sin cookies ni secretos y con tiempo limitado; no genera ni reintenta una escritura. [Código, línea 65](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/worker_wakeup.py#L65)
  Firma: `_wake()`.

## catalog_platform/worker_web.py

Entrada del worker gratuito: servidor HTTP mínimo de salud y supervisor de trabajos.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/worker_web.py)

- `health_server` — Sirve únicamente salud/readiness por HTTP para el worker gratuito; no ejecuta imágenes en la petición. [Código, línea 14](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/worker_web.py#L14)
  Firma: `health_server(ready, port)`.

- `health_server.HealthHandler` — Handler HTTP mínimo que expone readiness del supervisor del worker. [Código, línea 15](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/worker_web.py#L15)

- `health_server.HealthHandler.setup` — Limita a cinco segundos el socket de una consulta pública de salud. [Código, línea 16](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/worker_web.py#L16)
  Firma: `health_server.HealthHandler.setup(self)`.

- `health_server.HealthHandler.do_GET` — Acepta solo /service-health y responde versión/readiness sin datos de sesión ni tareas de imagen. [Código, línea 20](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/worker_web.py#L20)
  Firma: `health_server.HealthHandler.do_GET(self)`.

- `health_server.HealthHandler.log_message` — Omite rutas/cabeceras arbitrarias en logs del puerto público. [Código, línea 36](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/worker_web.py#L36)
  Firma: `health_server.HealthHandler.log_message(self, *_)`.

- `main` — Arranca el health y mantiene el supervisor RQ en el proceso principal. [Código, línea 44](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/worker_web.py#L44)
  Firma: `main()`.

## creative_pipeline.py

Pipeline protegido de investigación, referencias, prompts y generación de imágenes Gemini.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/creative_pipeline.py)

- `product_data` — Selecciona los campos de producto que alimentan la investigación y el prompt aceptado. [Código, línea 31](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/creative_pipeline.py#L31)
  Firma: `product_data(product)`.

- `interaction_for` — Resuelve una interacción coherente con el tipo de producto para el brief de uso. [Código, línea 37](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/creative_pipeline.py#L37)
  Firma: `interaction_for(product)`.

- `interaction_for.has` — Comprueba patrones de producto dentro del contexto normalizado de interacción. [Código, línea 48](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/creative_pipeline.py#L48)
  Firma: `interaction_for.has(words)`.

- `fallback_brief` — Construye el brief de respaldo existente cuando la investigación no aporta uno válido. [Código, línea 65](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/creative_pipeline.py#L65)
  Firma: `fallback_brief(product, reason='No se encontraron anuncios verificables.')`.

- `grounding` — Extrae fuentes/enlaces de investigación de la respuesta Gemini. [Código, línea 82](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/creative_pipeline.py#L82)
  Firma: `grounding(response)`.

- `brief` — Investiga y valida el brief creativo lifestyle/comercial con las referencias existentes. [Código, línea 98](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/creative_pipeline.py#L98)
  Firma: `brief(client, product, style_paths=())`.

- `plan_key` — Identifica el contexto/referencias del plan para reutilizarlo sin mezclar productos. [Código, línea 140](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/creative_pipeline.py#L140)
  Firma: `plan_key(product, style_paths)`.

- `load_style_examples` — Lee referencias de estilo únicamente de la carpeta de la sesión. [Código, línea 145](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/creative_pipeline.py#L145)
  Firma: `load_style_examples(runtime, session)`.

- `image_config` — Construye la configuración de imagen/modelo del pipeline protegido. [Código, línea 186](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/creative_pipeline.py#L186)
  Firma: `image_config()`.

- `image_contents` — Construye las partes de prompt y referencias visuales del modelo. [Código, línea 191](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/creative_pipeline.py#L191)
  Firma: `image_contents(paths, prompt, slot, *, previous=None, corrections=(), styles=())`.

- `extract_image` — Extrae y valida los bytes de imagen de la respuesta Gemini. [Código, línea 210](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/creative_pipeline.py#L210)
  Firma: `extract_image(response)`.

- `generate` — Llama al modelo de imagen aceptado y entrega el resultado para marca/QA/guardado. [Código, línea 220](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/creative_pipeline.py#L220)
  Firma: `generate(client, paths, prompt, slot, *, previous=None, corrections=(), styles=())`.

## gemini_gateway.py

Cliente Gemini con presupuesto, rate limiting, caché de texto y contabilización de uso.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/gemini_gateway.py)

- `text_config` — Configuración protegida del modelo de texto; preserva opciones aceptadas. [Código, línea 21](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/gemini_gateway.py#L21)
  Firma: `text_config(max_tokens=1024, *, search=False, model='gemini-2.5-flash')`.

- `image_part` — Preparación protegida de una referencia visual inline con límites de tamaño. [Código, línea 35](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/gemini_gateway.py#L35)
  Firma: `image_part(path)`.

- `parse_json` — Extrae JSON de respuestas con texto/fences sin usar una captura de llaves ambigua. [Código, línea 50](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/gemini_gateway.py#L50)
  Firma: `parse_json(text)`.

- `usage_for_key` — Devuelve uso agregado bajo el hash de la clave, sin revelar la clave original. [Código, línea 66](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/gemini_gateway.py#L66)
  Firma: `usage_for_key(api_key)`.

- `_fingerprint` — Deriva una identidad de contenido para caché sin persistir el contenido secreto. [Código, línea 74](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/gemini_gateway.py#L74)
  Firma: `_fingerprint(value)`.

- `_reserve` — Reserva presupuesto y cuota local antes de permitir una llamada al proveedor. [Código, línea 86](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/gemini_gateway.py#L86)
  Firma: `_reserve(owner)`.

- `GeminiClient` — Cliente medido de Gemini con cuota, uso y caché de texto; no decide el flujo del worker. [Código, línea 105](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/gemini_gateway.py#L105)

- `GeminiClient.__init__` — Asocia una clave personal al cliente y sus contadores por hash. [Código, línea 106](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/gemini_gateway.py#L106)
  Firma: `GeminiClient.__init__(self, api_key)`.

- `GeminiClient.generate_content` — Aplica límites, caché elegible y medición antes/después de la llamada Gemini. [Código, línea 111](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/gemini_gateway.py#L111)
  Firma: `GeminiClient.generate_content(self, *, model, contents, config=None)`.

## image_generation_service.py

Fachada que reutiliza el generador Gemini aceptado; los otros proveedores son reservas inactivas.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/image_generation_service.py)

- `ImageProvider` — Contrato de proveedor de imagen; no habilita un proveedor nuevo. [Código, línea 8](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/image_generation_service.py#L8)
  Campos declarados: `name: str`, `model: str`.

- `ImageProvider.generate` — Firma común de generación que debe cumplir el proveedor configurado. [Código, línea 12](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/image_generation_service.py#L12)
  Firma: `ImageProvider.generate(self, *args, **kwargs)`.

- `GeminiProvider` — Proveedor activo que conserva el modelo del pipeline aceptado. [Código, línea 15](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/image_generation_service.py#L15)

- `GeminiProvider.generate` — Delega en creative_pipeline.generate sin reescribir prompts o referencias. [Código, línea 19](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/image_generation_service.py#L19)
  Firma: `GeminiProvider.generate(self, *args, **kwargs)`.

- `UnconfiguredProvider` — Base que falla de forma explícita para proveedores aún no habilitados. [Código, línea 23](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/image_generation_service.py#L23)

- `UnconfiguredProvider.generate` — Rechaza uso de un proveedor preparado pero no configurado. [Código, línea 24](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/image_generation_service.py#L24)
  Firma: `UnconfiguredProvider.generate(self, *args, **kwargs)`.

- `FluxProvider` — Reserva inactiva para Flux; no participa en la generación actual. [Código, línea 30](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/image_generation_service.py#L30)

- `OpenAIProvider` — Reserva inactiva para OpenAI; no participa en la generación actual. [Código, línea 34](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/image_generation_service.py#L34)

- `PhotoRoomProvider` — Reserva inactiva para PhotoRoom; no participa en la generación actual. [Código, línea 38](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/image_generation_service.py#L38)

- `ImageGenerationService` — Fachada aceptada de brief, generación, marca, QA y correcciones. [Código, línea 42](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/image_generation_service.py#L42)

- `ImageGenerationService.__init__` — Exige AI_PROVIDER=gemini para conservar el proveedor aceptado. [Código, línea 47](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/image_generation_service.py#L47)
  Firma: `ImageGenerationService.__init__(self)`.

- `ImageGenerationService.plan` — Delega la planificación en studio_api.creative_plan, protegida por contrato. [Código, línea 51](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/image_generation_service.py#L51)
  Firma: `ImageGenerationService.plan(self, value, current, progress)`.

- `ImageGenerationService.generate` — Delega en studio_api.make_image y devuelve el slot resultante del borrador. [Código, línea 56](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/image_generation_service.py#L56)
  Firma: `ImageGenerationService.generate(self, value, current, slot, prompt, styles, **options)`.

## product_generation.py

Limpieza de descripciones y composición de la marca sobre las imágenes.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/product_generation.py)

- `clean_description` — Limpia el texto del modelo conservando párrafos legibles. [Código, línea 19](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/product_generation.py#L19)
  Firma: `clean_description(value, *, short=False)`.

- `branded_image` — Aplica la composición de marca aceptada; no cambiar posiciones para corregir OAuth o cola. [Código, línea 40](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/product_generation.py#L40)
  Firma: `branded_image(image, logo)`.


# Integraciones: WooCommerce, medios y stock

Sección del índice del código de la aplicación. Las rutas y números de línea corresponden a esta entrega documental; buscar por nombre en una versión posterior. Una función compatible/histórica no implica que su integración esté activada.

## bulk_product_upload.py

Planificación y publicación históricas por oleadas, con resolución de padres y variantes.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/bulk_product_upload.py)

- `worker_limit` — Determina el límite de concurrencia del publicador histórico por oleadas. [Código, línea 9](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/bulk_product_upload.py#L9)
  Firma: `worker_limit(value=2)`.

- `plan_skus` — Prepara el orden/selección de SKU que se publicarán. [Código, línea 17](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/bulk_product_upload.py#L17)
  Firma: `plan_skus(inventory, selected)`.

- `next_wave` — Selecciona la próxima oleada respetando dependencias padre/variante. [Código, línea 40](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/bulk_product_upload.py#L40)
  Firma: `next_wave(items, index, workers)`.

- `run_wave` — Ejecuta una oleada de publicaciones históricas con su registro de resultados. [Código, línea 56](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/bulk_product_upload.py#L56)
  Firma: `run_wave(items, job, workers)`.

- `parent_attributes` — Obtiene atributos que el padre variable debe ofrecer a sus variantes. [Código, línea 63](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/bulk_product_upload.py#L63)
  Firma: `parent_attributes(parent_sku, inventory)`.

- `ensure_entity` — Resuelve o crea la entidad explícita necesaria para la publicación histórica. [Código, línea 84](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/bulk_product_upload.py#L84)
  Firma: `ensure_entity(wc, row, inventory, include_stock=False)`.

- `stock_is_placeholder` — Distingue un stock ausente/de relleno de una cantidad real antes de publicar. [Código, línea 128](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/bulk_product_upload.py#L128)
  Firma: `stock_is_placeholder(inventory)`.

- `publish_created` — A retry publishes our verified draft, without publishing other drafts. [Código, línea 133](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/bulk_product_upload.py#L133)
  Firma: `publish_created(wc, entity, created)`.

## catalog_platform/ecommerce.py

Lecturas WooCommerce, snapshots de pedidos/productos y asociación de identidades remotas.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/ecommerce.py)

- `parse_time` — Convierte fechas del proveedor a la representación usada por los snapshots. [Código, línea 26](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/ecommerce.py#L26)
  Firma: `parse_time(value)`.

- `store_order` — Inserta/actualiza un snapshot de pedido por su identidad WooCommerce. [Código, línea 41](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/ecommerce.py#L41)
  Firma: `store_order(db, tenant, data)`.

- `apply_snapshot` — Aplica una lectura remota a una ficha viva sin reactivar un tombstone eliminado. [Código, línea 61](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/ecommerce.py#L61)
  Firma: `apply_snapshot(db, product, data, event_id, actor)`.

- `refresh` — Consulta tienda por páginas con checkpoints; omite IDs eliminados y registra snapshots/resultados. [Código, línea 99](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/ecommerce.py#L99)
  Firma: `refresh(job, owner, value=None, drive=None)`.

- `remote_fields` — Selecciona los campos remotos que se conservan en el catálogo local. [Código, línea 324](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/ecommerce.py#L324)
  Firma: `remote_fields(data)`.

- `copy_first_image` — Descarga y asocia la primera imagen remota cuando la importación explícita lo requiere. [Código, línea 363](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/ecommerce.py#L363)
  Firma: `copy_first_image(job, value, drive, product_id, data)`.

## catalog_platform/enrichment.py

Propuesta de textos/clasificación por IA para revisión, sin aplicar precios o stock automáticamente.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/enrichment.py)

- `enrich` — Genera una propuesta de textos/clasificación con vocabulario existente; queda para revisión y no cambia stock o precio automáticamente. [Código, línea 15](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/enrichment.py#L15)
  Firma: `enrich(job, owner, value, drive)`.

## catalog_platform/inventory.py

Escritura explícita de stock comprobando entidad, valor inicial y resultado remoto.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/inventory.py)

- `sync_stock` — Identifica producto/variante, coteja stock remoto previo y confirma la escritura autorizada; no reintenta una cantidad incierta a ciegas. [Código, línea 15](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/inventory.py#L15)
  Firma: `sync_stock(job, owner)`.

## catalog_platform/webhooks.py

Verificación de firma, deduplicación y procesamiento durable de eventos externos.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/webhooks.py)

- `signature_valid` — Comprueba la firma del cuerpo recibido antes de aceptar un evento externo. [Código, línea 30](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/webhooks.py#L30)
  Firma: `signature_valid(raw, signature, secret)`.

- `receive` — Valida, deduplica y guarda cifrado el evento antes de encolar su procesamiento. [Código, línea 38](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/webhooks.py#L38)
  Firma: `receive(provider, request)`.

- `woocommerce` — Entrada del webhook WooCommerce que delega la verificación y persistencia. [Código, línea 138](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/webhooks.py#L138)
  Firma: `woocommerce(request: Request)`.
  Rutas/decoradores HTTP: `router.post('/webhooks/woocommerce', status_code=202)`; `router.post('/api/webhooks/woocommerce', status_code=202)`.

- `loyverse` — Entrada preparada para Loyverse, sujeta a la configuración de esa integración. [Código, línea 145](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/webhooks.py#L145)
  Firma: `loyverse(request: Request)`.
  Rutas/decoradores HTTP: `router.post('/webhooks/loyverse', status_code=202)`; `router.post('/api/webhooks/loyverse', status_code=202)`.

- `process_event` — Aplica un evento identificado con checkpoints y conserva el estado sin resucitar productos retirados. [Código, línea 151](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/webhooks.py#L151)
  Firma: `process_event(job, owner)`.

## ecommerce_services.py

Servicios de producto WooCommerce y medios WordPress sobre los clientes HTTP existentes.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/ecommerce_services.py)

- `WordPressMediaService` — Fachada de medios WordPress con validación de descarga y metadata. [Código, línea 8](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/ecommerce_services.py#L8)

- `WordPressMediaService.__init__` — Crea el cliente de medios con la conexión existente. [Código, línea 9](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/ecommerce_services.py#L9)
  Firma: `WordPressMediaService.__init__(self, client=None)`.

- `WordPressMediaService.upload` — Delega la subida validada al cliente WordPress, sujeta a WP_MEDIA_WRITE_ENABLED. [Código, línea 12](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/ecommerce_services.py#L12)
  Firma: `WordPressMediaService.upload(self, data, name, alt_text)`.

- `WordPressMediaService.get` — Consulta un medio existente por su ID WordPress. [Código, línea 17](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/ecommerce_services.py#L17)
  Firma: `WordPressMediaService.get(self, media_id)`.

- `WordPressMediaService.download` — Descarga imagen remota comprobando destino, tipo y límite de bytes. [Código, línea 20](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/ecommerce_services.py#L20)
  Firma: `WordPressMediaService.download(self, media_id)`.

- `WordPressMediaService.update_alt` — Actualiza explícitamente el texto alternativo de un medio identificado. [Código, línea 49](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/ecommerce_services.py#L49)
  Firma: `WordPressMediaService.update_alt(self, media_id, alt_text)`.

- `WooCommerceService` — Fachada de catálogo/pedidos que conserva el cliente WooCommerce y su control de escrituras. [Código, línea 60](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/ecommerce_services.py#L60)

- `WooCommerceService.__init__` — Crea el cliente y limita reintentos de transporte a lecturas seguras. [Código, línea 61](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/ecommerce_services.py#L61)
  Firma: `WooCommerceService.__init__(self, client=None)`.

- `WooCommerceService.product` — Lee un producto remoto por ID. [Código, línea 68](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/ecommerce_services.py#L68)
  Firma: `WooCommerceService.product(self, product_id)`.

- `WooCommerceService.variation` — Lee una variante remota por IDs de padre e hijo. [Código, línea 71](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/ecommerce_services.py#L71)
  Firma: `WooCommerceService.variation(self, parent, variation)`.

- `WooCommerceService.resolve` — Resuelve la entidad por IDs/mapping o SKU exacto y rechaza relaciones ambiguas. [Código, línea 76](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/ecommerce_services.py#L76)
  Firma: `WooCommerceService.resolve(self, product)`.

- `WooCommerceService.categories` — Consulta categorías de tienda. [Código, línea 95](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/ecommerce_services.py#L95)
  Firma: `WooCommerceService.categories(self)`.

- `WooCommerceService.orders` — Consulta una página de pedidos reales. [Código, línea 100](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/ecommerce_services.py#L100)
  Firma: `WooCommerceService.orders(self, since=None, page=1)`.

- `WooCommerceService.publish` — Construye campos revisados y publica sobre la entidad identificada con protección de escrituras. [Código, línea 113](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/ecommerce_services.py#L113)
  Firma: `WooCommerceService.publish(self, product, media_ids, parent=None, terms=None)`.

## single_product_auto.py

Sincronización compatible del SKU recién guardado, condicionada por los interruptores existentes.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/single_product_auto.py)

- `_text` — Normaliza texto de campos de una ficha histórica. [Código, línea 26](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/single_product_auto.py#L26)
  Firma: `_text(value: Any)`.

- `_terms_payload` — Traduce clasificación revisada a términos para el payload WooCommerce. [Código, línea 30](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/single_product_auto.py#L30)
  Firma: `_terms_payload(tax: dict[str, Any])`.

- `_create_simple` — Crea el producto simple en el flujo histórico bajo flags de escritura. [Código, línea 41](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/single_product_auto.py#L41)
  Firma: `_create_simple(row: dict[str, Any], wc: WooCommerceClient, image_result: dict[str, Any])`.

- `sync_saved_sku` — Sincroniza exclusivamente el SKU recién guardado por la interfaz IA. [Código, línea 73](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/single_product_auto.py#L73)
  Firma: `sync_saved_sku(session: dict[str, Any], sku: str)`.

## store_connection.py

Interruptor global de conectividad WooCommerce; separa el modo solo Drive de la tienda habilitada.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/store_connection.py)

- `drive_only` — Indica si SUITE_DRIVE_ONLY mantiene desactivadas las operaciones de tienda. [Código, línea 5](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/store_connection.py#L5)
  Firma: `drive_only()`.

- `require_store_connection` — Rechaza una operación WooCommerce en modo solo Drive; no cambia flags de escritura. [Código, línea 10](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/store_connection.py#L10)
  Firma: `require_store_connection(error_type=RuntimeError)`.

## woo_to_sheets_colab.py

Herramienta independiente de importación WooCommerce a Sheets; no se ejecuta por abrir la app.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woo_to_sheets_colab.py)

- `WooReader` — Lector paginado de la herramienta independiente WooCommerce a Sheets. [Código, línea 15](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woo_to_sheets_colab.py#L15)

- `WooReader.__init__` — Configura conexión y límites del lector de importación. [Código, línea 16](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woo_to_sheets_colab.py#L16)
  Firma: `WooReader.__init__(self, url, key, secret)`.

- `WooReader.pages` — Lee páginas del recurso remoto hasta completar el conjunto previsto. [Código, línea 23](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woo_to_sheets_colab.py#L23)
  Firma: `WooReader.pages(self, endpoint, **params)`.

- `category_paths` — Construye relaciones/caminos de las categorías remotas. [Código, línea 49](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woo_to_sheets_colab.py#L49)
  Firma: `category_paths(categories)`.

- `category_value` — Traduce las categorías de una ficha a su valor de columna Sheets. [Código, línea 65](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woo_to_sheets_colab.py#L65)
  Firma: `category_value(items, paths)`.

- `record` — Convierte un producto/variante WooCommerce al contrato de fila de importación. [Código, línea 72](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woo_to_sheets_colab.py#L72)
  Firma: `record(product, paths, parent=None)`.

- `download_catalog` — Descarga catálogo y relaciones necesarios para preparar el plan independiente. [Código, línea 108](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woo_to_sheets_colab.py#L108)
  Firma: `download_catalog(reader)`.

- `column_letter` — Convierte una posición de columna a su notación A1. [Código, línea 131](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woo_to_sheets_colab.py#L131)
  Firma: `column_letter(index)`.

- `make_plan` — Prepara filas y destinos de escritura antes de aplicar la importación independiente. [Código, línea 139](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woo_to_sheets_colab.py#L139)
  Firma: `make_plan(values, formulas, records, add_new=True)`.

- `apply_plan` — Aplica el plan explícito de esa herramienta a Sheets; no se ejecuta por abrir la app. [Código, línea 184](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woo_to_sheets_colab.py#L184)
  Firma: `apply_plan(book, worksheet, baseline, baseline_formulas, writes, row_count, col_count)`.

## woocommerce_batch_sync.py

Registro y lectura del progreso de lotes históricos en una pestaña de Sheets.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_batch_sync.py)

- `_now` — Fecha de los registros históricos de progreso de lote. [Código, línea 24](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_batch_sync.py#L24)
  Firma: `_now()`.

- `_sheet_map` — Relaciona encabezados reales con posiciones de columnas. [Código, línea 28](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_batch_sync.py#L28)
  Firma: `_sheet_map(sheets_service, spreadsheet_id: str)`.

- `ensure_batch_sheet` — Prepara la pestaña de lotes solo en el flujo histórico de escritura explícito. [Código, línea 39](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_batch_sync.py#L39)
  Firma: `ensure_batch_sheet(sheets_service, spreadsheet_id: str)`.

- `_all_rows` — Lee filas del registro de lotes compatible. [Código, línea 72](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_batch_sync.py#L72)
  Firma: `_all_rows(sheets_service, spreadsheet_id: str)`.

- `successful_skus` — Extrae los SKU cuyo paso ya terminó correctamente. [Código, línea 95](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_batch_sync.py#L95)
  Firma: `successful_skus(sheets_service, spreadsheet_id: str)`.

- `processed_skus` — Extrae los SKU que ya tienen registro de procesamiento para revisión/reanudación. [Código, línea 103](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_batch_sync.py#L103)
  Firma: `processed_skus(sheets_service, spreadsheet_id: str)`.

- `create_batch` — Crea el registro de un lote histórico autorizado. [Código, línea 111](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_batch_sync.py#L111)
  Firma: `create_batch(sheets_service, spreadsheet_id: str, skus: list[str], *, include_images=True, include_stock=False, workers=2)`.

- `read_batch` — Lee el lote identificado y sus pasos. [Código, línea 139](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_batch_sync.py#L139)
  Firma: `read_batch(sheets_service, spreadsheet_id: str, batch_id: str)`.

- `update_batch_item_fast` — Actualiza solo E:I en una llamada; ideal para el loop de sincronización. [Código, línea 147](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_batch_sync.py#L147)
  Firma: `update_batch_item_fast(sheets_service, spreadsheet_id: str, *, sheet_row: int, status: str, message: str='', started_at: str='', finished_at: str='', permalink: str='')`.

- `update_batch_item` — Compatibilidad: preserva campos omitidos leyendo la fila antes de escribir. [Código, línea 174](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_batch_sync.py#L174)
  Firma: `update_batch_item(sheets_service, spreadsheet_id: str, *, sheet_row: int, status: str, message: str='', started_at: str | None=None, finished_at: str | None=None, permalink: str='')`.

- `batch_summary` — Resume progreso/resultados del lote registrado. [Código, línea 209](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_batch_sync.py#L209)
  Firma: `batch_summary(rows: list[dict[str, Any]])`.

## woocommerce_catalog_light.py

Índice ligero WooCommerce por SKU y caché de lecturas de productos/variantes.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_catalog_light.py)

- `_slim` — Selecciona campos mínimos de una entidad WooCommerce para el índice. [Código, línea 24](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_catalog_light.py#L24)
  Firma: `_slim(row: dict[str, Any], entity_type: str, parent_id: int | None=None)`.

- `_pages` — Recorre páginas de lectura del cliente WooCommerce. [Código, línea 41](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_catalog_light.py#L41)
  Firma: `_pages(client: WooCommerceClient, endpoint: str, fields: str)`.

- `catalog_by_sku_light` — Construye/cachea un catálogo reducido por SKU conservando relaciones y ambigüedades. [Código, línea 54](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_catalog_light.py#L54)
  Firma: `catalog_by_sku_light(client: WooCommerceClient, *, force: bool=False)`.

- `catalog_by_sku_light.add` — Añade una entidad identificada al índice ligero. [Código, línea 67](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_catalog_light.py#L67)
  Firma: `catalog_by_sku_light.add(row: dict[str, Any], entity_type: str, parent_id: int | None=None)`.

- `catalog_by_sku_light.fetch_variations` — Lee las variantes de un padre para completar el índice. [Código, línea 83](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_catalog_light.py#L83)
  Firma: `catalog_by_sku_light.fetch_variations(parent_id: int)`.

- `clear_catalog_cache` — Invalida la caché ligera después de cambios que afectan sus lecturas. [Código, línea 111](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_catalog_light.py#L111)
  Firma: `clear_catalog_cache()`.

## woocommerce_client.py

Transporte WooCommerce: autenticación, paginación, búsqueda exacta de entidades y escrituras controladas.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_client.py)

- `WooCommerceError` — Error de transporte/configuración WooCommerce que puede convertirse en un mensaje público redactado. [Código, línea 21](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_client.py#L21)

- `WooCommerceConfig` — Datos de conexión y límites de HTTP; no deben copiarse con sus valores a Notion/logs. [Código, línea 33](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_client.py#L33)
  Campos declarados: `base_url: str`, `consumer_key: str`, `consumer_secret: str`, `write_enabled: bool`, `timeout: int`, `max_workers: int`, `metadata_workers: int`, `cache_ttl: int`.

- `WooCommerceConfig.from_env` — Lee configuración del entorno conservando nombres de variables y límites permitidos. [Código, línea 44](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_client.py#L44)
  Firma: `WooCommerceConfig.from_env(cls)`.

- `WooCommerceConfig.configured` — Indica si están presentes los datos necesarios de conexión. [Código, línea 61](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_client.py#L61)
  Firma: `WooCommerceConfig.configured(self)`.

- `WooCommerceClient` — Cliente REST WooCommerce usado por catálogo y herramientas compatibles. [Código, línea 65](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_client.py#L65)

- `WooCommerceClient.__init__` — Configura sesión HTTP, límites y política de reintento. [Código, línea 66](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_client.py#L66)
  Firma: `WooCommerceClient.__init__(self, config: WooCommerceConfig | None=None)`.

- `WooCommerceClient._auth_header` — Construye la autenticación en servidor sin enviar claves al navegador. [Código, línea 83](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_client.py#L83)
  Firma: `WooCommerceClient._auth_header(self)`.

- `WooCommerceClient._invalidate_catalog_cache` — Invalida lecturas cacheadas tras una escritura del catálogo. [Código, línea 89](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_client.py#L89)
  Firma: `WooCommerceClient._invalidate_catalog_cache(self)`.

- `WooCommerceClient.request` — Ejecuta HTTP con modo de tienda y WC_WRITE_ENABLED comprobados; convierte fallos del proveedor en errores controlados. [Código, línea 95](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_client.py#L95)
  Firma: `WooCommerceClient.request(self, method: str, endpoint: str, *, params: dict[str, Any] | None=None, payload: dict[str, Any] | None=None)`.

- `WooCommerceClient.list_products` — Lee una página completa de productos. [Código, línea 138](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_client.py#L138)
  Firma: `WooCommerceClient.list_products(self, *, page: int=1, per_page: int=100)`.

- `WooCommerceClient.list_products_catalog` — Lee una página con campos reducidos para construir el catálogo. [Código, línea 141](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_client.py#L141)
  Firma: `WooCommerceClient.list_products_catalog(self, *, page: int=1, per_page: int=100)`.

- `WooCommerceClient.get_product` — Lee un producto por ID WooCommerce. [Código, línea 152](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_client.py#L152)
  Firma: `WooCommerceClient.get_product(self, product_id: int)`.

- `WooCommerceClient.list_variations` — Lee una página de variantes de un padre. [Código, línea 155](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_client.py#L155)
  Firma: `WooCommerceClient.list_variations(self, product_id: int, *, page: int=1, per_page: int=100)`.

- `WooCommerceClient.list_variations_catalog` — Lee campos reducidos de variantes para indexarlas. [Código, línea 158](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_client.py#L158)
  Firma: `WooCommerceClient.list_variations_catalog(self, product_id: int, *, page: int=1, per_page: int=100)`.

- `WooCommerceClient.get_variation` — Lee una variante por sus IDs de padre e hijo. [Código, línea 169](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_client.py#L169)
  Firma: `WooCommerceClient.get_variation(self, parent_product_id: int, variation_id: int)`.

- `WooCommerceClient.list_setting_groups` — Consulta grupos de configuración WooCommerce. [Código, línea 172](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_client.py#L172)
  Firma: `WooCommerceClient.list_setting_groups(self)`.

- `WooCommerceClient.list_settings` — Consulta opciones de un grupo de configuración. [Código, línea 175](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_client.py#L175)
  Firma: `WooCommerceClient.list_settings(self, group_id: str)`.

- `WooCommerceClient.get_setting` — Consulta una opción de configuración identificada. [Código, línea 178](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_client.py#L178)
  Firma: `WooCommerceClient.get_setting(self, group_id: str, setting_id: str)`.

- `WooCommerceClient._iter_pages` — Recorre páginas hasta terminar la lectura dentro del límite previsto. [Código, línea 181](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_client.py#L181)
  Firma: `WooCommerceClient._iter_pages(self, getter, *, per_page: int=100, max_pages: int=100)`.

- `WooCommerceClient.list_all_products` — Reúne productos paginados mediante el iterador del cliente. [Código, línea 190](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_client.py#L190)
  Firma: `WooCommerceClient.list_all_products(self)`.

- `WooCommerceClient.list_all_variations` — Reúne variantes paginadas de un padre. [Código, línea 193](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_client.py#L193)
  Firma: `WooCommerceClient.list_all_variations(self, product_id: int)`.

- `WooCommerceClient.list_all_variations_catalog` — Reúne las variantes con campos reducidos. [Código, línea 196](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_client.py#L196)
  Firma: `WooCommerceClient.list_all_variations_catalog(self, product_id: int)`.

- `WooCommerceClient._slim` — Extrae campos necesarios para un índice ligero de catálogo. [Código, línea 200](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_client.py#L200)
  Firma: `WooCommerceClient._slim(row: dict[str, Any], entity_type: str, parent_id: int | None=None)`.

- `WooCommerceClient.catalog_by_sku` — Construye/cacha el índice SKU y detecta duplicados; conserva relaciones padre/variante. [Código, línea 216](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_client.py#L216)
  Firma: `WooCommerceClient.catalog_by_sku(self, *, include_variations: bool=True, force_refresh: bool=False)`.

- `WooCommerceClient.catalog_by_sku.add` — Inserta una entidad en el índice y conserva la lista de duplicados de SKU. [Código, línea 229](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_client.py#L229)
  Firma: `WooCommerceClient.catalog_by_sku.add(row: dict[str, Any], entity_type: str, parent_id: int | None=None)`.

- `WooCommerceClient.find_entity_by_sku` — Busca un SKU exacto acotado antes de recurrir al índice completo compatible. [Código, línea 274](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_client.py#L274)
  Firma: `WooCommerceClient.find_entity_by_sku(self, sku: str, parent_sku: str='')`.

- `WooCommerceClient.find_product_by_sku` — Busca productos por SKU y confirma coincidencia exacta en la respuesta. [Código, línea 304](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_client.py#L304)
  Firma: `WooCommerceClient.find_product_by_sku(self, sku: str)`.

- `WooCommerceClient.update_stock` — Escribe stock de una entidad identificada mediante el transporte controlado. [Código, línea 311](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_client.py#L311)
  Firma: `WooCommerceClient.update_stock(self, product_id: int, stock_quantity: int)`.

- `WooCommerceClient.update_product` — Actualiza un producto por ID con WC_WRITE_ENABLED comprobado. [Código, línea 314](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_client.py#L314)
  Firma: `WooCommerceClient.update_product(self, product_id: int, payload: dict[str, Any])`.

- `WooCommerceClient.update_variation` — Actualiza una variante por IDs de padre/hijo con escritura autorizada. [Código, línea 317](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_client.py#L317)
  Firma: `WooCommerceClient.update_variation(self, parent_product_id: int, variation_id: int, payload: dict[str, Any])`.

## woocommerce_image_sync.py

Asociación de imágenes por naming, previsualización y sincronización histórica por producto.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_image_sync.py)

- `parse_image_names` — Separa los nombres de imágenes registrados en una fila de inventario. [Código, línea 33](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_image_sync.py#L33)
  Firma: `parse_image_names(value: Any)`.

- `list_drive_images` — Lista la carpeta elegida por el usuario; nunca usa un ID ajeno por defecto. [Código, línea 37](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_image_sync.py#L37)
  Firma: `list_drive_images(drive_service, folder_id: str | None=None)`.

- `fallback_names` — Obtiene nombres compatibles por SKU cuando no hay una lista explícita de archivos. [Código, línea 64](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_image_sync.py#L64)
  Firma: `fallback_names(sku: str, position: int)`.

- `resolve_product_images` — Resuelve referencias Drive correspondientes a los nombres de un producto. [Código, línea 75](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_image_sync.py#L75)
  Firma: `resolve_product_images(row: dict[str, Any], drive_index: dict[str, dict[str, Any]])`.

- `ensure_media_sync_sheet` — Prepara el registro histórico de sincronización de medios en el flujo autorizado. [Código, línea 108](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_image_sync.py#L108)
  Firma: `ensure_media_sync_sheet(sheets_service, spreadsheet_id: str)`.

- `read_media_cache` — Lee relaciones de archivos Drive y medios WordPress ya registrados. [Código, línea 130](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_image_sync.py#L130)
  Firma: `read_media_cache(sheets_service, spreadsheet_id: str)`.

- `append_media_log` — Añade el resultado identificado de una sincronización histórica de medios. [Código, línea 150](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_image_sync.py#L150)
  Firma: `append_media_log(sheets_service, spreadsheet_id: str, values: list[list[Any]])`.

- `build_image_preview` — Construye el plan revisable de archivos/medios/producto antes de escribir. [Código, línea 163](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_image_sync.py#L163)
  Firma: `build_image_preview(rows: list[dict[str, Any]], drive_index: dict[str, dict[str, Any]], wc_index: dict[str, dict[str, Any]], duplicate_skus: dict[str, Any], media_cache: dict[str, dict[str, Any]] | None=None)`.

- `_download_drive_file` — Descarga un archivo Drive identificado para el envío explícito a WordPress. [Código, línea 219](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_image_sync.py#L219)
  Firma: `_download_drive_file(drive_service, file_id: str)`.

- `sync_one_product_images` — Sube medios, asigna al SKU y verifica el estado guardado en WooCommerce. [Código, línea 231](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_image_sync.py#L231)
  Firma: `sync_one_product_images(*, row: dict[str, Any], drive_index: dict[str, dict[str, Any]], media_cache: dict[str, dict[str, Any]], drive_factory: Callable[[], Any], sheets_service, spreadsheet_id: str, wp_client: WordPressMediaClient, wc_client: WooCommerceClient, wc_entity: dict[str, Any], max_workers: int=3)`.

- `sync_one_product_images.upload_ref` — Reutiliza o sube una referencia del producto y registra su medio remoto. [Código, línea 262](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_image_sync.py#L262)
  Firma: `sync_one_product_images.upload_ref(ref: dict[str, Any])`.

## woocommerce_inventory.py

Comparación conservadora entre una ficha del inventario y su entidad WooCommerce.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_inventory.py)

- `SyncPreview` — Resultado estructurado de comparación entre inventario y WooCommerce. [Código, línea 18](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_inventory.py#L18)
  Campos declarados: `sku: str`, `status: str`, `product_id: int | None`, `entity_type: str | None`, `parent_product_id: int | None`, `inventory_stock: int | None`, `woocommerce_stock: int | None`, `manages_stock: bool`, `stock_status: str | None`, `inventory_price: float | None`, `woocommerce_price: float | None`, `name_matches: bool`, `changes: tuple[str, ...]`, `notes: tuple[str, ...]`.

- `SyncPreview.as_dict` — Serializa la comparación para una respuesta/pantalla compatible. [Código, línea 34](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_inventory.py#L34)
  Firma: `SyncPreview.as_dict(self)`.

- `_money` — Normaliza importes para comparar registros de inventario/tienda. [Código, línea 38](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_inventory.py#L38)
  Firma: `_money(value: Any)`.

- `_normalize_name` — Normaliza solo para detectar cambios de texto sin castigar espacios/acentos. [Código, línea 45](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_inventory.py#L45)
  Firma: `_normalize_name(value: Any)`.

- `_manages_stock` — Comprueba si la entidad remota administra cantidades de stock. [Código, línea 54](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_inventory.py#L54)
  Firma: `_manages_stock(value: Any)`.

- `compare_product` — Compara identidad, precio y stock y devuelve diferencias para revisión. [Código, línea 60](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_inventory.py#L60)
  Firma: `compare_product(inventory_row: Mapping[str, Any], wc_product: Mapping[str, Any] | None)`.

## woocommerce_media_prepare.py

Preparación histórica de medios y registro de resultados antes de publicar productos.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_media_prepare.py)

- `_append_logs_fast` — Añade resultados de medios al registro histórico de forma agrupada. [Código, línea 24](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_media_prepare.py#L24)
  Firma: `_append_logs_fast(sheets_service, spreadsheet_id: str, values: list[list[Any]])`.

- `_skip_images` — Resultado no fatal: producto se sincroniza sin tocar las imágenes remotas. [Código, línea 36](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_media_prepare.py#L36)
  Firma: `_skip_images(sku: str, reason: str, missing: list[str] | None=None)`.

- `prepare_product_media` — Prepara/reutiliza medios del producto antes de su publicación compatible. [Código, línea 51](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_media_prepare.py#L51)
  Firma: `prepare_product_media(*, row: dict[str, Any], drive_index: dict[str, dict[str, Any]], media_cache: dict[str, dict[str, Any]], drive_factory: Callable[[], Any], sheets_service, spreadsheet_id: str, wp_client: WordPressMediaClient)`.

## woocommerce_product_sync.py

Publicación histórica de campos, taxonomías, precios, stock y relaciones de variantes.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_product_sync.py)

- `_text` — Normaliza texto de campos del producto histórico. [Código, línea 26](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_product_sync.py#L26)
  Firma: `_text(value: Any)`.

- `_key` — Deriva una clave normalizada para cotejar términos/familias. [Código, línea 30](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_product_sync.py#L30)
  Firma: `_key(value: Any)`.

- `_money` — Interpreta el importe que se enviará en el payload compatible. [Código, línea 34](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_product_sync.py#L34)
  Firma: `_money(value: Any)`.

- `parse_tags` — Separa y limpia las etiquetas registradas en la fila. [Código, línea 41](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_product_sync.py#L41)
  Firma: `parse_tags(value: Any)`.

- `_load_terms` — Consulta términos WooCommerce necesarios para la clasificación. [Código, línea 53](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_product_sync.py#L53)
  Firma: `_load_terms(client: WooCommerceClient, endpoint: str, *, force: bool=False)`.

- `_remember_term` — Conserva un término identificado en la caché de la operación. [Código, línea 83](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_product_sync.py#L83)
  Firma: `_remember_term(client: WooCommerceClient, endpoint: str, row: dict[str, Any])`.

- `ensure_term` — Resuelve o crea un término requerido por una publicación explícita. [Código, línea 95](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_product_sync.py#L95)
  Firma: `ensure_term(client: WooCommerceClient, endpoint: str, name: str, *, parent: int=0)`.

- `resolve_taxonomies` — Traduce categorías/etiquetas del inventario a sus términos remotos. [Código, línea 129](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_product_sync.py#L129)
  Firma: `resolve_taxonomies(client: WooCommerceClient, row: dict[str, Any])`.

- `_pricing_and_stock` — Construye los campos de precio/stock compatibles preservando valores ausentes. [Código, línea 161](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_product_sync.py#L161)
  Firma: `_pricing_and_stock(row: dict[str, Any])`.

- `_parent_signature` — Identifica atributos y relación del padre variable para cotejar su publicación. [Código, línea 175](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_product_sync.py#L175)
  Firma: `_parent_signature(tax: dict[str, Any])`.

- `sync_complete_product` — Actualiza un SKU. En lotes, verify_get=False evita un GET redundante. [Código, línea 183](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_product_sync.py#L183)
  Firma: `sync_complete_product(*, row: dict[str, Any], wc_client: WooCommerceClient, wc_entity: dict[str, Any], image_result: dict[str, Any] | None=None, verify_get: bool=True, include_stock: bool=True)`.

## woocommerce_publish_preview.py

Previsualización histórica de publicación/stock y visibilidad de productos agotados.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_publish_preview.py)

- `inspect_out_of_stock_visibility` — Busca la preferencia de ocultar agotados de forma tolerante a versiones WC. [Código, línea 15](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_publish_preview.py#L15)
  Firma: `inspect_out_of_stock_visibility(client: WooCommerceClient)`.

- `build_stock_publish_preview` — Construye el plan compatible de publicación/stock y sus advertencias para revisión. [Código, línea 52](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_publish_preview.py#L52)
  Firma: `build_stock_publish_preview(inventory_rows: list[dict[str, Any]], client: WooCommerceClient, *, catalog=None)`.

## woocommerce_stock.py

Lectura explícita de stock y agregación compatible de padres variables.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_stock.py)

- `enabled` — Comprueba si está habilitada la lectura/control de stock correspondiente. [Código, línea 4](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_stock.py#L4)
  Firma: `enabled(value)`.

- `attach_parent_stock` — Asocia a un padre variable el stock derivado de sus variantes según la regla existente. [Código, línea 8](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_stock.py#L8)
  Firma: `attach_parent_stock(variation, parent)`.

- `stock_reading` — Obtiene la representación de stock de una entidad remota, diferenciando ausente de cero. [Código, línea 22](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/woocommerce_stock.py#L22)
  Firma: `stock_reading(product)`.

## wordpress_media.py

Transporte de medios WordPress: búsqueda, descarga/subida y autorización independiente de escrituras.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/wordpress_media.py)

- `WordPressMediaError` — Error controlado de configuración o transporte de medios WordPress. [Código, línea 20](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/wordpress_media.py#L20)

- `WordPressMediaClient` — Cliente REST de medios con autenticación del servidor y flag de escritura independiente. [Código, línea 24](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/wordpress_media.py#L24)

- `WordPressMediaClient.__init__` — Configura la sesión HTTP y límites del cliente de medios. [Código, línea 25](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/wordpress_media.py#L25)
  Firma: `WordPressMediaClient.__init__(self)`.

- `WordPressMediaClient.configured` — Comprueba que existen los datos necesarios de conexión WordPress. [Código, línea 48](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/wordpress_media.py#L48)
  Firma: `WordPressMediaClient.configured(self)`.

- `WordPressMediaClient._auth` — Construye la cabecera de autenticación sin exponer la contraseña de aplicación. [Código, línea 51](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/wordpress_media.py#L51)
  Firma: `WordPressMediaClient._auth(self)`.

- `WordPressMediaClient._request` — Ejecuta HTTP de medios y exige WP_MEDIA_WRITE_ENABLED para escrituras. [Código, línea 57](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/wordpress_media.py#L57)
  Firma: `WordPressMediaClient._request(self, method: str, endpoint: str, *, params: dict[str, Any] | None=None, body: bytes | None=None, content_type: str='application/json', extra_headers: dict[str, str] | None=None, require_write: bool=False)`.

- `WordPressMediaClient.health` — Consulta el acceso a medios existentes sin subir una imagen. [Código, línea 88](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/wordpress_media.py#L88)
  Firma: `WordPressMediaClient.health(self)`.

- `WordPressMediaClient._source_filename` — Extrae el nombre de origen de un medio remoto para resolver coincidencias. [Código, línea 100](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/wordpress_media.py#L100)
  Firma: `WordPressMediaClient._source_filename(media: dict[str, Any])`.

- `WordPressMediaClient.find_media_by_filename` — Busca un nombre de archivo exacto entre medios existentes. [Código, línea 107](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/wordpress_media.py#L107)
  Firma: `WordPressMediaClient.find_media_by_filename(self, filename: str)`.

- `WordPressMediaClient.find_media_by_filenames` — Busca los nombres de un SKU en una sola consulta y conserva coincidencias identificadas. [Código, línea 111](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/wordpress_media.py#L111)
  Firma: `WordPressMediaClient.find_media_by_filenames(self, filenames: list[str])`.

- `WordPressMediaClient.upload_media` — Sube una imagen validada con nombre/metadata y evita duplicación cuando existe un medio identificado. [Código, línea 130](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/wordpress_media.py#L130)
  Firma: `WordPressMediaClient.upload_media(self, filename: str, data: bytes, *, mime_type: str | None=None, alt_text: str='', title: str='')`.


# Compatibilidad: herramientas históricas y Loyverse

Sección del índice del código de la aplicación. Las rutas y números de línea corresponden a esta entrega documental; buscar por nombre en una versión posterior. Una función compatible/histórica no implica que su integración esté activada.

## batch_web.py

Interfaz histórica de lotes, progreso y reanudación con ejecución local.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/batch_web.py)

- `_now` — Devuelve el instante usado por los registros de lote histórico. [Código, línea 37](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/batch_web.py#L37)
  Firma: `_now()`.

- `_set_active` — Marca el estado activo de un lote local de sesión. [Código, línea 41](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/batch_web.py#L41)
  Firma: `_set_active(batch_id: str | None)`.

- `_is_active` — Comprueba si un lote local todavía está en ejecución. [Código, línea 47](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/batch_web.py#L47)
  Firma: `_is_active(batch_id: str)`.

- `_parse_custom_skus` — Valida la selección textual de SKU para un lote compatible. [Código, línea 52](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/batch_web.py#L52)
  Firma: `_parse_custom_skus(value: str)`.

- `_run_batch` — Worker único: un SKU a la vez, sin paralelizar imágenes ni productos. [Código, línea 63](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/batch_web.py#L63)
  Firma: `_run_batch(session, batch_id: str)`.

- `_start_worker` — Inicia el hilo del lote histórico local; no es el supervisor RQ nuevo. [Código, línea 205](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/batch_web.py#L205)
  Firma: `_start_worker(session, batch_id: str)`.

- `_batch_payload` — Serializa progreso de lote compatible para la pantalla. [Código, línea 225](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/batch_web.py#L225)
  Firma: `_batch_payload(session, batch_id: str)`.

- `batch_page` — Sirve la página histórica de lotes. [Código, línea 249](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/batch_web.py#L249)
  Firma: `batch_page(request: Request)`.
  Rutas/decoradores HTTP: `fastapi_app.get('/woocommerce-batch-sync', response_class=HTMLResponse)`.

- `batch_create_route` — Valida y crea el lote solicitado por la sesión. [Código, línea 291](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/batch_web.py#L291)
  Firma: `batch_create_route(request: Request)`.
  Rutas/decoradores HTTP: `fastapi_app.post('/batch-create')`.

- `batch_status_route` — Devuelve el progreso del lote histórico autorizado. [Código, línea 334](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/batch_web.py#L334)
  Firma: `batch_status_route(request: Request, batch_id: str)`.
  Rutas/decoradores HTTP: `fastapi_app.get('/batch-status')`.

- `batch_resume_route` — Reanuda explícitamente un lote histórico existente. [Código, línea 347](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/batch_web.py#L347)
  Firma: `batch_resume_route(request: Request)`.
  Rutas/decoradores HTTP: `fastapi_app.post('/batch-resume')`.

## batch_web_v2.py

Interfaz compatible de lotes ejecutados por pasos y con reanudación explícita.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/batch_web_v2.py)

- `_set_processing` — Marca que la sesión está procesando un paso de lote compatible. [Código, línea 45](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/batch_web_v2.py#L45)
  Firma: `_set_processing(batch_id: str | None)`.

- `_processing` — Comprueba el estado de procesamiento del paso local. [Código, línea 51](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/batch_web_v2.py#L51)
  Firma: `_processing(batch_id: str)`.

- `_parse_custom` — Interpreta la selección de SKU del lote por pasos. [Código, línea 56](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/batch_web_v2.py#L56)
  Firma: `_parse_custom(value: str)`.

- `_batch_payload` — Construye la respuesta de progreso del lote por pasos. [Código, línea 67](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/batch_web_v2.py#L67)
  Firma: `_batch_payload(session, batch_id: str)`.

- `_bool` — Convierte una opción de formulario al booleano esperado. [Código, línea 89](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/batch_web_v2.py#L89)
  Firma: `_bool(value, default=False)`.

- `_option_bool` — Resuelve una opción booleana del formulario conservando su valor por defecto. [Código, línea 94](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/batch_web_v2.py#L94)
  Firma: `_option_bool(payload, key, default)`.

- `_process_one` — One HTTP request joins a bounded wave; closing the page pauses next wave. [Código, línea 101](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/batch_web_v2.py#L101)
  Firma: `_process_one(session, batch_id: str)`.

- `_process_one.job` — Construye/actualiza el estado local de una operación de lote por pasos. [Código, línea 125](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/batch_web_v2.py#L125)
  Firma: `_process_one.job(item)`.

- `_reset_for_resume` — Restablece controles locales para la reanudación explícita. [Código, línea 189](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/batch_web_v2.py#L189)
  Firma: `_reset_for_resume(session, batch_id: str)`.

- `batch_page` — Sirve la interfaz compatible de lotes por pasos. [Código, línea 213](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/batch_web_v2.py#L213)
  Firma: `batch_page(request: Request)`.
  Rutas/decoradores HTTP: `fastapi_app.get('/woocommerce-batch-sync', response_class=HTMLResponse)`.

- `_create_for_session` — Crea un lote identificado para la sesión autorizada. [Código, línea 252](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/batch_web_v2.py#L252)
  Firma: `_create_for_session(session, payload)`.

- `batch_create` — Ruta compatible de creación del lote por pasos. [Código, línea 282](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/batch_web_v2.py#L282)
  Firma: `batch_create(request: Request)`.
  Rutas/decoradores HTTP: `fastapi_app.post('/batch-create')`.

- `batch_status` — Consulta el estado de ese lote. [Código, línea 296](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/batch_web_v2.py#L296)
  Firma: `batch_status(request: Request, batch_id: str)`.
  Rutas/decoradores HTTP: `fastapi_app.get('/batch-status')`.

- `batch_step` — Ejecuta el siguiente paso explícito del lote compatible. [Código, línea 307](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/batch_web_v2.py#L307)
  Firma: `batch_step(request: Request)`.
  Rutas/decoradores HTTP: `fastapi_app.post('/batch-step')`.

- `batch_resume` — Reanuda el lote después de revisar el estado anterior. [Código, línea 325](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/batch_web_v2.py#L325)
  Firma: `batch_resume(request: Request)`.
  Rutas/decoradores HTTP: `fastapi_app.post('/batch-resume')`.

## catalog_platform/__init__.py

Paquete del catálogo SQL y de los procesos durables de la plataforma.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/catalog_platform/__init__.py)

Este módulo configura/importa componentes o registra callbacks anónimos; no declara funciones o clases nombradas propias.

## frontend_host.py

Hosting compatible de la exportación estática Next.js dentro de FastAPI; no es el frontend separado actual.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend_host.py)

- `register_frontend` — Monta la exportación compatible Next y rutas públicas dentro de FastAPI cuando se habilita ese modo. [Código, línea 7](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend_host.py#L7)
  Firma: `register_frontend(app)`.

- `register_frontend.manifest` — Sirve el manifest PWA de la exportación compatible. [Código, línea 15](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend_host.py#L15)
  Firma: `register_frontend.manifest()`.
  Rutas/decoradores HTTP: `app.get('/manifest.webmanifest', include_in_schema=False)`.

- `register_frontend.service_worker` — Sirve el script de caché de carcasa pública. [Código, línea 19](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend_host.py#L19)
  Firma: `register_frontend.service_worker()`.
  Rutas/decoradores HTTP: `app.get('/sw.js', include_in_schema=False)`.

- `register_frontend.index` — Sirve la página inicial de la exportación compatible. [Código, línea 23](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend_host.py#L23)
  Firma: `register_frontend.index()`.
  Rutas/decoradores HTTP: `app.get('/', include_in_schema=False)`.

- `register_frontend.logo` — Sirve el recurso público de marca de la interfaz. [Código, línea 29](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend_host.py#L29)
  Firma: `register_frontend.logo()`.
  Rutas/decoradores HTTP: `app.get('/logo.png', include_in_schema=False)`.

- `register_frontend.studio` — Sirve la entrada compatible del estudio de captura. [Código, línea 33](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend_host.py#L33)
  Firma: `register_frontend.studio()`.
  Rutas/decoradores HTTP: `app.get('/studio', include_in_schema=False)`.

- `register_frontend.old_logout` — Adapta la navegación histórica de salida al cierre de sesión actual. [Código, línea 37](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend_host.py#L37)
  Firma: `register_frontend.old_logout()`.
  Rutas/decoradores HTTP: `app.get('/logout', include_in_schema=False)`.

## gradio_security.py

Controles de sesión, permisos y archivos de las herramientas Gradio históricas.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/gradio_security.py)

- `GradioGuard` — Limita herramientas y archivos Gradio a la sesión/rol autorizado. [Código, línea 11](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/gradio_security.py#L11)

- `GradioGuard.__init__` — Configura los controles del runtime Gradio compatible. [Código, línea 12](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/gradio_security.py#L12)
  Firma: `GradioGuard.__init__(self)`.

- `GradioGuard.viewer` — Identifica el modo de solo lectura del usuario. [Código, línea 16](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/gradio_security.py#L16)
  Firma: `GradioGuard.viewer(self, request, session)`.

- `GradioGuard.bind` — Asocia un componente/acción Gradio a su control de permisos. [Código, línea 25](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/gradio_security.py#L25)
  Firma: `GradioGuard.bind(self, token, owner, *, create=False)`.

- `GradioGuard.permits` — Decide si una operación compatible está autorizada. [Código, línea 41](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/gradio_security.py#L41)
  Firma: `GradioGuard.permits(self, request, session, owner, body=b'')`.

- `GradioGuard.inputs_permitted` — Comprueba permisos de los inputs que recibe una acción Gradio. [Código, línea 67](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/gradio_security.py#L67)
  Firma: `GradioGuard.inputs_permitted(cls, value, session)`.

- `GradioGuard.file_permitted` — Comprueba si la ruta de archivo pertenece al usuario autorizado. [Código, línea 77](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/gradio_security.py#L77)
  Firma: `GradioGuard.file_permitted(path, session)`.

- `GradioGuard.register_uploads` — Registra las subidas que la sesión puede usar como referencias propias. [Código, línea 90](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/gradio_security.py#L90)
  Firma: `GradioGuard.register_uploads(session, raw)`.

## inventory_bulk.py

Conteos iniciales de inventario histórico por SKU con registro explícito.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_bulk.py)

- `counted_initial_skus` — Identifica SKU que ya tienen conteo inicial registrado. [Código, línea 26](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_bulk.py#L26)
  Firma: `counted_initial_skus(sheets_service, spreadsheet_id: str)`.

- `register_initial_counts` — Registra los conteos iniciales explícitos evitando duplicar los ya procesados. [Código, línea 36](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_bulk.py#L36)
  Firma: `register_initial_counts(sheets_service, spreadsheet_id: str, counts: list[dict[str, Any]], *, user: str='', reference: str='Conteo inicial masivo', reason: str='Conteo físico inicial')`.

## inventory_hub.py

Página compatible que reúne herramientas de inventario.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_hub.py)

- `inventory_hub` — Muestra enlaces y estado de las herramientas compatibles de inventario. [Código, línea 10](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_hub.py#L10)
  Firma: `inventory_hub(request: Request, q: str='', sku: str='')`.
  Rutas/decoradores HTTP: `app.get('/inventory-hub', response_class=HTMLResponse)`.

## inventory_operations.py

Inventario histórico: lectura, búsqueda y movimientos serializados con trazabilidad.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_operations.py)

- `serialized_stock_write` — Decorador que serializa escrituras de inventario del flujo compatible. [Código, línea 50](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_operations.py#L50)
  Firma: `serialized_stock_write(fn)`.

- `serialized_stock_write.locked` — Ejecuta la escritura decorada bajo el lock existente. [Código, línea 52](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_operations.py#L52)
  Firma: `serialized_stock_write.locked(*args, **kwargs)`.

- `stock_integer` — Valida una cantidad entera de inventario antes de registrar un movimiento. [Código, línea 58](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_operations.py#L58)
  Firma: `stock_integer(value)`.

- `_clean_text` — Normaliza celdas de texto del inventario. [Código, línea 70](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_operations.py#L70)
  Firma: `_clean_text(value: Any)`.

- `_search_key` — Construye la clave normalizada usada por la búsqueda histórica. [Código, línea 74](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_operations.py#L74)
  Firma: `_search_key(value: Any)`.

- `_cell_value` — Convierte un valor a la forma de celda Sheets aceptada. [Código, línea 80](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_operations.py#L80)
  Firma: `_cell_value(value: Any)`.

- `_sheet_map` — Relaciona nombres de columna con sus posiciones reales. [Código, línea 88](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_operations.py#L88)
  Firma: `_sheet_map(sheets_service, spreadsheet_id: str)`.

- `ensure_movements_sheet` — Prepara la pestaña histórica de movimientos en el flujo de escritura autorizado. [Código, línea 99](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_operations.py#L99)
  Firma: `ensure_movements_sheet(sheets_service, spreadsheet_id: str)`.

- `read_inventory` — Lee el inventario canónico conectado a la sesión. [Código, línea 159](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_operations.py#L159)
  Firma: `read_inventory(sheets_service, spreadsheet_id: str)`.

- `search_inventory` — Filtra registros por los campos de búsqueda del inventario. [Código, línea 179](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_operations.py#L179)
  Firma: `search_inventory(rows: list[dict[str, Any]], query: str='', limit: int=100)`.

- `inventory_table` — Construye la tabla de presentación de registros históricos. [Código, línea 197](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_operations.py#L197)
  Firma: `inventory_table(rows: list[dict[str, Any]])`.

- `inventory_summary` — Resume cantidades/datos disponibles del inventario leído. [Código, línea 211](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_operations.py#L211)
  Firma: `inventory_summary(rows: list[dict[str, Any]])`.

- `_find_unique_sku` — Resuelve una única fila por SKU y bloquea ambigüedades antes de escribir. [Código, línea 229](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_operations.py#L229)
  Firma: `_find_unique_sku(rows: list[dict[str, Any]], sku: str)`.

- `read_movements` — Lee movimientos históricos registrados. [Código, línea 239](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_operations.py#L239)
  Firma: `read_movements(sheets_service, spreadsheet_id: str, sku: str='', limit: int=50)`.

- `movements_table` — Construye la tabla visible de movimientos. [Código, línea 261](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_operations.py#L261)
  Firma: `movements_table(rows: list[dict[str, Any]])`.

- `register_movement` — Valida y registra un movimiento explícito con su cantidad y trazabilidad. [Código, línea 279](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_operations.py#L279)
  Firma: `register_movement(sheets_service, spreadsheet_id: str, *, sku: str, movement_type: str, quantity: Any, reason: str='', reference: str='', user: str='')`.

## inventory_web.py

Pantallas históricas de inventario, conteos y movimientos.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_web.py)

- `_session` — Obtiene la sesión autorizada para pantallas históricas de inventario. [Código, línea 38](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_web.py#L38)
  Firma: `_session(request: Request)`.

- `_context` — Resuelve inventario y servicios necesarios de esa sesión. [Código, línea 43](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_web.py#L43)
  Firma: `_context(request: Request)`.

- `_money` — Formatea importes mostrados en la interfaz de inventario. [Código, línea 54](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_web.py#L54)
  Firma: `_money(value: Any)`.

- `_render_movements` — Renderiza filas del historial de movimientos. [Código, línea 61](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_web.py#L61)
  Firma: `_render_movements(rows: list[dict[str, Any]])`.

- `_render_bulk_rows` — Renderiza filas de la pantalla compatible de conteo múltiple. [Código, línea 82](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_web.py#L82)
  Firma: `_render_bulk_rows(rows: list[dict[str, Any]], counted: set[str])`.

- `render_inventory` — Construye la interfaz HTML de inventario con sus datos reales. [Código, línea 111](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_web.py#L111)
  Firma: `render_inventory(request: Request, q: str='', sku: str='')`.

- `inventory_manager` — Ruta compatible de búsqueda/gestión de inventario. [Código, línea 169](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_web.py#L169)
  Firma: `inventory_manager(request: Request, q: str='', sku: str='')`.
  Rutas/decoradores HTTP: `fastapi_app.get('/inventory-manager')`.

- `inventory_count` — Ruta compatible de conteo de un producto. [Código, línea 174](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_web.py#L174)
  Firma: `inventory_count(request: Request, q: str='')`.
  Rutas/decoradores HTTP: `fastapi_app.get('/inventory-count')`.

- `inventory_history` — Ruta compatible del historial de movimientos. [Código, línea 179](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_web.py#L179)
  Firma: `inventory_history(request: Request, sku: str='')`.
  Rutas/decoradores HTTP: `fastapi_app.get('/inventory-history')`.

- `inventory_count_bulk` — Ruta compatible de conteos múltiples. [Código, línea 195](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_web.py#L195)
  Firma: `inventory_count_bulk(request: Request)`.
  Rutas/decoradores HTTP: `fastapi_app.post('/inventory-count-bulk')`.

- `inventory_movement` — Ruta de escritura confirmada de un movimiento del inventario histórico. [Código, línea 217](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/inventory_web.py#L217)
  Firma: `inventory_movement(request: Request)`.
  Rutas/decoradores HTTP: `fastapi_app.post('/inventory-movement')`.

## loyverse_client.py

Cliente HTTP Loyverse con lecturas y operaciones sujetas a su configuración existente.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/loyverse_client.py)

- `LoyverseError` — Error controlado de transporte/configuración Loyverse. [Código, línea 6](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/loyverse_client.py#L6)

- `LoyverseClient` — Cliente HTTP de la integración Loyverse compatible. [Código, línea 10](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/loyverse_client.py#L10)

- `LoyverseClient.__init__` — Configura sesión HTTP y conexión Loyverse del servidor. [Código, línea 13](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/loyverse_client.py#L13)
  Firma: `LoyverseClient.__init__(self, token, deadline=None)`.

- `LoyverseClient.request` — Ejecuta una operación REST con límites y tratamiento de errores del cliente. [Código, línea 19](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/loyverse_client.py#L19)
  Firma: `LoyverseClient.request(self, method, path, **kwargs)`.

- `LoyverseClient.list` — Recorre páginas de un recurso Loyverse. [Código, línea 42](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/loyverse_client.py#L42)
  Firma: `LoyverseClient.list(self, resource, **params)`.

- `LoyverseClient.snapshot` — Obtiene una lectura conjunta para comparación de catálogo/inventario. [Código, línea 60](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/loyverse_client.py#L60)
  Firma: `LoyverseClient.snapshot(self, store)`.

- `LoyverseClient.set_stock` — Envía una cantidad de stock en una operación explícita del flujo compatible. [Código, línea 66](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/loyverse_client.py#L66)
  Firma: `LoyverseClient.set_stock(self, variant, store, value)`.

- `LoyverseClient.create_item` — Crea una ficha Loyverse solo dentro del flujo autorizado de esa integración. [Código, línea 70](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/loyverse_client.py#L70)
  Firma: `LoyverseClient.create_item(self, payload)`.

## loyverse_jobs.py

Trabajos locales compatibles de Loyverse con progreso en sesión.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/loyverse_jobs.py)

- `status` — Lee el estado de un job Loyverse local de sesión. [Código, línea 13](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/loyverse_jobs.py#L13)
  Firma: `status(value, job_id=None)`.

- `update` — Actualiza progreso/mensaje del job compatible. [Código, línea 21](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/loyverse_jobs.py#L21)
  Firma: `update(value, job_id, **fields)`.

- `launch` — Inicia una operación Loyverse compatible y conserva su estado local. [Código, línea 28](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/loyverse_jobs.py#L28)
  Firma: `launch(value, preview_id, total, target)`.

- `launch.runner` — Ejecuta la operación en el hilo local y registra su resultado/error. [Código, línea 42](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/loyverse_jobs.py#L42)
  Firma: `launch.runner()`.

## loyverse_sync.py

Planes de coincidencias y stock para Loyverse; no activa automáticamente esa integración.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/loyverse_sync.py)

- `text` — Normaliza texto de las filas cotejadas con Loyverse. [Código, línea 7](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/loyverse_sync.py#L7)
  Firma: `text(value)`.

- `barcode` — Obtiene la representación compatible de código usada por ese plan de coincidencias. [Código, línea 11](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/loyverse_sync.py#L11)
  Firma: `barcode(value)`.

- `quantity` — Interpreta una cantidad de stock para la comparación compatible. [Código, línea 16](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/loyverse_sync.py#L16)
  Firma: `quantity(value)`.

- `plan_stock` — Construye diferencias/propuestas de stock para revisión antes de escribir. [Código, línea 26](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/loyverse_sync.py#L26)
  Firma: `plan_stock(rows, items, levels, store)`.

- `name_key` — Deriva una clave normalizada de nombre para cotejar registros. [Código, línea 88](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/loyverse_sync.py#L88)
  Firma: `name_key(value)`.

- `plan_catalog` — Add explicit creation actions for new simple products and complete families. [Código, línea 94](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/loyverse_sync.py#L94)
  Firma: `plan_catalog(rows, items, levels, store, stores)`.

## loyverse_web.py

Pantallas y confirmaciones históricas de conexión/publicación Loyverse.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/loyverse_web.py)

- `session` — Obtiene la sesión autorizada de la pantalla compatible Loyverse. [Código, línea 20](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/loyverse_web.py#L20)
  Firma: `session(request)`.

- `client` — Construye el cliente Loyverse configurado para ese flujo. [Código, línea 27](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/loyverse_web.py#L27)
  Firma: `client(value, deadline=None)`.

- `compare` — Genera coincidencias/diferencias de catálogo para revisión. [Código, línea 31](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/loyverse_web.py#L31)
  Firma: `compare(request, value, store, bundle=None, api=None)`.

- `_operate` — Ejecuta la operación Loyverse ya validada/confirmada. [Código, línea 54](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/loyverse_web.py#L54)
  Firma: `_operate(request, action, data)`.

- `consume_preview` — Consume la previsualización confirmada para evitar aplicar un plan distinto. [Código, línea 80](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/loyverse_web.py#L80)
  Firma: `consume_preview(value, data)`.

- `execute_upload` — Publica el plan explícito revisado de carga Loyverse. [Código, línea 94](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/loyverse_web.py#L94)
  Firma: `execute_upload(request, value, preview, selected, progress=lambda **fields: None)`.

- `execute_upload.result` — Registra el resultado de cada ficha del plan de carga. [Código, línea 101](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/loyverse_web.py#L101)
  Firma: `execute_upload.result(error=None)`.

- `start_upload` — Valida y comienza un trabajo compatible de carga Loyverse. [Código, línea 159](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/loyverse_web.py#L159)
  Firma: `start_upload(request, data)`.

- `start_upload.target` — Ejecuta la carga confirmada y reporta progreso al job local. [Código, línea 173](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/loyverse_web.py#L173)
  Firma: `start_upload.target(progress)`.

- `operate` — Entrada compatible que valida la operación antes de delegarla. [Código, línea 181](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/loyverse_web.py#L181)
  Firma: `operate(request, action, data)`.

- `register` — Registra rutas/pantallas Loyverse compatibles en FastAPI. [Código, línea 192](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/loyverse_web.py#L192)
  Firma: `register(app)`.

- `register.page` — Renderiza la pantalla compatible de conexión/comparación Loyverse. [Código, línea 194](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/loyverse_web.py#L194)
  Firma: `register.page(request: Request)`.
  Rutas/decoradores HTTP: `app.get('/loyverse', response_class=HTMLResponse)`.

- `register.upload_status` — Devuelve progreso de la carga Loyverse propia de la sesión. [Código, línea 202](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/loyverse_web.py#L202)
  Firma: `register.upload_status(request: Request, job_id: str='')`.
  Rutas/decoradores HTTP: `app.get('/loyverse-upload-status')`.

- `register.endpoint` — Valida y despacha una operación compatible recibida por la ruta registrada. [Código, línea 213](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/loyverse_web.py#L213)
  Firma: `register.endpoint(request: Request, action: str)`.
  Rutas/decoradores HTTP: `app.post('/loyverse/{action}')`.

## media_web.py

Diagnóstico y sincronización históricos de imágenes Drive hacia WordPress.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/media_web.py)

- `_session` — Obtiene la sesión autorizada de las herramientas de medios compatibles. [Código, línea 37](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/media_web.py#L37)
  Firma: `_session(request: Request)`.

- `_images_folder_id` — Resuelve la carpeta de imágenes del proyecto autorizado. [Código, línea 42](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/media_web.py#L42)
  Firma: `_images_folder_id(session)`.

- `_drive_index` — Construye un índice de archivos de esa carpeta para coincidencias. [Código, línea 51](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/media_web.py#L51)
  Firma: `_drive_index(session, force: bool=False)`.

- `_direct_inventory_context` — Resuelve el inventario/hoja para consultar imágenes sin cambiar el catálogo. [Código, línea 69](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/media_web.py#L69)
  Firma: `_direct_inventory_context(session)`.

- `_render_rows` — Renderiza las filas de revisión de medios históricos. [Código, línea 75](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/media_web.py#L75)
  Firma: `_render_rows(rows)`.

- `_sync_one_sku` — Ejecuta la sincronización de imágenes de un SKU explícito. [Código, línea 112](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/media_web.py#L112)
  Firma: `_sync_one_sku(session, sku: str)`.

- `wp_media_health` — Comprueba conexión WordPress sin subir una imagen. [Código, línea 157](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/media_web.py#L157)
  Firma: `wp_media_health()`.
  Rutas/decoradores HTTP: `fastapi_app.get('/wp-media-health')`.

- `image_preview` — Muestra coincidencias de imágenes antes de autorizar sincronización. [Código, línea 169](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/media_web.py#L169)
  Firma: `image_preview(request: Request)`.
  Rutas/decoradores HTTP: `fastapi_app.get('/woocommerce-image-preview', response_class=HTMLResponse)`.

- `image_sync_one` — Ruta compatible de sincronización explícita de imágenes de un producto. [Código, línea 219](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/media_web.py#L219)
  Firma: `image_sync_one(request: Request)`.
  Rutas/decoradores HTTP: `fastapi_app.post('/image-sync-one')`.

## pos_provider.py

Contrato de lecturas POS y adaptador Loyverse; no convierte Loyverse en autoridad del catálogo.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/pos_provider.py)

- `POSProvider` — Contrato de lectura POS; no activa una integración por sí solo. [Código, línea 6](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/pos_provider.py#L6)

- `POSProvider.items` — Firma de lectura de productos POS. [Código, línea 7](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/pos_provider.py#L7)
  Firma: `POSProvider.items(self)`.

- `POSProvider.variants` — Firma de lectura de variantes POS. [Código, línea 8](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/pos_provider.py#L8)
  Firma: `POSProvider.variants(self)`.

- `POSProvider.categories` — Firma de lectura de categorías POS. [Código, línea 9](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/pos_provider.py#L9)
  Firma: `POSProvider.categories(self)`.

- `POSProvider.stores` — Firma de lectura de tiendas POS. [Código, línea 10](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/pos_provider.py#L10)
  Firma: `POSProvider.stores(self)`.

- `POSProvider.inventory` — Firma de lectura de inventario POS. [Código, línea 11](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/pos_provider.py#L11)
  Firma: `POSProvider.inventory(self, store_id)`.

- `POSProvider.receipts` — Firma de lectura de recibos POS. [Código, línea 12](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/pos_provider.py#L12)
  Firma: `POSProvider.receipts(self)`.

- `LoyverseProvider` — Adaptador de lecturas Loyverse al contrato POS preparado. [Código, línea 15](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/pos_provider.py#L15)

- `LoyverseProvider.__init__` — Recibe la conexión autorizada Loyverse. [Código, línea 18](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/pos_provider.py#L18)
  Firma: `LoyverseProvider.__init__(self, token=None)`.

- `LoyverseProvider._list` — Ejecuta la lectura paginada compatible de un recurso Loyverse. [Código, línea 21](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/pos_provider.py#L21)
  Firma: `LoyverseProvider._list(self, entity, **params)`.

- `LoyverseProvider.items` — Lee productos Loyverse mediante el adaptador. [Código, línea 28](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/pos_provider.py#L28)
  Firma: `LoyverseProvider.items(self)`.

- `LoyverseProvider.variants` — Lee variantes Loyverse mediante el adaptador. [Código, línea 31](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/pos_provider.py#L31)
  Firma: `LoyverseProvider.variants(self)`.

- `LoyverseProvider.categories` — Lee categorías Loyverse mediante el adaptador. [Código, línea 34](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/pos_provider.py#L34)
  Firma: `LoyverseProvider.categories(self)`.

- `LoyverseProvider.stores` — Lee tiendas Loyverse mediante el adaptador. [Código, línea 37](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/pos_provider.py#L37)
  Firma: `LoyverseProvider.stores(self)`.

- `LoyverseProvider.inventory` — Lee cantidades Loyverse mediante el adaptador. [Código, línea 40](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/pos_provider.py#L40)
  Firma: `LoyverseProvider.inventory(self, store_id)`.

- `LoyverseProvider.receipts` — Lee recibos Loyverse mediante el adaptador. [Código, línea 43](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/pos_provider.py#L43)
  Firma: `LoyverseProvider.receipts(self)`.

## product_web.py

Rutas compatibles de sincronización completa de un producto WooCommerce.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/product_web.py)

- `_full_sync` — Ejecuta la sincronización completa histórica de un producto bajo sus controles existentes. [Código, línea 22](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/product_web.py#L22)
  Firma: `_full_sync(session, sku: str, include_images: bool=False)`.

- `product_sync_page` — Renderiza la pantalla compatible de sincronización por producto. [Código, línea 94](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/product_web.py#L94)
  Firma: `product_sync_page(request: Request)`.
  Rutas/decoradores HTTP: `fastapi_app.get('/woocommerce-product-sync')`.

- `product_sync_one` — Ruta compatible que valida y sincroniza un SKU seleccionado. [Código, línea 99](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/product_web.py#L99)
  Firma: `product_sync_one(request: Request)`.
  Rutas/decoradores HTTP: `fastapi_app.post('/product-sync-one')`.

## product_web_ai.py

Carga compatible de las herramientas web de producto en la aplicación histórica de IA.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/product_web_ai.py)

Este módulo configura/importa componentes o registra callbacks anónimos; no declara funciones o clases nombradas propias.

## publication_web.py

Revisión y previsualización históricas de publicación y stock.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/publication_web.py)

- `inventory_review` — Muestra la revisión histórica de inventario antes de publicar. [Código, línea 21](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/publication_web.py#L21)
  Firma: `inventory_review(request: Request)`.
  Rutas/decoradores HTTP: `fastapi_app.post('/inventory-review')`.

- `woocommerce_publish_preview` — Presenta la previsualización compatible de publicación/stock. [Código, línea 58](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/publication_web.py#L58)
  Firma: `woocommerce_publish_preview(request: Request)`.

- `retired_stock_preview` — Respuesta de compatibilidad para una entrada antigua de previsualización retirada. [Código, línea 65](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/publication_web.py#L65)
  Firma: `retired_stock_preview(request: Request)`.
  Rutas/decoradores HTTP: `fastapi_app.post('/stock-preview-start')`; `fastapi_app.get('/stock-preview-result')`.

## server.py

Herramientas web históricas de conexión, comparación y diagnóstico WooCommerce.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/server.py)

- `_current_session` — Resuelve la sesión de una herramienta web histórica. [Código, línea 28](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/server.py#L28)
  Firma: `_current_session(request: Request)`.

- `_read_master_inventory` — Lee el inventario canónico para consultas de tienda compatibles. [Código, línea 35](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/server.py#L35)
  Firma: `_read_master_inventory(session)`.

- `_wc_config_status` — Describe la conexión/flags WooCommerce sin devolver credenciales. [Código, línea 58](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/server.py#L58)
  Firma: `_wc_config_status()`.

- `_connection_test` — Ejecuta la comprobación de lectura de conexión existente. [Código, línea 68](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/server.py#L68)
  Firma: `_connection_test()`.

- `_stock_source_profile` — Describe la fuente/autoridad configurada de cantidades de inventario. [Código, línea 88](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/server.py#L88)
  Firma: `_stock_source_profile(rows: list[dict[str, Any]])`.

- `_build_preview` — Construye una comparación revisable de inventario y tienda. [Código, línea 109](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/server.py#L109)
  Firma: `_build_preview(rows, *, limit: int | None=None)`.

- `pause_store_tools` — Desactiva/retira las herramientas de tienda en modo solo Drive. [Código, línea 149](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/server.py#L149)
  Firma: `pause_store_tools(request: Request, call_next)`.

- `wc_health` — Ruta compatible de diagnóstico de conexión WooCommerce. [Código, línea 172](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/server.py#L172)
  Firma: `wc_health()`.
  Rutas/decoradores HTTP: `fastapi_app.get('/wc-health')`.

- `wc_preview` — Ruta compatible de comparación previa con WooCommerce. [Código, línea 180](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/server.py#L180)
  Firma: `wc_preview(request: Request, limit: int=50)`.
  Rutas/decoradores HTTP: `fastapi_app.get('/wc-preview')`.

- `inventory_sync_dashboard` — Renderiza el panel histórico de revisión de sincronización. [Código, línea 194](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/server.py#L194)
  Firma: `inventory_sync_dashboard(request: Request)`.
  Rutas/decoradores HTTP: `fastapi_app.get('/inventory-sync')`.

## sync_bridge_protocol.py

Configuración y firmas para la comunicación entre servicios históricos de sincronización.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_bridge_protocol.py)

- `setting` — Resuelve una opción de configuración del puente de sincronización. [Código, línea 25](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_bridge_protocol.py#L25)
  Firma: `setting(key, default='')`.

- `signature` — Calcula la firma de un mensaje del puente con su clave configurada. [Código, línea 30](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_bridge_protocol.py#L30)
  Firma: `signature(body: bytes, timestamp: str, nonce: str, key: str)`.

- `verify` — Valida la firma y condiciones del mensaje antes de aceptar la delegación. [Código, línea 35](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_bridge_protocol.py#L35)
  Firma: `verify(body, timestamp, nonce, supplied, key)`.

## sync_gateway.py

Entrega firmada de sesión y reenvío a las herramientas del servicio de sincronización.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_gateway.py)

- `redirect_tool` — Construye la navegación autorizada hacia una herramienta del servicio compatible. [Código, línea 16](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_gateway.py#L16)
  Firma: `redirect_tool(request)`.

- `install_handoff_routes` — Registra las rutas de delegación/reclamación de sesión firmada. [Código, línea 25](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_gateway.py#L25)
  Firma: `install_handoff_routes(app, legacy)`.

- `install_handoff_routes.launch` — Prepara la entrega de sesión a la herramienta compatible elegida. [Código, línea 29](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_gateway.py#L29)
  Firma: `install_handoff_routes.launch(request: Request, path: str='/woocommerce-product-sync', query: str='')`.
  Rutas/decoradores HTTP: `app.get('/sync-launch')`.

- `install_handoff_routes.redeem` — Consume la entrega firmada para crear una sesión delegada autorizada. [Código, línea 50](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_gateway.py#L50)
  Firma: `install_handoff_routes.redeem(request: Request)`.
  Rutas/decoradores HTTP: `app.post('/sync-handoff/redeem')`.

- `worker_enabled` — Comprueba si se habilitó el servicio remoto compatible de sincronización. [Código, línea 71](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_gateway.py#L71)
  Firma: `worker_enabled()`.

- `_worker_context` — Construye el contexto autorizado que se enviará al servicio compatible remoto. [Código, línea 75](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_gateway.py#L75)
  Firma: `_worker_context(session, legacy)`.

- `forward_tool` — Reenvía la operación a la herramienta remota usando el protocolo del puente. [Código, línea 98](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_gateway.py#L98)
  Firma: `forward_tool(request, legacy)`.

## sync_lite_app.py

Aplicación histórica independiente de sincronización con sesiones, cachés y lotes locales.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_lite_app.py)

- `_session` — Obtiene la sesión local de la aplicación histórica de sincronización ligera. [Código, línea 82](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_lite_app.py#L82)
  Firma: `_session(request: Request)`.

- `_credentials` — Reconstruye las credenciales Google de esa sesión compatible. [Código, línea 87](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_lite_app.py#L87)
  Firma: `_credentials(session: dict)`.

- `_drive` — Obtiene el cliente Drive autorizado de la aplicación ligera. [Código, línea 98](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_lite_app.py#L98)
  Firma: `_drive(session: dict)`.

- `_sheets` — Obtiene el cliente Sheets autorizado de la aplicación ligera. [Código, línea 106](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_lite_app.py#L106)
  Firma: `_sheets(session: dict)`.

- `_inventory_cached` — Lee/reutiliza la caché de inventario del servicio compatible. [Código, línea 114](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_lite_app.py#L114)
  Firma: `_inventory_cached(session: dict, *, force: bool=False)`.

- `_drive_index_cached` — Lee/reutiliza el índice de imágenes de la carpeta autorizada. [Código, línea 127](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_lite_app.py#L127)
  Firma: `_drive_index_cached(session: dict, *, force: bool=False)`.

- `_media_cache_cached` — Lee/reutiliza las relaciones de medios WordPress registradas. [Código, línea 140](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_lite_app.py#L140)
  Firma: `_media_cache_cached(session: dict, *, force: bool=False)`.

- `_now` — Fecha de los eventos/lotes de la aplicación compatible. [Código, línea 153](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_lite_app.py#L153)
  Firma: `_now()`.

- `login` — Inicia OAuth del servicio histórico ligero; no sustituye el login del frontend nuevo. [Código, línea 158](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_lite_app.py#L158)
  Firma: `login()`.
  Rutas/decoradores HTTP: `app.get('/login')`.

- `auth_callback` — Resuelve el callback de la aplicación ligera histórica. [Código, línea 175](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_lite_app.py#L175)
  Firma: `auth_callback(request: Request)`.
  Rutas/decoradores HTTP: `app.get('/auth/callback')`.

- `logout` — Cierra la sesión propia de la aplicación ligera. [Código, línea 201](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_lite_app.py#L201)
  Firma: `logout(request: Request)`.
  Rutas/decoradores HTTP: `app.get('/logout')`.

- `health` — Expone la salud de esa aplicación compatible. [Código, línea 211](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_lite_app.py#L211)
  Firma: `health()`.
  Rutas/decoradores HTTP: `app.get('/health')`.

- `_parse_custom` — Interpreta una selección explícita de SKU del lote ligero. [Código, línea 231](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_lite_app.py#L231)
  Firma: `_parse_custom(value: str)`.

- `_payload` — Serializa el progreso del lote de la aplicación ligera. [Código, línea 242](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_lite_app.py#L242)
  Firma: `_payload(session: dict, batch_id: str)`.

- `_reset_resume` — Restablece los controles de reanudación de un lote ligero. [Código, línea 260](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_lite_app.py#L260)
  Firma: `_reset_resume(session: dict, batch_id: str)`.

- `_process_one` — Procesa un SKU usando caches de proceso y un solo PUT WooCommerce final. [Código, línea 282](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_lite_app.py#L282)
  Firma: `_process_one(session: dict, batch_id: str)`.

- `root` — Sirve la página raíz compatible de sincronización ligera. [Código, línea 386](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_lite_app.py#L386)
  Firma: `root(request: Request)`.
  Rutas/decoradores HTTP: `app.get('/')`.

- `batch_page` — Sirve su pantalla compatible de lotes. [Código, línea 391](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_lite_app.py#L391)
  Firma: `batch_page(request: Request)`.
  Rutas/decoradores HTTP: `app.get('/woocommerce-batch-sync', response_class=HTMLResponse)`.

- `batch_create` — Crea un lote de sincronización ligera para la sesión. [Código, línea 421](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_lite_app.py#L421)
  Firma: `batch_create(request: Request)`.
  Rutas/decoradores HTTP: `app.post('/batch-create')`.

- `batch_status` — Consulta el progreso de ese lote compatible. [Código, línea 454](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_lite_app.py#L454)
  Firma: `batch_status(request: Request, batch_id: str)`.
  Rutas/decoradores HTTP: `app.get('/batch-status')`.

- `batch_resume` — Reanuda explícitamente un lote ligero existente. [Código, línea 467](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_lite_app.py#L467)
  Firma: `batch_resume(request: Request)`.
  Rutas/decoradores HTTP: `app.post('/batch-resume')`.

- `batch_step` — Ejecuta un paso explícito del lote ligero. [Código, línea 485](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_lite_app.py#L485)
  Firma: `batch_step(request: Request)`.
  Rutas/decoradores HTTP: `app.post('/batch-step')`.

## sync_service.py

API compatible del rol sync para sesiones delegadas y herramientas históricas.

[Abrir archivo](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_service.py)

- `_service` — Obtiene el servicio Google compatible para una sesión delegada. [Código, línea 27](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_service.py#L27)
  Firma: `_service(api, version, session)`.

- `_prepared` — Comprueba/prepara el contexto que necesita la herramienta compatible. [Código, línea 35](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_service.py#L35)
  Firma: `_prepared(_drive, session)`.

- `_validate` — Valida la delegación firmada y su payload antes de usarla. [Código, línea 39](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_service.py#L39)
  Firma: `_validate(sheets, spreadsheet_id)`.

- `main_url` — Resuelve el origen del servicio principal compatible. [Código, línea 65](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_service.py#L65)
  Firma: `main_url()`.

- `start_session` — Acepta una delegación autorizada y crea la sesión del rol sync. [Código, línea 70](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_service.py#L70)
  Firma: `start_session(ticket: str)`.
  Rutas/decoradores HTTP: `app.get('/session/start')`.

- `health` — Ruta de salud del servicio histórico de sincronización. [Código, línea 105](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_service.py#L105)
  Firma: `health()`.
  Rutas/decoradores HTTP: `app.get('/health')`.

- `tools` — Ejecuta la herramienta compatible solicitada con contexto validado. [Código, línea 111](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_service.py#L111)
  Firma: `tools(request: Request)`.
  Rutas/decoradores HTTP: `app.post('/internal/tools')`.

- `direct_tool` — Atiende la entrada directa de una herramienta compatible autorizada. [Código, línea 169](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/sync_service.py#L169)
  Firma: `direct_tool(request: Request, tool_path: str)`.

# Herramientas nativas y retirada pública de Gradio

Ver [NATIVE_TOOLS](NATIVE_TOOLS.md): responsabilidades, rutas, controles y reversión.

## native_tools.py

JSON adapters for tools inside Next.js; the established business functions stay intact.

- `movements` — Read existing history without creating its sheet merely to show a screen. [Código, línea 37](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/native_tools.py#L37)

- `inventory` — Reuse the canonical inventory, with count flags and parent stock rules. [Código, línea 52](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/native_tools.py#L52)

- `media_preview` — Return the same Drive/WordPress comparison as JSON, without an HTML page. [Código, línea 65](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/native_tools.py#L65)

- `execute` — Delegate to established handlers; no automatic retry of an external write. [Código, línea 78](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/native_tools.py#L78)

- `execute.read` — Lee los últimos movimientos del SKU en la hoja del usuario. [Código, línea 86](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/native_tools.py#L86)

- `register` — Register the identical JSON contract on the public API and signed sync executor. [Código, línea 108](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/native_tools.py#L108)

- `register.tools` — Valida método, sesión, rol, confirmación y modo tienda; ejecuta o delega JSON. [Código, línea 111](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/native_tools.py#L111)

## retired_service.py

Retired public origins: canonical redirects and the existing signed sync backend.

- `health` — Identifica la versión retirada sin consultar proveedores. [Código, línea 28](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/retired_service.py#L28)

- `retired` — Redirige GET/HEAD al frontend y bloquea escrituras públicas antiguas con 410. [Código, línea 35](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/retired_service.py#L35)

## frontend/components/InventoryTools.tsx

Pantallas React nativas para conteos, revisión Drive/WordPress y publicación por grupos. No monta páginas antiguas ni Gradio.

- `Tool` — Modos count, media y publication de la pantalla integrada. [Código, línea 7](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/InventoryTools.tsx#L7)

- `Row` — Fila canónica de Drive con conteo realizado y regla de portada. [Código, línea 8](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/InventoryTools.tsx#L8)

  Campos declarados: `sku: string;`, `nombre_producto: string;`, `Marca: string;`, `categorias: string;`, `Existencias: number;`, `precio: number;`, `counted: boolean;`, `variable_parent: boolean;`.

- `Inventory` — Filas, resumen de existencias y tipos de movimientos permitidos. [Código, línea 12](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/InventoryTools.tsx#L12)

  Campos declarados: `rows: Row[];`, `total: number;`, `pending: number;`, `movement_types: string[];`, `summary: { products: number; units: number; retail_value: number; low_stock: number; out_of_stock: number };`.

- `History` — Movimiento con fecha, cantidades, stock antes/después y motivo. [Código, línea 16](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/InventoryTools.tsx#L16)

  Campos declarados: `timestamp: string;`, `tipo: string;`, `cantidad: number;`, `stock_anterior: number;`, `stock_nuevo: number;`, `motivo: string;`, `referencia: string;`, `usuario: string`.

- `Review` — Comparación de nombres, stock y precios entre Drive y WooCommerce. [Código, línea 18](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/InventoryTools.tsx#L18)

  Campos declarados: `rows: { sku: string; name: string; status: string; inventory_stock: number | null;   woocommerce_stock: number | null; inventory_price: number | null; woocommerce_price: number | null }[];`, `summary: Record<string, number>`.

- `Media` — Coincidencias de imágenes y gates independientes de WordPress/WooCommerce. [Código, línea 21](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/InventoryTools.tsx#L21)

  Campos declarados: `rows: { sku: string; name: string; ready: boolean; wc_id?: number;   images: { requested_filename: string; resolved_filename: string; resolution: string }[] }[];`, `summary: Record<string, number>;`, `woocommerce_write: boolean;`, `wordpress_write: boolean;`, `wordpress_configured: boolean`.

- `Batch` — ID, progreso y resultados del lote existente de Sheets. [Código, línea 24](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/InventoryTools.tsx#L24)

  Campos declarados: `batch_id: string;`, `processing: boolean;`, `summary: { total: number; success: number; error: number; pending: number; running: number };`, `rows: { position: number; sku: string; status: string; message: string; permalink?: string }[]`.

- `Confirmation` — Datos y callback del modal anterior a la escritura. [Código, línea 27](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/InventoryTools.tsx#L27)

  Campos declarados: `title: string;`, `text: string;`, `label: string;`, `action: () => Promise<void>`.

- `Props` — Permisos, cuenta/carpeta, estado de red y adaptadores de API/confirmación. [Código, línea 28](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/InventoryTools.tsx#L28)

  Campos declarados: `tool: Tool;`, `namespace: string;`, `canEdit: boolean;`, `isAdmin: boolean;`, `online: boolean;`, `api: <T>(path: string, method?: string, body?: unknown, timeout?: number) => Promise<T>;`, `ask: (confirmation: Confirmation) => void;`.

- `money` — Presenta cantidades monetarias o un valor ausente. [Código, línea 33](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/InventoryTools.tsx#L33)

- `InventoryTools` — Organiza las herramientas nativas en el mismo shell y protege sus escrituras. [Código, línea 48](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/InventoryTools.tsx#L48)

- `InventoryTools.request` — Consulta la API JSON con cookie de mismo origen y espera acotada. [Código, línea 87](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/InventoryTools.tsx#L87)

- `InventoryTools.attempt` — Impide doble envío y presenta errores sin reintentar escrituras. [Código, línea 89](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/InventoryTools.tsx#L89)

- `InventoryTools.loadInventory` — Carga filas canónicas y prepara conteos sin enviar cambios. [Código, línea 95](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/InventoryTools.tsx#L95)

- `InventoryTools.inspectHistory` — Consulta los movimientos del SKU seleccionado. [Código, línea 100](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/InventoryTools.tsx#L100)

- `InventoryTools.refreshBatch` — Lee el lote; no inicia publicación ni reanuda automáticamente. [Código, línea 105](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/InventoryTools.tsx#L105)

- `InventoryTools.runBatch` — Ejecuta grupos confirmados; vuelve a comprobar pausa/pantalla antes de cada POST. [Código, línea 110](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/InventoryTools.tsx#L110)

- `InventoryTools.confirm` — Abre el modal; solo la acción confirmada inicia la operación. [Código, línea 129](https://github.com/MisterReto/suite-ecommerce-ia/blob/feature/woocommerce-and-product-removal-20261009/frontend/components/InventoryTools.tsx#L129)
