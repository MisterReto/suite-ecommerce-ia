# Loyverse: conexión y sincronización de existencias

Abre `/loyverse` desde el servicio principal. Conecta Google Drive y pega un token
personal de Loyverse con STORES_READ, ITEMS_READ, INVENTORY_READ, INVENTORY_WRITE e ITEMS_WRITE para crear artículos.
El token permanece en la sesión del servidor; no se guarda en Drive, Git ni el navegador.
Desconectar o expirar/reiniciar la sesión elimina la conexión.

1. Selecciona la sucursal destino.
2. Compara Lista completa de inventario_completo con Loyverse.
3. Revisa coincidencias por SKU o EAN/UPC/GTIN y cantidades.
4. Selecciona hasta 20 SKU, confirma las cantidades de Drive y envía.
5. Vuelve a comparar para verificar. Un resultado incierto nunca se reintenta automáticamente.

Permite crear productos simples faltantes y familias nuevas completas con variantes.
La revisión muestra nombre (hasta 64 caracteres), precios y atributos antes de crear.
Cada variante conserva SKU y código como texto. Un nombre o referencia ya existente,
SKU/código ambiguo, padre ausente, atributo repetido o dato inválido bloquea la creación.
Las familias parcialmente existentes requieren revisión manual; no se alteran sus hijos.

Los artículos nuevos se crean con stock 0 y se habilitan en la sucursal seleccionada.
Después se compara otra vez para enviar las existencias con la revisión de stock.
No configura impuestos ni sube portadas: revisar esos datos en Loyverse antes de vender.
No cambia precios existentes ni importa ventas automáticamente.
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


La subida responde inmediatamente con una tarea de sesión y muestra progreso por
producto. `Consultar progreso` y recargar la página recuperan el resultado sin
reenviar el lote. Si se corta la conexión, no se reintentan escrituras. Se conservan
los SKU confirmados y se identifica el SKU incierto. Si el servicio reinició,
reconecta y compara con Loyverse antes de enviar otra vez.

La validación inicial lee Drive y el catálogo una sola vez. Antes de cada creación
consulta cambios recientes del catálogo con `updated_at_min` y revalida duplicados;
antes de cada ajuste verifica el stock de esa variación. Las lecturas HTTP tienen
tiempo límite; una tarea deja de iniciar escrituras al alcanzar 10 minutos.
El proceso es temporal, ligado a la sesión, y utiliza un único worker en Render.
