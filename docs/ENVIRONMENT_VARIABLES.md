# Variables por servicio y módulo

`.env.example` tiene placeholders. La app no carga `.env` automáticamente;
Render Environment configura los valores en privado. No guardar claves reales
en Git, frontend, NEXT_PUBLIC, una captura o un documento. Los IDs de carpetas
no son secretos, pero la cuenta debe tener acceso.

| Variable | Dónde | Necesaria / efecto |
| --- | --- | --- |
| SUITE_API_ORIGIN | frontend, build | origen HTTPS API, sin path/query/credenciales; obligatorio standalone |
| SUITE_FRONTEND_MODE | build frontend | standalone; export conserva Dockerfile compatible |
| SUITE_SERVE_FRONTEND | API | false separa interfaz del servidor Python |
| APP_PUBLIC_ORIGIN | API | origen HTTPS frontend exacto para CSRF; sin wildcard |
| RENDER_EXTERNAL_URL | Render API automático | valida Host del servicio, no confiar en forwarded Host |
| GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET | API + worker | OAuth actual, requeridos al cargar runtime; reutilizar sin rotar |
| GOOGLE_REDIRECT_URI | API + worker | callback del frontend `/auth/callback`, registrado exactamente en Google |
| GOOGLE_DRIVE_FOLDER_ID | API + worker | raíz autorizada actual; puede seleccionarse en sesión sin cuenta dedicada |
| GOOGLE_SHEET_ID | API + worker, opcional | Sheet nativo exacto dentro de raíz; si falta, búsqueda por nombre inventario_completo |
| GOOGLE_SERVICE_ACCOUNT_JSON | API + worker, opcional | JSON en env privada; cuenta dedicada compartida con raíz; no necesario ahora |
| DATABASE_URL | API + worker | conexión PostgreSQL interna; activa catálogo y jobs durables |
| REDIS_URL | API + worker | conexión interna Redis/rediss; obligatoria en modo rq |
| GENERATION_QUEUE_BACKEND | API + worker | rq en propuesta; postgres conserva mecanismo SQL anterior |
| STUDIO_IMAGE_JOBS | API + worker | worker aísla generación de captura; local es fallback compatible, no aislamiento |
| CREDENTIAL_ENCRYPTION_KEY | API + worker | Fernet válida e idéntica; protege conexiones persistidas |
| IMAGE_WORKER_CONCURRENCY | worker | entero 1–8, default 1; cambiar solo tras medir RAM |
| IMAGE_JOB_TIMEOUT_SECONDS | API + worker | timeout RQ, default 1800; resultado incierto no se repite solo |
| APP_ROLE_MAP | API + worker | JSON email→admin/editor/viewer; autoriza catálogo por membresía |
| APP_DEFAULT_ROLE | API + worker | viewer en propuesta; no sustituye membresía explícita |
| APP_ALLOWED_EMAILS | API | allowlist de login Google; APP_ROLE_MAP sirve de lista si no se proporciona |
| APP_REQUIRE_ALLOWLIST | API | true en nuevo Blueprint; vacío false conserva guard histórico permisivo |
| AI_API_KEY | API | clave Gemini servidor opcional si no se introduce en la sesión; worker usa conexión cifrada |
| AI_PROVIDER | API + worker | gemini; otros proveedores preparados fallan sin fallback pagado |
| GEMINI_IMAGE_MODEL | API + worker | override existente, **no modificar**; default aceptado gemini-3.1-flash-image |
| GEMINI_TEXT_MODEL | API + worker | override existente de investigación; preservar el actual |
| AI_ESTIMATED_IMAGE_USD | API | tarifa estimada opcional; si falta usa registro existente del modelo |
| MAX_IMAGES_PER_BATCH | API | máximo configurable; propuesta 30, código default 300 si no existe alias |
| MAX_BATCH_IMAGES | API, compatibilidad | alias anterior; MAX_IMAGES_PER_BATCH tiene prioridad |
| MAX_ESTIMATED_BATCH_COST | API | techo USD opcional; rechaza coste desconocido o mayor; excluye investigación/QA variable |
| GENERATION_REQUESTS_PER_MINUTE | API | default 12 por sesión; limitador local de una instancia |
| STOCK_AUTHORITY | API + worker | app hoy; Loyverse futuro exige completar nueva dirección de sync |
| WOOCOMMERCE_URL / WOOCOMMERCE_CONSUMER_KEY / WOOCOMMERCE_CONSUMER_SECRET | worker y API si lectura directa | aliases de WC_URL / WC_CONSUMER_KEY / WC_CONSUMER_SECRET existentes |
| WORDPRESS_URL / WP_USERNAME / WP_APP_PASSWORD | worker y API si lectura directa | WordPress/Application Password; nunca frontend |
| WC_WRITE_ENABLED / WP_MEDIA_WRITE_ENABLED | worker + API | false por defecto/propuesta; habilitar solo para prueba controlada |
| WOOCOMMERCE_WEBHOOK_SECRET | API | necesario solo al habilitar receptor WooCommerce |
| WEBHOOK_TENANT_ID | API | raíz a asociar al receptor; sin valor retorna 503 |
| MEDIA_ALLOWED_HOSTS | worker | hosts explícitos adicionales para lectura de medios, no destinos arbitrarios |
| SUITE_SERVICE_ROLE | API/worker | main para API, sync para runtime del worker; worker no arranca un servidor HTTP |
| SUITE_DRIVE_ONLY | API/worker | true API compatible, false worker con ecommerce; credenciales permanecen servidor |
| SYNC_SERVICE_URL / SYNC_SERVICE_SHARED_KEY | API, compatibilidad | puente al sync histórico; no es transporte de jobs de imagen nuevos |
| BACKUP_DIRECTORY | proceso backup, opcional | default /tmp/rincon-backups; exportar dump a ubicación privada durable |
| LOYVERSE_CLIENT_ID / LOYVERSE_CLIENT_SECRET | futuro | placeholders, no OAuth nuevo implementado/activado |
| LOYVERSE_ACCESS_TOKEN | módulo POS futuro/histórico | no necesario para generación; no habilita escritura automáticamente |
| LOYVERSE_WEBHOOK_SECRET | futuro | reservado; ruta continúa inactiva hasta verificar contrato |

`GOOGLE_REFRESH_TOKEN` no es actualmente un bootstrap de entorno del generador:
el refresh token procede de OAuth y se guarda cifrado en la conexión del usuario.
No añadir una variable pensando que por sí sola conectará Drive. La UI devuelve
estados de conexión, jamás tokens.

Antes de activar: copiar configuración vigente sin mostrarla; generar una
clave Fernet **solo si esta plataforma aún no tiene una**, respaldarla fuera de
Git y usarla en API/worker. No reemplazar una clave existente con datos cifrados.
No requieren credenciales nuevas las pruebas con dobles/Redis/PostgreSQL local.
Las conexiones ecommerce/Google se validan por módulo, no se obliga a configurar
Loyverse ni proveedores alternativos para arrancar la aplicación actual.
