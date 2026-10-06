# Despliegue incremental

Estado: código y configuración en el PR #25; infraestructura propuesta separada de producción. La rama de producción sigue siendo `agent/woocommerce-inventory-foundation`, no `main`.

## Antes de activar

Revisar checks verdes del commit exacto, [SECURITY_AUDIT.md](SECURITY_AUDIT.md), backup de código/hoja, coste recurrente y [MANUAL_ACTIONS_REQUIRED.md](MANUAL_ACTIONS_REQUIRED.md). Conservar las variables actuales antes de cualquier cambio. No copiar una plantilla de variables encima de la configuración operativa.

## Crear recursos

Aplicar `deploy/render-platform.yaml` desde la rama revisada; Render permite seleccionar un path de Blueprint distinto de `render.yaml`. Los nombres nuevos evitan adoptar involuntariamente los servicios históricos. La base y el worker tienen planes con coste. El frontend y la API propuestos usan plan free.

Configurar PostgreSQL y clave Fernet idéntica en API/worker. Crear tablas una sola vez en una base nueva:

    python -m catalog_platform.migrate

Arrancar worker y comprobar heartbeat desde `/api/platform/status` autenticado. Configurar el upstream real del frontend y registrar su callback OAuth. Ver [RENDER_SERVICES.md](RENDER_SERVICES.md).

## Comprobación técnica

La CI construye la exportación compatible y Next standalone, typecheck, proxy HTTP con backend local TLS, cookies, redirects OAuth y transferencia íntegra de 12 MB. Valida el Blueprint con el schema oficial de Render. Ejecuta los grupos de pruebas Python, auditoría de dependencias, y concurrencia contra PostgreSQL 17. El contrato del generador se prueba con Python 3.11 y 3.14.

Next requiere `experimental.proxyClientMaxBodySize=13000000` para no truncar el upload antes de llegar a la API. La API mantiene su límite de archivo de 12 MB y validación de imagen. Esta opción experimental está declarada explícitamente y cubierta por la prueba de transferencia completa.

Esto no verifica los contenedores finales en Render, la cuenta Google real ni una llamada Gemini. El proxy conserva el origen visible de la UI; la API mantiene validación de Host y exige el `APP_PUBLIC_ORIGIN` configurado.

## Pase real antes de cambiar la entrada

1. Iniciar sesión con una cuenta permitida y comprobar roles admin/editor/viewer.
2. Importar una muestra del inventario con respaldo, incluyendo una familia/variante.
3. Generar tres vistas de un producto conocido y comprobar dimensiones, marca, identidad y Drive.
4. Corregir una imagen usando el raw previo y conservar la anterior.
5. Cerrar el navegador durante un lote pequeño, reconectar y confirmar progreso persistente.
6. Aprobar y publicar una ficha de prueba explícitamente; releer IDs de WordPress y WooCommerce.
7. Comprobar inventario con versión/evento; enviar un webhook firmado repetido y comprobar deduplicación.
8. Verificar PWA/cámara/navegación en móvil; API e imágenes privadas permanecen fuera del cache.
9. Verificar herramientas sync y su handoff durante el cambio de entrada; aplicar rollback si falla.

No cerrar el PR ni declarar completada la migración durable antes de este pase real. Loyverse físico/webhooks nuevos siguen pendientes de validar su contrato.

Los checks no autorizan gasto ni publicación de productos por sí mismos. La entrada de usuarios solo se cambia después del pase operativo.
