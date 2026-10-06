# Auditoría de seguridad del proyecto

Fecha: 2026-10-06. Alcance: código de plataforma y módulos históricos invocados,
historial accesible, configuración declarada, Render/Drive/Sheet de solo lectura,
dependencias y regresiones. No se consultaron valores secretos Render ni se
realizó una prueba de intrusión de producción. No declarar todos los controles
operativos validados por tener pruebas con dobles.

## Clasificación y hallazgos

CRITICAL: pérdida masiva/exposición privilegiada confirmada. HIGH: acceso o
integridad importante. MEDIUM: requiere condiciones adicionales o deja un
control incompleto. LOW: endurecimiento. INFO: límite o hecho operativo.

| ID | Severidad | Evidencia / estado | Acción |
| --- | --- | --- | --- |
| SEC-01 | HIGH | oauth_guard.email_allowed histórico acepta cualquier Google verificado si allowlist vacía. No se conocen env actuales. | Nuevo Blueprint exige APP_REQUIRE_ALLOWLIST=true; APP_ROLE_MAP/allowlist cierran login. Verificar producción sin cambiarla antes del pase IA. |
| SEC-02 | HIGH | OAuth usa scope drive amplio; ownership limita app, no el token. | No revocar. Probar alternativa de mínimo privilegio/cuenta dedicada compartida antes de sustituir. Pendiente operativo. |
| SEC-03 | HIGH | Generación captura inicial en API/RAM; OOM Render 512Mi confirmado. | Modo worker con SQL/RQ, pool aislado y concurrency 1. Medición real y reinicio en staging pendientes. |
| SEC-04 | HIGH | _subir_imagen_drive histórico reemplaza contenido por nombre sin backup. | En modo separado delega a save_approved; copia antes de reemplazar, rechaza duplicados. Modo productivo viejo intacto. |
| SEC-05 | HIGH | Llamadas pagadas/escrituras interrumpidas pueden ser inciertas. | in_flight + leases + checkpoint + revisión obligatoria; no retry automático. Regresiones verdes, ensayo real pendiente. |
| SEC-06 | MEDIUM | URLs HTTPS validan host textual; DNS rebinding y todos los redirects de clientes históricos no están demostrados cubiertos. | Descarga nueva WordPress usa host allowlist y sin redirects. Revisar clientes históricos antes de permitir URLs no confiables. |
| SEC-07 | MEDIUM | Sesiones, rate limit y locks de captura son locales a API. | Una instancia/proceso inicial. Varias réplicas exigen sesiones/limitador distribuido; jobs ya son durables. |
| SEC-08 | MEDIUM | Sheets no aporta CAS/transacción con SQL ni garantía contra edición humana entre read/write. | Celda precisa, SKU único, cobertura de pestaña, expected/readback; prueba reversible, sin sync masivo. |
| SEC-09 | MEDIUM | Clientes/callbacks históricos tienen mensajes y excepciones que requieren verificar en logs reales. | Errores nuevos redactan secretos/contexto; sin access log en Docker API, worker no imprime payload. No afirmar sanitización universal de todos los módulos heredados. |
| SEC-10 | MEDIUM | Free Key Value de staging no persiste; capacidad sin validar. | SQL outbox y reconciliación probados. Revisar plan persistente/retención para producción. |
| SEC-11 | LOW | CSP conserva unsafe-inline para Next/estilos. | Headers nosniff/frame/HSTS/permissions; nonces se mejorarán separadamente. |
| SEC-12 | INFO | No .env real, claves de patrones conocidos o private key encontrados en archivos y 208 commits accesibles. | No requiere rotación por un hallazgo inexistente. El escaneo no prueba ausencia de todo secreto posible. |
| SEC-13 | INFO | pip-audit de requirements y npm audit producción no reportan vulnerabilidades conocidas. | Nuevas dependencias fijadas RQ/Redis; no upgrade general. Repetir al cambiar lock. |
| SEC-14 | INFO | Loyverse nuevo webhook bloqueado 503; proveedores alternativos no habilitados. | No usar firma supuesta ni fallback pagado; autorización/contrato reales pendientes. |

No hay un hallazgo CRITICAL confirmado en el alcance observado. No significa
que producción esté certificada ni que todo su entorno sea conocido.

## Cobertura de controles

| Control | Código / evidencia | Límites pendientes |
| --- | --- | --- |
| Secretos / env / frontend | archivos + parches de 208 commits; .env.example vacío; Next solo origen API | valores Render privados; patrones no exhaustivos |
| Autenticación | OAuth state/verifier, email verificado/allowlist; app.py, oauth_guard.py | login real en nuevo dominio/callback |
| Autorización | RoleMiddleware, context, require_role y tenant/product ownership | comprobar herramientas históricas habilitadas |
| CORS / CSRF / Host | proxy mismo origen, Origin/Referer exacto, Host API; sin wildcard CORS | APP_PUBLIC_ORIGIN real; webhook exento por firma, no cookie |
| Sesiones / cookies | HttpOnly/Secure/SameSite, expiración, logout y no-store | locales; re-login tras reinicio |
| SQL | SQLAlchemy/parámetros; DDL aditivo fijo; locks/versiones | concurrencia PG real en CI; no extrapolar SQLite |
| Uploads | 12 MB, MIME Pillow, 24 MP, verify, nombre/path traversal; 413 HTTP | memoria integral con archivos grandes simultáneos |
| Webhooks | HMAC raw, tamaño, IDs/hash únicos, payload cifrado, worker | entrega Woo real; Loyverse bloqueado |
| Drive | owns/root, downloads limitados, candidatos privados y backup | scope OAuth amplio, ACL/duplicados completos no auditados |
| Sheets | rangos precisos, headers compatibles, SKU único, expected | datos completos/carreras humanas; nunca sobrescribir por una celda |
| APIs / SSRF | HTTPS sin credenciales/query/private IP; allowlist media, no redirect nuevo | resolución DNS/clientes históricos |
| Logs | public_error [REDACTED], error_message con clave de sesión, sin payload/cookie/Authorization nuevos | revisar logs staging sin copiar valores al informe |
| Headers / XSS | CSP/nosniff/frames/HSTS API/no-referrer, bleach HTML, React escaping | unsafe-inline; observación real de proxy/hosting |
| Rate limit / gasto | límite sesión, ref doble clic, request_key, imágenes/USD/token de estimación | no distribuido; research/QA variable fuera de estimado |
| Cola / filesystem | JSONSerializer, ID SQL, post-commit/lease/outbox, /tmp propio y cleanup | exportar backups temporales; retención Drive manual |
| Render / DB / Redis | nombres aislados, private network, contenedores sin root | recursos no provisionados; plan/RAM reales |
| AuditLog / integridad | precio/stock/review/publicación/lotes/jobs/sync/eventos e IDs permanentes | retención/acceso operativo del historial |
| Dependencias | versions/locks, pip-audit, npm audit/CI | índices evolucionan; resultado representa fecha/run |

## Gate de producción

Regresiones protegen AST del generador, roles/tenant, uploads corruptos/grandes,
errores sin clave, aprobación/QA, idempotencia, firmas, leases/incertidumbre,
Redis real, cookies/proxy y backup antes de reemplazo. IA/Drive/Woo privados son
dobles: no hubo gasto ni escritura real.

Antes de cambio de entrada: comprobar roles/callbacks, flags de escritura,
ACL/scopes, logs seguros y RAM; completar TEST_PLAN. Si falla generación real
en 5–9 se detiene. Consultar MANUAL_ACTIONS_REQUIRED. No rotar credenciales
actuales ni otorgar acceso Drive global adicional por esta auditoría.
