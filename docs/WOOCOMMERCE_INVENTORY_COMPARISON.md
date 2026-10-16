# Comparación de inventario y publicación

## Uso

En **Inventario → Conteo y movimientos → Comparar inventarios**, la app consulta
productos y variantes de WooCommerce y los compara por SKU exacto con el catálogo
registrado en la app. Si ese catálogo está vacío, carga el inventario de Drive y
usa **Sincronizar catálogo de la app** antes de comparar.

Se muestran faltantes en WooCommerce, productos exclusivos de la tienda,
borradores, publicados, publicados ocultos, conflictos de SKU/familia y diferencias
de cantidades. Los filtros se pueden descargar como CSV. Los totales de registros
incluyen familias y variantes; las familias no se cuentan como unidades de stock.

La diferencia es `stock WooCommerce − stock app`. Una cantidad desconocida o una
gestión de stock desactivada no equivalen a cero. Las variantes con stock heredado
de su familia requieren revisión conjunta y no producen diferencias individuales.
El estado de una variante también depende del estado de su familia.

La comparación es de lectura: no cambia cantidades, estados locales ni productos
de la tienda. No es una sincronización automática. Un fallo en cualquier página
invalida la consulta completa, sin presentar el resultado parcial como faltantes.
Se muestra la fecha de consulta; el botón Actualizar fuerza una lectura nueva.

## Publicación

En **Más → Publicar en WooCommerce**, el estado predeterminado es **Publicado y
visible en la tienda**. La vista previa muestra el estado y requiere confirmación.
También se pueden guardar los productos nuevos como borradores.

El cargador Colab conserva sus 27 funciones originales. Crea inicialmente los
productos como borradores ocultos. La capa `Exporter.execute` publica el padre
con `status=publish` y `catalog_visibility=visible` después de completar la
selección. Si una variante falla, una familia nueva permanece en borrador y se
puede reintentar sin duplicar las variantes ya reconocidas.

Si ya existe un borrador del SKU, elegir Publicado publica ese producto conservando
sus demás datos. Al publicar una variante se publica su familia y las variantes
que ya tenga: la pantalla lo explica antes de confirmar. Añadir variantes nuevas a
una familia publicada sigue requiriendo la autorización específica de esa pantalla.
Elegir Borrador no retira productos que ya estén publicados.

Los trabajos antiguos sin la opción `status` conservan el comportamiento anterior
de borrador. No se publican borradores existentes por consultar el comparador.

## Código

| Función | Archivo |
| --- | --- |
| Perfil HTTP, paginación, normalización y comparación | `catalog_platform/woocommerce_compare.py` |
| Sesión, tenant y endpoint GET de comparación | `catalog_platform/woocommerce_api.py` |
| Panel de comparación, filtros y CSV | `frontend/components/WooCommerceInventory.tsx` |
| Ubicación en Inventario | `frontend/components/InventoryTools.tsx` |
| Estado revisado y confirmación de carga | `frontend/components/WooCommercePublisher.tsx` |
| Publicación posterior a la carga y protección de reintentos | `catalog_platform/woocommerce_export.py` |
| Registro durable y mensaje de finalización | `catalog_platform/woocommerce_jobs.py`, `catalog_platform/worker.py` |

## Referencia y verificación

Se reutiliza el patrón del notebook **Extractor de productos.ipynb**
(`1oDLruQsit4B_gy-TVDJiiTl2HEZvc4a6`): `Accept: application/json`,
`User-Agent: RinconDeAsia-CatalogExporter/1.0`, autenticación REST, páginas de 100,
`status=any`, `X-WP-TotalPages`, recorrido de variantes y reintentos solo para GET.
Se mantienen el control del host de destino y la prohibición de redirecciones.

Las pruebas controladas cubren paginación con y sin cabeceras, errores sin resultado
parcial, SKU duplicado, estados de familia/variante, stock desconocido, aislamiento
por tenant, publicación visible, borradores explícitos, fallo de variantes y
reintentos. No usan credenciales reales ni escriben en la tienda.

Para revertir esta entrega, revierte su commit y vuelve a desplegar API, frontend
y worker. La reversión del código no cambia el estado de productos que el usuario
ya haya confirmado y publicado en WooCommerce.
