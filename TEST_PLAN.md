# Plan obligatorio de validación

Fecha: 2026-10-06. No alterar producción. CI/dobles prueban comportamiento;
el siguiente pase valida conexiones reales en staging. Las escrituras/pagos
reales **no se ejecutaron**. Si falla generación en 5–9: DETENER; no continuar
nuevas integraciones. Registrar evidencia antes de considerar un paso aprobado.

## Orden del pase real

| Paso | Prueba / criterio | Escritura / reversión | Estado actual |
| --- | --- | --- | --- |
| 1 | Frontend básico: login, móvil 360–430 px, cinco rutas, cards, formularios/roles | staging; sin modificar producción | automatización local; login Google real pendiente |
| 2 | FastAPI: health, 401/403, DB lectura, errores; worker caído no tumba API | BD prueba, sin DDL implícito | regresiones locales; staging pendiente |
| 3 | Drive SOLO LECTURA: raíz/carpetas/imágenes, IDs/listado | cero write/move/delete | conector verificado; conexión staging pendiente |
| 4 | inventario_completo SOLO LECTURA: pestañas/headers, buscar SKU, posiciones | ninguna columna/rango modificado | metadata/muestras verificadas; staging pendiente |
| 5 | Una imagen limpia con referencias conocidas: SKU TEST-INTEGRATION, mismo modelo, HTTP queued/worker ejecuta | candidato aislado; registrar ID,size,MIME,dimensiones,checksum | dobles pasan; Gemini real pendiente |
| 6 | Lifestyle: identidad/ref/brief conservados y producto correcto | candidato prueba; original intacto | regresión pasa; real pendiente |
| 7 | Comercial: investigación/reglas/marca/naming originales | candidato prueba, revisión humana | regresión pasa; real pendiente |
| 8 | Regeneración: nuevo candidato con originales y anterior conservado | job individual, coste mostrado | regresión pasa; real pendiente |
| 9 | Corrección: feedback/raw/brief, sin doble marca; error conserva anterior | nuevo job, éxitos no repetidos | regresión pasa; real pendiente |
| 10 | Drive ESCRITURA controlada: aprobada a destino de prueba, backup antes de reemplazo/readback | IDs TEST-INTEGRATION; restaurar backup de prueba | dobles pasan; real pendiente |
| 11 | Lote 2–3: job por producto, estados independientes/error controlado | registros prueba, sin publicación | regresión lote/Redis pasa; real pendiente |
| 12 | Lote ~10: memoria pool/temporales, restart API/worker, coste/idempotencia | revisar inciertos; no repetir todo | infraestructura real pendiente |
| 13 | WordPress Media: un JPEG prueba, ID/URL/alt/metadata | borrar solo medio prueba sin uso | real pendiente |
| 14 | WooCommerce LECTURA: producto/variación por mapping + SKU | cero escrituras | dobles pasan; real pendiente |
| 15 | WooCommerce ESCRITURA: un draft TEST-INTEGRATION con media | flags controlados; eliminar objeto identificado | real pendiente |
| 16 | WooCommerce WEBHOOK: firma/evento durable/duplicado, respuesta rápida | pedido/producto prueba; un efecto | dobles pasan; real pendiente |
| 17 | Loyverse LECTURA FUTURA: items/variants/store/inventory | solo cuenta autorizada | no configurado; no forzar |
| 18 | Loyverse ESCRITURA FUTURA: artículo prueba/eventos verificados | restaurar/limpiar solo IDs prueba | no autorizado/configurado |
| 19 | Stock: SKU prueba, before/acción/expected/final/restauración | compensación/readback; no doble descuento | Woo dobles; real/POS pendiente |
| 20 | Producción: pasos aplicables validados, monitor/rollback | cambiar entrada conservando antiguos | NO activado |

17–18 son futuros si no hay POS; no habilitar una API sin autorización por
completar la lista. Generación es obligatoria antes de cualquier ampliación.

## Datos reversibles

Usar TEST-INTEGRATION-* para SKU/nombres y carpeta de prueba autorizada.
Primero leer originales. Una raíz compatible de prueba se prepara después de
4 copiando fuentes, sin mover originales, y registrando IDs. Conservar modelo,
prompts y referencias de estilo. 5–9 suben candidatos/raw/referencias por job;
10 valida guardado final, no supone que generar no produzca archivos Drive.

Stock: registrar inicial app/tienda, ID evento, acción, esperado, final y valor
restaurado. Si ya existe diferencia, detener/conciliar; no ajustar un producto
real solo para hacer pasar el test. Media/objetos Woo se limpian exclusivamente
por IDs registrados de prueba y después de comprobar que no están usados.

## Registro por prueba

Fecha/operador, rama/commit, servicio/deploy, tenant, SKU/UUID, job/batch,
modelo/proveedor, coste estimado/observado, IDs/nombres Drive, tamaño/MIME,
dimensiones/checksum, tabla/rango afectado y resultado. Añadir before/after,
cleanup/rollback y readback. Nunca tokens, cookies completas ni Authorization.
Un pendiente no es passed porque la UI se vea bien.

## Regresión reproducible

CI: .github/workflows/validate-drive-client.yml. Mantiene grupos históricos
en procesos separados porque algunos cargan un runtime sintético.

```bash
python -m unittest test_store_connection test_stability test_sync_changes test_generation_content test_catalog_capture test_variation_stock -q
python -m unittest test_split_services test_parent_full -q
python -m unittest test_bulk_security test_inventory_unified -q
python -m pytest test_gemini_costs.py test_capture_workflow.py test_loyverse.py test_loyverse_jobs.py -q
python -m pytest test_studio_api.py test_creative_pipeline.py test_generation_contract.py test_catalog_platform.py test_frontend_separation.py -q
```

Exportar privadamente TEST_DATABASE_URL/TEST_REDIS_URL de **almacenes dedicados**,
nunca producción, y ejecutar:

```bash
python -m pytest test_catalog_platform.py test_stabilization.py -q
```

CI crea PG17 y Redis7 efímeros. Sin TEST_DATABASE_URL usa SQLite doble y omite
dos pruebas de concurrencia: no anunciar PG validado por ellas. Sin TEST_REDIS_URL
omite los tests RQ real. No se usa Gemini/Google/tienda real en esos tests.

Frontend: npm ci/audit, export build/typecheck y standalone build; luego
`node test_frontend_proxy.cjs` usa TLS local para rutas/cookies/callback/upload
12 MB. Los tests PWA impiden cachear APIs/fotos privadas. `node test_loyverse_ui.js`
conserva recuperación de respuesta perdida. pip-audit revisa requirements;
Blueprint pasa esquema oficial de Render.

test_generation_contract compara AST con 3ba6a2f; conservar historial git y
fetch-depth 0. Validar formato/dimensiones/tamaño/relación/naming/estado/guardado;
no comparar píxeles exactos de una imagen aleatoria.

## Aceptación

Rama revisable con tests verdes todavía no equivale a producción validada.
Falta pase real IA completo, Drive/Sheet intactos, RAM aislada, Woo/Media prueba,
roles/logs/móvil y rollback ensayado. Registrar evidencia/pendientes en
docs/VERIFICATION.md y MANUAL_ACTIONS_REQUIRED; no ocultarlos bajo “terminado”.
