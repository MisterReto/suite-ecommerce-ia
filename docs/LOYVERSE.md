# Loyverse POS

La sección **Más → Loyverse POS** usa el cargador de Colab entregado el 16 de
octubre de 2026. Sus 23 funciones se conservan en `catalog_platform/loyverse_colab.py`.
El manifiesto de pruebas compara cada función con el texto original recibido.
No se importan ni se reactivan los módulos históricos retirados.

## Uso

1. Un administrador abre **Configuración de conexiones**, introduce su token y
   prueba la conexión. Se consulta la identidad de la cuenta y sus sucursales.
2. Asigna un nombre, elige una sucursal predeterminada y guarda la conexión
   verificada. Puede agregar otras cuentas o reutilizar esa conexión para otra
   sucursal. Para cambiar el token o volver a probarlo usa **Editar**.
3. Selecciona conexión y sucursal en el encabezado. **Comparar y publicar** lee
   las cuatro pestañas originales de Sheets y compara SKU con el catálogo
   completo de esa cuenta. **Catálogo Loyverse** muestra los artículos remotos
   y su disponibilidad/precio en la sucursal elegida.
4. Busca y filtra por marca, categoría, tipo y comparación. Selecciona simples,
   familias o variantes; la selección se conserva al cambiar de página.
5. Revisa datos e imagen principal. Puedes incluir imágenes y autorizar crear
   categorías faltantes. La revisión vence a los diez minutos.
6. Escribe **PUBLICAR**. Loyverse crea artículos reales y no tiene borradores.
   Las variantes nuevas quedan disponibles en la sucursal elegida; las nuevas
   variantes se marcan no disponibles en las demás sucursales de esa cuenta.
   Los artículos pertenecen al catálogo compartido de la cuenta.
7. Sigue cada trabajo en **Progreso y resultados**. Puedes pausar, reanudar,
   cancelar pendientes y reintentar fallidos. Reanudar/reintentar vuelve a
   exigir **PUBLICAR**. Una llamada ya iniciada termina antes de detenerse.

## Datos y límites

- Se conservan el documento `1gnuDwcceWwN4ksNnyq3Hs_MQHTfnZQZjeLnph72aUrE` y las
  pestañas `Lista Simple`, `Lista Variable`, `Lista completa` y `CSV 2 Variaciones`.
- Las imágenes finales numeradas se leen directamente de `imagenes_generadas`
  (`1V4HgnTCRnwVGwrGD968eNdtvQDGGY7wt`). Originales y subcarpetas privadas no se
  publican. La prioridad SKU/número/HD y el PNG cuadrado de 800 × 800 son los
  originales del Colab. Se publica una imagen por artículo.
- Una familia usa un solo atributo de variación. Se conservan sus nombres,
  valores, relaciones por SKU, código de barras, descripciones y precios.
- Los SKU existentes se omiten. Solo se agregan variantes faltantes a una
  familia compatible. Se bloquean SKU eliminados, referencias ambiguas,
  familias incompatibles y SKU de otras familias.
- No hay llamadas de escritura de inventario, eliminación de artículos ni
  modificación de precios de variantes existentes. La sincronización automática
  entre plataformas permanece desactivada y no se registran webhooks.
- Hasta 300 selecciones y 1000 variantes por revisión. Familias grandes se
  dividen en trabajos de hasta 50 variantes; cada uno usa el cargador original.

## Seguridad y ejecución

Los tokens son personales por usuario y catálogo. Se guardan con Fernet mediante
el `CREDENTIAL_ENCRYPTION_KEY` existente de API y worker. No se necesita un token
Loyverse global en Render ni un servicio adicional. Los tokens nunca se devuelven
al navegador; las pruebas pendientes también guardan su token cifrado.

Se reutilizan `IntegrationAccount`, `GenerationBatch` y `GenerationJob`: no hay
migraciones ni cambios en las columnas históricas de productos. Cada trabajo
guarda una instantánea privada cifrada de su conexión en un registro separado,
fuera del payload y de las respuestas de la API. Conserva cuenta, sucursal y datos
revisados aunque el usuario cambie su selección. Eliminar una conexión retira
esas credenciales y detiene las siguientes operaciones de sus trabajos.

Flujo: React → FastAPI → SQL/outbox → Redis/RQ → worker existente → Loyverse.
La cola de imágenes conserva prioridad. La API de publicación solo valida y
encola. Los locks de PostgreSQL serializan escrituras de una misma cuenta, incluso
desde conexiones/usuarios diferentes. Cada ejecución vuelve a consultar los SKU.
Las escrituras remotas no se repiten ciegamente; un resultado incierto permanece
registrado hasta que se consulte el catálogo al reintentar. Hay tres intentos
manuales por trabajo y reintentos acotados de lectura para fallos transitorios.

Los eventos y errores se guardan en SQL. El worker también guarda JSON en
`Publicaciones_Loyverse` dentro de la carpeta Drive de trabajo, separado por
cuenta. Si Drive falla, el historial sigue disponible en la aplicación y se puede
descargar desde cada trabajo. Una imagen fallida se reintenta sobre el artículo
ya creado. Si se perdió la respuesta de creación sin confirmar su ID, se omite
el SKU existente al reconciliar; no se sobrescribe su imagen sin evidencia de
que este trabajo creó el artículo.

Referencia oficial de cuenta, sucursales y ajustes por variante:
https://developer.loyverse.com/docs/

## Verificación y reversión

`test_loyverse_colab.py` usa un transporte remoto controlado; no publica productos
reales. Cubre aislamiento, cifrado, revisión/confirmación, idempotencia, variantes,
respuesta perdida, imágenes, pausa/cancelación, límites y RQ. La concurrencia de
cuenta se prueba además con un PostgreSQL dedicado en CI.

Ejecutar también las cuatro suites WooCommerce y los contratos de generación.
Los cargadores, componentes y referencias protegidos de esas funciones no se
modifican. Para revertir, desplegar el commit anterior en los tres servicios; los
registros nuevos pueden permanecer sin ejecutarse y no se borra información.
