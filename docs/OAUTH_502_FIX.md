# Conectar Google: 502 durante el arranque gratuito de Render

Rama: `agent/stabilize-architecture-20261006`. Base de esta corrección:
`568c2a38d8f03c12073fed24b4f5e66be2c6ec67`.

## Evidencia del 8 de octubre de 2026 (UTC)

- Los registros de `rincon-catalog-api` muestran un cierre limpio a las
  08:38:21, sin excepción de OAuth. Los registros de `rincon-frontend` muestran
  arranques posteriores independientes.
- Se abrió `https://rincon-frontend.onrender.com/login` con ambos servicios
  inactivos. Render mostró su pantalla de arranque y terminó en **502 Bad
  Gateway**, request ID `a476cc4bce3c1ef3-PDX`.
- El frontend arrancó a las 17:17:09; FastAPI completó su arranque a las
  17:18:31. El frontend `/` respondió 200 mientras su `/service-health`
  devolvía 502. La comprobación directa de la API agotó su tiempo de espera.
- Después del arranque, los `/service-health` directo y del frontend devolvieron
  200 y el mismo `service_id` y commit. `/login` respondió 307 a Google,
  con callback del frontend, PKCE S256 y dos cookies separadas.

La causa reproducida es el proxy de `/login` intentando iniciar OAuth antes de
que la API gratuita esté disponible. No se encontró un error de credenciales.
Render documenta el apagado por 15 minutos de inactividad y el arranque de
aproximadamente un minuto en <https://render.com/docs/free>.

## Corrección

En modo `standalone`, `/login` sirve una página local con «Iniciando servidor».
La página hace GET a `/service-health`, con tiempo máximo de 8 segundos por
solicitud, separación de 3 segundos y ventana de espera de 3 minutos.
Solo acepta JSON con `ok: true` y `backend: "fastapi"`; HTML de arranque,
502/503, errores de red y tiempos de espera se reintentan dentro de esa ventana.
Si no se recupera, muestra un botón **Reintentar** y deja de sondear.

Cuando la API está lista, una navegación completa a `/auth/start` se dirige al
`/login` original de FastAPI. Así se conservan las cookies HttpOnly en el dominio
del frontend. La espera no emite estado OAuth. No se reintentan callbacks,
códigos Google, escrituras ni peticiones de generación. La página local usa
`Cache-Control: no-store`. La exportación estática compatible sigue compilando;
sus rutas de OAuth originales siguen a cargo de FastAPI.

## Configuración comprobada sin secretos

| Variable | Comprobación |
| --- | --- |
| `SUITE_API_ORIGIN` | El `/service-health` del frontend llega a `rincon-catalog-api` y devuelve su ID y versión. La URL HTTPS se valida al compilar. |
| `GOOGLE_REDIRECT_URI` | El redirect real a Google contiene `https://rincon-frontend.onrender.com/auth/callback`. |
| `GOOGLE_REDIRECT_BASE` | El Blueprint referencia el origen del frontend. `configure_redirect()` añade `/auth/callback` cuando no hay URI explícita; el resultado efectivo coincide con Google. No se leyó ni cambió el valor literal del entorno en Dashboard. |
| `APP_PUBLIC_ORIGIN` | Un POST a una ruta inexistente con el origen del frontend pasa la protección de origen (404); con un origen externo es rechazado (403). Se mantuvo la validación de Host de la API. |

No se cambiaron variables, credenciales, planes, los dos servicios históricos,
el generador, Drive ni `inventario_completo`.

## Validación y límites

- Compilación estática, TypeScript y compilación standalone.
- `test_frontend_proxy.cjs`: página local, health, redirect Google, las dos
  cookies de OAuth, callback, cookie de sesión, logout y upload íntegro de 12 MB.
- `test_oauth_wakeup.cjs`: navegador móvil, timeout/502/HTML/JSON incorrecto,
  ausencia de inicio OAuth antes de readiness, un solo inicio, límite de espera
  y reintento explícito. Incluido en el workflow existente.
- `test_frontend_separation.py` y la prueba existente de estado OAuth y PKCE.
- Ensayo local con Google simulado: callback, validación de estado, único
  intercambio de código, cookies seguras, sesión consultable en `/api/session`
  y tras otra consulta, rechazo de replay y caducidad del estado.

El estado OAuth sigue en `oauth_guard._pending`: 600 segundos, PKCE y consumo
único. La sesión sigue en `app.SESSIONS`, con cookie Secure/HttpOnly/SameSite=Lax
y duración de 8 horas. Ambos almacenes son del proceso. Un reinicio o apagado
de la API invalida esas sesiones; se debe volver a conectar. No se sustituyó
este mecanismo por almacenamiento compartido como parte del arreglo del 502.
Una autorización nueva debe completarse dentro de 10 minutos. No se usa la
cookie de PKCE como alternativa a un estado que el servidor ya perdió.

La comprobación final con una cuenta Google real necesita el inicio de sesión
del usuario. Llegar a la pantalla de Google no prueba que exista una sesión
autenticada: se debe verificar el regreso al frontend y `/api/session` con
`authenticated: true`, y recargar la interfaz. No requiere escribir en Drive.

## Revertir

Para revertir solo el comportamiento del frontend, crear un commit que elimine
`frontend/app/connect-google/page.tsx` y restaure
`frontend/next.config.ts` desde la base indicada arriba. Esto evita deshacer
otros cambios posteriores de la rama. No cambiar variables ni bases de datos.

Para un rollback inmediato de Render, seleccionar únicamente **rincon-frontend**
y restaurar el deploy anterior `dep-db3mf7ei0phs73ap8b00`, correspondiente a
`568c2a38d8f03c12073fed24b4f5e66be2c6ec67`. El 502 durante un arranque en frío
volverá a ser posible. Los servicios históricos no forman parte del rollback.

## Rechazo del formato de la clave personal de Gemini

El endpoint `/api/settings` solo admitía 20–256 caracteres de
`A-Za-z0-9_-`. Una clave larga o con puntuación era rechazada antes de consultar
a Google. La documentación oficial admite claves estándar y de autorización:
<https://ai.google.dev/gemini-api/docs/api-key>. No se leyó la clave del usuario
ni se comprobó su validez real como parte del diagnóstico.

La validación ahora trata la clave como un valor opaco de 20–4096 caracteres
ASCII imprimibles sin espacios internos. Recorta únicamente los espacios y
saltos de línea de los extremos al pegar. El cifrado, aislamiento por cuenta y
persistencia permanecen iguales. El botón existente **Comprobar clave** consulta
los modelos disponibles sin generar contenido. Aceptar el texto no garantiza
que Google autorice la clave.

Las pruebas HTTP usan claves sintéticas estándar y largas con puntuación:
verifican guardado cifrado, restauración exacta en una nueva sesión, ausencia
de la clave en la respuesta y eliminación. Las entradas vacías, incompletas,
con espacios internos, caracteres de control/invisibles o tamaño excesivo se
rechazan sin reemplazar la clave ya guardada. No hay llamadas de pago.

Para revertir este ajuste, restaurar únicamente la condición y mensaje de
validación de `/api/settings` en `studio_api.py` desde el commit
`d885596bc7fa3bda30567e1291d75311f269b829`. No requiere cambiar claves,
variables, Drive ni el esquema de base de datos.
