# Resultados de regresión

Fecha: 2026-10-12. Rama: cleanup/remove-store-integrations-20261012. Base: b4aa4051cd2d1b897cc7a582e67ee8b938cfcc2b. Esta entrega no está desplegada.

## Ejecutado localmente

| Verificación | Resultado / alcance |
|---|---|
| Pytest, 18 archivos, incluida retirada | **222 passed, 11 skipped, 18 subtests passed**; 1 warning; 29.56 s |
| TypeScript | tsc --noEmit, aprobado |
| Build Next.js standalone | Aprobado; página principal, not-found y connect-google |
| Navegación móvil real, servicios simulados | Chromium/Edge: 360, 390 y 430 px; escritorio 1280; menús, conteos confirmados, cancelación, eliminación, idempotencia y ausencia de controles externos |
| Captura móvil real, servicios simulados | 360/390/430 px: foto, edición, ajustes, familia, slots, corrección, sonidos, pérdida de respuesta, recuperación y reparación |
| Proxy Next.js real | Aprobado: cookies, PKCE/callback, cuerpos DELETE/cancel y upload de 12 MB, backend HTTPS local |
| Schema oficial Render | Blueprint aprobado con jsonschema y schema oficial; no aplicado |
| Links/documentación y whitespace | Sin enlaces locales rotos; diff --check aprobado |
| Sonidos de generación | Prueba Node aprobada |
| Contrato creativo | Funciones creativas comparadas contra fuente GitHub inmutable aceptada; modelos/prompts conservados |
| Archive/restore | Pruebas de familia, stock, imágenes, histórico, versión incorrecta y jobs activos aprobadas |
| Aislamiento de integraciones | Rutas externas 404, retry de job retirado 410, rechazo del worker antes de credenciales y SQL histórico preservado |
| Dependencias | requirements.txt y package-lock existentes conservados; clientes usan librerías compartidas aún necesarias |
| Render real | Metadata/deploys live de cinco servicios y disponibilidad declarada de PostgreSQL/Redis verificados; no equivale a SQL/PING/heartbeat funcional |

La suite usa dobles de Google/Gemini y una conexión de prueba local. Un guard de socket permite solo loopback; no llama a Gemini/WooCommerce/Loyverse reales. En Windows, el runner adapta únicamente las rutas /tmp de las pruebas a un temporal local y obtiene las funciones congeladas desde el commit real de GitHub; no cambia producción. Los 11 skips son casos condicionados a PostgreSQL/Redis reales o plataforma local. CI usa Ubuntu, PostgreSQL 17 y Redis de prueba, sin credenciales de producción.

## Matriz solicitada

| # | Prueba | Automatizada | Aceptación real / manual |
|---|---|---|---|
| 1 | Google OAuth | PKCE, sesión y permisos simulados | Pendiente login con cuenta autorizada |
| 2 | FastAPI | TestClient, arranque, rutas y health | Pendiente GET del entorno limpio |
| 3 | PostgreSQL | SQLite de prueba y contratos SQL; CI configurado para PG17 | Pendiente SELECT seguro en instancia privada |
| 4 | Redis | Outbox/RQ con dobles; CI configurado con Redis | Pendiente PING en red privada |
| 5 | API ↔ Image Worker | Contratos encolado/actor/heartbeat/checkpoints | Pendiente heartbeat/ejecución con credenciales reales, sin generación pagada |
| 6 | Leer imágenes Drive | DriveService y naming simulados | Pendiente leer una imagen existente |
| 7 | Leer inventario_completo | Lectura y límites de Sheet simulados | Pendiente lectura de Lista completa sin escritura |
| 8 | Crear producto simple | Aprobada | Pendiente en entorno de aceptación |
| 9 | Crear producto variable | Aprobada | Pendiente en entorno de aceptación |
| 10 | Crear variante | Aprobada | Pendiente en entorno de aceptación |
| 11 | Analizar foto con Gemini | Proveedor simulado, coste/clave aislados | Pendiente autorización de consumo real |
| 12 | Buscar similares | Local + Sheet simulado | Pendiente con catálogo existente |
| 13 | Portada del padre | Pipeline/familia simulados | Pendiente autorización de consumo real |
| 14 | Producto limpio | Slot HD simulado + contrato congelado | Pendiente autorización de consumo real |
| 15 | Lifestyle | Slot/brief simulado + contrato congelado | Pendiente autorización de consumo real |
| 16 | Comercial | Slot/brief simulado + contrato congelado | Pendiente autorización de consumo real |
| 17 | Regenerar | Historial, checkpoint, idempotencia simulados | Pendiente autorización de consumo real |
| 18 | Corrección | Feedback/raw/revisión simulados | Pendiente autorización de consumo real |
| 19 | Guardar en Drive | Naming, backup, versión y duplicados simulados | Pendiente guardado aprobado en carpeta autorizada |
| 20 | Consultar/editar inventario local | Stock SQL y conteos/movimientos Sheet simulados | Pendiente aceptación de ajuste puntual |
| 21 | Archivar/restaurar | Aprobada sin borrar stock/Drive/historial | Pendiente aceptación de familia en UI |
| 22 | Navegación móvil | Edge real 360/390/430 | Pendiente cámara nativa Android/iOS y Safari |
| 23 | Cero llamadas WooCommerce | Rutas/clientes/dispatch retirados; red externa bloqueada | Pendiente observar logs del entorno limpio |
| 24 | Cero llamadas Loyverse | Rutas/clientes/dispatch retirados; red externa bloqueada | Pendiente observar logs del entorno limpio |

No se probó el contenido de credenciales reales ni se validó un token pagado. La lectura SQL vía conector Render no pudo entrar por la allowlist privada; no se abrió acceso público. La configuración real completa de entorno sigue pendiente: consultar ENVIRONMENT_VARIABLES.md.

## Puerta de despliegue

No merge ni deploy automático. GitHub Actions debe completar build, schema Render, auditoría de dependencias, proxy/OAuth/móvil, matriz del contrato creativo y regresión con PostgreSQL/Redis de prueba. Después realizar la aceptación real de Google/Drive/Sheet y comunicar cualquier pendiente. La generación real requiere autorización de gasto independiente.

La limpieza del entorno real se realiza tras verificar el código limpio, con respaldo seguro y sin modificar históricos. El procedimiento de rollback se documenta en ../ROLLBACK.md.
