# Reglas del proyecto

## WooCommerce protegido

Conservar toda la integración de WooCommerce salvo una petición explícita del usuario que requiera modificarla. Las mejoras de captura, interfaz, Drive, etiquetas o generación no autorizan reescribir, sustituir ni modernizar sus métodos.

- Proteger `catalog_platform/woocommerce_colab.py`, `woocommerce_export.py`, `woocommerce_api.py`, `woocommerce_jobs.py`, `woocommerce_compare.py`, los componentes `WooCommercePublisher.tsx` y `WooCommerceInventory.tsx`, y sus contratos y fixtures.
- Mantener las funciones aceptadas del Colab, cabeceras HTTP, autenticación, límites de Drive, resolución por SKU, prioridades de imágenes, caché de medios, publicación confirmada y reintentos durables.
- Aplicar cualquier cambio autorizado en el adaptador más pequeño posible y ejecutar `test_woocommerce_colab.py`, `test_woocommerce_api.py`, `test_woocommerce_queue.py` y `test_woocommerce_compare.py`. No actualizar el fixture para hacer pasar una regresión.
- Los originales, referencias, archivos raw y respaldos son privados. Solo los archivos finales numerados de `imagenes_generadas` participan en la selección de WooCommerce. Los IDs técnicos permanecen internos; la interfaz usa SKU.
- Cada producto usa un único atributo de variación, compartido con su padre. Tamaño y tipo reconocido no se añaden como ejes extra. Un valor compuesto con comas es una sola opción. La revisión de una familia publicada muestra la vista previa y su advertencia; la carga sigue exigiendo autorización explícita.

## Generador protegido

Gemini usa exclusivamente `GEMINI_API_KEY` como secreto de Render en API y worker. No reintroducir claves personales, formularios de clave ni credenciales Gemini en snapshots o conexiones de usuario. El frontend solo recibe el estado de configuración.

Preservar los prompts, modelos, referencias, correcciones, marca y nombres de archivo. Mantener el contrato de `test_generation_contract.py` y `test_colab_generation.py`; no regenerar sus referencias para aceptar cambios accidentales.

El Colab conserva su flujo masivo original de CSV y Drive, guardado directo y auditoría. Cualquier reparación de otra área debe dejar intacto ese flujo.

## Documentación

Drive debe validar pertenencia a la carpeta autorizada, sin exigir que el usuario sea propietario. Cuando Google omita `parents`, la prueba alternativa es un listado acotado desde esa carpeta, con ID exacto, paginación y sin seguir accesos directos. Nunca autorizar solo por nombre ni saltarse la validación de una hoja global fuera de su carpeta. Una carpeta personal seleccionada usa su propio inventario y no la hoja predeterminada de Render.

Notion es una guía de funcionamiento vigente. Actualizar sus secciones existentes; no acumular mapas duplicados, notas de versiones ni registros de cambios. Documentar restricciones de manera visible.
