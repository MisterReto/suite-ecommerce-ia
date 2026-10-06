# Glosario para leer la app

| Término | Qué significa aquí | Ejemplo para encontrarlo |
| --- | --- | --- |
| Frontend | Pantallas que utiliza el navegador. | `frontend/app/page.tsx`. |
| React | Biblioteca para construir pantallas como componentes. | Un formulario que cambia al editar un producto. |
| Componente | Función que devuelve una parte de la interfaz. | `CaptureStudio.tsx`. |
| Estado / hook | Datos temporales de la pantalla y su actualización. | `useState`; no equivale a guardar en SQL. |
| TypeScript | JavaScript con tipos comprobados durante el build. | Tipos de producto/respuesta de API. |
| Next.js | Framework que construye/sirve el frontend React. | `next.config.ts`, export o standalone. |
| FastAPI | Framework Python que recibe solicitudes HTTP. | `@router.post` en `catalog_platform/api.py`. |
| Endpoint | Método y ruta con una función servidor. | `POST /api/platform/generation/jobs`. |
| JSON | Formato de datos entre UI/API y en payloads. | SKU, slots, request_key. |
| Proxy / rewrite | Servidor que envía una solicitud a otro destino fijo. | Next conserva `/api/session` en el dominio UI. |
| Sesión | Contexto temporal de un usuario autenticado. | Cookie `session_id`; datos en memoria API. |
| OAuth | Acceso delegado a Google sin guardar la contraseña. | `/login` y `/auth/callback`. |
| Tenant | Frontera de carpeta/catálogo autorizado. | `tenant_id` en consultas SQL. |
| ORM | Código Python que representa tablas y consultas SQL. | SQLAlchemy en `models.py`. |
| Transacción | Grupo de cambios que se confirma junto. | Crear job y conexión cifrada. |
| Worker | Proceso que trabaja fuera de la petición del navegador. | `catalog_platform.worker`. |
| Cola | Trabajos pendientes almacenados para ejecutar. | Filas con estado queued en PostgreSQL. |
| Lease | Reserva temporal de un trabajo para un worker. | `lease_owner`, `lease_until`. |
| Checkpoint | Progreso durable desde el que recuperar trabajo. | Slots/muestras ya completados. |
| Idempotencia | Repetir una solicitud no duplica una operación lógica. | `request_key` y IDs de evento. |
| Resultado incierto | Puede existir una operación externa sin confirmación local. | No regenerar hasta reconciliar. |
| AST | Estructura del código Python, independiente de espacios/comentarios. | Contrato de generación contra commit aceptado. |
| PWA | Web instalable con manifest/service worker. | UI shell cacheada; datos privados online. |
| Dockerfile | Instrucciones para construir y ejecutar un contenedor. | Archivos separados de frontend/API/worker. |
| Variable de entorno | Configuración del servidor sin escribirla en el código. | `DATABASE_URL`, `APP_ROLE_MAP`. |

## Un ejercicio breve

Sigue `POST /api/platform/generation/jobs` desde el botón hasta `enqueue`, localiza dónde se crea `GenerationJob`, sigue `queue.claim` y termina en `worker.generation`. Explica qué ocurre si cierras el navegador y qué ocurre si reinicias la API: son dos situaciones distintas. No necesitas entender todos los archivos a la vez.
