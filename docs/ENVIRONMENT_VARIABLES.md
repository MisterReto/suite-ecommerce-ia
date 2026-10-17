# Variables de entorno

Auditoría de código y Blueprint: 2026-10-12. **No es un volcado del entorno real de Render.** El conector no ofrece enumeración de variables; están pendientes los nombres/orígenes de los tres servicios actuales y los dos históricos. Nunca imprimir ni copiar valores en logs, Git, capturas o este documento.

A = secreto necesario; B = configuración no sensible; C = obsoleta para runtime limpio; D = credencial archivada que debe conservarse. Que una variable sea eliminable aquí significa una decisión sobre el **código limpio**, no que ya se haya borrado de Render. No se eliminó, archivó físicamente ni rotó ninguna variable real.

## Opciones trasladadas al repositorio, 2026-10-14

`Dockerfile.api` y `Dockerfile.worker` incluyen los valores predeterminados `GENERATION_QUEUE_BACKEND=rq`, `STUDIO_IMAGE_JOBS=worker`, `INITIALIZE_EMPTY_DATABASE=false` y `MAX_IMAGES_PER_BATCH=30`. Una imagen construida con este cambio conserva la cola RQ, el worker separado, el esquema existente y el límite de imágenes aunque se eliminen esas cuatro entradas del panel de Render. Un valor explícito del entorno todavía puede sobrescribir el predeterminado de la imagen.

El Blueprint deja de declarar estas cuatro opciones para que una sincronización no vuelva a crearlas en el panel. `SUITE_SERVICE_ROLE`, `WC_WRITE_ENABLED` y `WP_MEDIA_WRITE_ENABLED` tampoco son necesarios en el API actual: no controlan su comportamiento. La configuración de servicios históricos se revisa por separado.

Estos ajustes viven en los Dockerfiles versionados en GitHub. Las variables de GitHub Actions no se transfieren automáticamente al entorno de Render. Antes de retirar las entradas del panel, se debe construir y desplegar la nueva imagen, o guardar la eliminación con la opción de reconstruir y desplegar el commit nuevo.

Las credenciales de conexión y cifrado siguen configuradas en Render. No se trasladan valores secretos a archivos del repositorio.

## Inventario de lectores y nombres auditados

| Nombre | Categoría | Servicio que la utiliza | Para qué sirve | Secreta | Sigue necesaria | Se puede eliminar | Debe permanecer configurable | Impacto de eliminarla |
|---|---|---|---|---|---|---|---|---|
| `AI_API_KEY` | C | No lector activo; verificar históricos | Fallback global retirado antes de esta entrega | Sí | No para clave personal | Sí actuales tras comprobar históricos | No | La clave personal sigue en SQL cifrado |
| `AI_ESTIMATED_IMAGE_USD` | B | API | Tarifa estimada por imagen; no precio facturado | No | Opcional según modelo | Sí para modelo con default | Sí | Puede perder estimación en otro modelo |
| `AI_PROVIDER` | B | API + worker | Proveedor de imagen existente: gemini | No | Default en código | Sí si Gemini es el proveedor | Sí; sin cambio automático | No habilita proveedores nuevos |
| `APP_ALLOWED_EMAILS` | B | API | Allowlist OAuth adicional | No; contiene datos personales | Condicional con APP_ROLE_MAP | Sí si roles definen la allowlist | Sí | Puede bloquear o ampliar login |
| `APP_DEFAULT_ROLE` | B | API + worker | Fallback viewer con SQL | No | Default seguro en código | Sí si viewer es correcto | Sí | Cambia fallback si no se usa SQL |
| `APP_ENV` | B | API + worker | Entorno para validaciones de DB | No | Opcional | Sí con default revisado | Sí | Puede alterar validación de producción |
| `APP_PUBLIC_ORIGIN` | B | API | Origen navegador para controles de solicitud | No | Sí en arquitectura separada | No | Sí | CSRF/origen rechaza acciones o valida el origen erróneo |
| `APP_REQUIRE_ALLOWLIST` | B | API | Exigir pertenencia; Blueprint true | No | Sí como política | Solo si se conserva equivalente seguro | Sí; true recomendado | Puede ampliar acceso si se relaja |
| `APP_ROLE_MAP` | B | API + worker | Miembros y roles del catálogo | No; contiene correos, no publicar datos reales | Sí | No | Sí | Rechaza miembros o pierde permisos previstos |
| `BACKUP_DIRECTORY` | B | Utilidad backup | Destino de backup explícito | No | Solo si se usa utilidad | Sí en runtime sin utilidad | Sí | Utilidad usa su default; no hay backup automático en esta entrega |
| `BULK_MAX_WORKERS` | C | Módulo retirado / verificar históricos | Parámetro exclusivo de ecommerce/puente retirado | No | No en tres procesos limpios | Sí actuales después de corte; históricos pendiente | No en runtime activo | Sin efecto en flujo limpio; histórico puede depender |
| `CREDENTIAL_ENCRYPTION_KEY` | A | API + worker | Fernet; misma clave existente en ambos | Sí | Sí | No | Sí; sin rotación en esta limpieza | Impide recuperar OAuth/Gemini y sesiones cifradas |
| `DATABASE_URL` | A | API + worker | Conexión SQL existente | Sí | Sí | No | Sí | Pierde catálogo, sesiones, jobs y credenciales |
| `DRIVE_IMAGES_FOLDER_ID` | B | Import local / API + worker | Carpeta explícita opcional para resolver imágenes | No | Opcional | Sí si se resuelve por contexto | Sí | Puede cambiar búsqueda/fallback; revisar naming |
| `GEMINI_CALLS_PER_DAY` | B | API + worker | Límite de llamadas por clave | No | Default del gateway | Sí si default sirve | Sí | Cambia límite al default existente |
| `GEMINI_CALLS_PER_MINUTE` | B | API + worker | Rate limit del gateway | No | Default del gateway | Sí si default sirve | Sí | Cambia presión/esperas |
| `GEMINI_IMAGE_ATTEMPTS` | B | API + worker | Intentos de imagen 1–3, default 1 | No | Default seguro | Sí si default sirve | Sí | Usa 1; afecta reintentos/coste |
| `GEMINI_IMAGE_MODEL` | B | API + worker | Modelo imagen actual; default gemini-3.1-flash-image | No | Default o override actual | Solo si override coincide con default | Sí; mantener igualdad | Rechaza jobs que confirmaron otro modelo |
| `GEMINI_TEXT_MODEL` | B | API + worker | Modelo texto actual; default gemini-2.5-flash | No | Default o override actual | Solo si override coincide con default | Sí; mantener igualdad | Quitar override puede cambiar prompts/resultado |
| `GENERATION_QUEUE_BACKEND` | B | API + worker | rq predeterminado en Dockerfiles | No | Sí en runtime; incluida en imagen | Sí del panel después de construir la imagen nueva | Override opcional | La imagen nueva conserva RQ; imágenes anteriores requieren la variable |
| `GENERATION_REQUESTS_PER_MINUTE` | B | API | Límite de solicitudes de generación, default 12 | No | Default seguro | Sí si 12 sirve | Sí | Usa el default, protege peticiones repetidas |
| `GOOGLE_CLIENT_ID` | B | API + worker | Cliente OAuth; app exige su presencia | No | Sí | No | Sí | No inicia runtime Google |
| `GOOGLE_CLIENT_SECRET` | A | API + worker | OAuth y refresco de tokens del usuario | Sí | Sí | No | Sí | Rompe OAuth y trabajo autónomo del worker |
| `GOOGLE_DRIVE_FOLDER_ID` | B | API + worker | Carpeta raíz existente; selección personal prevalece | No | Sí como default operativo | No sin selección garantizada | Sí | Puede perder destino/acotación Drive |
| `GOOGLE_REDIRECT_BASE` | B | API + worker | Origen frontend para derivar /auth/callback | No | Si no hay URI explícita | Sí con URI explícita | Sí | Sin ambos falla el callback |
| `GOOGLE_REDIRECT_URI` | B | API + worker | Callback explícito; prevalece sobre BASE | No | Uno de URI/BASE | Sí si BASE correcto | Sí | OAuth vuelve al destino incorrecto |
| `GOOGLE_REFRESH_TOKEN` | C | Sin lector activo; verificar históricos | Refresh de usuario está dentro de OAuth cifrado | Sí | No en código actual | Solo tras verificar consumidores históricos | No en runtime actual | Quitar de histórico sin comprobar puede romper su OAuth |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | A | API + worker, opcional | Cuenta dedicada existente, si se usa | Sí | Condicional | Solo si no se usa; confirmar primero | Sí | Cambia acceso Google y scopes del modo dedicado |
| `GOOGLE_SHEET_ID` | B | API + worker | Inventario existente de la carpeta predeterminada; otra carpeta seleccionada busca su propia hoja nativa | No | Sí operativamente | No recomendado | Sí | Depende de discovery, puede resolver otro archivo |
| `IMAGE_JOB_TIMEOUT_SECONDS` | B | API + worker | Timeout de ejecución RQ; default 1800 | No | Default en código | Sí si default sirve | Sí | Tiempo distinto puede cortar jobs |
| `IMAGE_WORKER_CONCURRENCY` | B | Worker | Procesos RQ 1–8; default 1 | No | Default seguro en código | Sí si 1 basta | Sí | Usa 1; afecta RAM/tiempo si se cambia |
| `IMAGE_WORKER_ORIGIN` | B | API | URL pública de despertar del worker existente | No | Sí operativamente con suspensión free | No recomendado | Sí | Worker puede continuar dormido; no reemplaza Redis |
| `INITIALIZE_EMPTY_DATABASE` | B | API + worker / utilidad | Crear tablas solo en DB vacía; default false | No | No para DB existente | Sí del entorno actual tras verificar | Sí solo para alta explícita | No inicializa automáticamente; no cambiar a true |
| `INVENTORY_SPREADSHEET_ID` | C | Módulo retirado / verificar históricos | Parámetro exclusivo de ecommerce/puente retirado | No | No en tres procesos limpios | Sí actuales después de corte; históricos pendiente | No en runtime activo | Sin efecto en flujo limpio; histórico puede depender |
| `LOYVERSE_ACCESS_TOKEN` | C | Módulo retirado / verificar históricos | Parámetro exclusivo de ecommerce/puente retirado | Sí | No en tres procesos limpios | Sí actuales después de corte; históricos pendiente | No en runtime activo | Sin efecto en flujo limpio; histórico puede depender |
| `LOYVERSE_CLIENT_ID` | C | Módulo retirado / verificar históricos | Parámetro exclusivo de ecommerce/puente retirado | No | No en tres procesos limpios | Sí actuales después de corte; históricos pendiente | No en runtime activo | Sin efecto en flujo limpio; histórico puede depender |
| `LOYVERSE_CLIENT_SECRET` | C | Módulo retirado / verificar históricos | Parámetro exclusivo de ecommerce/puente retirado | Sí | No en tres procesos limpios | Sí actuales después de corte; históricos pendiente | No en runtime activo | Sin efecto en flujo limpio; histórico puede depender |
| `MAIN_SERVICE_URL` | B | Solo retirados históricos | Destino redirect de servicio retirado | No | Solo si histórico lo usa | No de histórico sin comprobar | Sí por histórico | Puede romper redirect histórico |
| `MAX_BATCH_IMAGES` | B | API | Alias legado fallback de MAX_IMAGES_PER_BATCH | No | Solo si no hay nombre canónico | Sí si MAX_IMAGES_PER_BATCH configurado | Usar nombre canónico | Sin ambos usa default 300 |
| `MAX_ESTIMATED_BATCH_COST` | B | API | Tope opcional de coste estimado USD | No | Si se aplica política de coste | Solo con decisión operativa | Sí | Deja de bloquear lotes por importe |
| `MAX_IMAGES_PER_BATCH` | B | API | Límite de 30 imágenes incluido en Dockerfiles | No | Sí como límite operativo | Sí del panel después de construir la imagen nueva | Override opcional | La imagen nueva conserva 30; fuera de Docker puede usar el fallback legado |
| `MEDIA_ALLOWED_HOSTS` | C | Módulo retirado / verificar históricos | Parámetro exclusivo de ecommerce/puente retirado | No | No en tres procesos limpios | Sí actuales después de corte; históricos pendiente | No en runtime activo | Sin efecto en flujo limpio; histórico puede depender |
| `NEXT_PUBLIC_SUITE_API_ORIGIN` | B | Frontend derivada | Origen público para despertar API; generado por next.config | No | Derivada; no duplicar en Render | Sí como entrada duplicada | Derivar de SUITE_API_ORIGIN | No necesita variable manual ni admite secretos |
| `OAUTHLIB_IGNORE_SCOPE_CHANGE` | B | Runtime Google | Compatibilidad de scopes; app establece 1 | No | Default existente conservado | Sí como variable duplicada | Conservar comportamiento actual | Sin override sigue default actual |
| `OAUTHLIB_RELAX_TOKEN_SCOPE` | B | Runtime Google | Compatibilidad OAuth; app establece 1 | No | Default existente conservado | Sí como variable duplicada | Conservar comportamiento actual | Sin override sigue default actual |
| `PORT` | B | Worker / Next / uvicorn | Puerto asignado por Render | No | Inyectado por plataforma | No eliminar valor de plataforma | Por plataforma | Health/escucha puede fallar |
| `REDIS_URL` | A | API + worker | Broker Redis/RQ | Sí | Sí | No | Sí | No entrega trabajos al worker |
| `RENDER_EXTERNAL_URL` | B | Origen plataforma | URL pública para referencias de servicios | No | Inyectada por Render | No editar | Por plataforma | Referencias fromService y origen fallback fallan |
| `RENDER_GIT_COMMIT` | B | API + worker + histórico | Identificar build y heartbeat | No | Inyectada por Render | No editar | Por plataforma | Pierde trazabilidad, afecta verificación de versión |
| `RENDER_SERVICE_ID` | B | API | Identificar servicio en health | No | Inyectada por Render | No editar | Por plataforma | Pierde trazabilidad del health |
| `STOCK_AUTHORITY` | C | Módulo retirado / verificar históricos | Parámetro exclusivo de ecommerce/puente retirado | No | No en tres procesos limpios | Sí actuales después de corte; históricos pendiente | No en runtime activo | Sin efecto en flujo limpio; histórico puede depender |
| `STUDIO_IMAGE_JOBS` | B | API + worker | worker predeterminado en Dockerfiles y entrypoint API | No | Sí en runtime; incluida en imagen | Sí del panel después de construir la imagen nueva | Override opcional | API y worker de la imagen nueva conservan generación separada |
| `SUITE_API_ORIGIN` | B | Frontend build | Origen HTTPS de FastAPI | No | Sí con standalone | No | Sí | Build/proxy falla; nunca añadir credenciales |
| `SUITE_DRIVE_ONLY` | C | Módulo retirado / verificar históricos | Parámetro exclusivo de ecommerce/puente retirado | No | No en tres procesos limpios | Sí actuales después de corte; históricos pendiente | No en runtime activo | Sin efecto en flujo limpio; histórico puede depender |
| `SUITE_FRONTEND_MODE` | B | Frontend build | standalone o export | No | Sí para Next separado | No en arquitectura actual | Sí | Default export no conserva proxy standalone |
| `SUITE_SERVE_FRONTEND` | B | API | Compatibilidad hosting frontend; default false | No | Default seguro false | Sí en API separada | Sí | true carga hosting adicional; false mantiene proxy Next |
| `SUITE_SERVICE_ROLE` | C | Solo retired_service; API/worker no lo leen | Etiqueta de health histórico, antes main/sync | No | No en tres procesos actuales | Sí actuales después del corte; conservar históricos | Histórico solamente | Sin efecto en API/worker limpios; histórico usa default |
| `SYNC_DRIVE_CACHE_TTL` | C | Módulo retirado / verificar históricos | Parámetro exclusivo de ecommerce/puente retirado | No | No en tres procesos limpios | Sí actuales después de corte; históricos pendiente | No en runtime activo | Sin efecto en flujo limpio; histórico puede depender |
| `SYNC_INVENTORY_CACHE_TTL` | C | Módulo retirado / verificar históricos | Parámetro exclusivo de ecommerce/puente retirado | No | No en tres procesos limpios | Sí actuales después de corte; históricos pendiente | No en runtime activo | Sin efecto en flujo limpio; histórico puede depender |
| `SYNC_MEDIA_CACHE_TTL` | C | Módulo retirado / verificar históricos | Parámetro exclusivo de ecommerce/puente retirado | No | No en tres procesos limpios | Sí actuales después de corte; históricos pendiente | No en runtime activo | Sin efecto en flujo limpio; histórico puede depender |
| `SYNC_SERVICE_SHARED_KEY` | C | Módulo retirado / verificar históricos | Parámetro exclusivo de ecommerce/puente retirado | Sí | No en tres procesos limpios | Sí actuales después de corte; históricos pendiente | No en runtime activo | Sin efecto en flujo limpio; histórico puede depender |
| `SYNC_SERVICE_URL` | C | Módulo retirado / verificar históricos | Parámetro exclusivo de ecommerce/puente retirado | No | No en tres procesos limpios | Sí actuales después de corte; históricos pendiente | No en runtime activo | Sin efecto en flujo limpio; histórico puede depender |
| `TEST_DATABASE_URL` | A | Solo CI/pruebas | PostgreSQL de prueba | Sí si contiene auth | Solo pruebas PG | Sí de Render productivo si existiera | Sí por entorno de test | Omite regresión PG real; nunca usar DB productiva |
| `TEST_REDIS_URL` | A | Solo CI/pruebas | Redis de prueba | Sí si contiene auth | Solo pruebas Redis | Sí de Render productivo si existiera | Sí por entorno de test | Omite regresión RQ real |
| `WC_CACHE_TTL` | C | Módulo retirado / verificar históricos | Parámetro exclusivo de ecommerce/puente retirado | No | No en tres procesos limpios | Sí actuales después de corte; históricos pendiente | No en runtime activo | Sin efecto en flujo limpio; histórico puede depender |
| `WC_CONSUMER_KEY` | D | Archivo seguro / origen histórico sin verificar | Credencial futura WC/WP; aliases según tabla | Sí o metadato de credencial | No en runtime; conservar archivo | Solo de runtime tras archivo verificado; nunca destruir | Archivo, sin carga activa | No afecta flujo limpio; puede afectar histórico si se quita allí |
| `WC_CONSUMER_SECRET` | D | Archivo seguro / origen histórico sin verificar | Credencial futura WC/WP; aliases según tabla | Sí o metadato de credencial | No en runtime; conservar archivo | Solo de runtime tras archivo verificado; nunca destruir | Archivo, sin carga activa | No afecta flujo limpio; puede afectar histórico si se quita allí |
| `WC_MAX_WORKERS` | C | Módulo retirado / verificar históricos | Parámetro exclusivo de ecommerce/puente retirado | No | No en tres procesos limpios | Sí actuales después de corte; históricos pendiente | No en runtime activo | Sin efecto en flujo limpio; histórico puede depender |
| `WC_METADATA_WORKERS` | C | Módulo retirado / verificar históricos | Parámetro exclusivo de ecommerce/puente retirado | No | No en tres procesos limpios | Sí actuales después de corte; históricos pendiente | No en runtime activo | Sin efecto en flujo limpio; histórico puede depender |
| `WC_TIMEOUT` | C | Módulo retirado / verificar históricos | Parámetro exclusivo de ecommerce/puente retirado | No | No en tres procesos limpios | Sí actuales después de corte; históricos pendiente | No en runtime activo | Sin efecto en flujo limpio; histórico puede depender |
| `WC_URL` | D | Archivo seguro / origen histórico sin verificar | Credencial futura WC/WP; aliases según tabla | Sí o metadato de credencial | No en runtime; conservar archivo | Solo de runtime tras archivo verificado; nunca destruir | Archivo, sin carga activa | No afecta flujo limpio; puede afectar histórico si se quita allí |
| `WC_WRITE_ENABLED` | C | Módulo retirado / verificar históricos | Parámetro exclusivo de ecommerce/puente retirado | No | No en tres procesos limpios | Sí actuales después de corte; históricos pendiente | No en runtime activo | Sin efecto en flujo limpio; histórico puede depender |
| `WEBHOOK_TENANT_ID` | C | Módulo retirado / verificar históricos | Parámetro exclusivo de ecommerce/puente retirado | No | No en tres procesos limpios | Sí actuales después de corte; históricos pendiente | No en runtime activo | Sin efecto en flujo limpio; histórico puede depender |
| `WOOCOMMERCE_CONSUMER_KEY` | D | Archivo seguro / origen histórico sin verificar | Credencial futura WC/WP; aliases según tabla | Sí o metadato de credencial | No en runtime; conservar archivo | Solo de runtime tras archivo verificado; nunca destruir | Archivo, sin carga activa | No afecta flujo limpio; puede afectar histórico si se quita allí |
| `WOOCOMMERCE_CONSUMER_SECRET` | D | Archivo seguro / origen histórico sin verificar | Credencial futura WC/WP; aliases según tabla | Sí o metadato de credencial | No en runtime; conservar archivo | Solo de runtime tras archivo verificado; nunca destruir | Archivo, sin carga activa | No afecta flujo limpio; puede afectar histórico si se quita allí |
| `WOOCOMMERCE_TENANT_ID` | C | Módulo retirado / verificar históricos | Parámetro exclusivo de ecommerce/puente retirado | No | No en tres procesos limpios | Sí actuales después de corte; históricos pendiente | No en runtime activo | Sin efecto en flujo limpio; histórico puede depender |
| `WOOCOMMERCE_URL` | D | Archivo seguro / origen histórico sin verificar | Credencial futura WC/WP; aliases según tabla | Sí o metadato de credencial | No en runtime; conservar archivo | Solo de runtime tras archivo verificado; nunca destruir | Archivo, sin carga activa | No afecta flujo limpio; puede afectar histórico si se quita allí |
| `WOOCOMMERCE_WEBHOOK_SECRET` | C | Módulo retirado / verificar históricos | Parámetro exclusivo de ecommerce/puente retirado | Sí | No en tres procesos limpios | Sí actuales después de corte; históricos pendiente | No en runtime activo | Sin efecto en flujo limpio; histórico puede depender |
| `WORDPRESS_URL` | D | Archivo seguro / origen histórico sin verificar | Credencial futura WC/WP; aliases según tabla | Sí o metadato de credencial | No en runtime; conservar archivo | Solo de runtime tras archivo verificado; nunca destruir | Archivo, sin carga activa | No afecta flujo limpio; puede afectar histórico si se quita allí |
| `WP_APP_PASSWORD` | D | Archivo seguro / origen histórico sin verificar | Credencial futura WC/WP; aliases según tabla | Sí o metadato de credencial | No en runtime; conservar archivo | Solo de runtime tras archivo verificado; nunca destruir | Archivo, sin carga activa | No afecta flujo limpio; puede afectar histórico si se quita allí |
| `WP_MEDIA_METADATA_ENABLED` | C | Módulo retirado / verificar históricos | Parámetro exclusivo de ecommerce/puente retirado | No | No en tres procesos limpios | Sí actuales después de corte; históricos pendiente | No en runtime activo | Sin efecto en flujo limpio; histórico puede depender |
| `WP_MEDIA_WRITE_ENABLED` | C | Módulo retirado / verificar históricos | Parámetro exclusivo de ecommerce/puente retirado | No | No en tres procesos limpios | Sí actuales después de corte; históricos pendiente | No en runtime activo | Sin efecto en flujo limpio; histórico puede depender |
| `WP_TIMEOUT` | C | Módulo retirado / verificar históricos | Parámetro exclusivo de ecommerce/puente retirado | No | No en tres procesos limpios | Sí actuales después de corte; históricos pendiente | No en runtime activo | Sin efecto en flujo limpio; histórico puede depender |
| `WP_URL` | D | Archivo seguro / origen histórico sin verificar | Credencial futura WC/WP; aliases según tabla | Sí o metadato de credencial | No en runtime; conservar archivo | Solo de runtime tras archivo verificado; nunca destruir | Archivo, sin carga activa | No afecta flujo limpio; puede afectar histórico si se quita allí |
| `WP_USERNAME` | D | Archivo seguro / origen histórico sin verificar | Credencial futura WC/WP; aliases según tabla | Sí o metadato de credencial | No en runtime; conservar archivo | Solo de runtime tras archivo verificado; nunca destruir | Archivo, sin carga activa | No afecta flujo limpio; puede afectar histórico si se quita allí |

La tabla incluye todos los nombres leídos en código actual, los lectores de módulos retirados, los aliases de credenciales y nombres expresamente solicitados. Un nombre documentado no prueba que esté configurado en Render. Los tokens OAuth y Gemini personales no se enumeran como env vars: viven en IntegrationAccount cifrado; conservar DATABASE_URL y la clave Fernet existente.

## Defaults y variaciones por servicio

- Frontend: SUITE_FRONTEND_MODE=standalone y SUITE_API_ORIGIN del servicio API. Solo el origen público se expone al navegador, nunca tokens.
- API: STUDIO_IMAGE_JOBS=worker por defecto, SUITE_SERVE_FRONTEND=false por defecto. RQ, origen público, límites, allowlist, roles, carpeta/Sheet siguen configurables.
- Worker: GENERATION_QUEUE_BACKEND=rq, STUDIO_IMAGE_JOBS=worker, DATABASE_URL y REDIS_URL compartidos con API. Concurrencia default 1 y timeout default 1800 permanecen parametrizables.
- CREDENTIAL_ENCRYPTION_KEY: conservar el valor actual en API y la referencia compartida del worker. El Blueprint cambia generateValue por sync:false para evitar generar una clave nueva. No rotar ni regenerar durante esta limpieza.
- Modelo y prompts actuales conservados. No quitar un override de GEMINI_*_MODEL sin comprobar que coincide con el modelo vigente.
- MAX_BATCH_IMAGES es fallback legado: usar únicamente MAX_IMAGES_PER_BATCH en la propuesta. SUITE_SERVICE_ROLE ya no gobierna API/worker. INITIALIZE_EMPTY_DATABASE deja de estar en el Blueprint; ningún alta/migración de DB forma parte del corte.

## Alias de credenciales históricas

| Nombre original | Alias detectado en código anterior | Criterio de archivo |
|---|---|---|
| WC_URL | WOOCOMMERCE_URL | Un único URL confirmado; documentar nombre original |
| WC_CONSUMER_KEY | WOOCOMMERCE_CONSUMER_KEY | Una credencial; no copiarla a dos entradas |
| WC_CONSUMER_SECRET | WOOCOMMERCE_CONSUMER_SECRET | Misma política, sin mostrar valor |
| WP_URL | WORDPRESS_URL | WP_URL solicitado se conserva; WORDPRESS_URL es alias antiguo |
| WP_USERNAME | Sin alias detectado | Conservar nombre y origen |
| WP_APP_PASSWORD | Sin alias detectado | Conservar secreto exacto, sin rotarlo |

WC_URL y WP_URL pueden coincidir, pero son ajustes conceptualmente distintos. No asumir igualdad ni fusionar sin una comparación privada. Las variantes WC_* y WOOCOMMERCE_* se resolvían como alias en sync_bridge_protocol. No crear duplicados para cumplir la lista: conservar lo que realmente existe y registrar alias, presencia y origen.

El Blueprint original toma WC_URL/WC_CONSUMER_KEY/WC_CONSUMER_SECRET/WP_URL/WP_USERNAME/WP_APP_PASSWORD desde suite-ecommerce-ia; el worker usaba aliases para parte de ellos. **La presencia real está pendiente**. No se ha creado un almacén nuevo ni contratado infraestructura.

## Procedimiento de archivo seguro pendiente

1. Enumerar únicamente nombres/orígenes de Environment y Environment Groups de los cinco servicios, en una sesión privada. Confirmar quién depende de cada variable; no compartir valores.
2. En el gestor de secretos existente del propietario, guardar una única entrada WC y otra WP, con URL, nombre de alias, origen Render y fecha; conservar valores exactos. Registrar aquí solo el nombre del almacén/entrada cuando se complete.
3. Verificar de forma privada que las entradas pueden recuperarse y restringir acceso. No ligar este archivo a grupos de entorno activos. Si no existe almacén disponible, conservar temporalmente el origen protegido de Render y no borrar nada.
4. Desplegar/verificar el código limpio en los tres servicios. Retirar de esos procesos las referencias WC/WP, las variables C y la clave del puente; no cambiar históricos automáticamente.
5. Si un Environment Group comparte secretos con históricos, desacoplar primero los servicios actuales sin alterar el grupo ni los históricos.
6. Conservar histórico SQL y credenciales cifradas de antiguos proveedores; accounts.load solo utiliza Google/clave personal. No sobrescribir snapshots históricos.

**Ubicación actual conocida:** referencias al entorno histórico suite-ecommerce-ia según Blueprint original; ubicación efectiva/aliases pendientes. **Archivo separado del runtime:** pendiente. Estas limitaciones impiden afirmar que el inventario completo de Render o el archivo físico ya esté terminado.

## Variables retiradas de la propuesta

Se retiran del Blueprint las referencias WC/WOOCOMMERCE/WP/WORDPRESS, SYNC_SERVICE_URL, SYNC_SERVICE_SHARED_KEY, WC_WRITE_ENABLED, WP_MEDIA_WRITE_ENABLED, SUITE_DRIVE_ONLY, STOCK_AUTHORITY, SUITE_SERVICE_ROLE e INITIALIZE_EMPTY_DATABASE. También se elimina requirements-sync y los lectores de jobs/webhooks/clientes asociados. Se conservan PostgreSQL, Redis, OAuth, cifrado, worker y límites.

SYNC_SERVICE_SHARED_KEY está expuesto en evidencia de la sesión; si sigue válido debe rotarse coordinadamente para sus consumidores históricos. No usarlo ni reproducirlo. La rotación y verificación privada están pendientes; no afectar históricos sin una acción independiente autorizada. Ver INTEGRATION_REMOVAL_AUDIT.md.

## Cambios reales en Render

**Ninguno.** Servicios, grupos, secretos y flags actuales permanecen intactos. El Blueprint es un artefacto revisable y no se ha aplicado.
