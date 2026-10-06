# Loyverse: preparación y límites actuales

Loyverse será la autoridad operativa del stock físico cuando se autorice e
integre. Hoy `STOCK_AUTHORITY=app` y no se activó ninguna sincronización POS
nueva. No se presupone la disponibilidad de OAuth o webhooks de una cuenta.

`pos_provider.py` contiene `POSProvider` y `LoyverseProvider` con items, variants,
categories, stores, inventory y receipts. La implementación delega lectura al
`LoyverseClient` histórico. Los módulos `loyverse_sync.py`, `loyverse_jobs.py`
y `loyverse_web.py` conservan herramientas anteriores; esa existencia no
autoriza tocar artículos reales o usar POS como autoridad automáticamente.

`Product` prepara `loyverse_item_id`, `loyverse_variant_id`, `loyverse_store_id`,
stock/fecha de sync. `InventoryMovement` registra producto/variante/tienda y
evento fuente. `IntegrationMapping` conserva relaciones permanentes.

`POST /api/webhooks/loyverse` existe como ruta preparada, pero responde 503;
no verifica una firma imaginada ni procesa inventario sin contrato probado.
`LOYVERSE_CLIENT_ID`, `_CLIENT_SECRET` y `_ACCESS_TOKEN` son opcionales futuros.
No se requieren para imágenes, Drive, Sheets o WooCommerce. No rotar ni crear
credenciales POS para esta fase.

## Antes de activar

- Confirmar en documentación/cuenta real mecanismos disponibles de OAuth,
  scopes, renovación, tiendas, eventos, firma y límites.
- Autorizar lectura sobre items/variants/stores/inventory/receipts.
- Relacionar UUID interno con IDs Loyverse y WooCommerce; revisar SKU ambiguos.
- Probar un artículo `TEST-INTEGRATION-*` y una tienda elegida explícitamente.
- Verificar una venta física: evento Loyverse → API → evento durable → movimiento
  → stock maestro → escritura identificada WooCommerce → lectura de confirmación.
- Verificar una venta web: webhook WooCommerce → evento durable → solicitud
  Loyverse → confirmación. No descontar dos veces el mismo evento ni asumir
  que todas las ventas ocurren en la misma tienda.
- Probar repetidos, fuera de orden, timeout, cancelación/devolución y corrección
  compensatoria. Conservar before/after/delta y source_event_id.
- Solo entonces cambiar la autoridad; el código actual bloquea `sync_stock`
  si `STOCK_AUTHORITY` ya no es app, hasta implementar esa nueva dirección.

Las pruebas de pasos 17–19 de TEST_PLAN permanecen pendientes y condicionadas
a autorización. El proveedor preparado no equivale a una integración activada.
