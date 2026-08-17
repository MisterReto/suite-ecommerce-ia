# Integración WooCommerce ↔ Suite Ecommerce IA

## Objetivo

Usar `inventario_completo` como catálogo operativo y sincronizarlo con WooCommerce por SKU, sin guardar credenciales de WordPress en el código.

## Fuente de datos canónica

La hoja principal es **Lista completa**. El esquema actual es:

`sku_padre, tipo, sku, nombre_producto, Marca, descripcion_corta, descripcion_larga, Existencias, categorias, etiquetas, Web link imagen, precio, Precio descuento, imagenes`

`categorias` usa una sola ruta con formato `Categoría > Subcategoría`.

Para determinar si un SKU es simple o variable se deben priorizar las pestañas **Lista Simple** y **Lista Variable**. Esto evita depender de inconsistencias históricas en la columna `tipo`.

## Variables de entorno en Render

Configurar en el servicio de Render, nunca dentro del repositorio:

- `WC_URL=https://rincon.creandotusite.com`
- `WC_CONSUMER_KEY=ck_...`
- `WC_CONSUMER_SECRET=cs_...`
- `WC_WRITE_ENABLED=false`

Mantener `WC_WRITE_ENABLED=false` durante la primera conciliación. Solo cambiarlo a `true` después de revisar el preview SKU por SKU.

## Flujo recomendado

1. Leer `Lista completa` desde Google Sheets.
2. Resolver el tipo de producto usando `Lista Simple` / `Lista Variable`.
3. Buscar cada SKU en WooCommerce.
4. Generar un preview de diferencias de stock, precio y nombre.
5. Resolver SKUs faltantes o duplicados.
6. Habilitar escrituras.
7. Sincronizar stock y después precios.
8. Añadir webhooks de pedidos para descontar existencias en la fuente operativa.

## Seguridad

No usar el usuario/contraseña de `/wp-admin` para esta integración. Crear una clave REST de WooCommerce con permisos mínimos necesarios y rotarla si se expone.

## Próxima fase

Con las credenciales REST configuradas en Render, conectar estos módulos a una pestaña de diagnóstico dentro de Gradio y agregar:

- prueba de conexión;
- contador de SKUs encontrados/faltantes;
- tabla de diferencias;
- botón de sincronización bloqueado mientras `WC_WRITE_ENABLED=false`;
- webhook de pedidos de WooCommerce;
- historial de movimientos de inventario.
