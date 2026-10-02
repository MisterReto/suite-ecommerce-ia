# Seguridad y consumo de Gemini

## Cambios

- Extracción de texto y etiquetas en una llamada; búsqueda de precio en otra: 2 llamadas por producto, antes 3.
- Caché de respuestas JSON durante 30 minutos, aislada por huella de API key y contenido/configuración/modelo. Máximo 256 entradas en memoria; no guarda errores ni JSON truncado. Los prompts de lifestyle/comercial se reutilizan cuando los datos coinciden.
- Respuestas de texto limitadas a 768–1536 tokens según tarea (QA: 1024). Thinking desactivado para Gemini 2.5 Flash en estas tareas. Otros modelos no reciben parámetros de thinking incompatibles.
- Un intento de imagen por defecto, configurable entre 1 y 3. Se conserva QA visual y validación local antes de subir a Drive. Un fallo técnico de QA detiene las regeneraciones; nunca aprueba la imagen.
- Las referencias se envían inline, sin crear archivos remotos persistentes en Gemini. Las fotos no se cachean: un clic de regeneración sí solicita una foto nueva.
- Prompts más breves, feedback limitado a 8 correcciones, vocabulario de hasta 80 etiquetas priorizadas por coincidencia con contexto. Un vocabulario muy grande puede requerir corregir las etiquetas manualmente.
- Logs de tokens de entrada/salida/thinking y aciertos de caché, sin prompts, API keys ni respuestas del proveedor. Para verlos, configura el logger `gemini_gateway` a nivel INFO.
- OAuth con state de un solo uso, vencimiento y PKCE S256; email verificado; sesiones de 8 horas, logout POST y protección de origen.
- Gradio requiere sesión para sus APIs, cargas y archivos. Archivos y hashes de cola vinculados a la sesión. Archivos locales privados y nombres aleatorios sin el token de sesión ni SKU en la ruta.
- WooCommerce exige una lista explícita de correos, HTTPS y rechaza redirecciones que podrían filtrar Authorization. Errores sin detalles internos.
- Dependencias directas fijadas a las versiones usadas en las pruebas; Docker sin root, un proceso y sin access logs que incluyan códigos OAuth.

## Configuración de despliegue

Conservar `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` (HTTPS) y las variables `WC_*` existentes.

| Variable | Valor predeterminado | Uso |
|---|---|---|
| `APP_ALLOWED_EMAILS` | Vacío | Lista de correos separados por coma para restringir la suite. Sin lista, cualquier cuenta Google verificada puede usar su propio Drive/API key. Para la tienda, configurar solo el personal autorizado. |
| `WC_ALLOWED_EMAILS` | Vacío: acceso denegado | Correos autorizados para consultar las credenciales compartidas de WooCommerce. Es necesario configurarla para recuperar el panel WC. |
| `GEMINI_TEXT_MODEL` | `gemini-2.5-flash` | Modelo ya usado en el proyecto; no se cambia de proveedor ni se presupone acceso a otro modelo. |
| `GEMINI_IMAGE_MODEL` | `gemini-2.5-flash-image` | Modelo de imágenes existente. |
| `GEMINI_IMAGE_ATTEMPTS` | `1` | Intentos automáticos por clic, entre 1 y 3. Los intentos adicionales pueden cobrar de nuevo. |
| `GEMINI_CALLS_PER_MINUTE` | `20` | Llamadas máximas por API key en una ventana móvil de 60 segundos. |
| `GEMINI_CALLS_PER_DAY` | `500` | Llamadas máximas por API key durante una ventana de 24 horas iniciada en la primera llamada. |

Inicio: `uvicorn server:fastapi_app --host 0.0.0.0 --port 7860 --workers 1 --proxy-headers --no-access-log`.
Health check sin acceso a proveedores: `/healthz`.

Las sesiones, límites y caché son locales al proceso: se reinician al desplegar y no se comparten entre réplicas. Mantener una sola instancia/proceso. Para escalar, migrar estos almacenes a Redis antes de habilitar varias réplicas. Los límites de llamadas no son un presupuesto monetario; configurar además las cuotas del proyecto en Google. El tamaño máximo de carga es 10 MB por archivo. Los POST del frontend requieren Origin del dominio configurado en el callback; clientes externos deben usar ese mismo origen y una sesión válida.

El scope de Drive completo se conserva para no romper la selección de carpetas existentes. Migrar a `drive.file` requiere implementar un selector y volver a autorizar los archivos; no se modifica silenciosamente.

## Validación

`python -m pip install -r requirements.txt pytest httpx`

`python -m pytest -q`

Las pruebas usan dobles de Gemini/Google/WooCommerce: no generan imágenes, consumen tokens ni modifican inventario real. Cubren state/PKCE, expiración, CSRF, rutas WC, archivos por sesión, caché, límites, JSON truncado, QA y extracción sin llamada extra de etiquetas.

Antes de desplegar: configurar los correos permitidos y comprobar manualmente OAuth con la cuenta real, extracción de un producto y generación de una foto aprobada. Falta esa validación real, la calidad visual con los prompts nuevos y medir el ahorro monetario; no se promete un porcentaje de ahorro ni una auditoría de seguridad integral.

Referencias técnicas: https://ai.google.dev/gemini-api/docs/generate-content/thinking y https://gradio.app/docs/gradio/mount_gradio_app.
