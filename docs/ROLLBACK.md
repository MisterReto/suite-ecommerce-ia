> Retirada autorizada de Gradio y herramientas nativas: ver [NATIVE_TOOLS](NATIVE_TOOLS.md) para rollback coordinado.

# Rollback por componente

Los controles de eliminación/cancelación del 10 de octubre están documentados
en [CATALOG_CONTROLS.md](CATALOG_CONTROLS.md). Sus estados `deleted`, `cancelling`
y `cancelled` requieren conservar los filtros y finalizar cancelaciones antes
de arrancar una versión anterior. No hay cambio de esquema para esos controles.

No ejecutar DROP, TRUNCATE o borrados masivos. Un rollback de código no deshace
automáticamente Drive, Sheet o WooCommerce. Conservar IDs y backups. Esta
auditoría no creó objetos reales en esas integraciones ni cambió env Render.

## Referencias seguras

Producción histórica: rama `backup/pre-platform-20261006`, commit
`41d0599a45dda1edca13b1c253a68524e3567ad2`; deploys
`dep-db0m3orm8hqs73d8ris0` y `dep-db0m3orm8hqs73d8rj70`.
Base previa de plataforma: `9dc9a09`; generador aceptado protegido: `3ba6a2f...`.
Registrar el primer deploy separado que supere el pase real para futuros
rollbacks frontend/API/worker. Todavía no existe uno validado en esta auditoría.

## Frontend

En Render elegir el servicio nuevo → Deploys → último deploy validado → Rollback
(o Manual Deploy del commit exacto conservado). Restaurar también SUITE_API_ORIGIN
de ese build y recompilar si cambió. En un fallo de la primera activación,
dirigir al usuario a https://suite-ecommerce-ia.onrender.com. No borrar resultados
SQL nuevos por volver a la interfaz histórica. No usar main como equivalente.

## API

Pausar nuevas solicitudes pagadas y elegir el deploy API validado compatible
con el esquema. Conservar SQL y las conexiones cifradas. Si se vuelve a la
plataforma anterior 9dc9a09, su cola SQL puede leer trabajos ya compatibles,
pero desconoce tipos nuevos studio_generation/asset_save: no arrancar su worker
sobre esos jobs. El modo local es solo contingencia y vuelve a usar RAM API;
no es un rollback que mantenga el aislamiento de tres servicios.

Para una primera migración fallida, usar API/frontend históricos juntos y
dejar los nuevos detenidos o en lectura para investigar. Restaurar origin,
callback y puentes sync de la configuración previa. La sesión puede exigir login.

## Worker

Detener el worker nuevo antes de iniciar una versión anterior: no mezclar dos
consumidores con protocolos distintos. Conservar job ID, payload, completed_keys,
IDs Drive e in_flight. Un deploy del worker se revierte independientemente de
frontend/API, siempre que soporte los tipos de job y modelo confirmados.

Con lease vencido sin llamada en vuelo, el reconciliador reentrega desde checkpoint.
Con `in_flight`, el job pasa a failed/resultado incierto y requiere revisión.
No cambiar simplemente failed→queued ni volver a enviar todo el lote. Consultar
Drive/proveedor/tienda antes de autorizar retry individual. No repetir éxitos.

## Redis

Detener nuevas entregas y consumidores para investigar. No ejecutar FLUSHALL
como rollback. Redis es transporte; SQL conserva el registro. Después de
recuperar conexión, el supervisor reentrega jobs queued y deduplica ID RQ.
Una cola perdida no justifica repetir llamadas processing/inciertas. Un job
que RQ marcó finished puede haber fallado en SQL: SQL es el estado de negocio.

## PostgreSQL

Respaldar base actual y exportar fichas/resultados creados desde la migración.
La nueva columna batch_id y tabla de lotes pueden permanecer al revertir código;
son aditivas. No se necesita borrarlas para el rollback ordinario.

Para recuperación de corrupción, restaurar el dump validado **en una base nueva**
privada con `pg_restore --no-owner --dbname` apuntando a esa conexión, verificar
tablas/filas/checksums y conexiones cifradas con la misma clave Fernet, y cambiar
DATABASE_URL de API/worker durante mantenimiento. Un dump anterior omite jobs
posteriores: conciliar sus IDs Drive y no regenerarlos automáticamente. Evitar
`--clean` sobre la base viva. No afirmar restauración completa sin ese ensayo.

## Variables Render

Se proponen nuevas REDIS_URL, GENERATION_QUEUE_BACKEND, STUDIO_IMAGE_JOBS,
IMAGE_WORKER_CONCURRENCY, timeout, límites de lote/coste y APP_REQUIRE_ALLOWLIST.
La plataforma separada necesita SUITE_SERVE_FRONTEND, APP_PUBLIC_ORIGIN,
SUITE_API_ORIGIN y CREDENTIAL_ENCRYPTION_KEY, además de conexiones vigentes.
Registrar nombres/flags/orígenes previos; no incluir valores secretos en Git.
Restaurar flags con código compatible y conservar la clave Fernet. El callback
Google antiguo no se elimina durante staging; no revocar credenciales actuales.

## Google Drive

Durante esta auditoría: cero archivos creados, modificados, movidos o borrados.
En un futuro pase: registrar IDs de TEST-INTEGRATION, carpeta por job, raws,
referencias y backups; conservar candidatos antes de limpiar una prueba.

Si se reemplazó un canónico aprobado, encontrar backup
`<old_file_id>_before_<asset_id>.jpg`, comparar metadata/checksum y restaurar
su contenido en el ID original de forma controlada. No eliminar carpetas enteras
por nombre. Productos reales nunca se limpian como objetos de prueba.

## Google Sheets

Durante esta auditoría: ningún rango/columna modificado. En pruebas futuras,
registrar pestaña y A1 exacto con before/after. Restaurar solo esa celda/fila de
prueba después de comprobar que no hubo otra edición. El backup existente es
`1dUG_xuuIUwGLTMfXl56dGRyJSFc18VlD2EkD5aWjym8`; restaurar todo el Sheet desde
esa copia perdería operaciones posteriores y requiere conciliación explícita.

## WordPress / WooCommerce

Durante esta auditoría: ningún producto, pedido, stock o media modificado.
Para pruebas futuras conservar product_id, variation_id y media_ids. Consultar
por ID antes de eliminar un TEST-INTEGRATION draft/media y comprobar que no
está usado en otra ficha. Restituir stock inicial con operación identificada,
registrar movimiento compensatorio y volver a leer. Si hubo un timeout, descubrir
el objeto creado antes de reenviar. No limpiar productos por un prefijo ambiguo
ni revertir inventario sin comparar su estado actual.
