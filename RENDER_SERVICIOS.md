# Interfaz y sincronización en servicios separados

La app principal conserva sus URL y páginas. Las solicitudes de herramientas
WooCommerce se delegan por HTTPS al segundo servicio. Inventario físico y
generación IA siguen en el principal. Guardar un producto sigue escribiendo
solo en Drive; la publicación es una operación explícita.

## Principal: suite-ecommerce-ia

- `SUITE_SERVICE_ROLE=main`
- `SUITE_DRIVE_ONLY=false`
- `SYNC_SERVICE_URL=https://suite-ecommerce-ia-ai.onrender.com`
- `SYNC_SERVICE_SHARED_KEY`: secreto aleatorio de 32 bytes o más.
- `WC_WRITE_ENABLED=true`, `WP_MEDIA_WRITE_ENABLED=true`.
- Conservar las credenciales OAuth, WooCommerce y WordPress actuales.

## Segundo: suite-ecommerce-ia-ai

- `SUITE_SERVICE_ROLE=sync`
- `SUITE_DRIVE_ONLY=false`
- `SYNC_SERVICE_SHARED_KEY`: el mismo secreto del principal.
- `WC_WRITE_ENABLED=true`, `WP_MEDIA_WRITE_ENABLED=true`.
- `/health` informa `role=sync`. La única entrada de trabajo es
  `/internal/tools`, autenticada con firma HMAC y protección contra replay.

Ambos usan el Dockerfile del repositorio. El segundo importa un runtime ligero;
no carga Gradio, Gemini ni pandas. Las páginas y callbacks existentes se reutilizan.
No hace falta un nuevo OAuth: el principal refresca su sesión y transmite solo
el access token temporal y las carpetas elegidas. El segundo borra el contexto
de Google después de cada solicitud. Refresh token, secreto OAuth y API key de
Gemini nunca se transfieren. Las credenciales de tienda se transmiten por HTTPS
entre los dos servicios, sin quedar en logs ni en el navegador.

En Render Free el segundo servicio puede tardar en despertar. No se reintentan
escrituras automáticamente. Después de un timeout, comprobar el SKU antes de
repetir. La separación aísla memoria y CPU; la caché de Elementor se administra
en WordPress y no la modifica esta configuración.
