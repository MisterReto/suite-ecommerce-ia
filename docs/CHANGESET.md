# Archivos de la limpieza

Base real: `b4aa4051cd2d1b897cc7a582e67ee8b938cfcc2b`. Rama: `cleanup/remove-store-integrations-20261012`.

147 archivos: 7 añadidos, 80 modificados y 60 eliminados. Se conserva el historial Git y el árbol original de imágenes/iconos; no hay borrado de datos externos.

Módulos creativos, prompts/modelos y `catalog_platform/models.py` conservados idénticos a la base. Las funciones compartidas Drive/Sheet se extraen, no se eliminan.

| Archivo | Acción |
|---|---|
| `.dockerignore` | Modificado |
| `.env.example` | Modificado |
| `.github/workflows/validate-drive-client.yml` | Modificado |
| `.gitignore` | Modificado |
| `ai_app.py` | Modificado |
| `app_security.py` | Modificado |
| `ARCHITECTURE.md` | Modificado |
| `batch_web_v2.py` | Eliminado de la rama activa |
| `batch_web.py` | Eliminado de la rama activa |
| `bulk_product_upload.py` | Eliminado de la rama activa |
| `catalog_platform/accounts.py` | Modificado |
| `catalog_platform/api.py` | Modificado |
| `catalog_platform/capture_bridge.py` | Modificado |
| `catalog_platform/catalog.py` | Modificado |
| `catalog_platform/ecommerce.py` | Eliminado de la rama activa |
| `catalog_platform/imports.py` | Modificado |
| `catalog_platform/inventory.py` | Eliminado de la rama activa |
| `catalog_platform/job_types.py` | Añadido |
| `catalog_platform/rbac.py` | Modificado |
| `catalog_platform/webhooks.py` | Eliminado de la rama activa |
| `catalog_platform/worker.py` | Modificado |
| `DATA_MODEL.md` | Modificado |
| `deploy/render-platform.yaml` | Modificado |
| `DEPLOYMENT.md` | Modificado |
| `docs/ARCHITECTURE.md` | Modificado |
| `docs/AUDIT_INITIAL.md` | Modificado |
| `docs/AUTH_AND_DRIVE_REGRESSION_REVIEW.md` | Modificado |
| `docs/BARCODE_SKU_AND_SOUNDS.md` | Modificado |
| `docs/CAPTURE_WORKFLOW.md` | Modificado |
| `docs/CATALOG_CONTROLS.md` | Modificado |
| `docs/CHANGE_PLAN.md` | Modificado |
| `docs/CHANGESET.md` | Añadido |
| `docs/CODE_GUIDE.md` | Modificado |
| `docs/CODE_MAP.md` | Modificado |
| `docs/current-image-generation-flow.md` | Modificado |
| `docs/DATA_MODEL.md` | Modificado |
| `docs/DEPLOYMENT.md` | Modificado |
| `docs/DRIVE_AND_SHEETS.md` | Modificado |
| `docs/ENVIRONMENT_VARIABLES.md` | Modificado |
| `docs/FUNCTION_INDEX.md` | Modificado |
| `docs/FUNCTIONAL_PARITY_AUDIT.md` | Modificado |
| `docs/GLOSSARY.md` | Modificado |
| `docs/IMAGE_GENERATION_FLOW.md` | Modificado |
| `docs/INTEGRATION_REMOVAL_AUDIT.md` | Añadido |
| `docs/LOYVERSE_FUTURE.md` | Eliminado de la rama activa |
| `docs/NATIVE_TOOLS.md` | Modificado |
| `docs/platform-rollout.md` | Modificado |
| `docs/PRODUCT_FAMILY_AND_VARIANTS.md` | Modificado |
| `docs/REGRESSION_RESULTS.md` | Añadido |
| `docs/RENDER_SERVICES.md` | Modificado |
| `docs/REQUEST_FLOWS.md` | Modificado |
| `docs/ROLLBACK.md` | Modificado |
| `docs/VERIFICATION.md` | Modificado |
| `docs/WOOCOMMERCE.md` | Eliminado de la rama activa |
| `DRIVE_AND_SHEETS.md` | Modificado |
| `drive_image_index.py` | Añadido |
| `ecommerce_services.py` | Eliminado de la rama activa |
| `ENVIRONMENT_VARIABLES.md` | Modificado |
| `frontend/app/page.tsx` | Modificado |
| `frontend/components/CaptureStudio.tsx` | Modificado |
| `frontend/components/InventoryTools.tsx` | Modificado |
| `frontend/next.config.ts` | Modificado |
| `GEMINI_CONSUMO.md` | Modificado |
| `GLOSSARY.md` | Modificado |
| `gradio_security.py` | Eliminado de la rama activa |
| `GUIA_ENTREGA_CLIENTE.md` | Modificado |
| `IMAGE_GENERATION_FLOW.md` | Modificado |
| `INTEGRACION_LOYVERSE.md` | Eliminado de la rama activa |
| `INTEGRACION_WOOCOMMERCE.md` | Eliminado de la rama activa |
| `inventory_bulk.py` | Modificado |
| `inventory_hub.py` | Eliminado de la rama activa |
| `inventory_operations.py` | Modificado |
| `inventory_web.py` | Eliminado de la rama activa |
| `loyverse_client.py` | Eliminado de la rama activa |
| `loyverse_jobs.py` | Eliminado de la rama activa |
| `loyverse_sync.py` | Eliminado de la rama activa |
| `loyverse_web.py` | Eliminado de la rama activa |
| `MANUAL_ACTIONS_REQUIRED.md` | Modificado |
| `media_web.py` | Eliminado de la rama activa |
| `native_tools.py` | Modificado |
| `pos_provider.py` | Eliminado de la rama activa |
| `product_web_ai.py` | Eliminado de la rama activa |
| `product_web.py` | Eliminado de la rama activa |
| `publication_web.py` | Eliminado de la rama activa |
| `README.md` | Modificado |
| `RENDER_SERVICES.md` | Modificado |
| `RENDER_SERVICIOS.md` | Modificado |
| `REQUEST_FLOWS.md` | Modificado |
| `requirements-sync.txt` | Eliminado de la rama activa |
| `retired_service.py` | Modificado |
| `ROLLBACK.md` | Modificado |
| `SECURITY_AUDIT.md` | Modificado |
| `SEGURIDAD.md` | Modificado |
| `server.py` | Eliminado de la rama activa |
| `service_entrypoint.py` | Modificado |
| `sheet_inventory.py` | Añadido |
| `single_product_auto.py` | Eliminado de la rama activa |
| `static/accessibility.js` | Eliminado de la rama activa |
| `static/generation-sounds.js` | Eliminado de la rama activa |
| `static/inventory.css` | Eliminado de la rama activa |
| `static/inventory.js` | Eliminado de la rama activa |
| `static/loyverse.html` | Eliminado de la rama activa |
| `static/loyverse.js` | Eliminado de la rama activa |
| `static/tutorial.css` | Eliminado de la rama activa |
| `static/tutorial.js` | Eliminado de la rama activa |
| `static/ui.css` | Eliminado de la rama activa |
| `store_connection.py` | Eliminado de la rama activa |
| `studio_api.py` | Modificado |
| `sync_bridge_protocol.py` | Eliminado de la rama activa |
| `sync_gateway.py` | Eliminado de la rama activa |
| `sync_lite_app.py` | Eliminado de la rama activa |
| `sync_service.py` | Eliminado de la rama activa |
| `test_bulk_security.py` | Modificado |
| `test_capture_mobile.cjs` | Modificado |
| `test_capture_workflow.py` | Modificado |
| `test_catalog_controls.py` | Modificado |
| `test_catalog_platform.py` | Modificado |
| `test_frontend_mobile.cjs` | Modificado |
| `test_frontend_proxy.cjs` | Modificado |
| `test_functional_parity.py` | Modificado |
| `test_gemini_costs.py` | Modificado |
| `test_integration_removal.py` | Añadido |
| `test_inventory_unified.py` | Eliminado de la rama activa |
| `test_loyverse_jobs.py` | Eliminado de la rama activa |
| `test_loyverse_ui.js` | Eliminado de la rama activa |
| `test_loyverse.py` | Eliminado de la rama activa |
| `test_native_tools.py` | Modificado |
| `test_parent_full.py` | Eliminado de la rama activa |
| `TEST_PLAN.md` | Modificado |
| `test_split_services.py` | Eliminado de la rama activa |
| `test_stability.py` | Modificado |
| `test_stabilization.py` | Modificado |
| `test_store_connection.py` | Eliminado de la rama activa |
| `test_studio_api.py` | Modificado |
| `test_sync_changes.py` | Eliminado de la rama activa |
| `test_variation_stock.py` | Eliminado de la rama activa |
| `woo_to_sheets_colab.py` | Eliminado de la rama activa |
| `woocommerce_batch_sync.py` | Eliminado de la rama activa |
| `woocommerce_catalog_light.py` | Eliminado de la rama activa |
| `woocommerce_client.py` | Eliminado de la rama activa |
| `woocommerce_image_sync.py` | Eliminado de la rama activa |
| `woocommerce_inventory.py` | Eliminado de la rama activa |
| `woocommerce_media_prepare.py` | Eliminado de la rama activa |
| `woocommerce_product_sync.py` | Eliminado de la rama activa |
| `woocommerce_publish_preview.py` | Eliminado de la rama activa |
| `woocommerce_stock.py` | Eliminado de la rama activa |
| `wordpress_media.py` | Eliminado de la rama activa |
