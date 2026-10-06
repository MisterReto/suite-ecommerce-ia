# Google Drive y Google Sheets

Las dependencias prioritarias son las carpetas actuales de imágenes generadas y el Google Sheet `inventario_completo`. No se presupone que existan otros Excel importantes.

| Fuente | Uso real | Política de la transición |
| --- | --- | --- |
| `Proyecto_IA/imagenes_generadas` | Imágenes históricas, referencias de estilo y medios de tienda. | Conservar nombres, IDs y ubicación. |
| `inventario_completo` / `Lista completa` | Operación histórica de captura e inventario. | Conservar origen; importación con respaldo y revisión. |
| Archivos Excel/CSV/ODS aportados | Intercambio e importación. | Mantener el original; vista previa y confirmación. |
| `Rincon_de_Asia_App/images/originals` | Nuevas referencias del catálogo. | Crear dentro de la carpeta autorizada. |
| `Rincon_de_Asia_App/images/generated` | Resultados y raws nuevos del worker. | Guardar ID, producto y job en SQL. |
| `Rincon_de_Asia_App/backups` | Copias de fuentes/exportaciones. | Acceso con la misma frontera de carpeta. |

`DriveService.for_session` reutiliza `_get_drive_service` y `_preparar_estructura`. `DriveService.owns` recorre padres antes de leer o escribir. Los resultados de búsqueda no autorizan por sí mismos acceder a un archivo.

## Qué ocurre al guardar

En captura compatible, generar no sube automáticamente imágenes: `/api/save` usa `ProductCapture.save` después de aprobar. En el catálogo durable, el worker persiste resultados en Drive para recuperarlos; aprobar o generar sigue sin publicar en WooCommerce.

## Importación al catálogo

El importador normaliza filas, prepara una muestra, conserva SKU ya existentes y crea respaldo antes de confirmar. Sheets/Excel son intercambio y respaldo del catálogo SQL; mientras siga activo el modo compatible, la hoja aún es una fuente operativa histórica. No afirmar que esa transición ya terminó.

Las llamadas Sheets históricas aún viven en `app.py` y módulos de inventario; no existe un `SheetsService` independiente completo. Separarlo es una tarea futura que debe seguir su contrato probado, sin reescribir el generador.

## Credenciales

OAuth mantiene el acceso existente. La cuenta dedicada es opcional y requiere compartir explícitamente la carpeta autorizada. No cambiar scopes, permisos ni propiedad durante esta continuación. La clave de cifrado se conserva junto al respaldo fuera del repositorio.

La copia previa de la hoja está registrada en [docs/backups.md](docs/backups.md). Esta continuación no hizo escrituras en Drive ni Sheets.
