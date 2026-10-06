# Drive y Sheets encontrados

Auditoría de solo lectura del 2026-10-06. No se movió, renombró ni eliminó
ningún recurso. La búsqueda no constituye un inventario exhaustivo de duplicados.

## Recursos verificados

| Recurso real | ID | Papel |
| --- | --- | --- |
| Proyecto_IA | `1WNDrC4rMfeg066uciiS5VVOYuTvqoAPT` | raíz actual de trabajo |
| imagenes_generadas | `1V4HgnTCRnwVGwrGD968eNdtvQDGGY7wt` | resultados/archivos usados por la app |
| imagenes_temporales | `1HHe116AZFECvkvqy0bGJsXNKLvfw4bPL` | temporales existentes; nuevos candidatos separados por job |
| inventario_completo | `1gnuDwcceWwN4ksNnyq3Hs_MQHTfnZQZjeLnph72aUrE` | Sheet nativo, no Excel |
| inventario_completo_BACKUP_pre_plataforma_2026-10-06 | `1dUG_xuuIUwGLTMfXl56dGRyJSFc18VlD2EkD5aWjym8` | backup previo ya existente, no creado en esta auditoría |

También hay archivos históricos CSV/Excel y un backup anterior. No son motivo
para reorganizar Drive. Los IDs son referencias, no credenciales; tener un ID
no sustituye permiso de acceso.

## Naming y originales

Se observaron `GLIPOC41GX_1_hd.jpg`, `GLIPOC41GX_2_uso.jpg`,
`GLIPOC41GX_3_comercial.jpg`, equivalentes GLIPOC55GX, STECMA1PZX y SINPEL1PZX.
También existen nombres históricos `.png`, por ejemplo `SPTLB680ML_2.png`.
`woocommerce_media_prepare.py`, `app.py` y los resolutores históricos
siguen considerando variantes de nombre. No renombrar esos archivos en bloque.

El catálogo nuevo escribe candidatos en
`imagenes_temporales/<job_uuid>/<SKU>_<slot>.jpg`, junto al raw sin marca.
Samples adicionales usan `_2`, `_3`, etc. dentro de esa carpeta. Al guardar
explícitamente, el nombre canónico sigue siendo `<SKU>_1_hd.jpg`, `_2_uso.jpg`
o `_3_comercial.jpg`. Las referencias subidas por captura se identifican por
`reference_<n>.jpg`; el job guarda sus IDs. Nunca se decide el producto a partir
del nombre de un temporal local.

`DriveService.save_approved` requiere aprobación previa de catálogo. Si hay
un archivo canónico, primero copia un respaldo determinista en
`Proyecto_IA/Rincon_de_Asia_App/backups/images/`, y después actualiza el contenido
conservando su ID. Ese árbol es **una creación futura condicionada al guardado**;
no se afirma que exista en la inspección inicial. Dos archivos del mismo nombre
bloquean el guardado para selección manual por ID. Un fallo de backup impide
reemplazar el original. No se limpia automáticamente el historial de candidatos.

El guardado compatible de captura conserva `ProductCapture.save` y sus reglas
de SKU, familia, portada e inventario. Se mantiene separado de publicar en web.

## Pestañas y estructura de inventario_completo

| Pestaña | sheetId | Grid observado | Uso |
| --- | --- | --- | --- |
| Lista completa | 974398866 | 1000 × 40, 1 fila congelada | catálogo principal de captura/inventario |
| Lista Variable | 1422428291 | 988 × 49, 1 congelada | productos variables / estructura histórica |
| Lista Simple | 1613817900 | 882 × 26, 1 congelada | productos simples / estructura histórica |
| Media Sync | 174141688 | 1681 × 26 | resolución Drive ↔ medios WordPress |
| Movimientos Inventario | 1053052795 | 1000 × 26, 1 congelada | registro histórico de movimientos |
| WooCommerce Batch Sync | 1556161029 | 1720 × 26 | resultados del batch ecommerce histórico |
| CSV 1 Productos | 2097442362 | 1000 × 26, 1 congelada | preparación/exportación histórica |
| CSV 2 Variaciones | 691360367 | 1000 × 47, 1 congelada | preparación/exportación de variaciones |

El tamaño del grid no equivale al número de productos. Zona horaria del Sheet:
`America/Mexico_City`. No alterar pestañas por inferir que alguna ya no sirve.

| Columna principal observada | Posición | Concepto utilizado |
| --- | --- | --- |
| sku_padre | A | relación de familia |
| tipo | B | simple/variable/variation |
| sku | C | identificación operativa |
| nombre_producto | D | nombre |
| Marca | E | marca, mayúscula preservada |
| descripcion_corta | F | descripción breve |
| descripcion_larga | G | descripción de ficha |
| Existencias | H | stock histórico |
| categorias | I | categorías/subcategorías codificadas en estructura histórica |
| etiquetas | J | tags |
| Web link imagen | K | enlace de imagen/medio |
| precio | L | precio |
| Precio descuento | M | oferta |
| imagenes | N | referencias de imágenes |
| encabezados vacíos | O–R en Lista completa | conservar posiciones; no compactar |
| atributo_nombre | S en Lista completa | nombre de atributo |
| atributo_valor | T en Lista completa | valor de variante |

La inspección leyó encabezados y muestras acotadas. No se inventan columnas
de barcode o mappings que no fueron verificadas en la hoja: el código admite
campos opcionales y aliases en importación. `inventory_schema.py`,
`catalog_capture.records_from_values` y `imports.normalize` convierten por
encabezado, no por una nueva estructura impuesta.

`Media Sync` tiene timestamp, sku, requested_filename, resolved_filename,
drive_file_id, wp_media_id, wp_media_url, status, note. La muestra
`FIDATB400G_2.png` resolvió `FIDATB400G_2_uso.jpg`, media ID 5675. Esto acredita
compatibilidad histórica del naming, no conectividad actual de WordPress.

`Movimientos Inventario` tiene timestamp, movement_id, sku, producto, tipo,
cantidad, stock_anterior, stock_nuevo, motivo, referencia, usuario. La muestra
no mostró movimientos; no se deduce que todo el registro esté vacío.

## Dónde se accede a Google

| Operación | Código real |
| --- | --- |
| OAuth y cliente | `app.py`: login/auth_callback, `_get_drive_service`, `_get_sheets_service`; `google_credentials.py` opcional |
| Encontrar raíz, generadas, temporales y Sheet | `app._preparar_estructura`, `_buscar_archivo`; `ai_app.py` ajusta Lista completa |
| Búsqueda/listado/ownership | `DriveService.list`, `find`, `folder`, `owns` |
| Metadata/URLs | `DriveService.metadata`, `url`; preview privado vía API, no token en URL |
| Descargar | `DriveService.download_to` para worker; `download` compatible limitado |
| Subir candidatos | `worker.generation`, `studio_jobs.process_capture`, `DriveService.upload` |
| Guardar producto histórico | `ProductCapture.save` y funciones existentes de app/Sheets |
| Lectura precisa nueva | `SheetsService.metadata`, `columns`, `read_range`, `find_sku` |
| Escritura de celda nueva | `SheetsService.update_cell`, RAW, valor esperado y verificación posterior |
| Importación SQL | `catalog_platform/imports.py`, acción explícita y respaldo |

Los wrappers permiten `.files()` / `.spreadsheets()` para no reescribir módulos
funcionales. Siguen existiendo llamadas SDK históricas dentro de esa frontera;
su sustitución total sería otro refactor con nuevas regresiones.

## Seguridad y límites

OAuth histórico solicita `openid`, userinfo.email y scope amplio `drive`.
La autorización de aplicación limita archivos a la raíz mediante ownership,
pero **eso no reduce el permiso OAuth concedido**. No revocar el token actual
ni cambiar scopes hasta probar una alternativa. `drive.file` no garantiza
lectura de todos los archivos preexistentes: requiere validar consentimiento
y selección. Una cuenta dedicada compartida solo con esta carpeta es opcional;
no necesita introducirse para completar las regresiones actuales.

El worker transmite a `/tmp` por chunks, aplica límite de 12 MB y elimina
parciales si falla la descarga. Los tres servicios no comparten disco. Las
pruebas de escritura futura deben usar una carpeta `TEST-INTEGRATION-*`,
registrar IDs, verificar tamaño/MIME/checksum y borrar solo esos objetos.

`SheetsService` rechaza encabezados repetidos, SKU duplicado incluso después
de filas vacías, pestañas mayores al límite de búsqueda y valor previo obsoleto.
No sobrescribe todo el Sheet para cambiar una celda. No hay CAS atómico de
Sheets: una edición simultánea entre lectura y escritura no puede resolverse
con una transacción SQL. Mantener una sola operación de escritura de prueba y
restaurar el valor inicial; no automatizar conciliaciones masivas ahora.
