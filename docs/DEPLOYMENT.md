# Activar sin reemplazar producción de golpe

Estado: propuesta en rama; Render actual sigue en 41d0599. No hubo migraciones
reales ni cambio de tráfico. El Blueprint está en `deploy/render-platform.yaml`.
Seguir [TEST_PLAN](../TEST_PLAN.md); CI verde no sustituye las pruebas reales.

## 1. Preparar referencias y backups

Conservar `backup/pre-platform-20261006`, el commit live y los deploy IDs
registrados en RENDER_SERVICES. Mantener el contrato IA en `3ba6a2f...` y no
usar el `main` antiguo como rollback. Registrar env names/flags de servicios
actuales en un registro privado sin exportar valores secretos al repositorio.

Hay backup de Sheet previo documentado en DRIVE_AND_SHEETS; verificar acceso
antes de escribir. Si SQL ya tiene datos, ejecutar:

```bash
python -m catalog_platform.backup
pg_restore --list /ruta/privada/al/respaldo.dump
```

El dump en `/tmp` debe transferirse a almacenamiento privado durable y probarse
en otra base. Conservar la clave Fernet aparte. No iniciar una migración porque
simplemente existe un archivo dump sin comprobar su restauración.

## 2. Provisionar staging aditivo

Crear mediante el Blueprint los tres nombres nuevos, PG y Key Value. Revisar
que **todos los recursos sean free** antes de confirmar creación. No añadir
tarjeta, aceptar pagos ni cambiar las
ramas ni Dockerfiles de los dos servicios existentes. Key Value noeviction,
sin acceso público abierto; PG conexión interna en Oregon.

Los orígenes se enlazan directamente por
`RENDER_EXTERNAL_URL` de cada servicio. Google/tienda se reutilizan mediante
`fromService` del servicio histórico; sus valores no se leen ni se copian al chat.
Render genera la nueva Fernet base64 de 256 bits en API y worker la referencia.
Completar roles/correos `sync:false` en privado; allowlist permanece cerrada.
`GOOGLE_REDIRECT_BASE` deriva el callback frontend `/auth/callback` al arrancar,
si no existe un GOOGLE_REDIRECT_URI explícito. Añadir ese callback a Google Console
conservando el callback antiguo. Esto reutiliza cliente/secret existentes;
no requiere rotar claves por iniciativa de la migración.

API y worker: misma DATABASE_URL, REDIS_URL, clave Fernet, carpeta, roles y
modelos vigentes. API usa main, no sirve frontend y no genera imágenes localmente.
Worker usa rq, concurrency 1, runtime sync y Dockerfile.worker con override
`python -m catalog_platform.worker_web`. `IMAGE_WORKER_ORIGIN` referencia el
origen HTTPS público del worker; no URL privada (free web no recibe tráfico
privado) ni credenciales en ese origen. No añadir
Redis/Google/tienda al entorno Next; solo origen API público.

Los flags WC_WRITE_ENABLED y WP_MEDIA_WRITE_ENABLED siguen false. Mantener
Loyverse sin configurar. Si se requieren herramientas históricas, conservar
SYNC_SERVICE_URL al servicio viejo durante el periodo de validación.

## 3. Preparar esquema, arranque y lectura

La base **nueva y vacía** del Blueprint usa `INITIALIZE_EMPTY_DATABASE=true` en
API/worker: crea el esquema con lock PostgreSQL, sin importar el Sheet. En
reinicios solo verifica un esquema completo. Si hay otras tablas o un esquema
incompleto, rechaza el arranque sin hacer DDL. Desactivar este flag después de
preparar staging. No activar este opt-in en una base existente de producción.

Para una base que ya existe, preparar backup y migrar explícitamente desde una
terminal privada autorizada; el shell/pre-deploy de Render no está disponible
en web free:

```bash
python -m catalog_platform.migrate
```

La migración de datos existentes es aditiva y manual. Verificar
tablas, GenerationBatch y batch_id nullable. No importar el Sheet al arrancar.
Comprobar health frontend/API y heartbeat worker/Redis desde el status autenticado.
Los health web no deben depender de que el proveedor IA esté disponible.
Probar wake desde dormido: aceptar job en SQL aunque el heartbeat esté vencido,
esperar arranque en frío, comprobar una sola entrega y consumo. El status separa
`worker_ready` real de `worker_can_queue`; no declarar ejecutándose un job queued.
Sin trabajo pendiente, consultar status no manda tráfico al worker.

Registrar la caducidad de PostgreSQL free a 30 días, exportar cualquier dato de
pruebas antes de esa fecha y mantener Drive/Sheets como fuente operativa. No
cambiar la entrada a producción con una base que va a caducar. Las 750 horas
mensuales se comparten con los dos servicios históricos; no usar keepalive.

Validar login, roles, móvil, Drive lectura y Sheet lectura. La estructura de
Drive debe ser exactamente la documentada. Hasta aquí no generar ni escribir.

## 4. Pase real de generación y estabilidad

Pasos 5–9 de TEST_PLAN: producto limpio, lifestyle, comercial, regeneración y
corrección. Usar referencias conocidas y SKU TEST-INTEGRATION; revisar tamaño,
formato, fidelidad, nombre, Drive IDs, raw, modelo y estado SQL. Confirmar que
el endpoint responde con job queued mientras IA corre únicamente en worker.
Si alguno falla, DETENER nuevas integraciones y conservar producción antigua.

Después, escritura Drive controlada, lote 2–3 y lote ~10. Medir memoria real
del pool completo, no solo RSS de un hijo; validar el límite gratis de 512 MB.
Si no cabe, detener el pase y optimizar dentro del presupuesto, sin upgrade.
Reiniciar worker
y comprobar frontend/API disponibles, checkpoints conservados y ninguna
llamada incierta repetida. Reiniciar API, volver a login y recuperar resultados.

## 5. Ecommerce y entrada de producción

Solo tras generación: Media de prueba, Woo lectura, producto draft de prueba,
webhook y stock reversible. Habilitar flags en staging durante ese pase; luego
restablecerlos si no se aprueba uso operativo. No integrar Loyverse por completar
la cola de imágenes. Registrar IDs, before/after y limpieza.

Cambiar la entrada pública solo después de validar todos los pasos aplicables.
Conservar servicios anteriores y sus callbacks hasta cerrar el periodo de
rollback. SQL no es aún fuente exclusiva: documentar qué operaciones siguen
escribiendo Sheet y cómo reconciliar nuevas fichas. No retirar sync histórico
si todavía existen herramientas delegadas hacia él.

## Desarrollo local reproducible

Python 3.11 y Node 22 según Docker/CI. Los comandos siguientes presuponen
variables exportadas y PG/Redis de pruebas, nunca conexiones de producción:

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt pytest
cd frontend
npm ci
npm run build
```

Desde la raíz, en procesos separados:

```bash
.venv/bin/python -m catalog_platform.migrate
.venv/bin/uvicorn service_entrypoint:fastapi_app --host 0.0.0.0 --port 7860
```

```bash
GENERATION_QUEUE_BACKEND=rq STUDIO_IMAGE_JOBS=worker SUITE_SERVICE_ROLE=sync SUITE_DRIVE_ONLY=false .venv/bin/python -m catalog_platform.worker
```

El Next separado requiere upstream HTTPS y callback público HTTPS; para pruebas
locales de proxy, `test_frontend_proxy.cjs` crea un backend TLS y Next real.
No relajar validación de URL, cookies o CSRF para simular producción.
