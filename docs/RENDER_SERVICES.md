# Servicios Render observados

Lectura de metadata y deploys live, 2026-10-12, workspace ProyectoInventario.

| Servicio | ID | Rama live | Commit live |
|---|---|---|---|
| rincon-frontend | srv-db2mlb2j9qps73eob7og | feature/woocommerce-and-product-removal-20261009 | b4aa4051cd2d1b897cc7a582e67ee8b938cfcc2b |
| rincon-catalog-api | srv-db2mlqij9qps73eobrg0 | feature/woocommerce-and-product-removal-20261009 | b4aa4051cd2d1b897cc7a582e67ee8b938cfcc2b |
| rincon-catalog-worker | srv-db2mlqqj9qps73eobsk0 | feature/woocommerce-and-product-removal-20261009 | b4aa4051cd2d1b897cc7a582e67ee8b938cfcc2b |
| suite-ecommerce-ia, histórico | srv-d9kc2lvavr4c73am1rug | agent/woocommerce-inventory-foundation | 1a1c3bc9c9e56422c290fb59247a6dff2602d315 |
| suite-ecommerce-ia-ai, histórico | srv-da3841gae00c73aaour0 | agent/woocommerce-inventory-foundation | 1a1c3bc9c9e56422c290fb59247a6dff2602d315 |

Los tres actuales son web Docker free; esta entrega conserva su topología. No se cambia autodeploy real, rama, plan ni variables. La propuesta de configuración limpia está separada y no aplicada.

PostgreSQL rincon-catalog-db: dpg-db2mlb2j9qps73eob7u0-a, PG17, metadata available. Redis rincon-generation-queue: red-db2mlb2j9qps73eob7hg, metadata available, noeviction. Esto no demuestra SELECT/PING operativo. El acceso SQL externo está restringido; no se cambia la allowlist.

Los históricos conservan su runtime anterior; no se afirma que sus lectores de entorno estén eliminados. La auditoría de los nombres/orígenes del entorno efectivo de los cinco servicios está pendiente, porque el conector no ofrece enumerarlos.

Consultar DEPLOYMENT.md, ENVIRONMENT_VARIABLES.md y ../ROLLBACK.md.
