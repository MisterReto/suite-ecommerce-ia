# Rollback de esta restauración

Base: `405f423fd79419700346c743eb90005e6bbbab82`, rama previa
`agent/stabilize-architecture-20261006`. Auditoría inicial aislada: `ef1b756`.
Los deploys anteriores y los IDs de servicio están registrados en
`docs/FUNCTIONAL_PARITY_AUDIT.md`. No usar main como referencia equivalente.

| Componente staging | Servicio | Deploy anterior observado |
|---|---|---|
| Frontend | `srv-db2mlb2j9qps73eob7og` | `dep-db2mrmbrjlhs73fl00fg` |
| FastAPI | `srv-db2mlqij9qps73eobrg0` | `dep-db3hfpd9fdbs73dqqgf0` |
| Image worker | `srv-db2mlqqj9qps73eobsk0` | `dep-db2rgh2d0e5s73e5jru0` |

Ante fallo de captura, credencial, variantes, análisis o generación, detener
promoción. Registrar job/SKU/revisión y si hay una llamada o escritura en vuelo.
Pausar solo nuevas solicitudes de staging; no lanzar automáticamente otro job
para compensar una respuesta incierta. En Render restaurar el deploy anterior
del componente afectado; si depende de la nueva API, restaurar frontend y API
coherentemente. El worker conserva el protocolo de jobs y pipeline existentes.

Si se actualizó la rama staging, revertir el commit de restauración mediante
un nuevo commit sobre esa rama; no reescribir commits de otro colaborador.
Aplicar despliegue después de CI y comprobar salud y navegación. Los dos servicios
históricos permanecen fuera de este cambio, en `41d0599` y su rama histórica.

No hay migración de esquema que revertir. Mantener IntegrationAccount/SyncEvent
y sus filas cifradas nuevas; volver al código previo no requiere borrar claves,
borradores ni relaciones. Conservar `CREDENTIAL_ENCRYPTION_KEY`, PostgreSQL,
Redis y las variables anteriores. No rotar el cifrado como paso de rollback.

Un rollback de código no deshace el Sheet ni Drive. Verificar productos aceptados
antes de repetir guardado; conservar portadas, originales, IDs y metadata para
reparación. No ejecutar DROP/TRUNCATE ni borrar en masa. La variante/padre SQL
se confirma o revierte completa dentro de su propia transacción.

El código previo admite un fallback Gemini global; por eso restaurarlo cambia
el comportamiento de credenciales. Antes de reabrir generación, comprobar
explícitamente la fuente usada. No presentar ese fallback como configuración
personal persistente. Detalles de arquitectura: `docs/ROLLBACK.md`.
