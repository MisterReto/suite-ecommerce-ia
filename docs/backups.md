# Respaldos previos a la plataforma

- Código desplegado protegido en la rama GitHub `backup/pre-platform-20261006`,
  commit `41d0599a45dda1edca13b1c253a68524e3567ad2`.
- Hoja nativa copiada, sin editar ni mover origen:
  [inventario_completo_BACKUP_pre_plataforma_2026-10-06](https://docs.google.com/spreadsheets/d/1dUG_xuuIUwGLTMfXl56dGRyJSFc18VlD2EkD5aWjym8/edit).
- Se conserva en la misma carpeta autorizada. No se cambiaron permisos.
- Las imágenes históricas permanecen en su carpeta original; no hay migración
  destructiva ni obligación de duplicar todos los binarios antes de leerlos.
- El contrato AST en `tests/fixtures/generation_contract.json` protege el flujo
  creativo aceptado para esta actualización.

Antes de importar desde Sheets/Excel, el servicio crea una copia de la fuente.
Antes de una migración importante SQL, ejecutar el script de backup con la URL
servidor y verificar la restauración en una base aparte. Nunca ejecutar DROP,
TRUNCATE ni borrados masivos como parte del arranque o de la importación.
