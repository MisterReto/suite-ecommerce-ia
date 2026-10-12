# Rollback de la limpieza

## Estado recuperable

Repositorio: `MisterReto/suite-ecommerce-ia`.

| Alcance | Rama de respaldo | Commit exacto |
|---|---|---|
| Tres servicios actuales | `backup/pre-integration-cleanup-20261012` | `b4aa4051cd2d1b897cc7a582e67ee8b938cfcc2b` |
| Dos servicios históricos | `backup/historical-before-cleanup-20261012` | `1a1c3bc9c9e56422c290fb59247a6dff2602d315` |

La rama de trabajo es `cleanup/remove-store-integrations-20261012`, basada en el commit realmente desplegado. Ningún servicio de Render, secreto, dato externo o esquema SQL se modifica durante la preparación. Mientras no se despliegue, **no hay nada que revertir en producción**.

## Revertir un futuro despliegue

1. Detener nuevas solicitudes de generación desde la UI y revisar los jobs en curso. Conservar checkpoints; no volver a lanzar operaciones pagadas inciertas.
2. Desactivar autodeploy en los tres servicios antes de elegir la versión. No tocar los dos servicios históricos.
3. En Render → servicio → Deploys, elegir el deploy anterior de la tabla y hacer rollback, o seleccionar la rama de respaldo y el commit exacto b4aa4051. Usar el mismo commit para API, worker y frontend; cambiar primero API/worker y después frontend.
4. Mantener DATABASE_URL, REDIS_URL, CREDENTIAL_ENCRYPTION_KEY, Google OAuth, carpeta y Sheet existentes. **No generar otra clave de cifrado.** No restaurar una base de datos: no hay migración de esquema que deshacer.
5. Si se hubiera ejecutado la limpieza de entorno posterior, recuperar las variables necesarias de su respaldo seguro y del archivo de credenciales. Restablecer únicamente las variables del servicio correspondiente; no duplicar alias. Los flags de escritura antiguos deben mantenerse desactivados hasta una autorización específica de uso de tiendas. Restaurar un secreto del puente solo con una clave coordinada válida, nunca el secreto expuesto.
6. Comprobar service-health, OAuth, sesión, PostgreSQL, Redis, heartbeat del worker, lectura de Drive/Sheet y navegación. No probar generación pagada sin autorización.
7. Revisar productos archivados: el estado usa la columna existente. La versión previa no ofrece restaurarlos; restaurar los productos deseados desde la rama limpia **antes** del rollback si debe conservarse su visibilidad anterior. No eliminar esos registros ni auditorías.
8. Registrar deploys, commit y resultado; mantener desactivado autodeploy hasta cerrar la incidencia.

| Servicio | ID | Deploy funcional observado |
|---|---|---|
| rincon-frontend | srv-db2mlb2j9qps73eob7og | dep-db5go6740ujc73cfjf70 |
| rincon-catalog-api | srv-db2mlqij9qps73eobrg0 | dep-db5hlb8473hc73b749f0 |
| rincon-catalog-worker | srv-db2mlqqj9qps73eobsk0 | dep-db5hm6h42hec7390pou0 |

## Recuperación de código sin alterar producción

```sh
git fetch origin
git switch -c recovery/pre-cleanup origin/backup/pre-integration-cleanup-20261012
git rev-parse HEAD
# Debe imprimir b4aa4051cd2d1b897cc7a582e67ee8b938cfcc2b
```

Para rescatar un único módulo en otra rama, usar `git restore --source=origin/backup/pre-integration-cleanup-20261012 -- ruta/al/archivo`. Revisar sus consumidores y secretos antes de activarlo. No ejecutar force push, migraciones, DROP/TRUNCATE, restauraciones masivas de Sheets ni borrar archivos de Drive.

## Entorno y credenciales

Antes del cambio de entorno posterior al código, guardar un inventario de nombres/orígenes por servicio y un respaldo cifrado con acceso limitado fuera del repositorio. Las credenciales WC/WP todavía no se han movido ni borrado: las referencias existentes del Blueprint original señalan al servicio histórico suite-ecommerce-ia, y su presencia real sigue pendiente de verificación. Ver [ENVIRONMENT_VARIABLES.md](docs/ENVIRONMENT_VARIABLES.md) y [INTEGRATION_REMOVAL_AUDIT.md](docs/INTEGRATION_REMOVAL_AUDIT.md).
