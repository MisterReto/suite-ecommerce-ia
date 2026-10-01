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


## Inventario unificado y publicación masiva

El botón **Inventario y stock** abre `/inventory-hub` en el segundo servicio.
Contiene Inventario, Conteo inicial y Preview stock. Solo carga la pestaña elegida;
el preview requiere pulsar Revisar y no corre en segundo plano. Las portadas FULL
no aparecen en los conteos y no reciben existencias ni precios propios.

**Subida masiva** abre `/woocommerce-batch-sync`. Los grupos usan 2 hilos por
petición; `BULK_MAX_WORKERS=2` limita el máximo del proceso (tope absoluto: 4).
Cada hilo crea sus propios clientes HTTP y mantiene el contexto de su tienda.
Las portadas se crean antes que sus variaciones; no se procesan dos variaciones
del mismo padre simultáneamente. Un padre fallido bloquea sus hijos.

Los productos nuevos empiezan como borrador/privados y se publican tras verificar
el contenido. El marcador `_suite_bulk_created` permite terminar un borrador propio
al reanudar sin publicar borradores ajenos. Cada intento busca de nuevo por SKU.
Un POST de creación que devuelve timeout no se repite automáticamente.

El progreso y las opciones viven en `WooCommerce Batch Sync` (A:L).
Cerrar la página detiene los siguientes grupos; el grupo iniciado termina.
Al caducar la sesión temporal, abrir la herramienta desde la Suite y pulsar
Reanudar continúa el lote. No se ejecutan trabajos detached ni preview automático.
La casilla **Publicar existencias físicas** está desmarcada: así se conserva el
stock de WooCommerce. Marcándola se publica el conteo; se rechazan inventarios con
todas las existencias 0/1 hasta confirmar un conteo real.

Los movimientos y conteos de la Suite se serializan en el único proceso del
segundo servicio (`--workers 1`) para evitar actualizaciones perdidas. No ejecutes
réplicas de este servicio para editar stock sin incorporar un bloqueo distribuido.
Google Sheets no ofrece una transacción con editores externos: coordina cambios
manuales/otros programas durante un conteo.
