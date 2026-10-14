# Validación de paridad — 8 octubre 2026

No se da la tarea por aceptada hasta completar el pase real. Las pruebas
automáticas usan fotos locales y dobles de Gemini/Drive/Sheets/Woo; no gastan
créditos ni cambian stock o productos reales. La rama parte de `405f423` y
la auditoría previa publicada es `ef1b756`.

## Resultados locales

Los seis grupos existentes del workflow pasaron: 35 + 9 + 24 unittest,
63 pytest históricos, 52 pytest de contrato/catálogo/captura y 35 de
estabilización/free Render: **218 pasadas, 10 omitidas**. Las omisiones son
pruebas que necesitan PostgreSQL/Redis reales; SQLite no demuestra concurrencia.
Después se ampliaron las pruebas de paridad de 17 a **24**, todas pasaron.
No sumar los 24 de nuevo como pruebas independientes: 17 ya estaban en el grupo de 52.

Next export y standalone compilaron; TypeScript y el proxy Next real pasaron
rutas, cookies, OAuth y uploads de 12 MB. La prueba Node de Loyverse pasó
progreso y recuperación de respuesta perdida. `npm audit --omit=dev` informó
cero vulnerabilidades. Se registra CI posterior en `docs/VERIFICATION.md`.

El contenedor no tiene un navegador ejecutable y la descarga Playwright quedó
truncada. No se afirma pase móvil local. `test_capture_mobile.cjs` añade
perfiles táctiles Pixel/iPhone en Chromium y WebKit a 360/390/430 px en CI:
servicio despertando con respuesta HTML, catálogo listo, controles alcanzables de al menos 44 px, inputs de cámara y
galería, error de carga y reintento, sustitución del frente, eliminar reverso,
campos de 16 px y teclados por dato, autosave estable, salir antes del debounce,
navegación/recarga, clave, familia/portada, tres slots, corrección individual
sin perder las otras imágenes y reparación. También reduce la altura a 480 px
para comprobar formulario y diálogo. Usa APIs sintéticas; no abre una cámara
física ni demuestra el comportamiento del teclado del sistema.

Después del ajuste para celular y recuperación pasaron 30 pruebas focales de
paridad, contrato y separación. TypeScript, build standalone y proxy Next real
de 12 MB correctos. La rama está publicada en PR #27. El run 37744572296 pasó
Chromium/WebKit completos y la batería general; PostgreSQL/Redis encontró un
marcador de guardado desactualizado (79 pasadas, una fallida). La corrección
confirma job y borrador en la misma transacción y cubre resultados terminados
durante una desconexión, sin recuperar capturas descartadas. La evidencia y
el enlace al estado posterior están en `docs/VERIFICATION.md`. La repetición
37746010480 sobre `d894f0c` terminó verde: **82 pruebas PostgreSQL17/Redis7 sin
omisiones**, móvil completo Chromium/WebKit y los tres jobs correctos. El run
de push 37746004169 también pasó. Los teléfonos físicos y el proveedor real
mantienen su aceptación separada.

## Pase real, en el orden solicitado

Usar staging, cuenta autorizada y un inventario/carpeta de pruebas. Para
escrituras identificar SKUs con prefijo `TEST-INTEGRATION-`; registrar imagen,
cuenta sin secretos, commit/deploy y resultado de cada paso. Gemini real solo
con presupuesto explícito; no usar claves Render como sustituto personal.

| # | Prueba / aceptación | Evidencia automática | Pase real |
|---|---|---|---|
| 1 | Celular → Productos → Nuevo producto con IA | Entrada independiente de ready; browser CI | Pendiente Chrome Android y Safari iPhone |
| 2 | Cámara + galería, preview/reemplazo/remover, EXIF | Upload real JPEG/EXIF y validación bytes; browser CI | Pendiente dispositivos; HEIC solo si decoder instalado |
| 3 | Ajustes Gemini, salir/entrar conserva configuración | `test_key_is_encrypted_persistent_and_never_uses_render` | Pendiente cuenta real, clave mediante UI segura |
| 4 | Foto conocida autocompleta campos editables y dudas | `test_photo_analysis_fills_editable_fields_and_marks_unknowns` | Pendiente Gemini y comparación con etiqueta |
| 5 | Existente exacto detectado y sin duplicar | Barcode real, SKU/SQL/Sheet; no IA antes de exacto | Pendiente lectura real, sin crear copia |
| 6 | Otro sabor/tamaño utiliza padre correcto | `test_existing_family_is_suggested_without_gemini`, browser CI | Pendiente familia de prueba |
| 7 | Padre nuevo e hijo relacionados, sin guardado parcial | `test_new_parent_cover_and_variant_are_atomic_in_master`, rollback SQL | Pendiente familia de prueba |
| 8 | Portada solo con fotos reales y estado de una variante | Composición JPEG real, token/revisión y marca | Pendiente revisar visualmente en staging |
| 9 | Producto ajeno a familia se guarda simple | `test_simple_save_mirrors_once_and_preserves_reference` | Pendiente SKU simple de prueba |
| 10 | Maestro + inventario_completo + imágenes coherentes | Padre SQL faltante en Sheet; repair/lost-response sin doble escritura | Pendiente lectura de ambos tras guardar prueba |
| 11 | Producto limpio, lifestyle y comercial | Contrato AST y pipeline/worker con doubles; browser tres slots | Pendiente solicitudes mínimas con presupuesto |
| 12 | Corregir un slot conserva los otros dos | `test_studio_api`, `test_stabilization`, contratos/history | Pendiente una corrección autorizada |
| 13 | Lote de 2–3 productos, resultados por SKU | `test_catalog_platform`, `test_stabilization` con providers dobles | Pendiente presupuesto e inventario de prueba |
| 14 | Reinicio API/worker recupera clave y borrador | Nueva sesión/namespace; key vigente y tombstone | Pendiente reinicio controlado de staging |
| 15 | Dos usuarios/tiendas no comparten claves/datos/fotos | Actor/tenant + viewer 403 + archivo ajeno 404 + Woo scope | Pendiente dos cuentas de prueba |
| 16 | Cada sección del tutorial tiene resultado individual | Matriz en `docs/FUNCTIONAL_PARITY_AUDIT.md` | Pendiente aceptación funcional real por sección |

## Ejecución reproducible

Los comandos completos están en `.github/workflows/validate-drive-client.yml`.
Prueba focal: `python -m pytest test_functional_parity.py -q`. La batería de
PostgreSQL/Redis usa `TEST_DATABASE_URL` / `TEST_REDIS_URL` de servicios efímeros
de CI y añade este archivo. Nunca apuntar esos tests a la base operativa: los
fixtures usan cuentas, filas y claves sintéticas.

El browser requiere build standalone y copia de `public` y `.next/static`.
Ejecutar `TEST_WEBKIT=true node test_capture_mobile.cjs` con Playwright y sus
browsers instalados. Un fallo guarda una captura en `test-results`, publicada
como artifact CI. `test_frontend_mobile.cjs` conserva los cinco menús,
conexión y request_key tras respuesta perdida; `test_frontend_proxy.cjs`
comprueba el proxy TLS real.

## Barrera de despliegue

CI fallido detiene promoción. Staging de tres servicios free precede al pase
real; ningún servicio histórico se sustituye. La aceptación real incompleta
impide publicación final. Los cambios de datos de prueba se revisan y limpian
solo por ID/SKU explícito, sin borrados masivos ni cambios en productos reales.
