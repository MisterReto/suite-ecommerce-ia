# Render: producción conservada y staging gratuito

Estado verificado: 2026-10-06. Workspace `ProyectoInventario`
(`tea-d9kbmqegekts73cogq3g`). Se crearon cinco recursos nuevos, todos `free`,
mediante el Blueprint `rincon-staging-20261006`
(`exs-db2m0g1srm7s73bv129g`). No se añadió tarjeta ni se contrataron planes
pagados. Los dos servicios históricos conservaron su rama, configuración y
despliegue. No se cambió la entrada de producción.

## Servicios históricos conservados

| Dato | suite-ecommerce-ia | suite-ecommerce-ia-ai |
| --- | --- | --- |
| ID | srv-d9kc2lvavr4c73am1rug | srv-da3841gae00c73aaour0 |
| URL | https://suite-ecommerce-ia.onrender.com | https://suite-ecommerce-ia-ai.onrender.com |
| Tipo/runtime | web / Docker | web / Docker |
| Plan/región/instancias | free / Oregon / 1 | free / Oregon / 1 |
| Rama | agent/woocommerce-inventory-foundation | agent/woocommerce-inventory-foundation |
| Commit live | 41d0599a45dda1edca13b1c253a68524e3567ad2 | mismo |
| Deploy live | dep-db0m3orm8hqs73d8ris0 | dep-db0m3orm8hqs73d8rj70 |
| rootDir/context | vacío / `.` | vacío / `.` |
| Dockerfile | ./Dockerfile | ./Dockerfile |
| Build/start override | no observado; Docker build/CMD del archivo | igual |
| Auto deploy | commit habilitado | commit habilitado |
| Health path | no configurado | no configurado |

El código histórico tiene roles main/sync, pero el conector no expone todos los
valores de entorno de esos servicios. No se asigna al segundo un rol efectivo
sin inspeccionar su configuración real. Conservar el CMD del Dockerfile del
commit live como referencia, no el del archivo modificado en otra rama.

En la inspección inicial no había PostgreSQL ni Key Value en este workspace.
Ahora existen los dos recursos de staging registrados abajo. No se observó
disco configurado en los servicios históricos. No se creó un Background Worker
de pago: el proceso RQ nuevo se aloja como web free.

Se confirmó `oomKilled` en el segundo servicio el 2026-10-01 a las
23:48:31.840779 UTC, evento `evt-davf2jou01pc73bohtrg`, límite 512Mi.
La consulta de métricas no devolvió series RAM; no equivale a consumo cero y
no permite atribuir un pico exacto a una función.

## Staging aditivo desplegado

`deploy/render-platform.yaml` usa nombres nuevos; no reemplaza los dos servicios.

| Recurso | Qué ejecuta | Configuración desplegada |
| --- | --- | --- |
| rincon-frontend | Dockerfile.frontend → node server.js, Next standalone | web free, Oregon, health `/`, sin secretos privados |
| rincon-catalog-api | Dockerfile.api → uvicorn service_entrypoint:fastapi_app, 1 proceso | web free, health `/service-health`, SUITE_SERVE_FRONTEND=false |
| rincon-catalog-worker | Dockerfile.worker + override python -m catalog_platform.worker_web → health + RQ pool | web free, 512 MB, concurrency 1, health `/service-health`; plazo de parada predeterminado |
| rincon-generation-queue | Key Value compatible Redis | free para staging, noeviction, sin IP públicas permitidas |
| rincon-catalog-db | PostgreSQL administrado | versión 17, free, 1 GB, sin IP públicas permitidas; caduca a los 30 días |

| Recurso | ID | URL / estado observado |
| --- | --- | --- |
| rincon-frontend | srv-db2mlb2j9qps73eob7og | https://rincon-frontend.onrender.com/ · live |
| rincon-catalog-api | srv-db2mlqij9qps73eobrg0 | https://rincon-catalog-api.onrender.com · live |
| rincon-catalog-worker | srv-db2mlqqj9qps73eobsk0 | https://rincon-catalog-worker.onrender.com · live |
| rincon-catalog-db | dpg-db2mlb2j9qps73eob7u0-a | available · PostgreSQL 17 |
| rincon-generation-queue | red-db2mlb2j9qps73eob7hg | available · Valkey 8, persistencia off |

Los tres deploys live observados ejecutan
`df88da8c0ea664ecf456868492f5a8cdd897c7ee`: frontend
`dep-db2mlqqj9qps73eobsm0`, API `dep-db2mmhqj9qps73eod90g`, worker
`dep-db2mlr2j9qps73eobtb0`. Los checks de ese commit están verdes.
El panel muestra Deployed para las tres apps y Available para los almacenes.
La interfaz abre y muestra la conexión Google cuando no hay sesión; todavía
no se verificó login real, generación ni acceso efectivo a Drive/Sheets.

**Vencimiento exacto de PostgreSQL:** `2026-11-05T21:39:57.500361Z`.
Mantenerlo como pruebas; no trasladar la autoridad del inventario a esta base.
El acceso administrativo de la app sigue sin configurar: la revisión automática
rechazó la asignación propuesta por faltar autorización explícita del correo,
rol y alcance. La allowlist permanece vacía y cerrada. Render sigue conectado;
el bloqueo corresponde al permiso en la app de staging.

Son **tres servicios de aplicación** y dos almacenes, no cinco aplicaciones ni
un servicio único. Todos apuntan a `agent/stabilize-architecture-20261006`, con
Docker context `.` y autodeploy solo tras checks verdes. Builds: Dockerfiles,
sin comandos personalizados aparte. El frontend necesita SUITE_API_ORIGIN en
build; API y worker reciben DATABASE_URL/REDIS_URL mediante referencias internas.
Los orígenes públicos se enlazan mediante referencias directas a
`RENDER_EXTERNAL_URL`; no se usan hosts privados para recibir tráfico web free.
Las claves Google/tienda se referencian dentro de Render desde el servicio
histórico, sin leer valores ni modificarlo. Render genera la clave Fernet nueva
en API y worker la comparte por referencia. Las env `sync:false` restantes
(roles/correos/límite de coste) se completan en privado tras autorizar el acceso.
El callback que debe registrarse/verificarse en el cliente Google existente es
`https://rincon-frontend.onrender.com/auth/callback`, conservando el antiguo.

El presupuesto solicitado es **cero para alojamiento**: todos los recursos
declaran `plan: free`. No registrar tarjeta ni aceptar upgrades. Render admite
varios web services free, pero su tipo Background Worker no tiene plan gratis;
por eso el proceso de imágenes se publica como web con un health mínimo.
`IMAGE_WORKER_ORIGIN` en la API apunta al origen HTTPS público de ese servicio.
Una operación aceptada despierta el worker con HTTP, sin enviar credenciales o
datos del producto. No hay pings para mantener servicios sin trabajo.

Límites oficiales: web se duerme tras 15 minutos sin tráfico, arranque en frío
aproximadamente un minuto, 750 horas mensuales compartidas por workspace y
512 MB por servicio. Cinco web services siempre activos excederían ese cupo;
los dos históricos permanecen intactos durante staging. Key Value free pierde
su cola al reiniciarse; SQL la reconstruye. PostgreSQL free **caduca a los 30
días**, sin backup administrado: registrar fecha de caducidad, exportar datos
de pruebas a tiempo y no convertirlo en fuente exclusiva de inventario.
Una base PostgreSQL externa gratuita y persistente puede conectarse después,
cuando exista una conexión autorizada; no crear cuentas ajenas automáticamente.
Fuente: [Render Free](https://render.com/docs/free).

La revisión del Dashboard rechazó `maxShutdownDelaySeconds` por no estar
disponible en free. Se omite ese override; no asumir 300 segundos para terminar
un job. El SIGTERM conserva checkpoints y las llamadas inciertas requieren revisión.

## Aislamiento y RAM

La API no ejecuta llamadas de imagen en `/api/generate` cuando
`STUDIO_IMAGE_JOBS=worker`. Es requisito del Blueprint; no confundirlo con el
modo local compatible. SQL conserva jobs/checkpoints y Redis transporta IDs.
El worker descarga sus archivos, genera, sube y elimina su `/tmp`. No comparte
disco con API o frontend; un Persistent Disk no sirve como comunicación entre ellos.

Auditoría de código: streaming de descargas y checksums, limpieza por imagen,
procesos hijos RQ por job, concurrencia explícita, threads numéricos limitados.
El pipeline aceptado todavía necesita imágenes en PIL/base64 para el proveedor;
no se reescribió esa parte. Los ejemplos de estilo y originales necesarios
permanecen durante el job. Eso exige medir generación real, no extrapolar RAM
de un proveedor simulado.

Registrar RSS de inicio/pico por job (`Worker: pico RSS`), métricas Render,
memoria del pool completo, temporales y duración para pasos 5–12. Empezar con
1 proceso. El plan gratis tiene 512 MB: si falta margen, detener el pase y
reducir memoria/tamaño del lote sin cambiar el pipeline protegido. No subir
a un plan pagado automáticamente. Sigue siendo **una capacidad a validar**,
no una promesa para cualquier tamaño de imagen. Un trabajo largo puede
interrumpirse al dormir; los leases/checkpoints no autorizan repetir una
llamada IA de resultado incierto.
El worker debe poder reiniciarse mientras ambos health web siguen respondiendo.

## Configuración a comprobar antes de activar

Roles/allowlist, callback OAuth en dominio frontend, raíz/Sheet exactos, clave
Fernet común, modelo actual sin overrides nuevos, límites de coste, flags de
escritura en false y sin secretos Next. Las herramientas históricas pueden
seguir usando `SYNC_SERVICE_URL` al servicio existente durante la transición;
los jobs nuevos usan servicios Python en worker. No retirar el antiguo sync
hasta probar también esas herramientas o migrarlas explícitamente.

Ver [ENVIRONMENT_VARIABLES](ENVIRONMENT_VARIABLES.md), [DEPLOYMENT](DEPLOYMENT.md)
y [MANUAL_ACTIONS_REQUIRED](../MANUAL_ACTIONS_REQUIRED.md).
