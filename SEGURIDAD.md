# Seguridad del runtime limpio

Se conservan OAuth/PKCE, cookies HttpOnly, sesión cifrada/durable, control de origen/CSRF, aislamiento por actor/carpeta, roles servidor, validación/límites de imágenes y redacción de errores.

DATABASE_URL, REDIS_URL, GOOGLE_CLIENT_SECRET y CREDENTIAL_ENCRYPTION_KEY permanecen secretos servidor. La clave de cifrado existente debe coincidir en API/worker; regenerarla impediría leer las conexiones actuales. Gemini personal vive cifrado en SQL; no en navegador, .env versionado o Render como clave de usuario.

Los clientes y receptores ecommerce se retiran, incluyendo sus exenciones de webhook. Un job histórico de integración no carga credenciales ni ejecuta una llamada. La serialización de productos excluye IDs/stock externos, conservando las columnas históricas.

Las credenciales WC/WP se conservan para archivo seguro futuro; no se copian al código ni se rotan sin necesidad. SYNC_SERVICE_SHARED_KEY fue expuesto en evidencia de la sesión; su rotación coordinada está pendiente de verificar consumidores históricos. No usar ni revelar el valor. Consultar docs/INTEGRATION_REMOVAL_AUDIT.md.

Esta revisión no es una certificación de seguridad ni un escaneo exhaustivo. Se verifican las regresiones pertinentes y se mantienen los controles existentes.
