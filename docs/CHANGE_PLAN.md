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
estimado de coste por job. La propuesta inicia worker en 2 GB/concurrency 1,
con capacidad/coste pendientes de validación real.

Cada etapa requiere pruebas verdes. Las pruebas con dobles no habilitan
producción. Si la generación real falla en pasos 5–9 de `TEST_PLAN.md`, se
detienen las nuevas integraciones. No se ejecutan migraciones destructivas.
