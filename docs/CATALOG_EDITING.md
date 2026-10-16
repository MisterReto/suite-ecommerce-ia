# Captura y edición del catálogo

La captura asigna etiquetas al analizar el producto usando todo el vocabulario de Drive. Las propuestas conservan la escritura de las etiquetas existentes; si la respuesta viene vacía, solo se seleccionan coincidencias literales respaldadas por la identidad reconocida. No se infieren alegaciones de salud.

El autoguardado del borrador funciona en segundo plano. Una acción explícita espera la escritura pendiente. Una respuesta antigua no reemplaza texto más reciente.

El formulario de catálogo envía `sync_drive: true` tanto al crear como al editar. `catalog_platform/product_edit.py` resuelve el padre por `parent_sku`, limitado al tenant, y actualiza las celdas de `Lista completa` por SKU. Conserva imágenes, enlaces, columnas ajenas y las fórmulas que alimentan Lista Simple, Lista Variable y los CSV. La versión de producto protege las ediciones concurrentes; el bloqueo compartido coordina captura, edición y sincronización.

Si Drive falla, la respuesta indica que el catálogo quedó guardado y Drive está pendiente. Al volver a guardar se reintenta la fila, conservando el SKU de origen de una edición fallida y sin repetir el movimiento de stock. No se anuncia un guardado completo sin verificar las celdas de la fila. Los campos propios de SQL sin columna en el esquema, como costo y atributos adicionales, permanecen en el catálogo; no se inventan columnas.

Los UUID se usan dentro de API y SQL. Los formularios y fichas muestran SKU y SKU del padre.

WooCommerce conserva sus métodos aceptados. El filtro del adaptador permite nombres finales `SKU_n.png/jpg/jpeg/webp` y `SKU_n_hd/uso/comercial.ext`; descarta referencias, originales, raw y respaldos, incluidos los snapshots de trabajos antiguos. Esto se aplica a futuras cargas; no borra medios ya publicados en la tienda.

Pruebas: `test_product_edit.py`, `test_functional_parity.py`, `test_capture_mobile.cjs` y los cuatro contratos de WooCommerce indicados en `AGENTS.md`.
