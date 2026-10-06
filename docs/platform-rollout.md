# Activación incremental y validación

## Base auditada

Repositorio `MisterReto/suite-ecommerce-ia`, producción en
`agent/woocommerce-inventory-foundation`, base `41d0599`.
Servicios web existentes: `srv-d9kc2lvavr4c73am1rug` (principal) y
`srv-da3841gae00c73aaour0` (herramientas de tienda). Ambos Docker/free/Oregon,
con auto deploy por commit y sin override del CMD. La inspección encontró **cero
PostgreSQL y cero Key Value** en el workspace ProyectoInventario. No se obtuvo
un listado legible de variables desde el conector; no se inventaron credenciales.

La continuación incorpora la instrucción de tres servicios: frontend Next.js
standalone, API FastAPI y worker Python. El frontend hace proxy de API/OAuth en
un mismo origen visible. La API autoriza APP_PUBLIC_ORIGIN y mantiene Host.
El Dockerfile compatible conserva la exportación durante la transición; los
servicios históricos no se retiran. Ver ../RENDER_SERVICES.md y ../DEPLOYMENT.md.

## Paso 1: revisión y respaldo

1. Revisar el PR y sus checks, incluidos tests con PostgreSQL.
2. Conservar `backup/pre-platform-20261006` y el respaldo de la hoja documentado
   en `backups.md`. No se movió ni borró ningún archivo histórico.
3. Validar costes y aprovisionar PostgreSQL + worker con
   `deploy/render-platform.yaml`. Este archivo es una propuesta separada; no crea
   servicios por estar en git y no reemplaza los web actuales.
4. No usar una base temporal gratuita que caduque para la entrega final.

## Paso 2: configurar, sin escrituras ecommerce

- Base y worker en Oregon, la misma región de los web.
- Clave Fernet válida idéntica en principal y worker; conservarla fuera de git
  junto al backup. Cambiarla sin recifrar deja las conexiones ilegibles.
- `APP_ROLE_MAP` con los correos reales y roles; cuentas no listadas → sin acceso al catálogo.
- `DATABASE_URL` interno en principal y worker. Los web anteriores mantienen
  todas sus variables actuales; añadir mediante merge, nunca reemplazarlas.
- Copiar las variables Google OAuth existentes al worker, mismo redirect URI.
- Configurar la carpeta de trabajo existente por ID; no reorganizarla.
- Store worker: `SUITE_SERVICE_ROLE=sync`, `SUITE_DRIVE_ONLY=false`, credenciales
  WooCommerce / WordPress; escrituras inicialmente `false`.
- No configurar `SYNC_SERVICE_URL` en el worker de catálogo para sus operaciones
  servidor; los web mantienen su delegación actual.
- No introducir claves de IA en `NEXT_PUBLIC_*`. Puede configurarse `AI_API_KEY`
  en el servidor o conservar el ingreso de la clave por sesión.
- Conectar Google en la UI; los trabajos guardan las credenciales cifradas para
  seguir funcionando sin el navegador. Una sesión expirada pide conectar otra vez;
  los trabajos aceptados siguen en SQL.

La cuenta dedicada es opcional: compartir exclusivamente Proyecto_IA con ella,
configurar `GOOGLE_SERVICE_ACCOUNT_JSON` como variable de entorno (nunca archivo
versionado) y `GOOGLE_DRIVE_FOLDER_ID` en principal/worker. En ese modo el login
solicita identidad, y Drive usa los permisos efectivos de la cuenta dedicada.
No activar ni revocar los scopes históricos sin validar acceso a las referencias.

## Paso 3: desplegar la etapa revisada

1. Confirmar que la rama de producción no avanzó respecto al PR; integrar sin force.
2. Render auto deploya al actualizar la rama: no disparar un segundo deploy manual.
3. Comprobar los builds Docker separados, proxy del frontend y URL principal, `/api/session`,
   manifest, iconos, service worker y herramientas sync.
4. Ejecutar **una sola vez** `python -m catalog_platform.migrate` contra una base
   nueva. Crea tablas `rincon_*`; no borra ni sobrescribe datos anteriores.
5. En cualquier base con datos, generar un dump previo antes de futuros cambios
   de esquema. `python -m catalog_platform.backup` requiere `pg_dump` compatible;
   el Docker del worker incluye cliente PostgreSQL. Descargar el dump privado y
   verificarlo (`pg_restore --list`) antes de modificar un esquema operativo.
6. Iniciar worker y comprobar `/api/platform/status` como usuario autenticado.
7. Importar primero una muestra revisada de Sheet/Excel/WooCommerce. La fuente
   y el catálogo se respaldan; SKU existentes se omiten. Las imágenes históricas
   se vinculan por nombres compatibles, sin mover los archivos; faltantes aparecen
   como eventos pendientes. Los padres FULL no reciben precio ni stock.

## Paso 4: validación real, acotada

- Producto conocido con referencia real: generar 1 limpia, 1 lifestyle y 1
  comercial; comprobar fichero JPEG, dimensiones, checksum, model, producto/job
  y Drive. Verificar personas usando/consumiendo y dirección artística comercial.
- Cerrar el navegador durante un lote pequeño; reconectar y comprobar progreso.
- Regenerar una lifestyle con una corrección; comprobar uso de raw anterior,
  originales e historial, y conservación de la imagen previa.
- Rechazar / aprobar y asignar principal/galería/lifestyle/comercial. Generar o
  aprobar no publica automáticamente.
- Confirmar publicación de una ficha de prueba; habilitar escrituras de tienda
  solo en el worker aprobado y verificar IDs WordPress y WooCommerce por relectura.
- Consultar stock/pedidos. Cambio de stock identificado, después sincronización:
  el destino debe coincidir con la lectura anterior o la operación se detiene.
- Evento WooCommerce firmado: reenviarlo y comprobar un solo movimiento.
  Loyverse devuelve 503 hasta validar su contrato; no simular una firma inexistente.
- Móvil: cámara, búsqueda, formularios, revisión, navegación inferior, instalación
  PWA y reconexión. Solo UI pública se cachea; API y fotografías privadas no.

Ningún test con dobles sustituye esta validación con las conexiones reales.

## Recuperación

La cola guarda cada imagen terminada junto al checkpoint. Una operación en curso
sin confirmación se marca incierta y **no** se repite sola. Tras comprobar Drive y
la tienda, un usuario con rol suficiente autoriza el intento adicional. No es una
promesa de exactly-once entre proveedores externos; una caída justo después de
una respuesta externa puede requerir reconciliación manual.

Para volver al código anterior, usar el commit de respaldo o revertir el merge,
conservar PostgreSQL y los archivos nuevos, y retirar solamente la activación de
la plataforma de las variables del web (no borrar recursos ni datos). La hoja
histórica no habrá recibido nuevas fichas del catálogo SQL: exportarlas antes de
volver a un flujo que dependa de ella. No eliminar originales ni ejecutar
DROP/TRUNCATE/DELETE masivo como parte de la recuperación.

## Límites visibles

- La captura compatible sin DB conserva jobs de sesión/proceso y Sheet/Drive;
  es una etapa transitoria, distinta de la generación masiva durable.
- La revisión muestra los últimos 100 assets/jobs; detalle/historial por producto
  muestra los últimos 50. Se limita cada lote a 300 imágenes por defecto.
- La tarifa estimada de imagen 1K excluye texto, referencias, grounding y QA;
  el modelo activo no se cambia automáticamente.
- No hay operaciones offline ni Loyverse físico activo.
- Conexiones muestra presencia de credenciales; el resultado de la consulta confirma
  la conexión y el log muestra errores reales. No se devuelve ningún token.
