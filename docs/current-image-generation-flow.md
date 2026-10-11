# Generación protegida para la migración

La aclaración del usuario del 2026-10-06 establece como referencia el flujo
preparado con su primer prompt. Se conserva `creative_pipeline.py` sin rediseñar
su lógica al introducir catálogo, jobs persistentes o PWA.

## Flujo actual que se conserva

- FastAPI: `/api/uploads` → `/api/capture` → `/api/analyze` y `/api/draft`.
- Generación: `POST /api/generate` crea job por sesión y procesa slots seleccionados.
- `creative_plan` carga dos referencias comerciales de la carpeta Drive actual,
  prioriza los `_3.png` artísticos y cachea el brief por datos de producto/referencias.
- `creative_pipeline.brief` usa `gemini-2.5-flash` + Google Search para investigar
  anuncios, generar dos prompts y conservar fuentes verificadas/sugerencias Google.
- Lifestyle muestra adultos consumiendo o usando el producto según categoría.
  Si no hay anuncios, conserva la escena original generada por Gemini; si falta
  interacción humana válida, usa la alternativa apropiada al producto.
- Comercial usa ilustración, color y movimiento alrededor del producto exacto.
  Las fotos de estilo no son autoridad para marcas, sabores o empaques.
- `make_image` llama a `creative_pipeline.generate` una sola vez por imagen.
  Modelo activo: `GEMINI_IMAGE_MODEL`, predeterminado `gemini-3.1-flash-image`.
  Configuración: TEXT + IMAGE, 1:1. Las fotos originales son autoridad visual.
- Valida imagen no vacía, cuadrada y al menos 1024×1024; recodifica JPEG y aplica
  marca oficial de forma determinista. QA adicional es optativo, no genera otra imagen.
- `POST /api/images/{slot}/correct` conserva brief e historial, adjunta la imagen
  anterior sin marca como referencia de edición, además de los originales.
  Un fallo conserva la vista previa y las correcciones solicitadas.
- Archivos privados: namespace distinto del token OAuth, IDs opacos, autorización
  por sesión en `/api/files/{id}`; la API no devuelve rutas ni claves.
- `/api/images/{slot}/approve` confirma revisión. `/api/save` exige aprobación,
  usa `ProductCapture.save` y conserva nombres `<SKU>_1_hd.jpg`, `_2_uso.jpg`,
  `_3_comercial.jpg`. Publicar a ecommerce sigue siendo una acción separada.

El catálogo nuevo añade un `ImageGenerationService` y `ImageProvider` que
encapsulan estas funciones. La cola persistente crea contexto de ejecución
servidor, recupera referencias desde Drive y almacena metadata SQL; no cambia
prompts ni el proveedor. El archivo anterior no se publica automáticamente.

## Regresiones y límites de la evidencia

`test_creative_pipeline.py` comprueba interacciones, grounding, imagen anterior,
referencias, correcciones acumuladas, formato nativo y ausencia de reintentos.
`test_studio_api.py` verifica HTTP real con proveedor/Drive simulados, generación,
QA opcional, asociación, sesión, progreso recuperable, aprobación y guardado.
Un fingerprint AST protege funciones y prompts frente a cambios accidentales.
La comparación de píxeles exacta no se requiere. Las pruebas simuladas no se
presentan como llamadas reales a Gemini ni como verificación de calidad artística.

La siguiente sección conserva el mapa del despliegue anterior para compatibilidad.

---

# Referencia histórica del generador desplegado

Commit desplegado: `41d0599a45dda1edca13b1c253a68524e3567ad2`.

## Entrada y endpoints

No hay un endpoint REST propio `/api/generate` en la base. El botón Gradio
invoca `modulo_extraer_textos` y posteriormente `generar_todas_fotos` a través
de la cola `/gradio_api/queue/*`. Los callbacks de imágenes comparten
`concurrency_id="image_generation"`, `concurrency_limit=1`.

Entradas: sesión OAuth de Google, clave Gemini de esa sesión, foto frontal y
reverso opcional, SKU/nombre/marca/gramaje/descripción y metadatos de catálogo.
La captura copia las fotos al namespace privado de la sesión en `/tmp`.

## Llamadas y prompts congelados

1. `gemini_gateway.GeminiClient`: proveedor Google Gemini; límites por clave,
   caché de JSON en memoria y SDK sin reintentos HTTP pagados automáticos.
2. `investigar_prompts(nombre, marca, desc, api_key)` genera JSON con lifestyle
   y comercial en una llamada. Modelo `GEMINI_TEXT_MODEL`, predeterminado
   `gemini-2.5-flash`; `text_config(768)` sin Google Search.
3. `generar_todas_fotos` procesa `1_hd`, `2_uso`, `3_comercial` secuencialmente.
4. `_rehacer_generico` valida SKU, namespace y propiedad de las referencias;
   construye historial mediante `_construir_correccion` y llama al generador.
5. `generar_foto_individual` compone prompt + `_contrato_visual(slot)` +
   correcciones, adjunta `_imagen_para_ia` de cada foto original y usa
   `GEMINI_IMAGE_MODEL`, predeterminado `gemini-3.1-flash-image`.
6. `_configuracion_imagen_cuadrada` solicita modalidad IMAGE y relación 1:1.
7. `_extraer_imagen_bytes` ignora imágenes de pensamiento; `_validacion_local_imagen`
   exige imagen no vacía, cuadrada y de al menos 1024×1024.
8. `_validar_con_vision` compara con originales: puntuación mínima 90, sin errores
   de identidad. Un fallo técnico de QA detiene el intento sin otra generación.
9. Solo tras QA aprobado se recodifica a JPEG y `estampar_logo` aplica el logo.

`GEMINI_IMAGE_ATTEMPTS` es 1 por defecto, acotado 1–3. Se preserva la política
actual del generador; la cola externa nunca repite por su cuenta una llamada
incierta. `PROMPT_HD`, `_contrato_visual`, prompt de QA e investigación se
comparan contra la base, no se sustituyen por creatividad nueva.

El contrato histórico pedía escenas sin personas/manos. El usuario aclaró
expresamente que desea conservar la generación nueva del primer prompt; esta
sección describe la referencia histórica, no el flujo que se debe restablecer.

## Salidas y guardado

Resultado de `generar_foto_individual`: diccionario con ruta, puntuación,
intentos, resumen y posibles errores. `_rehacer_generico` devuelve ruta válida
o un field update que conserva la imagen anterior, historial acumulado y mensaje.
`ProductCapture.stage_image` asocia el archivo a SKU + slot + revisión de captura.

La generación NO sube la imagen automáticamente a Drive. `ProductCapture.save`
valida duplicados y variaciones, sube los borradores aprobados y escribe el
producto en `Lista completa`. Padres FULL no tienen precio ni stock propios.
Los nombres finales se mantienen: `<SKU>_1_hd.jpg`, `<SKU>_2_uso.jpg`,
`<SKU>_3_comercial.jpg`. El uploader reutiliza un archivo existente con el mismo
nombre dentro de la carpeta de esa sesión; no elimina los nombres históricos.

Drive: `_get_drive_service` → `_preparar_estructura` → carpeta
`imagenes_generadas`. Logo desde Drive si existe, en caso contrario oficial
incluido en `static/rincon-logo.png`. WordPress/WooCommerce están separados:
guardar en Drive no publica; la publicación explícita usa media sync y el worker
de herramientas existente.

## Regeneración y errores

`rehacer_hd`, `rehacer_uso`, `rehacer_com` pasan errores seleccionados, feedback
y el historial al mismo `_rehacer_generico`. El pipeline existente vuelve a
usar fotos originales y las correcciones acumuladas. No adjunta por sí mismo
la salida anterior como nueva autoridad visual. La nueva UI puede compararla,
pero no cambia silenciosamente esa regla del proveedor.

Una imagen rechazada no reemplaza el resultado anterior ni se publica. Errores
de cuota, formato, permisos, falta de imagen, QA técnico y logo se muestran
sin revelar secretos. No hay comparación de píxeles exacta en las regresiones.

## Abstracción y criterios de regresión

`ImageGenerationService` debe llamar a las funciones anteriores y traducir
sus resultados a jobs/assets. No debe duplicar la implementación del generador.
`ImageProvider` describe la interfaz; Gemini es el único proveedor activo.
FLUX/OpenAI/PhotoRoom permanecen como adaptadores no habilitados.

Pruebas: igualdad AST de funciones críticas, archivo JPEG no vacío y 1024²,
QA conservado, naming compatible, asociación producto-job, no publicación sin
aprobación, fallo que conserva resultado previo y almacenamiento autenticado.
Los dobles de proveedor/Drive no cuentan como generación real. El pase real
debe registrarse con su job, archivo, metadata y verificación de Drive.
