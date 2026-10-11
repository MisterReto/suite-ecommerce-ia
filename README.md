# Suite Ecommerce IA · El Rincón de Asia

Interfaz unificada **Next.js / React + FastAPI**. La generación
creativa aceptada se encapsula en `ImageGenerationService` y se protege con un
contrato AST y pruebas de generación, correcciones y almacenamiento. No se
cambian automáticamente proveedor, modelo, prompts ni referencias.

## Estado y activación

- Interfaz móvil con Inicio, Productos, Generar, Inventario y Más; PWA instalable.
- Catálogo PostgreSQL, roles, auditoría, importación con respaldo y exportación.
- Redis/RQ transporta IDs; PostgreSQL conserva estado, leases, checkpoints y
  recuperación si cae el broker. Un job por producto, concurrencia configurable.
- WordPress / WooCommerce reutilizan sus clientes existentes y IDs permanentes.
- Loyverse preparado como contrato; nuevas escrituras/webhooks permanecen inactivos.
- Si falta PostgreSQL, la captura compatible sigue disponible. No se aceptan lotes
  durables sin PostgreSQL y un worker configurado; en free, un worker dormido
  recibe una petición de arranque después de guardar el job. Se distingue
  disponibilidad de cola de heartbeat activo. Esta modalidad conserva Drive/Sheets
  durante la transición; no equivale a completar la migración.

[Auditoría inicial real](docs/AUDIT_INITIAL.md) · [Flujo protegido](docs/IMAGE_GENERATION_FLOW.md)
· [Despliegue y validación](docs/platform-rollout.md) · [Backups](docs/backups.md)

## Entender y controlar la aplicación

Empieza por la [guía del código y de reparación](docs/CODE_GUIDE.md) y el
[índice de funciones y objetos](docs/FUNCTION_INDEX.md): indican qué archivo
revisar según el fallo y qué reglas conservar al modificarlo.

[Arquitectura](docs/ARCHITECTURE.md) · [Mapa del código](docs/CODE_MAP.md) · [Solicitudes paso a paso](docs/REQUEST_FLOWS.md) · [Generación](docs/IMAGE_GENERATION_FLOW.md) · [Glosario](docs/GLOSSARY.md)

[Modelo de datos](docs/DATA_MODEL.md) · [Drive/Sheets](docs/DRIVE_AND_SHEETS.md) · [WooCommerce](docs/WOOCOMMERCE.md) · [Loyverse futuro](docs/LOYVERSE_FUTURE.md) · [Render](docs/RENDER_SERVICES.md) · [Variables](docs/ENVIRONMENT_VARIABLES.md)

[Despliegue](DEPLOYMENT.md) · [Recuperación](ROLLBACK.md) · [Estado de seguridad](SECURITY_AUDIT.md) · [Pendientes operativos](MANUAL_ACTIONS_REQUIRED.md)

[Plan obligatorio de pruebas](TEST_PLAN.md) · [Evidencia y límites](docs/VERIFICATION.md)

Los dos dominios históricos redirigen al frontend; su ejecutor de sincronización
conserva solo la API interna firmada. Ver [herramientas integradas y retirada de
Gradio](docs/NATIVE_TOOLS.md). La app utiliza `rincon-frontend`, `rincon-catalog-api`
y `rincon-catalog-worker`, con sesión durable, WooCommerce y controles de
eliminar/cancelar en `feature/woocommerce-and-product-removal-20261009`.
La unificación de navegación parte de `a7869dc` y conserva el generador protegido.
Las pruebas automáticas usan datos sintéticos; el pase manual con escrituras se
realiza por separado.

El Blueprint configura los tres servicios separados gratuitos sin modificar los
dos históricos. El Dockerfile compatible conserva el modo exportado. Los
documentos iniciales del 6 de octubre mantienen su contexto histórico: para
sesiones, clasificación, WooCommerce y controles actuales consultar la nueva
guía y los documentos específicos enlazados desde ella. Ver IDs/URLs y evidencia
en [Render](docs/RENDER_SERVICES.md) y [controles](docs/CATALOG_CONTROLS.md).

Para ejecutar la protección del generador, conservar el historial git del commit aceptado; CI hace checkout con `fetch-depth: 0`.

## Desarrollo

Python 3.11 y Node 22.

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt pytest
cd frontend
npm ci
npm run build
```

Configura las variables servidor de `.env.example` en tu entorno. La app no lee
un archivo `.env` automáticamente y no contiene secretos predeterminados.

```bash
.venv/bin/python -m catalog_platform.migrate
.venv/bin/uvicorn service_entrypoint:fastapi_app --host 0.0.0.0 --port 7860
```

En otro proceso con las mismas conexiones cifradas y configuración de tienda:

```bash
GENERATION_QUEUE_BACKEND=rq STUDIO_IMAGE_JOBS=worker SUITE_SERVICE_ROLE=sync SUITE_DRIVE_ONLY=false .venv/bin/python -m catalog_platform.worker
```

`catalog_platform.migrate` solo crea el esquema inicial aditivo; no sustituye una
migración versionada ni un respaldo para cambios de esquema futuros. No ejecuta
DDL al iniciar el servidor web por defecto. El Blueprint nuevo habilita
`INITIALIZE_EMPTY_DATABASE=true` únicamente para la BD vacía de staging:
crea tablas con lock, verifica reinicios y rechaza esquemas ajenos/incompletos
sin aplicar cambios. No habilitarlo para migrar datos existentes.

## Pruebas

Los grupos de pruebas de herramientas sync cargan un runtime ligero sintético y
se ejecutan en procesos separados para evitar contaminación de módulos:

```bash
.venv/bin/python -m unittest test_store_connection test_stability test_sync_changes test_generation_content test_catalog_capture test_variation_stock -q
.venv/bin/python -m unittest test_split_services test_parent_full -q
.venv/bin/python -m unittest test_bulk_security test_inventory_unified -q
.venv/bin/python -m pytest test_gemini_costs.py test_capture_workflow.py test_loyverse.py test_loyverse_jobs.py -q
.venv/bin/python -m pytest test_studio_api.py test_creative_pipeline.py test_generation_contract.py test_catalog_platform.py -q
node test_loyverse_ui.js
```

La CI usa PostgreSQL real para comprobar adquisiciones concurrentes con
`SKIP LOCKED` y solicitudes HTTP duplicadas. Las pruebas locales sin
`TEST_DATABASE_URL` usan SQLite exclusivamente como doble de persistencia y
omiten esas dos pruebas de concurrencia. Las APIs de IA/Drive/tienda se sustituyen
por dobles en regresión: no hay gasto ni modificaciones en producción.

`test_stabilization.py` usa Redis real cuando se exporta `TEST_REDIS_URL` de una
instancia dedicada: entrega idempotente, fallo del broker, captura/corrección,
recuperación y aprobación, naming, backup y límites. Nunca apuntar tests a las
conexiones operativas. `test_frontend_mobile.cjs` requiere Playwright y build
standalone: verifica menús/cards/formularios a 360/390/430 px, desktop, conexión
y reutilización de request_key al perder una respuesta; utiliza API sintética.
