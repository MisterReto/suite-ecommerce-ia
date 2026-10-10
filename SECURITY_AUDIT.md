# Seguridad de captura y credenciales — 8 octubre 2026

Auditoría de código y pruebas sintéticas; no es una prueba de penetración.
Complementa la auditoría inicial funcional y la seguridad previa del repositorio.

| Control | Implementación comprobada | Evidencia / límite |
|---|---|---|
| Sesión y CSRF | Middleware existente; `studio_api::session` | Cookies/OAuth same origin; proxy conserva cabeceras |
| Rol para escrituras | `editor` + `security::require_role` en POST/PUT/DELETE del estudio | Viewer no cambia borrador, notas, clave, portada ni guarda |
| Credencial personal | `accounts::put`, `seal/unseal`, `gemini_for` | Fernet por actor/tenant; no echo ni fallback AI_API_KEY |
| Worker correcto | Job actor/tenant → `accounts::load` vigente | Cambio/borrado no revertido por snapshot Google obsoleto |
| Redis | Broker/RQ existente: solo ID de job | Contratos existentes verifican ausencia de secretos y payload fotográfico |
| Fotos privadas | `asset`, `file_path`, namespace + ID opaco | Actor ajeno 404; rutas /tmp no llegan al frontend |
| Fotos reales | `checked_image_type` + Pillow/EXIF | MIME/extensión/bytes, 12 MB y 24 MP; HEIC con decoder opcional |
| Datos estructurados | Pydantic `Product`, límites de campos/atributos | Precios finitos/no negativos; SKU caracteres permitidos; GTIN checksum |
| Fuente Woo por tienda | `woo_rows` asociación de root, GET | Tienda ajena no consulta credenciales globales; modo solo Drive respetado |
| Doble guardado | Lock PG por tienda, fresh read, guardia save_phase, SyncEvent | Sheets incierto se verifica en lectura; repair solo SQL |
| Padre/hijo | `prepare_capture_updates`, `mirror_records` | Una petición Sheets; una transacción SQL; rollback no deja padre parcial |
| Generación/costo | Request key, cotización/límites existentes; contrato protegido | No reintento pagado automático; no llamadas reales en estas pruebas |
| Secretos en UI/logs | `SecretStr`, errores filtrados, password vaciado | Respuestas de pruebas sin claves; no se leyeron valores de env Render |

El catálogo y sus imágenes siguen filtrados por tenant. El borrador persistido
usa tenant + actor y guarda referencias de Drive, no rutas del host. Cambiar
de carpeta invalida los IDs de archivos de la sesión y recupera otro checkpoint;
no traslada fotos al tenant nuevo. Logout conserva la configuración cifrada.

Las claves viejas que pudieran estar en snapshots cifrados Google no se usan.
No se eliminan automáticamente esos registros históricos ni las variables
existentes de Render. Una migración de limpieza de secretos antiguos requiere
su backup y revisión; el flujo nuevo escribe exclusivamente el provider personal.

No se añadió schema SQL, migración masiva ni servicio de pago. Se reutiliza
IntegrationAccount para `gemini`, `studio_profile`, `capture_draft` y SyncEvent
para reparación. La nueva asociación opcional `WOOCOMMERCE_TENANT_ID` solo
restringe una fuente de lectura; no añade permiso de publicación.

## Límites prácticos

No hay commit distribuido entre Google y PostgreSQL. Un Sheet aceptado y SQL
caído queda visible como pendiente y puede verificarse/repararse. La detección
de coincidencias de nombre es una heurística explicada al operador; datos
ilegibles o diferentes dimensiones requieren revisión, no invención automática.

La clave de cifrado API/worker debe ser la misma y conservarse entre deploys.
Fernet protege el almacenamiento, no un proceso servidor ya comprometido.
Las fotos temporales ocupan Drive y siguen su control de acceso; este cambio no
borra originales ni backups y no incluye una política automática de retención.

Faltan el pase de cuentas reales, Safari/Android físicos y uso de Gemini con
presupuesto. No presentar CI sintético como evidencia de esos tres controles.
