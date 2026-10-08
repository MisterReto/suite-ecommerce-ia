# Identidad, familias y variantes

## Fuentes y prioridad

`catalog_platform/capture_bridge.py::check` combina el maestro PostgreSQL del
tenant y las filas de `inventario_completo` de la carpeta autorizada. Con Woo
activo añade consultas GET de la tienda asociada. `SUITE_DRIVE_ONLY=true`
mantiene Woo pausado. `WOOCOMMERCE_TENANT_ID` puede asociar explícitamente las
credenciales existentes a una carpeta; se admite la asociación existente
`WEBHOOK_TENANT_ID` o `GOOGLE_DRIVE_FOLDER_ID`. Una tienda distinta no las usa.

`catalog_capture.py::find_duplicate` prioriza GTIN válido (con ceros iniciales
y equivalencias EAN/UPC), SKU exacto sin distinguir mayúsculas, opción bajo el
mismo padre y nombre/marca/presentación. No equipara guion con guion bajo en
el SKU. Distintos GTIN válidos requieren comparación, no un bloqueo solo por
nombre. Marca compartida sin un nombre de familia compatible no crea familia.

`family_score`, `family_label` y `review_product` producen cuatro casos:

| Caso | Evidencia | Acción del operador |
|---|---|---|
| `existing` | Identidad exacta o atributo ya registrado | Abrir/actualizar existente; guardado nuevo bloqueado |
| `existing_parent` | Padre compatible con marca y familia | Comparar hijos y elegir ese padre |
| `new_family` | Referencias similares, sin padre compatible | Revisar familia nueva y sus atributos |
| `simple` | Sin evidencia registrada de una familia | Guardar simple o investigar presentaciones |

Las coincidencias de marca/familia son propuestas; una familia desconocida no
se inventa. `/api/find-variants` devuelve primero evidencia del catálogo para
los primeros tres casos, sin IA. Para investigar un simple utiliza la función
original `app.py::buscar_variantes_por_imagen`; muestra la recomendación y
requiere clave personal. Nunca cambia automáticamente la decisión del operador.

Woo se consulta en lectura: SKU usando el resolutor existente, familia por
nombre, padres e hijos con atributos/imágenes. La búsqueda de nombre está
acotada a 30 productos y las variaciones a 300 por padre; no es un inventario
exhaustivo. Si una familia supera el límite de variaciones, la verificación
queda incompleta y no permite guardar. Una falla de lectura activa también
bloquea crear un producto hasta revisar la conexión.

## Modelo padre e hijo

Se reutilizan `ProductCapture::load_parents`, `next_parent_sku` y
`generar_sku_logica`. El sufijo FULL sigue reservado al padre; no se cambia la
regla histórica para hijos. `/api/parents` añade padres SQL a los de Sheets y
explica su origen. Un padre SQL seleccionado que falta en Sheets se incorpora
en el mismo batch que su nuevo hijo, conservando el ID SQL existente.

| Registro | PostgreSQL | Sheets | Precio / stock |
|---|---|---|---|
| Simple | `Product.product_type=simple` | `tipo=simple`, sin `sku_padre` | Propios; captura inicia stock en cero |
| Padre | `product_type=variable`, sin parent_id | `tipo=variable`, SKU FULL | Nulos en SQL; no se vende como unidad |
| Hijo | `product_type=variation`, `parent_id`; `ProductVariant` | `tipo=variation`, `sku_padre` | Propios del hijo |

El padre conserva las opciones de su atributo; la variación conserva su valor
y demás atributos reconocidos. La interfaz histórica de Sheets admite un
atributo principal (por ejemplo Sabor o Tamaño); para variantes con varias
dimensiones, revisar explícitamente un valor combinado o el diseño de familia
antes de guardar. No se fabrican dimensiones ni opciones.

## Portada fiel

`POST /api/family-cover` llama `ProductCapture::cover` y
`compose_family_cover`. Compone hasta cuatro fotos reales, título y marca de
agua; no llama a un modelo de imagen. Si solo existe la foto actual, lo indica
en la UI. La revisión/SKU/padre/modo/nombre invalidan una portada incompatible;
se exige prepararla otra vez antes de guardar. Su archivo mantiene
`<PADRE>_portada_<token>.jpg` en la carpeta original de imágenes.

`prepare_capture_updates` prepara padre + hijo y opciones en una única petición
Sheets. `capture_bridge::mirror_records` incorpora Product, ProductVariant e
imágenes en una transacción SQL. El marcador SyncEvent hace idempotente la
reparación; repetirla no vuelve a aplicar cantidades ni recrear productos.
