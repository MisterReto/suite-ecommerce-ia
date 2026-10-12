# Herramientas locales

InventoryTools muestra stock del maestro Google, conteos, movimientos e historial. El catálogo SQL mantiene sus propios ajustes de stock y auditoría. La limpieza conserva ambas operaciones existentes y elimina comparaciones/sincronizaciones con tiendas.

| Ruta | Método | Acción |
|---|---|---|
| /api/tools/inventory | GET | Leer/buscar inventario y conteos pendientes |
| /api/tools/history | GET | Leer movimientos del SKU seleccionado |
| /api/tools/counts | POST | Conteo confirmado |
| /api/tools/movement | POST | Movimiento confirmado |

native_tools registra rutas en FastAPI, valida sesión/rol/método y llama directamente a sheet_inventory. GET no inicia escrituras. POST requiere confirm=true y admin/editor; viewer solo consulta. SecurityMiddleware conserva origen/CSRF y límites.

No hay forwarding ni secreto compartido. Las herramientas externas anteriores devuelven 404. Los bookmarks de conteo que se conservan abren la sección nativa; no cargan páginas HTML ecommerce.
