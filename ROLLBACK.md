# Recuperación

| Referencia | Propósito |
| --- | --- |
| `backup/pre-platform-20261006` / `41d0599a45dda1edca13b1c253a68524e3567ad2` | Código histórico desplegado antes de migrar. |
| `3ba6a2f9aeb65265a6165ee6c48b7ab273256d7f` | Generación aceptada protegida durante esta continuación. |
| Copia de `inventario_completo` en `docs/backups.md` | Respaldo histórico registrado por el trabajo anterior. |

## Si falla el nuevo frontend/API

Volver a la URL histórica de `suite-ecommerce-ia`. Los servicios nuevos y PostgreSQL se conservan para investigar y recuperar resultados. Si se cambió `MAIN_SERVICE_URL` del sync, restaurar el valor registrado antes del cambio. Revertir el commit de configuración o redeploy del commit histórico requiere conservar el estado nuevo.

## Si un job queda incierto

Inspeccionar job, checkpoint, IDs Drive y estado de tienda. No reenviar automáticamente una llamada pagada en vuelo. Un intento adicional requiere comprobar qué resultado existe y usar el mecanismo de retry con revisión de incertidumbre.

## Antes de cambiar un esquema con datos

    python -m catalog_platform.backup

La herramienta necesita `pg_dump` compatible y la configuración servidor. Guardar el dump de forma privada y comprobarlo con `pg_restore --list`; probar restauración en otra base. Conservar también la clave Fernet, fuera del repositorio. Un dump sin esa clave no permite leer las conexiones cifradas.

Exportar las fichas nuevas del catálogo SQL antes de volver a un flujo que dependa de Sheets. Las nuevas fichas no se escriben automáticamente en la hoja histórica.

No borrar tablas, eliminar originales, mover carpetas históricas ni sobrescribir el Sheet completo como mecanismo de rollback.
