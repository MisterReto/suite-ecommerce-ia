# Variables de entorno por servicio

Configurar en Render Environment, combinando las variables existentes. La app no carga `.env` automáticamente. Los ejemplos de `.env.example` no son credenciales operativas.

| Variable | Servicio | Función |
| --- | --- | --- |
| `SUITE_FRONTEND_MODE=standalone` | Build del frontend | Generar servidor Next separado; el Dockerfile lo establece. |
| `SUITE_API_ORIGIN` | Build del frontend | Origen HTTPS real de la API, sin ruta, parámetros ni credenciales. Configuración pública. |
| `SUITE_SERVE_FRONTEND=false` | API | Desactivar alojamiento de la UI exportada; el Dockerfile API lo establece. |
| `APP_PUBLIC_ORIGIN` | API | Origen HTTPS exacto del frontend para validar solicitudes mutantes. |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | API y worker | Configuración OAuth existente. |
| `GOOGLE_REDIRECT_URI` | API y worker | `https://DOMINIO_REAL_FRONTEND/auth/callback`, registrado en Google. |
| `GOOGLE_DRIVE_FOLDER_ID` | API y worker | Carpeta actual autorizada. |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | API y worker, opcional | Cuenta dedicada con acceso explícito a la carpeta. |
| `APP_ALLOWED_EMAILS` | API | Correos autorizados para el acceso Google. Vacío admite cualquier correo Google verificado en el guard histórico. |
| `APP_ROLE_MAP` | API y worker | Objeto JSON de correos y roles admin/editor/viewer; el catálogo rechaza miembros no listados. |
| `APP_DEFAULT_ROLE=viewer` | API y worker | Rol mínimo de la configuración propuesta. No agrega miembros al catálogo. |
| `DATABASE_URL` | API y worker | URL interna PostgreSQL; secreto de servidor. |
| `CREDENTIAL_ENCRYPTION_KEY` | API y worker | Misma clave Fernet, persistida fuera de git. |
| `AI_API_KEY` | API/worker, opcional | Clave IA servidor o conexión por usuario existente. |
| `GEMINI_IMAGE_MODEL`, `GEMINI_TEXT_MODEL` | API y worker, si ya existen | Conservar overrides actuales; no se cambia automáticamente el modelo. |
| `MAX_BATCH_IMAGES` | API | Límite del lote; predeterminado 300. |
| `AI_ESTIMATED_IMAGE_USD` | API | Estimación por imagen, no una factura ni límite integral de consumo. |
| `SUITE_SERVICE_ROLE=main`, `SUITE_DRIVE_ONLY=true` | API | Rol de la nueva API; credenciales ecommerce separadas. |
| `SUITE_SERVICE_ROLE=sync`, `SUITE_DRIVE_ONLY=false` | Worker | Contexto de operaciones servidor. No ejecutar el worker como un servidor web. |
| `SYNC_SERVICE_URL`, `SYNC_SERVICE_SHARED_KEY` | API / sync histórico | Handoff firmado; mantener el secreto existente. |
| `MAIN_SERVICE_URL` | Sync histórico | API emisora del handoff; actualizar al hacer el cambio de entrada y respaldar valor previo. |
| `WOOCOMMERCE_*`, `WORDPRESS_URL`, `WP_USERNAME`, `WP_APP_PASSWORD` | Worker | Clientes existentes de tienda; no copiar al frontend. |
| `WC_WRITE_ENABLED`, `WP_MEDIA_WRITE_ENABLED` | Worker | Habilitar solo para publicación revisada. Inicialmente false. |
| `STOCK_AUTHORITY` | API y worker | Autoridad del inventario: app o Loyverse según operación validada. |
| `WOOCOMMERCE_WEBHOOK_SECRET`, `WEBHOOK_TENANT_ID` | API | Firma y carpeta para eventos de WooCommerce; sin valores devuelve 503. |

No poner secretos en `NEXT_PUBLIC_*`, argumentos Docker, URLs, logs ni archivos versionados. `SUITE_API_ORIGIN` puede ser argumento de build porque solo contiene un origen público. No concatenar una clave a esa URL.

Conservar la misma clave Fernet permite leer conexiones existentes. Una rotación exige recifrado y respaldo; no regenerarla en cada arranque.
