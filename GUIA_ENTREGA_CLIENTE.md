# Guía de uso · El Rincón de Asia

1. Conecta tu cuenta Google desde la Suite. El administrador debe incluir tu correo
   y rol en la configuración: admin, editor o viewer.
2. En **Más → Ajustes**, selecciona la carpeta existente y conecta Gemini si no está
   configurado por el servidor. La carpeta histórica conserva `inventario_completo`
   y `imagenes_generadas`; no muevas los archivos para instalar esta versión.
3. En **Más → Importar / Exportar**, revisa la vista previa de Excel/CSV o Google
   Sheets y confirma. La app respalda la fuente y el catálogo; omite SKU existentes.
   También se pueden importar fichas, familias e IDs desde WooCommerce.
4. En **Productos**, busca por nombre/SKU/código o usa la cámara para escanear.
   Revisa los datos, añade una foto original de referencia y guarda la ficha.
   Generar IA prepara una propuesta de textos/categorías/etiquetas que debes revisar.
5. En **Generar**, selecciona productos, categoría o pendientes, tipos y cantidad.
   Revisa cantidad total, proveedor, modelo y estimación antes de confirmar el lote.
6. En **Revisar imágenes**, compara con el original, aprueba/rechaza y marca el uso.
   Una corrección genera un candidato nuevo usando la imagen anterior y los
   originales. El archivo anterior se conserva. Aprobar no publica.
7. Un administrador puede publicar desde la ficha de producto. WordPress recibe las
   imágenes aprobadas y WooCommerce guarda sus IDs. El stock se gestiona aparte.
8. En **Inventario**, registra cantidades con motivo y revisa diferencias. Consultar
   tienda lee los datos remotos; sincronizar stock requiere confirmar. Si la tienda
   cambió desde la última lectura, la app detiene la escritura para revisar.
9. En **Más → Sincronización**, revisa errores y abre el producto/trabajo antes de
   reintentar. Una operación incierta requiere comprobar Drive y la tienda.

La PWA se puede añadir a la pantalla de inicio. Sin conexión carga la UI, muestra
el estado y permite reintentar al reconectar; no guarda operaciones offline.
Los lotes aceptados por el worker continúan aunque cierres el navegador.

El catálogo operativo vive en PostgreSQL; Excel y Sheets son intercambio y respaldo.
Las claves para continuar trabajos se almacenan cifradas en el servidor. Nunca se
escriben en el frontend, Drive, Sheets o git. Cerrar sesión retira archivos temporales
privados del proceso; una reconexión restaura acceso al catálogo y trabajos SQL.

Si la Suite muestra “PostgreSQL y worker pendientes”, está en la etapa compatible:
**Generar** conserva la captura de sesión y el guardado histórico en Sheet/Drive.
Los lotes persistentes y el catálogo nuevo requieren activar los servicios
indicados en [la guía de despliegue](docs/platform-rollout.md).

Loyverse es una integración futura. Sus escrituras nuevas se mantienen deshabilitadas.
