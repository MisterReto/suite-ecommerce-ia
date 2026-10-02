# Loyverse: conexión y sincronización de existencias

Abre `/loyverse` desde el servicio principal. Conecta Google Drive y pega un token
personal de Loyverse con STORES_READ, ITEMS_READ, INVENTORY_READ e INVENTORY_WRITE.
El token permanece en la sesión del servidor; no se guarda en Drive, Git ni el navegador.
Desconectar o expirar/reiniciar la sesión elimina la conexión.

1. Selecciona la sucursal destino.
2. Compara Lista completa de inventario_completo con Loyverse.
3. Revisa coincidencias por SKU o EAN/UPC/GTIN y cantidades.
4. Selecciona hasta 20 SKU, confirma las cantidades de Drive y envía.
5. Vuelve a comparar para verificar. Un resultado incierto nunca se reintenta automáticamente.

Esta entrega sincroniza existencias de productos y variaciones que YA existen en
Loyverse. Identifica productos faltantes y conflictos, pero no crea artículos,
no cambia precios, no sube portadas y no importa ventas automáticamente.
No es sincronización bidireccional ni en tiempo real. Los padres no tienen stock propio.

Las revisiones vencen en cinco minutos y solo pueden usarse una vez. Se releen
Drive y Loyverse antes de escribir; el stock se comprueba otra vez por SKU.
La API usa cantidades absolutas y no ofrece compare-and-swap: evita ventas y
ediciones simultáneas durante ajustes para no sobrescribir movimientos recientes.
Los ajustes a varias filas no son atómicos; la UI informa los SKU confirmados y
el SKU incierto. No se borran artículos ni se modifica track_stock.

Referencia oficial consultada: https://developer.loyverse.com/docs/
Esquema: https://developer.loyverse.com/docs/API-Reference__v1.0.yaml

Pruebas: `python -m pytest test_loyverse.py -q` (HTTP simulado, sin API key real).
