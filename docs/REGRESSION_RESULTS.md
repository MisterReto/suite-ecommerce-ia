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

## GitHub Actions completado

Código verificado: `63c1b511f879b1212b770075c8ae47832d47f2e7`.
[Run 38320147296](https://github.com/MisterReto/suite-ecommerce-ia/actions/runs/38320147296), terminado el 2026-10-12 a las 23:11 UTC: **los tres jobs aprobaron**.

| Verificación CI | Resultado |
|---|---|
| Contrato creativo, Python 3.11 y 3.14 | Ambos aprobados contra historial Git real |
| Build / typecheck / npm audit / proxy | Aprobados; npm audit reporta 0 vulnerabilidades conocidas |
| Navegación y OAuth wakeup, Chromium | Aprobados a 360/390/430 px, respuesta perdida e idempotencia |
| Captura, Chromium y WebKit | Ambos aprobados a 360/390/430 px; uploads, ajustes, familia, tres slots, corrección, sonidos, recuperación y reparación |
| pip-audit | Sin vulnerabilidades conocidas reportadas |
| Compilación Python / schema oficial Render / arranque | Aprobados |
| Regresión, primer grupo | 56 passed y 18 subtests passed |
| Regresión, segundo grupo | 131 passed y 4 skipped; skips de PostgreSQL en ese grupo sin TEST_DATABASE_URL |
| PostgreSQL 17 + Redis reales de prueba | **150 passed, sin skips**, incluidos RQ, concurrencia, controles del catálogo y retirada |

Los grupos se solapan: no sumar sus conteos como pruebas distintas. Los contenedores SQL/Redis son exclusivos de CI; no son la base ni el broker de Render. Google/Gemini siguen simulados y no se usaron claves reales ni se gastaron tokens. WebKit automatizado no sustituye la cámara física en iPhone/Android.

## Matriz solicitada

| # | Prueba | Automatizada | Aceptación real / manual |
|---|---|---|---|
| 1 | Google OAuth | PKCE, sesión y permisos simulados | Pendiente login con cuenta autorizada |
| 2 | FastAPI | TestClient, arranque, rutas y health | Pendiente GET del entorno limpio |
| 3 | PostgreSQL | SQLite local y PostgreSQL 17 real de prueba aprobados en CI | Pendiente SELECT seguro en instancia privada |
| 4 | Redis | Outbox/RQ y Redis real de prueba aprobados en CI | Pendiente PING en red privada |
| 5 | API ↔ Image Worker | Contratos y ejecución RQ/concurrencia aprobados en CI | Pendiente heartbeat/ejecución con credenciales reales, sin generación pagada |
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
| 22 | Navegación móvil | Edge local; Chromium/WebKit CI 360/390/430 | Pendiente cámara nativa Android/iOS y Safari |
| 23 | Cero llamadas WooCommerce | Rutas/clientes/dispatch retirados; red externa bloqueada | Pendiente observar logs del entorno limpio |
| 24 | Cero llamadas Loyverse | Rutas/clientes/dispatch retirados; red externa bloqueada | Pendiente observar logs del entorno limpio |

No se probó el contenido de credenciales reales ni se validó un token pagado. La lectura SQL vía conector Render no pudo entrar por la allowlist privada; no se abrió acceso público. La configuración real completa de entorno sigue pendiente: consultar ENVIRONMENT_VARIABLES.md.

## Puerta de despliegue

No merge ni deploy automático. CI del código verificado completó build, schema Render, auditoría de dependencias, proxy/OAuth/móvil, contrato creativo y PostgreSQL/Redis de prueba. Queda realizar la aceptación real de Google/Drive/Sheet y servicios privados, y revisar/archivar el entorno antes del corte. La generación real requiere autorización de gasto independiente.

La limpieza del entorno real se realiza tras verificar el código limpio, con respaldo seguro y sin modificar históricos. El procedimiento de rollback se documenta en ../ROLLBACK.md.
