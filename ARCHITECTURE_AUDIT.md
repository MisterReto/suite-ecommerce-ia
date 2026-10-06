# Auditoría previa a la migración de plataforma

Fecha: 2026-10-06. Base verificada: `41d0599a45dda1edca13b1c253a68524e3567ad2`.
Producción: rama `agent/woocommerce-inventory-foundation`, no `main`.
Los cambios de la migración permanecen separados de esa rama mientras se validan.

## Sistema que se conserva

| Parte | Implementación desplegada | Dependencias relevantes |
| --- | --- | --- |
| Captura y generación | `app.py`, interfaz Gradio montada en FastAPI | Gemini, Pillow, OAuth Google |
| Adaptación de catálogo | `ai_app.py`, `catalog_capture.py`, `product_capture.py` | Google Sheets, pandas, códigos de barras |
| Generación de imágenes | `investigar_prompts`, `generar_foto_individual`, `_rehacer_generico` | `gemini_gateway.py`, `product_generation.py` |
| Ecommerce | `product_web.py`, `batch_web_v2.py`, `woocommerce_*` | WooCommerce REST, WordPress REST |
| Inventario | `inventory_schema.py`, `inventory_operations.py`, `inventory_hub.py` | pestaña `Lista completa` y registros de movimientos |
| POS existente | `loyverse_client.py`, `loyverse_sync.py`, `loyverse_jobs.py` | token temporal, comparación y confirmación explícita |
| Seguridad | `oauth_guard.py`, `app_security.py`, aislamiento de archivos | PKCE, state de un uso, origen de solicitudes, cookies HttpOnly |

No se encontró en esta base una cola durable de generación IA para múltiples
productos. Sí existe generación secuencial de las tres vistas de un producto y
publicación masiva de productos/imágenes ya guardados en WooCommerce. No deben
confundirse esos dos flujos. La cola nueva envolverá el generador existente.

## Render: inspección de solo lectura

| Servicio | Tipo/plan | Rol | Arranque |
| --- | --- | --- | --- |
| `suite-ecommerce-ia` | web Docker / free / una instancia / Oregon | principal | `service_entrypoint:fastapi_app` |
| `suite-ecommerce-ia-ai` | web Docker / free / una instancia / Oregon | sync WooCommerce | mismo entrypoint, `SUITE_SERVICE_ROLE=sync` |

Los dos usan `./Dockerfile`, contexto `.`, sin override de comando Docker y
autodespliegue al cambiar la rama de producción. La última publicación del
principal corresponde al commit base y figura `live`.

No existen instancias PostgreSQL ni Key Value en el workspace inspeccionado.
No se observó un disco persistente en los detalles de estos servicios. No se
obtuvieron ni se imprimieron valores secretos. La integración disponible permite
actualizar variables, pero no inventariar sus valores; su presencia efectiva se
debe validar al arrancar sin exponerlos. Los archivos `/tmp` y las sesiones actuales
son efímeros. No son almacenamiento durable ni una cola apta para recuperación.

El filtro de logs de aplicación por Error/Traceback/memory devolvió un traceback
histórico del worker, no evidencia suficiente para afirmar que no hay otros fallos.
No se cambió infraestructura durante esta auditoría.

## Drive y mapa de dependencias

Estructura inspeccionada: `Proyecto_IA/`, con `inventario_completo`,
`imagenes_generadas/` y logo opcional. Se verificaron imágenes históricas
`SPLKK410ML_3.png`, `SAGRKK326G_3.png` y `GLIPOC41GX_3_comercial.jpg`.
Las primeras muestran anuncios artísticos; la última es una fotografía neutra.
Estas referencias sustentan la dirección artística ya preparada; se conserva tal
cual por la aclaración posterior del usuario.

| Archivo/pestaña | Consume | Escribe | Función actual |
| --- | --- | --- | --- |
| `inventario_completo` / `Lista completa` | captura, inventario, publicación y POS | guardar producto, conteos y movimientos | fuente operativa actual |
| archivo Excel/CSV/ODS histórico | importador | conversión a hoja nativa, conservando original | intercambio y respaldo |
| `imagenes_generadas/` | vista previa, resolución de medios y publicación | solo al confirmar guardado | resultados históricos y activos |
| `<SKU>_1_hd.jpg`, `_2_uso.jpg`, `_3_comercial.jpg` | media sync | guardado confirmado | nombres canónicos que se mantienen |
| `<SKU>_1.png`, `_2.png`, `_3.png` | resolutor compatible | no requiere renombrar | resultados históricos |
| `logo_rincon_asia.png` | composición de marca | no se modifica | logo opcional; respaldo oficial en `static/` |
| `Media Sync` | sincronización WordPress | IDs y URLs después de subir | evita duplicar medios |
| `WooCommerce Batch Sync` | publicación por lotes | progreso y reanudación | bitácora operativa existente |

No se movieron, renombraron ni borraron archivos. La estructura futura se crea
solo para archivos nuevos y respaldos; los IDs históricos permanecen válidos.

## Generación: congelación y validación

El detalle está en `docs/current-image-generation-flow.md`. Antes de conectar el
generador se compararán por AST las funciones críticas contra el commit base.
La aclaración del usuario protege la generación implementada con su primer prompt:
`creative_pipeline.py` y `studio_api.make_image`, incluyendo personas, publicidad
artística y edición con imagen anterior. No se cambiarán sus modelos, prompts,
referencias, naming ni política de llamadas por introducir el catálogo y la PWA.

La validación simulada comprueba archivos, formato, dimensiones, asociación a
producto/job y guardado. No demuestra calidad ni disponibilidad real de Gemini.
Una generación real requiere la clave de la cuenta autorizada y su cuota; no se
afirmará que pasó si no se ejecutó.

## Datos y migración incremental

Actualmente no hay catálogo maestro SQL. El nuevo catálogo tendrá IDs internos,
mappings externos permanentes, movimientos, jobs, eventos, cuentas cifradas y
auditoría. Sheets/Excel permanecen como importación/exportación y respaldo.
La importación inicial será explícita, idempotente por origen y con respaldo
previo; no se vaciará ninguna fuente ni se publicará automáticamente.

Se mantendrá un interruptor de activación: sin PostgreSQL y worker preparados,
el despliegue estable seguirá funcionando. Ningún endpoint nuevo debe aceptar
un lote que no pueda persistir y recuperar.

## Cola: decisión y alternativas

Para el volumen inicial, una cola en PostgreSQL con `FOR UPDATE SKIP LOCKED`,
leases, checkpoints por imagen y un worker dedicado evita agregar Redis además
de la base ya necesaria. Las peticiones solo validan y encolan. El worker inicia
una imagen a la vez, guarda su resultado en Drive y su relación en SQL.

| Opción | Ventaja | Coste operativo adicional |
| --- | --- | --- |
| RQ + Render Key Value | simple, ampliamente usado | broker durable y worker además de PostgreSQL |
| Celery + Key Value | enrutamiento y tareas complejas | mayor configuración y recuperación |
| Dramatiq + Key Value | middleware y workers ligeros | también requiere broker independiente |
| cola PostgreSQL | catálogo y jobs en la misma transacción | implementar y probar lease/checkpoint explícitos |

Un timeout de IA o de publicación no se reintenta automáticamente: se registra
el resultado incierto y se exige revisión. Cerrar el navegador no cancela el
worker. En un despliegue, SIGTERM detiene nuevas adquisiciones; la operación
iniciada termina o queda incierta, sin duplicar un gasto automáticamente.

## Riesgos y condiciones de activación

- Crear una base y un worker puede tener coste; no están presentes hoy.
- La cola durable necesita credenciales servidor cifradas para continuar sin la
  sesión del navegador. No se persisten claves en texto claro ni se copian al worker por URL.
- No se revoca ni reduce OAuth durante la migración si impide leer archivos
  existentes. La cuenta de servicio/carpetas compartidas es una transición separada.
- La autoridad inicial de stock es la app/WooCommerce según origen registrado;
  POS permanece deshabilitado hasta conectar y definir Loyverse como autoridad física.
- Mantener las herramientas ecommerce actuales mientras la capa de servicios
  nueva obtiene equivalencia verificable. No sustituirlas por datos ficticios.
- No declarar la actualización completa hasta validar generación real,
  publicación autorizada, medios y recuperación en Render.

## Actualización de esta continuación

La arquitectura de tres servicios y su mapa de código están en [ARCHITECTURE.md](ARCHITECTURE.md). `Dockerfile.frontend`, `Dockerfile.api` y el worker hacen explícita la separación. Se conserva el despliegue compatible para recuperar el servicio anterior.

El contrato AST compara directamente con `3ba6a2f9aeb65265a6165ee6c48b7ab273256d7f`; no se modificaron funciones ni prompts protegidos. Se añadieron regresiones de proxy y validación del origen público.

Consultar [SECURITY_AUDIT.md](SECURITY_AUDIT.md) para distinguir evidencia de CI, configuración pendiente y auditoría formal todavía no ejecutada. La documentación no implica que los nuevos servicios estén activos.
