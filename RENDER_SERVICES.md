# Servicios Render

## Inventario observado el 6 de octubre de 2026

| Servicio actual | ID | Rama | Rol |
| --- | --- | --- | --- |
| `suite-ecommerce-ia` | `srv-d9kc2lvavr4c73am1rug` | `agent/woocommerce-inventory-foundation` | Aplicación principal histórica. |
| `suite-ecommerce-ia-ai` | `srv-da3841gae00c73aaour0` | `agent/woocommerce-inventory-foundation` | Herramientas de tienda/sync. El nombre no lo convierte en worker de imágenes. |

Ambos son web Docker, plan free, Oregon y autodespliegue por commit. La inspección no encontró PostgreSQL ni Key Value. No se cambiaron estos servicios en esta continuación.

## Tres servicios preparados

| Servicio propuesto | Dockerfile | Proceso | Almacenamiento/configuración |
| --- | --- | --- | --- |
| `rincon-frontend` | `Dockerfile.frontend` | Node / Next.js standalone | UI pública y upstream HTTPS fijo. Sin claves IA/Google/tienda. |
| `rincon-catalog-api` | `Dockerfile.api` | Uvicorn / FastAPI, una instancia | Sesiones HTTP, SQL, OAuth y validación de origen. |
| `rincon-catalog-worker` | `Dockerfile.worker` | `python -m catalog_platform.worker` | SQL, conexión cifrada, Drive y proveedores. |

La base `rincon-catalog-db` es un recurso aparte. Se usa una cola SQL compartida, con SKIP LOCKED, leases, heartbeat y checkpoints; no se agrega Redis. Los tres procesos nuevos conviven inicialmente con los dos servicios anteriores para conservar la recuperación.

El Blueprint está en `deploy/render-platform.yaml`, rama `agent/catalog-platform`. Tiene nombres nuevos y previews desactivados. No se aprovisiona por estar en git.

## Activación

1. Revisar coste recurrente de la base y el worker antes de aprovisionar. Los planes web free no hacen gratuita toda la arquitectura.
2. Crear la API/base/worker y completar variables servidor; ejecutar una sola inicialización de base nueva.
3. Configurar la URL real de la API como `SUITE_API_ORIGIN` y construir el frontend.
4. Configurar la URL real del frontend como `APP_PUBLIC_ORIGIN` y como dominio de `GOOGLE_REDIRECT_URI`.
5. Validar OAuth, cookies, un lote pequeño y recuperación antes de cambiar la entrada de usuarios.

Los nombres de servicio no garantizan de antemano un subdominio exacto. Usar las URLs devueltas por Render. La URL upstream se incorpora al build del frontend: cambiarla exige rebuild.

Para herramientas sync históricas, reutilizar `SYNC_SERVICE_SHARED_KEY`. Al hacer el cambio de entrada, `MAIN_SERVICE_URL` del sync debe apuntar a la nueva API que emitió el handoff; conservar el valor anterior en el plan de rollback. No cambiarlo durante un preview si los usuarios siguen trabajando en la aplicación anterior.

Ver [ENVIRONMENT_VARIABLES.md](ENVIRONMENT_VARIABLES.md), [DEPLOYMENT.md](DEPLOYMENT.md) y [MANUAL_ACTIONS_REQUIRED.md](MANUAL_ACTIONS_REQUIRED.md).
