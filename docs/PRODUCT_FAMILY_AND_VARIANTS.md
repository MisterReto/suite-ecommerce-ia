# Padres y variantes

La captura conserva detección de simple/variable, propuesta de padre, selección de padre existente, atributos, SKU/barcode, marca/categoría y búsqueda de similares en catálogo local/Sheet.

Un padre variable representa la familia, no stock físico. Las variantes conservan su identidad UUID y parent_id; su SKU/barcode son campos de búsqueda. La portada del padre utiliza el flujo Gemini existente y la imagen HD conservada. No se añaden consultas de tiendas a esa decisión.

Version protege cambios concurrentes. Crear/editar registra auditoría. Archivar un padre incluye variantes activas; restaurar incluye solo las archivadas en ese mismo evento. Una variante no se restaura mientras su padre siga archivado. Cambiar estado se rechaza si hay jobs activos asociados.

Las pruebas de catálogo/captura, paridad y retirada cubren familias y variantes. La prueba con productos/portada reales sigue pendiente según REGRESSION_RESULTS.md.
