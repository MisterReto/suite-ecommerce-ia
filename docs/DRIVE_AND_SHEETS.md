# Google Drive y Sheets

Son dependencias críticas. Se conservan la carpeta raíz elegida por el usuario, las carpetas existentes de imágenes, los ejemplos de estilo, backups, originales y candidatos. No se ejecutó ningún movimiento, renombrado ni eliminación externa.

El Sheet operativo es **inventario_completo**, pestaña **Lista completa**. GOOGLE_SHEET_ID conserva su destino existente. No se asumen otros Excel críticos ni se reemplaza el documento completo. Las hojas auxiliares históricas de mapeos externos permanecen sin borrarse.

| Operación | Código | Límite |
|---|---|---|
| Leer imágenes y carpeta | app / DriveService | Carpeta autorizada, OAuth existente |
| Resolver imagen por SKU/nombre | drive_image_index | Funciones puras, mismo naming/fallback |
| Leer maestro | sheet_inventory._read_master_inventory | Lista completa, sin sincronizador ecommerce |
| Conteos/movimientos | sheet_inventory + inventory_operations | Confirmación, rol y escritura puntual existente |
| Historial | native_tools.movements | Lectura de Movimientos Inventario; no crea pestaña por mostrar una pantalla |
| Guardar captura/candidato | ProductCapture.save / worker.asset_save | Backup previo y naming existentes |
| Import/export local | catalog_platform.imports | Catálogo autorizado, sin importación de tienda |

La clave Gemini no se guarda en Drive/Sheets. Google OAuth se cifra en servidor para el worker; tokens nuevos se refrescan con el cliente existente. La cuenta de servicio opcional mantiene su lógica y requiere la carpeta compartida.

La captura conserva la reparación de un guardado parcial entre SQL y Sheet. Sus estados sync_status pertenecen a esa reparación local/Google, no a WooCommerce/Loyverse. La retirada no elimina esa función.

Lecturas/escrituras reales pendientes en REGRESSION_RESULTS.md. No usar una prueba para sobrescribir todo el Sheet ni limpiar hojas históricas.
