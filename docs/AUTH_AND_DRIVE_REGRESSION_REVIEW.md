# Login y clasificación de Drive: revisión del 9 de octubre de 2026

Base de esta corrección: `e6e5c1f5ce19d1067c3fab4d50b67b5e99558e8a`.
Rama: `agent/stabilize-architecture-20261006`.

## Qué cambió ayer

Horarios de Ciudad de México (UTC-6), contrastados con commits y despliegues reales.

| Cambio | Commit | Hora del commit, 8 de octubre | Frontend activo |
| --- | --- | --- | --- |
| Espera local antes de OAuth; `/login` deja de ir directamente a FastAPI | `d885596` | 11:29 | 11:36 |
| Aceptar el formato de claves Gemini opacas | `f74396a` | 11:38 | 11:44 |
| SKU por código de barras y sonidos de generación | `a2a5918` | 14:30 | Incluido en `419f849`, 15:05 |
| Evitar perder la clave Gemini durante consultas concurrentes | `419f849` | 14:57 | 15:05 |
| Persistencia cifrada de sesión y recuperación tras suspensión | `44022ca` a `cd7835f` | 19:11–19:35 | 19:42 |
| Inicio del login sin depender de la hidratación React | `e6e5c1f` | 21:29 | 21:37 |

El rango `f74396a..419f849` no cambia rutas OAuth, cookies, redirecciones ni
proxy. Sí despliega otra versión y reinicia la API. Las categorías fijas y los
campos manuales de subcategoría y etiquetas ya aparecen en `568c2a3` y
`f74396a`: no fueron introducidos por la lógica de SKU. El análisis por código
exacto también omitía esos tres campos al reconstruir un producto existente.

## Fallo reproducido con la versión anterior

- La API se apagó a las 03:54:21 UTC. El frontend volvió a arrancar a las
  06:59:34 UTC, pero la API seguía apagada al abrir `/login` en el navegador de
  prueba a las 07:10 UTC.
- Por el frontend, `/service-health` devolvió 502/HTML a las 07:11:29 UTC
  (10,20 s) y `/api/session` a las 07:11:40 UTC (11,10 s). Ambas respuestas
  indicaban `x-render-routing: no-deploy`. La API no registró un arranque durante
  la espera. El script inline sí terminó mostrando el botón de reintento.
- Una petición directa a la API comenzó después, a las 07:13:22 UTC. FastAPI
  arrancó a las 07:13:55 y respondió salud 200/JSON a las 07:14:02 (40,02 s).
- Después de ese arranque, «Reintentar» desde el mismo frontend llegó al selector
  real de cuentas Google. No se seleccionó cuenta ni se completó una nueva sesión.

Esto confirma que reintentar únicamente la salud mediante el rewrite no
despertaba la API en el caso observado. La hipótesis anterior sobre hidratación
no explica este nuevo ensayo: el script sí estaba funcionando. No se atribuye el
comportamiento a un encabezado concreto de Render sin evidencia de su interior.

## Corrección

- Al iniciar una recuperación, el navegador envía un único GET directo a
  `/service-health` del origen validado `SUITE_API_ORIGIN`. No envía cookies ni
  encabezados de la petición entrante y puede cancelarse. El navegador exige
  `redirect: follow` en modo `no-cors`; CSP restringe los destinos de conexión.
  Su respuesta opaca no se usa para dar el servidor por disponible.
- La disponibilidad y las cookies se siguen comprobando mediante el frontend.
  Se mantienen 45 segundos por petición, tres minutos de espera y reintento
  explícito. No hay sondas permanentes ni peticiones cuando la app está cerrada.
- Se permite conectar desde el navegador únicamente con el origen público de
  API que ya estaba validado para el proxy. No cambia el origen de OAuth,
  Host/origen de escrituras, cookie HttpOnly, estado, PKCE ni caducidad.
- `/api/session?auth_only=true` valida la sesión sin descargar imágenes del
  borrador. `/login` usa esta consulta; los demás endpoints conservan la carga de
  borradores y trabajos existente.
- `/api/catalog-taxonomy` descubre y lee una hoja existente de la carpeta del
  usuario. No llama al adaptador que crea/sincroniza carpetas u hojas. Utiliza
  `Lista completa`, `categorias` y `etiquetas`, preservando la ortografía.
- Captura y edición manual comparten selectores de categoría y subcategoría.
  Cambiar categoría limpia una subcategoría incompatible. Las etiquetas se
  eligen mediante casillas en una fila desplazable con búsqueda; escribir en la
  búsqueda no crea etiquetas. Solo se muestran hasta 60 coincidencias a la vez
  y las seleccionadas se conservan visibles.
- El análisis de producto recibe las subcategorías existentes por categoría y
  descarta una clasificación incompatible. Al encontrar un código ya registrado,
  recupera también categoría, subcategoría y etiquetas de ese registro.
- El error de lectura de Drive se muestra con reintento, sin sustituirlo
  silenciosamente por categorías fijas. Las opciones iniciales solo cubren un
  inventario sin clasificación.

La hoja real se comprobó mediante lecturas de `I:J`: 399 filas, 7 categorías,
31 subcategorías y 1.461 etiquetas distintas. No se guardan sus filas ni el
vocabulario privado en este repositorio. No se cambió la hoja, generador de
imágenes, modelos, credenciales, SKU, sonidos ni servicios históricos.

## Verificación

Pruebas locales: compilación estática y standalone, TypeScript, proxy real
Next.js, cookies/redirecciones/carga de 12 MB y script inline sin React. Las
pruebas Python cubren clasificación por carpeta, lectura sin creación de Drive,
error sin secretos, código exacto con clasificación, subcategoría incompatible,
sesión ligera sin descargas, persistencia y contrato del generador.

Los recorridos de CI prueban Chromium/WebKit en 360/390/430 px: error y reintento
de opciones, selección, búsqueda de etiquetas, guardado de borrador y recarga.
También comprueban la edición manual y que el aviso directo de arranque ocurra
una vez, sin iniciar OAuth antes de confirmar salud por el proxy.

La versión, ejecuciones completas de CI, despliegues y ensayo final del dominio
real se registran en la página privada de objetivo/cambios de Notion. Las pruebas
de callback/sesión completa usan credenciales sintéticas; una redirección al
selector Google no prueba la sesión real de un usuario.

## Revertir

Revertir el rango de esta entrega sobre esta rama:
`git revert --no-commit e6e5c1f5ce19d1067c3fab4d50b67b5e99558e8a..COMMIT_FINAL_ENTREGA`.
Revisar y crear/publicar el commit resultante. El SHA final y el ensayo de reversión
se registran en Notion. La base anterior es `e6e5c1f` y se conservan sus
correcciones de persistencia, SKU y sonidos. CI debe pasar antes del despliegue
automático. No revertir datos ni modificar Drive.

Despliegues de base: frontend `dep-db462l142hec73c7b8b0`, API
`dep-db462l142hec73c7b8dg` y worker `dep-db462l142hec73c7b8s0`.
Render limita los rollbacks de servicios gratuitos a los dos despliegues previos;
si ya no aparecen, usar el commit de reversión. No cambiar planes para revertir.
