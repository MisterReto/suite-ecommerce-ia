# Publicación desde el cargador probado en Colab

En la aplicación, abre **Más → Publicar en WooCommerce**. Busca por nombre o SKU,
filtra por categoría, marca o tipo y selecciona productos simples, familias o
variantes. La selección se conserva entre páginas. Revisa la vista previa,
elige imágenes, inventario y etiquetas y confirma la carga.

Los productos nuevos quedan en borrador. Los productos existentes se omiten.
Al seleccionar una variante, el cargador crea su padre cuando falta y conserva
los atributos de toda la familia. Añadir variantes a un padre publicado exige
habilitar la opción explícita: podrían quedar visibles inmediatamente.

## Procedencia y conservación

Notebook: [Extractor de productos](https://colab.research.google.com/drive/1oDLruQsit4B_gy-TVDJiiTl2HEZvc4a6#scrollTo=C_Z7cZqlZvFL).
La celda `C_Z7cZqlZvFL` se descargó el 14 de octubre de 2026.
SHA-256 del notebook: `591924eafe21117e9c490247cf74ef8673a1e7065858d869c0b96732b441335e`.

`catalog_platform/woocommerce_colab.py` conserva sin cambios los cuerpos de las
27 funciones del cargador. El manifiesto en `tests/fixtures/woocommerce_colab_manifest.json`
y una prueba comparan sus hashes. La autenticación de Colab, los widgets y las
variables globales de arranque se sustituyen por adaptadores de la aplicación.
Los encabezados HTTP originales se conservan, incluido
`User-Agent: RinconDeAsia-CatalogExporter/1.0`.

Se leen las cinco pestañas del Sheet original, con rangos acotados por su
metadata. Las imágenes se buscan recursivamente en la carpeta original y se
relacionan por el SKU real. La caché de medios se verifica contra WordPress
antes de reutilizar cada ID; se conserva cifrada en SQL. No se escribe en las
hojas ni se modifica la generación de imágenes con IA.

## Configuración

API y worker requieren `WOOCOMMERCE_URL`, `WOOCOMMERCE_CONSUMER_KEY` y
`WOOCOMMERCE_CONSUMER_SECRET`. Se admiten los alias históricos `WC_URL`,
`WC_CONSUMER_KEY` y `WC_CONSUMER_SECRET`. Para imágenes se requieren
`WP_USERNAME` y `WP_APP_PASSWORD`, con permiso para subir medios.

El Blueprint obtiene estos valores del servicio existente `suite-ecommerce-ia`;
no contiene secretos. Las credenciales Google y Neon existentes se conservan.
El frontend nunca recibe claves WooCommerce o WordPress.

Los IDs del Sheet y de Drive tienen los valores originales como predeterminados.
Puede configurarse `WOOCOMMERCE_SHEET_ID` o `WOOCOMMERCE_IMAGES_FOLDER_ID`.
La tienda autorizada por defecto es `https://rincon.creandotusite.com`.

## Cola, límites y recuperación

Una selección efectiva produce un trabajo SQL y un UUID en la cola RQ
`rincon-woocommerce-jobs`. Una familia se ejecuta dentro de su trabajo; un lote
produce trabajos independientes. Los workers atienden primero la cola existente
de imágenes y después la de WooCommerce. No se cambian su concurrencia ni el
pipeline de generación.

Cada lote admite hasta 100 selecciones y 1000 productos resultantes
(`WOOCOMMERCE_MAX_BATCH_PRODUCTS`). Las variantes cubiertas por una familia
seleccionada se excluyen. La aceptación del lote es transaccional: un error no
acepta sólo una parte. Vista previa y confirmación tienen una vigencia de diez
minutos. El acceso de publicación requiere administrador.

Las claves de solicitud evitan aceptar dos veces la misma carga. Un bloqueo SQL
por tienda y padre evita carreras entre familias. Antes y después de cada
escritura se guardan checkpoints. Si WordPress acepta una escritura pero se
pierde su respuesta, el trabajo exige revisar el SKU y los medios antes de
reintentar; el cargador vuelve a buscar productos existentes. Un rechazo HTTP
4xx no queda marcado como escritura incierta.

Antes de aceptar la vista previa, el adaptador consulta si el SKU ya existe en
la papelera de WooCommerce. En ese caso detiene la creación con el ID del
producto y una indicación de restaurarlo en WordPress. El worker repite esta
comprobación antes de escribir. No elimina ni restaura productos automáticamente.
Las 27 funciones originales siguen sin cambios; esta comprobación es un
adaptador adicional. Los errores de WordPress se muestran como mensajes legibles.

## Validación controlada

Primero se probaron producto simple, familia, variante e imágenes; después se
incorporaron los lotes. Las pruebas utilizan dobles de Sheets/Drive/WooCommerce,
SQL aislado y Redis simulado con un consumidor RQ real. Cubren duplicados,
rollback de lotes, acceso por usuario, respuesta perdida y reintentos.

Ejecuta `python scripts/validar_local.py` tras instalar `requirements.txt` y
`requirements-test.txt`. Los cinco grupos aislados pasaron, incluido el grupo
WooCommerce con 23 pruebas en la primera integración y 28 tras cubrir papelera
y mensajes de error. TypeScript, las compilaciones export/standalone y
la prueba de despertar servicios también pasaron. Chrome verificó la interfaz
compilada con una tienda simulada. Estas pruebas no certifican una nueva
escritura en la tienda de producción.
