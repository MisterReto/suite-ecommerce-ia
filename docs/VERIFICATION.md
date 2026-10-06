# Evidencia, alcance y pendientes

Fecha: 2026-10-06. Rama agent/stabilize-architecture-20261006, base 9dc9a09.
Producción histórica sigue en 41d0599. No hubo deploy, generación pagada,
escritura Drive/Sheet/Media/Woo ni creación de infraestructura.

## Comprobaciones locales

Python 3.12.14, Node 24, venv dedicado. Regresión base ejecutada antes de modificar
orquestación: 35 passed, 2 skipped, después del build export. AST del generador
aceptado contra 3ba6a2f. Nuevos cambios no alteran las funciones protegidas.

| Comprobación | Resultado observado |
| --- | --- |
| Histórico unittest: tienda/estabilidad/sync/captura/variantes | 35 passed |
| Histórico unittest: separación/padres | 9 passed |
| Histórico unittest: seguridad bulk/inventario | 24 passed |
| Pytest consumo/captura/Loyverse/jobs históricos | 63 passed |
| Pytest studio/creatividad/contrato/catálogo/separación | 35 passed, 2 concurrencia PG omitidas localmente |
| Nuevas regresiones | 17 passed con Redis/RQ real y dobles IA/Drive |
| Next export y standalone | builds correctos y TypeScript sin errores |
| Proxy HTTP Next real + TLS local | rutas/cookies/OAuth y 12 MB completos correctos |
| UI Loyverse histórica, Node | progreso y respuesta perdida correctos |
| Blueprint | pasa jsonschema oficial, tres servicios app + PG/Redis, históricos preservados |
| pip-audit requirements / npm audit producción | cero vulnerabilidades conocidas en ejecución |
| Secretos en archivos/historial accesible | cero patrones de token/private key; 208 commits; sin .env real versionado |

Las 17 regresiones nuevas cubren IDs sin secretos en Redis, no IA en HTTP,
entrega única, caída del broker, rollback SQL, batch por producto, coste/retry,
captura/corrección/recovery/approval/save, worker RQ fork, naming, regeneración
sin perder anterior, allowlist, proveedor no habilitado, contadores durables,
Sheets por celda/duplicados incluso tras huecos, backup/idempotencia, temporales
parciales, captura compatible, límite de frecuencia y llamada incierta no repetida.

Total de grupos locales: 183 passed, 2 skipped. El último grupo combinado
(17 nuevas + 35 existentes) pasó 52 tests y omitió los dos de PostgreSQL real.
Pico RSS del proceso de esa batería sintética: 219892 KiB; no es una medición
del pipeline Gemini real ni de todos los procesos del worker en Render.

Advertencias de tests: adaptación futura httpx/Starlette y fork en un test cuyo
proceso pytest ya tiene threads. La configuración productiva inicia el pool en
otro proceso y carga el pipeline en cada job. No actualizar todas las dependencias
para silenciar warnings en esta migración.

## CI y navegador

CI reproduce la batería con Python 3.11, contrato también 3.14, PostgreSQL17,
Redis7, builds/proxy y navegador Chrome con Playwright. Las dos pruebas de
SKIP LOCKED/HTTP concurrente requieren esa BD real; SQLite no las demuestra.

El entorno local no pudo iniciar Chrome (SIGSEGV incluso en --version) y el
bundle de navegador Playwright no estuvo disponible. Por ello no se declara
un pase móvil local. El [primer CI](https://github.com/MisterReto/suite-ecommerce-ia/actions/runs/37494585645)
sí pasó con Chrome real: 360/390/430 px, cinco menús, cards/formulario,
1280 px, conexión y reutilización de request_key tras perder respuesta.
También pasaron builds/proxy, auditorías de dependencias, Blueprint y contrato
del generador en Python 3.11/3.14. Son datos API sintéticos; no prueban login
Google real ni fidelidad de una foto Gemini.

Ese primer run **falló** en PostgreSQL: 31 passed, 1 failed después de un fork
RQ, por consultas preparadas psycopg heredadas. Se corrigió el pool SQL con
comprobación de PID al obtener una conexión y se amplió la regresión para
crear un producto desde el padre después del job hijo. No se ocultó la prueba
ni se deshabilitaron consultas preparadas. Ver docs/CHANGE_PLAN.md.

La repetición sobre `b50ca516` terminó con los tres jobs verdes en el
[run 37495343135](https://github.com/MisterReto/suite-ecommerce-ia/actions/runs/37495343135):
32 pruebas PostgreSQL17/Redis7 sin omisiones y móvil real correcto. Los cambios
posteriores para alojamiento gratuito requieren su propio CI en
[PR #26 → Checks](https://github.com/MisterReto/suite-ecommerce-ia/pull/26/checks).
Exigir validate y ambos generation-contract verdes antes de desplegar; los
dos casos PostgreSQL deben ejecutarse en ese grupo, sin omisiones. La evidencia
operativa de IA/Drive/Woo sigue separada y pendiente aunque CI esté verde.

## Adaptación a alojamiento gratuito

Blueprint validado con el schema oficial: los tres servicios app son web/free,
PG/Key Value también free; sin cambios a los servicios históricos. Se agregan
health liviano, wake tras commit y opt-in de esquema solo en base nueva vacía.
PG free caduca a 30 días; la fase es staging y no hay entrada a producción.
El Dashboard añade validación semántica a jsonschema: rechazó el plazo extendido
de apagado para free. Se retiró el campo y se añadió la comprobación en CI.

Pase local después de los cambios: 41 passed, 3 skipped en free-render,
catálogo, contrato y separación. Los tres omitidos necesitan PostgreSQL real
(concurrencia de solicitudes y DDL), están incluidos en CI. Antes también
pasaron 36 casos de estabilización/free-render con Redis real. Next standalone,
TypeScript y proxy real 12 MB correctos. Chrome local vuelve a fallar al iniciar
por SIGSEGV del binario: el pase móvil se exige en CI con Chrome del runner.
Las rutas simuladas de ese pase ahora reportan worker dormido pero cola disponible,
para verificar que las operaciones siguen siendo accesibles durante el cold start.

## Aceptación real todavía pendiente

- Generación real limpio/lifestyle/comercial/regeneración/corrección y lotes.
- Credenciales/callback/roles/scopes efectivos de staging, logs reales seguros.
- Drive escritura controlada, Sheet lectura completa y reversión precisa.
- Memoria y reinicio del worker completo, API/frontend disponibles.
- WordPress/Woo producto/media/webhook/stock TEST-INTEGRATION y limpieza.
- Despliegue aditivo, backup/restauración y cambio de entrada ensayado.
- Loyverse futuro sin activar ni asumir firma/OAuth.

El OOM de Render a 512Mi sí fue verificado; métricas no devolvieron series.
No convertir el RSS de un test simulado en una garantía de capacidad real.
Blueprint propone web free para worker, 512 MB/concurrency 1, sujeto a medir.
No autoriza upgrades ni pagos. PostgreSQL free solo staging, caduca a 30 días.

## Explicación correcta del sistema resultante

La rama prepara una PWA Next sin secretos, API FastAPI, Redis/RQ y worker
independiente que reutiliza el pipeline aceptado. Drive guarda imágenes; SQL
guarda estado/relaciones/counters y conexiones cifradas. inventario_completo
continúa durante la transición. WooCommerce es ecommerce; Loyverse es futuro.
El worker puede fallar sin terminar los procesos web; se revisan operaciones
inciertas antes de otro gasto. Hay auditoría, documentación y rollback.

Esta explicación describe la implementación preparada. La infraestructura
productiva sigue siendo la histórica hasta completar TEST_PLAN; no decir que
los tres servicios nuevos ya están activos ni que SQL es fuente exclusiva.
