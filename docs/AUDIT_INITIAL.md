# Auditoría inicial: hechos antes de modificar la aplicación

Fecha de inspección: 6 de octubre de 2026. Repositorio: `MisterReto/suite-ecommerce-ia`.
Producción: `41d0599a45dda1edca13b1c253a68524e3567ad2` en
`agent/woocommerce-inventory-foundation`. Base de esta continuación:
`9dc9a09` en `agent/catalog-platform`. `main` está en `7309359` y es más antiguo
que producción. No utilizar `main` como rollback de la migración.

## 1. Arquitectura real

Producción utiliza Gradio montado en FastAPI y módulos Python históricos.
La rama de plataforma ya contiene Next.js/React, FastAPI, SQLAlchemy,
credenciales cifradas, PWA, catálogo independiente y worker. Esta rama no está
desplegada. Se reutiliza, no se inicia otra aplicación.

## 2. Servicios reales de Render

| Servicio | ID | Tipo / plan | Rama / commit live |
| --- | --- | --- | --- |
| suite-ecommerce-ia | srv-d9kc2lvavr4c73am1rug | web Docker / free | agent/woocommerce-inventory-foundation / 41d0599 |
| suite-ecommerce-ia-ai | srv-da3841gae00c73aaour0 | web Docker / free | agent/woocommerce-inventory-foundation / 41d0599 |

Una instancia por servicio, Oregon, contexto `.`, Dockerfile `./Dockerfile`,
sin override Docker y autodespliegue al commit. No hay health check configurado.
No se encontraron PostgreSQL ni Key Value en el workspace `ProyectoInventario`.
La inspección de métricas de RAM no devolvió puntos; no se inventa una medición.
El evento `evt-davf2jou01pc73bohtrg`, 2026-10-01 23:48:31 UTC, sí confirma
`oomKilled` con límite `512Mi` en el segundo servicio. No se consultaron valores
secretos de variables. Sus roles efectivos requieren comprobación operacional.

## 3. Generación actual

Gradio llama a `generar_todas_fotos` / `_rehacer_generico` en `app.py`.
La generación aceptada para la migración vive en `creative_pipeline.py` y
`studio_api.make_image` / `creative_plan`, protegidos contra el commit inmutable
`3ba6a2f9aeb65265a6165ee6c48b7ab273256d7f` por `test_generation_contract.py`.
El catálogo nuevo usa `ImageGenerationService` desde `catalog_platform.worker`.
La captura individual nueva todavía usa `studio_api.start_job`, un executor y
jobs en RAM. El worker nuevo utiliza una cola SQL con leases, no Redis.

## 4. Dependencias críticas

Next.js/React/TypeScript; FastAPI/Pydantic/Uvicorn; Google GenAI; Pillow;
Google OAuth y APIs Drive/Sheets; SQLAlchemy/psycopg; requests/httpx;
cryptography. Las versiones concretas están en `requirements.txt` y
`frontend/package-lock.json`. Las auditorías de dependencias se registran
separadamente de la migración; no se propone un upgrade general.

## 5. Drive verificado, solo lectura

| Recurso | ID |
| --- | --- |
| Proyecto_IA | 1WNDrC4rMfeg066uciiS5VVOYuTvqoAPT |
| imagenes_generadas | 1V4HgnTCRnwVGwrGD968eNdtvQDGGY7wt |
| imagenes_temporales | 1HHe116AZFECvkvqy0bGJsXNKLvfw4bPL |
| inventario_completo | 1gnuDwcceWwN4ksNnyq3Hs_MQHTfnZQZjeLnph72aUrE |
| Respaldo previo existente del 6/oct | 1dUG_xuuIUwGLTMfXl56dGRyJSFc18VlD2EkD5aWjym8 |

Existen `GLIPOC41GX_1_hd.jpg`, `_2_uso.jpg`, `_3_comercial.jpg` y nombres
históricos como `SPTLB680ML_2.png`. La muestra es parcial; no demuestra ausencia
de duplicados en toda la carpeta. No se reorganizan Excel/CSV antiguos.

## 6. inventario_completo

Pestañas observadas: `Lista completa`, `Lista Variable`, `Lista Simple`,
`Media Sync`, `Movimientos Inventario`, `WooCommerce Batch Sync`,
`CSV 1 Productos`, `CSV 2 Variaciones`.

Las tres primeras conservan `sku_padre`, `tipo`, `sku`, `nombre_producto`,
`Marca`, `descripcion_corta`, `descripcion_larga`, `Existencias`, `categorias`,
`etiquetas`, `Web link imagen`, `precio`, `Precio descuento`, `imagenes`.
`Lista completa` tiene además encabezados vacíos y atributos en S/T; estos
espacios no deben desplazarse ni rellenarse automáticamente. `ai_app.py`
adapta el nombre histórico `Gabo nueva` a `Lista completa` en ejecución.
Las lecturas de esta auditoría se limitaron a encabezados y muestras pequeñas.

## 7. WooCommerce / WordPress / POS

Existen `woocommerce_client.py`, `wordpress_media.py`, `ecommerce_services.py`,
publicación revisada, resolución de medios, mappings y webhooks en la rama
nueva. La inspección del código no acredita conexiones reales ni escrituras.
También existe integración histórica Loyverse; su existencia no autoriza
activación, OAuth nuevo o sincronización del stock físico.

## 8. Problemas concretos

- Redis no está provisionado ni integrado.
- La captura individual procesa generación en la API y pierde jobs al reinicio.
- El worker propone nombres y carpeta nuevos; hay que conservar compatibilidad
  y evitar reemplazar originales antes de revisión.
- El lease SQL vence durante llamadas largas si no se renueva mientras trabaja.
- `DriveService.download` carga bytes completos; el worker vuelve a leer el
  JPEG completo para checksum y retiene temporales de varias imágenes.
- `email_allowed` permite cualquier Google verificado si falta allowlist.
- Documentación dispersa en la raíz; faltan mapa de código, pruebas ordenadas
  y clasificación de seguridad completa.
- La rama nueva ya altera el papel de Sheets a importación. Debe mantenerse
  explícita la transición, sin convertir SQL en autoridad por accidente.

## 9. Riesgos

Un push a la rama productiva dispara deploy. Cambiar modelo/prompts altera
calidad; repetir una llamada incierta duplica gasto. Una escritura por nombre
puede reemplazar imágenes o elegir un duplicado. Cambiar columnas puede dañar
el catálogo. No se declara generación real validada con pruebas simuladas.

## 10. Migración incremental

1. Congelar generador aceptado y ejecutar regresiones base.
2. Documentar archivos, endpoints, fuentes y reversión.
3. Añadir RQ/Redis como transporte de IDs; SQL conserva estado/checkpoints.
4. Separar la generación de captura mediante un adaptador, conservando el
   pipeline y el modo anterior para rollback hasta aprobar staging.
5. Probar naming, corrección, errores, recuperación, RAM y límites de costo.
6. Mantener Drive/Sheet originales y escrituras ecommerce bloqueadas.
7. Entregar Blueprint de tres servicios y dos almacenes administrados.
8. Ejecutar el orden de `TEST_PLAN.md` en staging; solo después cambiar la
   entrada de producción. No retirar servicios anteriores durante validación.

Esta auditoría registra el estado inicial. Los cambios y su validación posterior
se documentan en `docs/CHANGE_PLAN.md`, `TEST_PLAN.md` y `SECURITY_AUDIT.md`.
