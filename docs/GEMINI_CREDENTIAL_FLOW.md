# Clave personal de Gemini

Más → Ajustes permite guardar/cambiar, comprobar modelos y eliminar la clave.
`POST /api/settings` recibe `SecretStr`, valida formato y rol editor/admin y
confirma la carpeta. Requiere PostgreSQL y `CREDENTIAL_ENCRYPTION_KEY`; no
ofrece un guardado efímero como equivalente de persistencia.

| Paso | Función real | Información persistida |
|---|---|---|
| Guardar/cambiar | `studio_api::settings`, `accounts::save_gemini`, `put` | `IntegrationAccount`, provider `gemini`, tenant + actor, Fernet |
| Recuperar tienda | `accounts::save_profile`, `restore` | Provider `studio_profile`, carpeta elegida; prevalece sobre default Render |
| Comprobar | `POST /api/settings/gemini/test`, `test_gemini` | GET `models.list`; no genera texto ni imagen |
| Eliminar | `DELETE /api/settings/gemini`, `delete_gemini` | Tombstone disconnected, sin clave |
| Crear trabajo | `accounts::persist`, `studio_jobs::enqueue_capture`, `api::enqueue` | Conexión Google cifrada, separada de Gemini; actor y tenant del job |
| Ejecutar | `worker::process`, `accounts::load`, `gemini_for` | Se descifra la clave personal vigente de ese actor/tenant |

`accounts::restore` resuelve la clave en cada solicitud. Las respuestas de
sesión solo indican `gemini_configured` y `gemini_source=user_settings` o
`not_configured`. El input es password y se vacía tras guardar; no usa
localStorage, IndexedDB ni cookies para la clave.

`studio_api.py` y `catalog_platform/api.py` ya no adoptan `AI_API_KEY` como
fallback. La variable existente de Render no se borra. No se copian claves
globales/antiguas a registros personales sin la decisión del usuario.

Google mantiene provider `studio`, con OAuth cifrado. `accounts::persist` no
incluye Gemini, por lo que una sesión antigua del worker no puede sobrescribir
una clave recién actualizada. `load` ignora `gemini_key` legado dentro de esos
snapshots. Redis/RQ recibe exclusivamente IDs de job, nunca claves ni fotos.

Cambiar/eliminar afecta a los siguientes trabajos que carguen credenciales.
Una llamada al proveedor que ya está en vuelo no puede revocarse retroactivamente.
Cerrar sesión no elimina el registro personal. Un reinicio de API/worker no
elimina PostgreSQL; se recupera al conectar de nuevo con la misma cuenta/tienda.
La recuperación requiere conservar la misma clave de cifrado del servidor.

`test_functional_parity.py` cubre cifrado/no echo, logout equivalente con nueva
sesión, default Render distinto, cambio/borrado y snapshot obsoleto, aislamiento
por actor/tienda y listado de modelos sin generación. La prueba de Google y
Gemini reales todavía debe registrarse en `../TEST_PLAN.md`.
