# Render: observado y propuesto

Inspección de solo lectura: 2026-10-06. Workspace `ProyectoInventario`
(`tea-d9kbmqegekts73cogq3g`). No se crearon servicios ni se cambiaron variables,
planes, ramas, dominios o despliegues.

## Servicios actuales

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

No se encontraron PostgreSQL ni Key Value en este workspace. No se observó
disco configurado en la respuesta de servicios; confirmar el panel antes de
dar por hecho una ausencia absoluta. No hay un background worker independiente.

Se confirmó `oomKilled` en el segundo servicio el 2026-10-01 a las
23:48:31.840779 UTC, evento `evt-davf2jou01pc73bohtrg`, límite 512Mi.
La consulta de métricas no devolvió series RAM; no equivale a consumo cero y
no permite atribuir un pico exacto a una función.

## Propuesta aditiva de esta rama

`deploy/render-platform.yaml` usa nombres nuevos; no reemplaza los dos servicios.

| Recurso | Qué ejecuta | Configuración propuesta |
| --- | --- | --- |
| rincon-frontend | Dockerfile.frontend → node server.js, Next standalone | web free, Oregon, health `/`, sin secretos privados |
| rincon-catalog-api | Dockerfile.api → uvicorn service_entrypoint:fastapi_app, 1 proceso | web free, health `/service-health`, SUITE_SERVE_FRONTEND=false |
| rincon-catalog-worker | Dockerfile.worker → python -m catalog_platform.worker → RQ pool | background worker 1c-2g, concurrency 1, parada 300 s |
| rincon-generation-queue | Key Value compatible Redis | free para staging, noeviction, sin IP públicas permitidas |
| rincon-catalog-db | PostgreSQL administrado | versión 17, 0.1c-256mb, disco 1 GB, sin IP públicas permitidas |

Son **tres servicios de aplicación** y dos almacenes, no cinco aplicaciones ni
un servicio único. Todos apuntan a `agent/stabilize-architecture-20261006`, con
Docker context `.` y autodeploy solo tras checks verdes. Builds: Dockerfiles,
sin comandos personalizados aparte. El frontend necesita SUITE_API_ORIGIN en
build; API y worker reciben DATABASE_URL/REDIS_URL mediante referencias internas.
Las env `sync:false` se completan de forma privada en el panel, no en YAML.

Worker y PostgreSQL tienen coste recurrente. El Blueprint es revisable y válido
según el esquema oficial; no se provisionó ni se aceptó ese gasto en esta etapa.
Free puede dormir en web y Key Value free no tiene persistencia: validar
operación/capacidad y elegir planes operativos antes del cambio de producción.

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
1 proceso; si falta margen, subir RAM del worker antes de aumentar concurrencia.
La propuesta empieza en 2 GB tras el OOM observado a 512 MiB; sigue siendo
**una capacidad a validar**, no una promesa para cualquier tamaño de imagen.
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
