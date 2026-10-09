# Recuperar la sesión después de la inactividad

Entrega posterior a `419f849`, para `agent/stabilize-architecture-20261006`.

## Causa y reproducción

Render detiene los servicios web gratuitos después de 15 minutos sin tráfico:
<https://render.com/docs/free>. Los registros de `rincon-catalog-api` muestran
un apagado limpio el 9 de octubre de 2026 a las 00:21:33 UTC y su arranque a
las 00:48:04 UTC. En el diagnóstico, la petición de salud del proxy devolvió
502 y HTML en 3,71 segundos; la petición directa de la API terminó con JSON y
HTTP 200 después de 36,21 segundos.

`app.SESSIONS` era el único almacén de sesiones. El navegador conservaba una
cookie de ocho horas, pero la API ya no conocía su identificador después de
reiniciarse. Además, la carga inicial consultaba la sesión una sola vez; una
respuesta temporal del servidor dejaba la interfaz sin recuperar la cuenta.

## Corrección

- La sesión Google se guarda cifrada en `rincon_integration_accounts`, una tabla
  existente, con proveedor `web_session`. La clave de búsqueda es el SHA-256 del
  identificador aleatorio de sesión; el identificador original no se almacena.
  Se reutiliza `CREDENTIAL_ENCRYPTION_KEY`, sin cambiar su valor ni credenciales.
- Se guardan únicamente correo, credenciales Google, vencimiento y espacio de
  archivos. Carpeta y clave personal de Gemini se recuperan de las preferencias
  y conexiones existentes, para respetar cambios posteriores del usuario.
- El middleware recupera y valida la sesión antes de autorizar archivos o
  escrituras, después de comprobar Host, origen y límites de peticiones. SQL se
  consulta fuera del bucle asíncrono. Un fallo temporal de almacenamiento devuelve
  503 sin eliminar la cookie; no equivale a una sesión cerrada.
- La caducidad original no se extiende al restaurar. Se comprueban los permisos y
  la lista de cuentas autorizadas. Cerrar sesión borra el registro cifrado y las
  copias en memoria dejan de ser válidas en su siguiente petición.
- La página inicial, captura y `/login` comparten una espera de hasta tres minutos:
  solo reintentan GET de `/service-health` y `/api/session`. Cada petición puede
  durar hasta 45 segundos, en lugar de ocho. Se aceptan solo JSON válidos de la API.
- La interfaz muestra «Iniciando servidor y recuperando tu sesión…» y permite
  reintentar si se agota la espera. La página principal vuelve a consultar la
  sesión al recuperar conexión, foco o visibilidad. `/login` devuelve al inicio
  si la sesión sigue vigente; empieza Google cuando la API confirma que no existe.
- No se reintentan callbacks OAuth, códigos Google, generaciones ni escrituras.
  Estado y PKCE mantienen el consumo único y el vencimiento de diez minutos.

No se crea infraestructura, no se migra el esquema ni se cambian planes. Los
servicios históricos conservan sus ramas y despliegues. Generador, archivos de
Drive e `inventario_completo` quedan fuera de esta corrección.

## Validación

`test_web_sessions.py` utiliza credenciales sintéticas y el almacenamiento de
pruebas: callback y cookie segura, reinicio de la caché del proceso, recuperación
del mismo vencimiento, cifrado, ausencia de secretos en respuestas, revocación,
caducidad, cookie alterada, lista de acceso modificada, preferencias actualizadas,
error temporal SQL, permisos de subida y CSRF. Se ejecuta también en el PostgreSQL
dedicado de CI; nunca contra la base real de Render.

`test_oauth_wakeup.cjs` comprueba timeout, 502, HTML, readiness inválido, espera
limitada, reintento explícito, un solo inicio OAuth y recuperación sin Google de
una sesión vigente. Los seis recorridos móviles de captura comprueban además
que un 503 de sesión se recupera sin recargar ni mostrar una cuenta desconectada.
Se conservan las comprobaciones de proxy, cookies y carga de 12 MB y el contrato
del generador.

La prueba del dominio real alcanzó la redirección a Google, pero el navegador
remoto recibió una conexión rechazada de Google. No se completó un nuevo acceso
real ni se pidió introducir credenciales. Los casos de callback y recuperación
usan Google simulado. No se ejecutaron generaciones pagadas ni escrituras reales
de Drive o inventario.

Una sesión que ya se perdió antes de esta entrega no puede recuperarse a partir
de su cookie: hay que conectar Google una vez. Las nuevas sesiones se conservan
durante su vigencia de ocho horas. Si faltase `DATABASE_URL`, se conserva el modo
histórico en memoria; `/service-health` expone `session_backend` para comprobarlo.

## Revertir

Crear un commit que revierta esta entrega y publicarlo en la misma rama. Para una
reversión inmediata, restaurar únicamente los despliegues de `419f849` anteriores
a esta corrección: frontend `dep-db42mghsrm7s73amotsg`, API
`dep-db42mfij9qps73fujau0` y worker `dep-db42memb7d7c73a52ujg` si se desplegó.
La versión anterior conserva OAuth, formato Gemini, SKU y sonidos, pero vuelve a
perder sesiones en reinicios. No borrar filas de productos ni modificar datos de
Drive. Los registros `web_session` no requieren eliminarse para volver al código
anterior.
