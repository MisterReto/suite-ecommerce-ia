# Suite Ecommerce IA — El Rincón de Asia

Aplicación Next.js/React, FastAPI y Image Worker para capturar productos, analizarlos con Gemini, detectar coincidencias, crear familias, generar imágenes, revisarlas y guardarlas en Google Drive y el catálogo.

La versión actual usa Next.js, FastAPI y el worker existente. Los cargadores
aceptados de WooCommerce y [Loyverse POS](docs/LOYVERSE.md) funcionan de forma
independiente sobre Sheets y Drive. Loyverse permite conexiones personales
cifradas, selección de sucursal y publicación confirmada mediante trabajos.
La sincronización automática de inventario permanece desactivada.

## Entender el proyecto

- [Arquitectura](docs/ARCHITECTURE.md) y [mapa de código](docs/CODE_MAP.md).
- [Generación](docs/IMAGE_GENERATION_FLOW.md) y [credencial personal Gemini](docs/GEMINI_CREDENTIAL_FLOW.md).
- [Variables](docs/ENVIRONMENT_VARIABLES.md), [auditoría](docs/INTEGRATION_REMOVAL_AUDIT.md) y [cambios](docs/CHANGESET.md).
- [Pruebas y pendientes](docs/REGRESSION_RESULTS.md), [acciones manuales](MANUAL_ACTIONS_REQUIRED.md) y [rollback](ROLLBACK.md).

## Ejecutar y comprobar

Usar un entorno de prueba separado. No conectar las pruebas a PostgreSQL, Drive, Sheets o tokens reales de producción. Instalar requirements.txt y frontend/package-lock.json sin cambiar los modelos.

```sh
python -m pip install -r requirements.txt pytest
python -m pytest test_generation_contract.py test_creative_pipeline.py test_studio_api.py test_catalog_capture.py test_capture_workflow.py test_functional_parity.py test_catalog_controls.py test_stabilization.py test_gemini_costs.py test_generation_content.py test_free_render.py test_web_sessions.py test_frontend_separation.py test_catalog_platform.py test_bulk_security.py test_native_tools.py test_integration_removal.py test_stability.py -q
cd frontend
npm ci
npm run typecheck
npm run build
```

Los tests requieren los valores **ficticios** Google que preparan sus fixtures. El contrato de generación requiere el historial completo de Git (fetch-depth: 0 en CI). Las pruebas condicionales de PostgreSQL/Redis usan TEST_DATABASE_URL y TEST_REDIS_URL exclusivos de test.

API: `uvicorn service_entrypoint:fastapi_app --host 0.0.0.0 --port 8000`. Worker de Render: `python -m catalog_platform.worker_web`; necesita PostgreSQL, Redis y la misma clave de cifrado que API. Frontend separado: SUITE_FRONTEND_MODE=standalone y SUITE_API_ORIGIN HTTPS de API al construir.

La propuesta deploy/render-platform.yaml se valida en CI y mantiene autodeploy desactivado. No aplicarla como alta de infraestructura; corresponde a los recursos existentes. No guardar secretos en .env versionados ni NEXT_PUBLIC_*.
