# Flujos de solicitudes

| Acción | Recorrido | Resultado |
|---|---|---|
| Conectar Google | Next /login → /auth/start → FastAPI OAuth/PKCE → callback por proxy | Sesión HttpOnly y permisos conservados |
| Guardar clave Gemini | Más → Ajustes → studio_api.settings → accounts.save_gemini | Registro cifrado por actor/carpeta |
| Capturar / analizar | CaptureStudio → studio_api → ProductCapture/Gemini | Análisis y borrador, sin tienda externa |
| Detectar coincidencias | capture_bridge / catalog_capture | Catálogo local + Sheet |
| Crear/editar familia | catalog_platform.api / capture_bridge → SQL + mirror puntual existente | Padres/variantes, versión y auditoría |
| Generar | Confirmación/estimación → job SQL → Redis/RQ → worker → Gemini | Candidatos, raw y checkpoints |
| Corregir/regenerar | Revisión → nueva operación confirmada → mismo pipeline | Historial anterior conservado |
| Guardar aprobado | asset_save / ProductCapture.save → Drive y catálogo | Naming/backup existente |
| Stock local | API autenticada → transacción SQL | Stock y AuditLog |
| Conteo/movimiento Sheet | InventoryTools → native_tools → sheet_inventory | Escritura puntual confirmada |
| Archivar/restaurar | POST producto/archive o restore + confirm/version → SQL | Estado y auditoría; stock/Drive intactos |
| Eliminar local | DELETE producto + confirm/version → soft delete | Historial y archivos externos intactos |
| Reintentar job histórico retirado | POST jobs/id/retry | 410; no carga credenciales ni encola |

La separación de los tres servicios y los contratos de idempotencia/checkpoints no se sustituyen por el puente histórico. El código de las tiendas retiradas se recupera desde Git, no desde módulos cargados en producción.
