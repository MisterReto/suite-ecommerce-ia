# Suite e-commerce: servicios separados

La principal sirve captura, IA, ajustes y Google Drive. Los botones de WooCommerce
abren directamente https://suite-ecommerce-ia-ai.onrender.com. Las antiguas URL
del principal redirigen al segundo servicio y los POST locales quedan deshabilitados.
Los clientes WooCommerce/WordPress también impiden llamadas desde el principal.
Guardar un producto escribe solo en Drive; publicar requiere una acción explícita.

## Variables del principal

- SUITE_SERVICE_ROLE=main
- SUITE_DRIVE_ONLY=false
- SYNC_SERVICE_URL=https://suite-ecommerce-ia-ai.onrender.com
- SYNC_SERVICE_SHARED_KEY: clave compartida de al menos 32 bytes.
- Mantener OAuth y credenciales actuales de WooCommerce/WordPress.

## Variables del segundo servicio

- SUITE_SERVICE_ROLE=sync
- SUITE_DRIVE_ONLY=false
- MAIN_SERVICE_URL=https://suite-ecommerce-ia.onrender.com
- SYNC_SERVICE_SHARED_KEY: misma clave del principal.
- WC_WRITE_ENABLED=true y WP_MEDIA_WRITE_ENABLED=true.

La sesión de Google se conecta en el principal. El navegador recibe un ticket
aleatorio, válido durante 120 segundos y de un solo uso. El segundo lo canjea
por HTTPS con firma HMAC. No se exponen credenciales en enlaces ni HTML.
El segundo guarda una sesión temporal de 10 minutos, con cookie Secure/HttpOnly.
Al caducar, abrir de nuevo la herramienta desde la Suite renueva el acceso.
Solo se transmite el access token temporal de Google, referencias de carpetas
y credenciales de tienda; nunca refresh token, secreto OAuth ni API key de IA.
El segundo no importa Gradio, Gemini ni pandas. /service-health identifica el
servicio, versión desplegada y URL de sincronización; x-suite-executor identifica
las respuestas ejecutadas por el segundo servicio. No se reintentan escrituras
tras un timeout. Los SKU FULL son portadas variables sin precio ni stock propios.
