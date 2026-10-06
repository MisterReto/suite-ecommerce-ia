# WooCommerce y WordPress en este repositorio

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
