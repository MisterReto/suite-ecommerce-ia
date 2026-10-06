# Acciones operativas pendientes

No credential change required.

No se encontró un secreto expuesto que obligue a rotar claves. Reutilizar las
conexiones actuales; añadir callback/env para servicios nuevos no requiere
revocar el cliente Google. Staging ya está desplegado en recursos free, sin
tarjeta ni plan pagado. Todavía no se generó con Gemini real ni se escribió en
Drive/Sheet/WooCommerce. Las claves se enlazaron mediante referencias privadas
de Render sin extraer valores. No pegar tokens en chat o Git.

## [x] Revisar y crear staging aditivo en Render

**Qué:** tres servicios nuevos, PostgreSQL y Key Value del Blueprint.
**Por qué:** aislar el frontend, API y proceso de imágenes sin tocar producción.
**Dónde:** Render → Blueprint de esta rama, deploy/render-platform.yaml.
**Esperado/obtención:** rincon-frontend, rincon-catalog-api, rincon-catalog-worker;
BD interna y Redis noeviction; **todos free**, worker como web con health/RQ.
No añadir tarjeta ni aceptar upgrades. PostgreSQL free caduca en 30 días: usarlo
solo para pruebas y conservar Drive/Sheets operativos. No reemplazar servicios actuales.
**Verificación:** cinco recursos free; tres apps live en df88da8, almacenes
available; Dockerfiles/rama correctos. El frontend abre en navegador y muestra
conexión Google sin sesión. IDs y evidencia en docs/RENDER_SERVICES.md.
**Rollback:** detener staging, volver a URLs históricas; conservar datos nuevos.

## [x] Enlazar conexiones y clave de cifrado comunes

**Qué:** DATABASE_URL/REDIS_URL internas, Google vigente, raíz y Fernet.
**Por qué:** worker sin navegador necesita conexiones durables cifradas.
**Dónde:** Render Environment API/worker, nunca Next. **Esperado/obtención:**
referencias PG/Key Value y variables del servicio histórico del Blueprint; raíz
1WNDrC4rMfeg066uciiS5VVOYuTvqoAPT; GOOGLE_SHEET_ID opcional
1gnuDwcceWwN4ksNnyq3Hs_MQHTfnZQZjeLnph72aUrE. Render reutiliza claves Google/tienda
mediante referencias privadas, sin copiarlas al chat. Genera una Fernet nueva
base64 de 256 bits en API; worker referencia ese valor. No reemplazar ninguna
clave si ya hay conexiones cifradas; exportarla en privado con sus datos al
preparar backup/restauración.
**Verificación:** API y worker live con schema/Redis/heartbeat de arranque;
`IMAGE_WORKER_ORIGIN=https://rincon-catalog-worker.onrender.com` enlazado.
La consulta SQL directa por MCP no puede alcanzar la BD aislada; no abrir IPs
para ese fin. Persist/load de conexiones reales y wake de una operación
autenticada siguen pendientes en TEST_PLAN, sin imprimir secretos.
**Rollback:** conservar clave/configuración anterior; detener nuevos jobs.

## [ ] Autorizar administrador y registrar/verificar callback Google

**Qué:** SUITE_API_ORIGIN de build, APP_PUBLIC_ORIGIN API, GOOGLE_REDIRECT_URI
y allowlist/roles. **Por qué:** cookies/CSRF/OAuth deben coincidir con staging.
Los orígenes ya están enlazados y `GOOGLE_REDIRECT_BASE` deriva el callback.
La revisión automática rechazó asignar admin/allowlist al dueño propuesto por
faltar autorización explícita para el destinatario, rol y alcance de los servicios
nuevos. Pedir esa autorización concreta antes de cambiar los permisos; no
abrir acceso mediante un rol predeterminado o un método alternativo.
El registro autorizado de ese callback en Google sigue requiriendo revisión.
**Dónde:** Render y Google Cloud Console → OAuth client.
**Esperado:** orígenes HTTPS sin path/secreto; callback
https://rincon-frontend.onrender.com/auth/callback añadido conservando el antiguo;
APP_REQUIRE_ALLOWLIST=true, APP_ROLE_MAP con admin/editor/viewer reales.
**Verificación:** login permitido/denegado, viewer no escribe, cookies seguras,
401/403 sin datos privados. **Rollback:** frontend/callback viejo; no revocar claves.

## [ ] Backup y migración aditiva SQL

**Qué:** en la BD nueva/vacía del Blueprint, opt-in `INITIALIZE_EMPTY_DATABASE=true`;
desactivarlo después. Para una BD existente: backup y migración manual explícita.
**Por qué:** Render web free no tiene shell/pre-deploy; no cambiar datos existentes
automáticamente. **Dónde:** opt-in en Environment API/worker; una migración de base
existente exige terminal privada externa autorizada.
**Estado:** el esquema nuevo ya se preparó al arrancar API/worker; no se migraron
datos ni se importó el Sheet. El flag de inicialización sigue activado y solo
verifica el esquema existente en reinicios. Backup/restauración sigue pendiente.
**Esperado:** dump restaurable y clave Fernet; lotes/batch_id nullable.
**Verificación:** pg_restore --list y ensayo en base nueva; tablas intactas.
**Rollback:** dejar columnas aditivas; restaurar otra BD si hay corrupción,
nunca DROP de la viva. Exportar dump fuera de /tmp antes de perder la instancia.
La BD vence el 2026-11-05 a las 21:39:57 UTC; exportar datos de pruebas antes
de esa fecha. No hacer entrada a producción con la base que caduca.

## [ ] Validar Drive y Sheet solo lectura

**Qué:** pasos 3–4 de TEST_PLAN. **Por qué:** metadata del conector no prueba
credenciales efectivas del nuevo servicio. **Dónde:** staging autenticado.
**Esperado:** IDs/nombres actuales y Lista completa intacta.
**Verificación:** carpetas, muestra de imágenes, SKU conocido y columnas vacías
O–R. **Rollback:** no hay cambios; detener si falla. No reorganizar archivos ni
otorgar permisos globales para solucionar una lectura.

## [ ] Generación real reversible y RAM

**Qué:** pasos 5–12, referencias conocidas, SKU TEST-INTEGRATION y candidatos
aislados. **Por qué:** tests usan dobles; faltan calidad, disponibilidad, memoria
y coste real. **Dónde:** staging/Gemini actual y carpetas de pruebas autorizadas.
Si hace falta raíz compatible de pruebas, copiar después de solo lectura,
sin mover originales. Registrar IDs de todos los objetos.
**Esperado:** modelo/prompts/naming originales, raw/preview, corrección,
regeneración, jobs por producto y ningún autopublish.
**Verificación:** JPEG >0, formato/dimensiones, producto/slot, Drive/SQL,
re-login tras restart API; restart worker sin tumbar API, memoria de pool/RSS.
Concurrencia 1; si no hay margen, detener y reducir memoria/lote sin contratar
un plan pagado.
**Rollback:** si falla 5–9 detener integraciones; conservar inciertos, restaurar
solo archivos/celdas de prueba por ID, volver a deploy anterior.

## [ ] Media/Woo y stock de prueba

**Qué:** pasos 13–16 y 19 aplicable, solo TEST-INTEGRATION.
**Por qué:** tienda real no verificada en esta ejecución.
**Dónde:** staging/tienda con draft eliminable; flags habilitados solo para pase.
**Esperado:** leer producto/variación, un medio/draft, webhook repetido sin
duplicar y movimiento before/after identificado.
**Verificación:** readback, IDs/URL/alt, evento único, stock final/restaurado.
**Rollback:** flags false, limpiar IDs de prueba sin uso y compensar stock.

## [ ] Cambiar entrada pública después del pase

**Qué:** usar frontend nuevo conservando servicios y backups antiguos.
**Por qué:** evitar reemplazo sin validar generación/datos.
**Dónde:** URLs/dominio Render. **Esperado:** checklist verde, planes/RAM elegidos,
fuente Sheet/SQL explícita; conservar sync si hay herramientas delegadas.
**Verificación:** monitoreo y rollback ensayado.
**Rollback:** URL/commit anterior, conservar datos, exportar nuevas fichas SQL
para conciliarlas con Sheet.

## [ ] Loyverse futuro, cuando se autorice

**Qué:** lectura/artículo de prueba, OAuth/firma/eventos reales y reglas stock.
**Por qué:** preparación no habilita POS ni permite descontar inventario físico.
**Dónde:** cuenta/tienda elegida. **Esperado:** IDs/eventos idempotentes; autoridad
Loyverse solo después de pase. **Verificación:** pasos 17–19, repetidos y cancelaciones.
**Rollback:** desactivar nueva dirección, movimientos compensatorios y conexiones
vigentes conservadas.

Ver TEST_PLAN y docs/ROLLBACK.md. Estas acciones no son necesarias para ejecutar
las regresiones automáticas sin conexiones reales.
