# SKU por código de barras y sonidos de generación

Fecha: 2026-10-08. Rama: `agent/stabilize-architecture-20261006`.

## Comportamiento

- La captura asigna automáticamente el SKU al EAN/UPC/GTIN leído de las fotos o
  introducido por el operador. Se valida longitud (8, 12, 13 o 14 dígitos) y
  dígito de control, y se conservan los ceros iniciales.
- Si no hay lectura válida, se reutiliza `app.generar_sku_logica`: marca (3),
  nombre (3), gramaje (4), exactamente diez caracteres. La edición de nombre,
  marca o gramaje vuelve a calcular este respaldo. No se modifica esa función.
- Una entrada manual inválida se rechaza sin sustituir el borrador válido. Una
  lectura de IA inválida se descarta y utiliza el respaldo.
- Los códigos válidos guardados solo en un SKU histórico también participan
  en coincidencias GTIN, incluso si falta la columna de código de barras.
- El padre nuevo conserva el prefijo común de códigos de la misma marca y
  familia y reemplaza cada dígito restante con `x`. No usa el GTIN completo.
  Sin variantes distintas, conserva los primeros seis dígitos; varias fuentes
  o representaciones UPC/EAN del mismo GTIN no cuentan como variantes.
- Una familia sin ningún código legible conserva la propuesta histórica FULL.
  Una colisión de SKU padre o códigos sin prefijo común requiere revisión;
  no se unen familias automáticamente. Los padres elegidos existentes conservan
  su SKU. La máscara es un identificador de familia, no un código de barras.

| Caso | Código del producto | Otra variante | SKU padre propuesto |
|---|---|---|---|
| Una referencia | `4006381333931` | Ninguna | `400638xxxxxxx` |
| Dos variantes | `4006381333931` | `4006381340007` | `40063813xxxxx` |
| UPC con cero inicial | `036000291452` | `036000292459` | `03600029xxxx` |

El frontend actualiza el SKU devuelto por el servidor sin sobrescribir una
edición más reciente. El SKU del producto es automático; el padre propuesto
sigue siendo revisable antes de guardar. La estructura y contenido del Drive y
de `inventario_completo` no se migran ni se renombran en bloque.

## Sonidos

Web Audio reproduce tonos breves al observar el inicio, la finalización y el
fallo confirmado de un trabajo de generación o corrección. Cada transición se
anuncia una sola vez por ID de trabajo, incluidos resultados inmediatos. Los
trabajos antiguos ya terminados y las consultas, análisis, portadas compuestas
con fotos reales y guardados no emiten estos avisos.

Una respuesta perdida o fallo transitorio de la consulta de progreso no indica
que el trabajo haya fallado: no emite el sonido de error ni repite la generación.
La casilla «Sonidos al iniciar, terminar o fallar la generación» silencia los
avisos y conserva esa preferencia en este navegador; no guarda credenciales.

El contexto de audio se activa por una interacción del usuario antes de las
peticiones asíncronas. El navegador, el volumen y la suspensión de una pestaña
en segundo plano pueden impedir el sonido. Las restricciones de audio no
bloquean la captura ni la generación. No son notificaciones del sistema.

## Validación y límites

Pruebas HTTP con dobles de Gemini/Drive cubren códigos devueltos por el escáner,
lectura textual, códigos inválidos, respaldo, duplicados existentes, ceros
iniciales, prefijos, colisiones y guardado atómico de padre/hijo en el maestro.
Las pruebas de navegador usan datos sintéticos en Chromium y WebKit a 360,
390 y 430 px, incluidos éxito, fallo, pérdida temporal de consulta y silencio.
La CI también comprueba PostgreSQL real y el contrato de generación protegido.
No se generan imágenes de pago ni se escriben productos reales para validar.

Validación local completada: 133 pruebas Pytest, 74 pruebas unittest, compilación
Next.js/TypeScript, proxy/cookies/redirecciones/cargas de 12 MB y pruebas de
transiciones de audio. Diez casos requieren PostgreSQL/Redis de prueba y se
verifican en CI, junto con los navegadores móviles.

La suite de PostgreSQL detectó además una carrera existente: cada consulta de
progreso borraba la clave de Gemini de la sesión antes de terminar su lectura SQL;
el análisis concurrente podía fallar con `KeyError`. La restauración ahora resuelve
la credencial antes de actualizar la sesión compartida. Una prueba con lectura
SQL bloqueada garantiza disponibilidad para la operación en curso y comprueba
que eliminar la clave sigue dejándola desconectada. No se cambian credenciales.

Los modelos, prompts y funciones protegidas del generador quedan intactos.
No se cambian credenciales, planes ni los dos servicios históricos de Render.

## Reversión

La versión inmediatamente anterior es `f74396ace7f3ce49b46bb44edcbee7bfd594b0e8`,
que conserva las correcciones de OAuth y clave Gemini. Para revertir por código,
aplicar `git revert <commit que incorpora SKU y sonidos>` sobre esta rama y
publicar; CI debe pasar antes del despliegue automático.

Para una reversión inmediata en Render, seleccionar los despliegues anteriores:

- `rincon-frontend`: `dep-db3tcl3ncjis7389ss2g`.
- `rincon-catalog-api`: `dep-db3tcl3ncjis7389ss50`.

No revertir inventario ni borrar datos. Los productos ya guardados con SKU
numérico siguen siendo válidos; los padres enmascarados se reconocen por
`tipo=variable`, que ya admite la versión anterior. Si se desea revertir también
el worker de la misma rama, elegir su despliegue de `f74396a`; su generador no
se modifica con esta corrección.
