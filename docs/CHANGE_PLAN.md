# Cambios limitados y reversibles

## Redis/RQ y worker

**Problema actual:** cola SQL y generación de captura dentro de la API; no
cumple el aislamiento solicitado. **Por qué cambiar:** aislar RAM y persistir
jobs sin reescribir las funciones de IA. **Archivos afectados:**
`catalog_platform/queue.py`, `database.py`, `api.py`, `worker.py`, nuevo broker
RQ, `studio_api.py` solo en orquestación y Blueprint.
**Riesgo:** entrega duplicada o pérdida de la cola. **Cómo probar:** Redis real,
reenvíos, lease, reinicio, job ya terminado, ausencia de secretos en broker y
contrato AST. **Cómo revertir:** conservar rama/deploy actual; la cola SQL
permanece como registro durable. No repetir jobs con `in_flight` incierto.

## Drive, nombres y memoria

**Problema actual:** el worker agrega nombres que el flujo histórico no conoce
y retiene bytes/temporales. **Por qué cambiar:** conservar nombres finales y
revisión, reducir picos. **Archivos afectados:** adaptador de Drive y worker;
no prompts ni modelo. **Riesgo:** sustituir archivos existentes. **Cómo probar:**
dobles de Drive, nombres canónicos, ningún overwrite previo a aprobación,
checksums por chunks y limpieza de `/tmp`. **Cómo revertir:** resultados nuevos
tienen IDs explícitos; no se modifica la organización histórica.

El guardado de captura también pasa por `DriveService.save_approved` cuando
`STUDIO_IMAGE_JOBS=worker`: antes actualizaba el archivo canónico sin backup.
Se conserva su función, nombre e ID y se añade un respaldo antes de reemplazar;
el modo local histórico no se altera. `test_capture_save_uses_backup_boundary_only_when_separated`
y las regresiones de backup/deduplicación comprueban este límite.

## Sheets y seguridad

**Problema actual:** lecturas y actualizaciones dispersas, alcance OAuth amplio
y allowlist vacía permisiva. **Por qué cambiar:** encapsular operaciones nuevas
y fallar de forma segura en el modo separado. **Archivos afectados:** nuevo
`sheets_service.py`, wrappers y guard de OAuth. **Riesgo:** bloquear acceso
legítimo o confundir una columna. **Cómo probar:** compatibilidad por encabezado,
actualización de una celda, rechazo de SKU duplicado, roles y auth. **Cómo
revertir:** restaurar despliegue y flags; no revocar credenciales ni cambiar
columnas. El Google Sheet sigue siendo fuente operativa durante la transición.

## Criterio de continuación

El pool por job también cambia la vida de los contadores del gateway: dejarían
de verse en la API. `worker.record_usage` conserva deltas numéricos en SQL y
`studio_jobs.recorded_usage` los agrega sin cargar snapshots completos en RAM.
No cambia el gateway protegido ni inventa una factura. La regresión verifica
persistencia fuera de la memoria API; el rollback conserva esa metadata y el
estimado de coste por job. El usuario requiere alojamiento gratuito; la
propuesta usa 512 MB/concurrency 1, pendiente de medir con generación real.

Cada etapa requiere pruebas verdes. Las pruebas con dobles no habilitan
producción. Si la generación real falla en pasos 5–9 de `TEST_PLAN.md`, se
detienen las nuevas integraciones. No se ejecutan migraciones destructivas.
## Aislamiento SQL detectado en CI

**Problema actual:** el primer pase PostgreSQL/Redis ejecutó 31 pruebas, pero
la operación posterior a un fork RQ falló por una consulta preparada duplicada
de psycopg. El hijo heredaba una conexión abierta del padre.
**Por qué cambiar:** cada proceso debe usar su propio socket SQL; compartirlo
puede corromper el protocolo y el estado de las consultas preparadas.
**Archivos afectados:** catalog_platform/database.py, test_stabilization.py y
el health check PostgreSQL de CI.
**Riesgo:** el pool reconectará después de detectar un PID distinto; no altera
tablas, prompts, proveedor ni el pipeline.
**Cómo probar:** job RQ con fork, lectura de su estado y creación posterior
desde el proceso padre; batería completa en PostgreSQL17/Redis7.
**Cómo revertir:** revertir este commit y mantener detenido el worker nuevo
hasta reemplazar el aislamiento de conexiones. No modificar datos.

Se aplica el control connect/checkout por PID de la
[documentación oficial de SQLAlchemy](https://docs.sqlalchemy.org/en/20/core/pooling.html#using-connection-pools-with-multiprocessing-or-os-fork).

## Alojamiento gratuito solicitado

**Problema:** Background Worker y PostgreSQL de pago en el Blueprint contradicen
el presupuesto de cero del usuario. Render permite varios web services gratis,
pero no el tipo Background Worker gratuito. **Cambio:** mantener frontend, API y
proceso de imágenes en tres servicios independientes, todos `web/free`; el
tercero abre solamente un health HTTP liviano y sigue consumiendo RQ. La API
envía una petición HTTP al aceptar trabajo para despertar ese servicio, sin
pings artificiales de mantenimiento. SQL conserva los jobs si Redis se pierde.
**Archivos:** Blueprint, supervisor/arranque HTTP, notificación tras commit,
disponibilidad/estado del worker, interfaz y documentos operativos.
**Riesgos:** arranque en frío, límite compartido de 750 horas, RAM 512 MB y
PostgreSQL gratis con caducidad de 30 días. Este PostgreSQL solo sirve de staging;
Drive/Sheets siguen operativos y no se hace entrada a producción.
**Esquema:** opt-in `INITIALIZE_EMPTY_DATABASE=true` crea tablas únicamente en una
base nueva vacía, con lock PostgreSQL para arranques simultáneos. Una base con
esquema completo se verifica; esquemas ajenos/incompletos se rechazan sin DDL.
**Pruebas:** HTTP del worker sin rutas de generación ni secretos; wake tras
commit, fallo de wake/Redis con job SQL conservado y entrega única; inicialización
vacía/idempotente/rechazo; contrato protegido, PostgreSQL/Redis real y móvil.
**Rollback:** conservar URLs/rama de los dos servicios históricos, detener los
tres nuevos; no borrar SQL ni cambiar claves, prompts, modelos o Sheet.

## Reutilizar configuración privada sin leer sus valores

**Problema:** el navegador protege campos de credenciales y pedir que el usuario
copie múltiples claves sería innecesario. **Cambio:** referencias `fromService`
a variables existentes de `suite-ecommerce-ia`, comprobadas por nombre en Render;
API/worker comparten la clave nueva generada por Render (base64, 256 bits), sin
rotar ninguna clave histórica. Los orígenes públicos se enlazan usando un alias
self-reference de `RENDER_EXTERNAL_URL`; el callback nuevo se configura al
obtener la URL frontend, conservando el registro antiguo de Google.
**Archivos:** Blueprint, CI y documentos de configuración. **Riesgo:** referencias
a variables ausentes o un ciclo no resuelto por el proveedor. **Pruebas:** schema,
validación semántica del Dashboard, Fernet con base64 estándar generado, tres
health HTTP y roles cerrados antes de login. No revelar valores ni cambiar el
entorno de los servicios históricos. **Rollback:** URLs antiguas, conservar
la clave nueva con sus datos cifrados y detener staging.
Fuente: [Blueprint env vars](https://render.com/docs/blueprint-spec#setting-environment-variables).
