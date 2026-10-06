# Suite Ecommerce IA · El Rincón de Asia

Migración incremental de Gradio a **Next.js / React + FastAPI**. La generación
creativa aceptada se encapsula en `ImageGenerationService` y se protege con un
contrato AST y pruebas de generación, correcciones y almacenamiento. No se
cambian automáticamente proveedor, modelo, prompts ni referencias.

## Estado y activación

- Interfaz móvil con Inicio, Productos, Generar, Inventario y Más; PWA instalable.
- Catálogo PostgreSQL, roles, auditoría, importación con respaldo y exportación.
- Cola PostgreSQL con leases y checkpoints, worker independiente del navegador.
- WordPress / WooCommerce reutilizan sus clientes existentes y IDs permanentes.
- Loyverse preparado como contrato; nuevas escrituras/webhooks permanecen inactivos.
- Si falta PostgreSQL, la captura compatible sigue disponible. No se aceptan lotes
  durables sin un worker activo. Esta modalidad conserva el flujo de Drive/Sheets
  durante la transición; no equivale a completar la migración.

[Auditoría](ARCHITECTURE_AUDIT.md) · [Flujo protegido](docs/current-image-generation-flow.md)
· [Despliegue y validación](docs/platform-rollout.md) · [Backups](docs/backups.md)

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
SUITE_SERVICE_ROLE=sync SUITE_DRIVE_ONLY=false .venv/bin/python -m catalog_platform.worker
```

`catalog_platform.migrate` solo crea el esquema inicial aditivo; no sustituye una
migración versionada ni un respaldo para cambios de esquema futuros. No ejecuta
DDL al iniciar el servidor web.

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
