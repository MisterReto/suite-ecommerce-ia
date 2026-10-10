# Eliminar productos y detener procesos

Rama: `feature/woocommerce-and-product-removal-20261009`. Base anterior:
`47226a671f7334b1926f8e4511893cecc0fbf056`.

## Uso

En **Productos**, cada tarjeta tiene **Eliminar**. La ficha también incluye
**Eliminar producto**. El administrador confirma el nombre y SKU. La eliminación
afecta únicamente al catálogo PostgreSQL de la app: conserva los archivos de
Drive, `inventario_completo`, WooCommerce, movimientos y trabajos históricos.
El producto deja de aparecer en catálogo, inventario de la app, selección de
generación, exportaciones, imágenes para revisar y contadores.

Se conserva un registro con `status=deleted` y SKU interno `deleted_<id>`. El
SKU original se guarda en la auditoría y queda libre para una nueva creación
explícita. Una lectura corriente de WooCommerce no reactiva registros eliminados.
Se deben eliminar primero las variantes de un padre. Los trabajos en cola de
ese producto se cancelan en la misma transacción. Un trabajo procesando o
deteniéndose bloquea el borrado hasta que esté cancelado.

En **Generar → Trabajos**, **Detener proceso** cancela un trabajo y
**Detener todos (n)** permite confirmar los trabajos activos visibles. Este
último envía sus IDs actuales; no cancela trabajos creados después. Admin puede
detener los del catálogo; editor solo los propios. Viewer conserva acceso de
lectura. Ambas acciones exigen sesión, origen válido y confirmación.

## Cancelación y resultados

- `queued → cancelled`: inmediata en SQL, sin contactar Redis, Drive ni al
  worker. Una entrega RQ anterior no puede adquirir el trabajo cancelado.
- `processing → cancelling → cancelled`: el worker termina la operación ya
  autorizada, guarda su resultado y no inicia otro paso. Se conserva su lease
  durante la llamada y sus checkpoints terminados. Un cargo o escritura que ya
  empezó no se deshace al cancelar.
- Un lease perdido termina como cancelado y conserva `in_flight` si su resultado
  es incierto. Nunca se reentrega una cancelación ni se convierte en reintento
  automático. Los resultados de imagen ya guardados pueden revisarse y aprobarse
  sin quitar el estado cancelado del trabajo.

Los registros de Render del intervalo de los trabajos mostrados por el usuario
incluyen repetidos «Worker pendiente de arranque; el trabajo permanece en SQL»
en la API, sin registros de arranque del worker en ese intervalo. Esto confirma
la falta de consumo observada, pero no demuestra por sí solo la causa del
arranque fallido. Los controles funcionan aunque el worker gratuito esté dormido.
Este cambio no habilita `WP_MEDIA_WRITE_ENABLED` ni altera permisos de la tienda.

## Validación

`test_catalog_controls.py` verifica cancelación sin worker, repetición segura,
permisos/origen/tenant, conservación de resultados de una llamada en curso,
reinicios sin reentrega, cancelación de tres IDs, liberación de SKU, historial,
familias y protección contra reaparición por WooCommerce. PostgreSQL de CI añade
las carreras reales entre adquirir/cancelar y adquirir/eliminar. El navegador
móvil verifica confirmaciones, detener uno/todos, retirada del producto y
controles táctiles de 44 px. El contrato del generador sigue protegido.

No se realizan borrados ni cancelaciones de productos/trabajos reales como
prueba automática. No se cambian credenciales, planes ni los servicios históricos.

## Reversión

No hay migración de esquema. Conservar PostgreSQL, Redis y la clave de cifrado.
Para desactivar los controles conservando eliminaciones/cancelaciones, revertir
la interfaz mediante un commit nuevo en esta rama y mantener los filtros
`status != deleted` y el protocolo de cancelación en API/worker.

Para volver completamente a `47226a6`, registrar los IDs de trabajos y productos
afectados, esperar a que no queden trabajos `cancelling` y verificar los resultados
inciertos. No cambiar `cancelled` a `queued`. El código anterior no filtra los
productos `deleted`; antes de un rollback completo deben restaurarse las fichas
eliminadas que procedan o conservar los filtros de eliminación en la versión
anterior. No desplegar un worker antiguo durante una cancelación en curso.

Una eliminación concreta es reversible desde su auditoría `product.deleted`:
un administrador comprueba tenant e ID, recupera de `before` el SKU, status y
sync_status, verifica que el SKU siga libre y restaura esos campos en una
transacción, incrementando la versión y auditando la restauración. Si el SKU ya
se reutilizó, resolver el conflicto antes; nunca sobrescribir la ficha nueva.
Esto no vuelve a poner en cola sus trabajos ni escribe Drive, Sheets o WooCommerce.

Deploys anteriores de referencia: frontend `dep-db4s07o473hc738u62vg`,
API `dep-db4s07o473hc738u6330`, worker `dep-db4s07o473hc738u62a0`.
El rollback de código no revierte cambios de variables hechos después.
