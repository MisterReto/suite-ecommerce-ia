# WooCommerce y WordPress en este repositorio

## Activación de la rama de integración · 9 de octubre de 2026

Rama: `feature/woocommerce-and-product-removal-20261009`. Base funcional de
login, códigos de barras y clasificaciones: `07ca7e8`. La activación utiliza
los clientes y trabajos existentes; no añade eliminación de productos ni
cambia credenciales, imágenes, Drive o los dos servicios históricos.

El bloqueo era `SUITE_DRIVE_ONLY=true` en `rincon-catalog-api`: ese modo
rechaza incluso lecturas aunque `WC_WRITE_ENABLED=true`. Configuración de
los servicios actuales, aplicada sin cambiar sus credenciales:

| Servicio | SUITE_DRIVE_ONLY | WC_WRITE_ENABLED | Credenciales |
| --- | --- | --- | --- |
| rincon-catalog-api | false | true, para las herramientas delegadas | Se conservan |
| rincon-catalog-worker | false | true, por autorización del usuario | Se conservan las referencias existentes a WooCommerce |
| rincon-frontend | No aplica | No recibe claves | Solo SUITE_API_ORIGIN |

`sync: false` en los permisos de escritura del Blueprint conserva los valores
que el usuario estableció en Render. No se modifica `WP_MEDIA_WRITE_ENABLED`.
Para desplegar estas mejoras de interfaz/proxy, seleccionar la rama de
integración en los tres servicios nuevos. La rama estable y
`backup/working-oauth-20261009` conservan la base para revertir. La selección
de rama está pendiente: el conector Render no ofrece esa operación y el
acceso seguro al panel se declinó. Los flags ya están activos sobre `07ca7e8`:
API `dep-db4p5to473hc738kcmrg`; worker `dep-db4p5sqd0e5s73d0bhc0`.

La tarjeta WooCommerce consulta el resultado de la última lectura de **su
propio catálogo**: Pendiente antes de comprobar, Conectado al completarla y
Error si falla. No necesita copiar secretos del worker a la API. Se completan
las rutas del proxy para conexión, previews y stock; el login se conserva.

### Pruebas manuales autorizadas, a cargo del usuario

1. Desde el frontend actual, abrir **Más → Sincronización → Consultar tienda**.
   Después de desplegar la rama nueva también se puede entrar desde
   **Conexiones → WooCommerce → Comprobar conexión**.
   Confirmar la consulta y esperar el trabajo;
   una API/worker gratuitos pueden necesitar despertar. Esta consulta lee la
   tienda y guarda snapshots en SQL; no modifica WooCommerce ni importa Drive.
2. Verificar que el trabajo termina correctamente. En la rama nueva, volver a
   Conexiones y comprobar **Conectado**. Si aparece Error, abrir el
   trabajo para revisar permisos/credenciales, sin publicar ni repetir a ciegas.
   La versión anterior puede mostrar «Sin conectar» porque busca claves en la
   API aunque se configuran en el worker; esa etiqueta no bloquea la consulta.
3. Abrir un producto de prueba conocido y verificar su SKU, ID de producto,
   variante y stock WooCommerce antes de confirmar una escritura.
4. Para publicar imágenes, comprobar primero el permiso existente de WordPress
   Media. Si está deshabilitado, esa parte seguirá bloqueada; no se activa
   automáticamente con el permiso de WooCommerce.
5. Realizar una sola escritura confirmada sobre un producto de prueba, comprobar
   el resultado por ID y restaurar su stock si se cambió. Ante un timeout,
   consultar el objeto antes de repetir. No ejecutar la importación completa
   para probar la conexión: esa opción crea respaldos y archivos en Drive.

Reversión inmediata: establecer `SUITE_DRIVE_ONLY=true` en API y worker,
`WC_WRITE_ENABLED=false` en ambos y volver a desplegar para pausar la tienda.
Para revertir código, seleccionar los deploys de `07ca7e8` o la rama
`backup/working-oauth-20261009` en los tres servicios nuevos. Conservar SQL,
las claves y los registros; no tocar servicios históricos. Un rollback no
deshace escrituras manuales en la tienda; usar los IDs y valores iniciales.

## Auditoría anterior

La implementación existente se conserva. Esta auditoría no hizo lectura privada
ni escritura real en la tienda: faltan conexiones operativas en el entorno de
pruebas. Un mapping observado en Sheets no certifica que el objeto remoto siga
existiendo. No generar productos reales para probar.

| Componente | Responsabilidad |
| --- | --- |
| woocommerce_client.WooCommerceClient | configuración servidor, REST, productos/variantes/categorías, límites y errores |
| ecommerce_services.WooCommerceService | ID permanente, lectura/resolve, categorías/pedidos y operaciones del catálogo nuevo |
| wordpress_media.WordPressMediaClient | REST de medios, búsqueda por filename, upload, metadata y permisos de escritura |
| ecommerce_services.WordPressMediaService | upload/get/download/update_alt; valida host de descarga y 12 MB |
| catalog_platform/ecommerce.py | snapshots, mappings y pedidos guardados |
| catalog_platform/worker.py: publication | publicación explícita con versión e imágenes aprobadas |
| catalog_platform/inventory.py: sync_stock | cambio identificado de stock, valor remoto esperado y verificación |
| catalog_platform/webhooks.py | HMAC, registro durable, deduplicación y procesamiento |
| woocommerce_* / publication_web.py / media_web.py | herramientas históricas mantenidas por compatibilidad |

## Identidad y publicación

`Product.id` es la identidad interna; producto y variación guardan sus IDs
WooCommerce. `IntegrationMapping` enlaza la entidad externa. La búsqueda por
SKU sirve para descubrir un objeto todavía no relacionado, no para asumir
que cualquier coincidencia es el mismo producto. Se valida que el ID remoto
continúe teniendo el SKU esperado antes de escribir.

Flujo: generar → revisar → aprobar → confirmar publicación → job → WordPress
Media → guardar IDs → WooCommerce producto/variación → verificar → historial.
El término completed significa generado, no publicado. El worker rechaza una
ficha/version o galería cambiada desde la confirmación. Nuevas escrituras
encoladas no tienen retry HTTP ciego; un timeout deja revisión pendiente.

La API de catálogo exige admin para publicar. `WC_WRITE_ENABLED=false` y
`WP_MEDIA_WRITE_ENABLED=false` mantienen las escrituras bloqueadas por defecto.
Habilitarlas requiere el pase de una imagen y un producto de prueba del plan,
no solo que CI esté verde. Credenciales Consumer Key/Secret y Application
Password van en entorno API/worker, nunca Next ni logs.

## Stock y pedidos

El inventario muestra stock app y WooCommerce; Loyverse queda sin configurar.
La escritura compara `expected_remote` con una lectura actual; si difiere,
rechaza el envío. Se registra InventoryMovement con before/after/delta e ID
de evento. Se vuelve a leer la tienda antes de marcar synced.

Los pedidos son snapshots informativos para Inicio. El procesamiento de un
webhook de pedido no hace otro descuento sobre un stock ya descontado por
WooCommerce. Futura coordinación con POS exige definir compensaciones y
reversión de cancelaciones antes de activarla.

## Webhook WooCommerce

`POST /api/webhooks/woocommerce` y alias `/webhooks/woocommerce` usan:

- cuerpo original y HMAC SHA256 base64, verificado con compare_digest;
- `X-WC-Webhook-Signature`, `X-WC-Webhook-Delivery-ID`, `X-WC-Webhook-Topic`;
- `WOOCOMMERCE_WEBHOOK_SECRET` servidor y `WEBHOOK_TENANT_ID` explícito;
- máximo 512000 bytes en el receptor;
- evento cifrado y único; mismo ID/contenido es duplicado, mismo ID distinto
  contenido es conflicto;
- job durable y respuesta 202; procesamiento pesado en worker.

Un evento product actualiza el objeto mapeado/verificado. Uno order actualiza
el snapshot. Eventos no soportados quedan registrados sin inventar operaciones.
Loyverse no reutiliza esta firma por suposición.

## Pase reversible

1. Leer producto y variación conocidos sin modificar.
2. Subir un JPEG `TEST-INTEGRATION-*` a Media, comprobar ID, URL, alt y tamaño.
3. Crear un producto draft `TEST-INTEGRATION-*`, relacionar media y volver a leer.
4. Emitir webhook de ese producto/pedido de prueba; repetir la entrega y
   comprobar un único evento/movimiento.
5. Registrar stock inicial, acción, esperado y final; restaurar y verificar.
6. Eliminar solo producto/medios creados para esta prueba por sus IDs, después
   de revisar que no los utiliza otro objeto.

El worker no incorpora una eliminación masiva automática. Si existe un resultado
incierto, consultar ID/mapping/metadata antes de repetir o limpiar. Usar
[TEST_PLAN](../TEST_PLAN.md) y [ROLLBACK](ROLLBACK.md).
