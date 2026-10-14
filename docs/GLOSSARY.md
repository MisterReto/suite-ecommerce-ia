# Glosario con ejemplos del repositorio

| Concepto | Qué significa aquí |
| --- | --- |
| Component | bloque React de pantalla. Platform en page.tsx organiza cinco menús; CaptureStudio controla captura/revisión. |
| Props | datos que recibe el componente. CaptureStudio embedded initialSection="catalog" muestra catálogo compatible. |
| Hook | función React para estado/efectos. useState, useEffect, useRef y useCallback aparecen en ambos componentes. |
| useState | dato de interfaz que redibuja al cambiar: productos, sección, error, online. No es base de datos. |
| useEffect | tarea al montar/cambiar dependencias: registro de conexión y polling de jobs; cleanup elimina timers/listeners. |
| useRef | conserva valor sin redibujar. submitting bloquea segundo clic antes del render en CaptureStudio. |
| async/await | espera red sin cadenas de callbacks. api espera fetch/JSON; no convierte una tarea pesada en worker. |
| Endpoint | método/ruta: POST /api/platform/generation/jobs crea; GET /api/platform/jobs consulta. |
| Router | grupo de endpoints. catalog_platform.api.router tiene prefijo /api/platform y se incorpora en service_entrypoint. |
| Pydantic | valida cuerpos recibidos: BatchInput limita slots/cantidad y ProductInput precio/stock/longitudes. |
| Service | frontera de responsabilidad: DriveService, SheetsService, ImageGenerationService y WooCommerceService envuelven código existente. |
| Provider | contrato intercambiable: Gemini activo; Flux/OpenAI/PhotoRoom preparados sin fallback automático. |
| Proxy | Next reenvía rutas a FastAPI HTTPS conservando cookies; no conoce tokens Google/tienda. |
| OAuth | login/consentimiento Google. app.py intercambia code por credenciales servidor; redirect URI debe coincidir. |
| HttpOnly / Secure | cookie que JavaScript no lee, enviada por HTTPS. Contiene ID sesión, no token Google. |
| RBAC / Role | admin/editor/viewer en servidor. RoleMiddleware y require_role comprueban más que botones. |
| Tenant | carpeta raíz usada como espacio de datos; consultas filtran tenant_id. No es otra BD por usuario. |
| ORM | SQLAlchemy representa tablas como clases Python: Product y GenerationJob. |
| Transaction | database.transaction confirma cambios SQL completos o revierte; no incluye transacciones Google/Woo. |
| Migration | cambio explícito de esquema: migrate.py prepara tablas/batch_id, no corre al abrir pantalla. |
| UUID | identidad interna estable de models.uid; cambiar SKU no cambia IDs externos guardados. |
| Mapping | UUID interno ↔ ID externo en IntegrationMapping; evita depender solo de SKU. |
| Redis / Key Value | transporte rápido de cola; no guarda catálogo ni binarios. |
| Queue / RQ | cola de IDs consumidos por worker. JSONSerializer evita objetos Python arbitrarios/pickle. |
| Outbox | SQL conserva queued si falla Redis; redis_broker.reconcile reentrega después de commit. |
| Worker | proceso independiente de IA/tareas pesadas. execute_job reclama fila y ejecuta pipeline. |
| Heartbeat | señal reciente del supervisor en WorkerHeartbeat para indicar disponibilidad. |
| Lease | reserva temporal lease_owner/lease_until que impide otro consumidor activo. |
| Checkpoint | avance durable: completed_keys, IDs Drive, brief/progreso; no repite éxitos. |
| in_flight | llamada externa iniciada sin confirmación durable: reinicio exige revisión de incertidumbre. |
| Idempotency | repetir la misma intención no la ejecuta otra vez: request_key, ID RQ y eventos/movimientos únicos. |
| Batch | grupo de productos con un job por producto, no 500 imágenes retenidas juntas en RAM. |
| Asset | candidato de GeneratedAsset con producto/job/slot/modelo/raw/estado; aprobar no publica. |
| Raw | imagen anterior a marca; corrección la reutiliza sin duplicar logo. |
| Slot | 1_hd, 2_uso, 3_comercial; parte del naming compatible Drive. |
| Checksum | SHA256 detecta contenido cambiado sin comparar píxeles de generaciones aleatorias. |
| MIME | formato real comprobado con Pillow; extensión .jpg no basta. |
| PWA | instalación móvil por manifest/iconos/standalone/SW; no implica generación offline. |
| Webhook | evento externo: webhooks.py verifica firma Woo y registra antes del 202. |
| HMAC | firma del cuerpo crudo con secreto compartido; compare_digest verifica entrega. |
| Optimistic locking | version de Product rechaza guardar una ficha obsoleta con 409. |
| Rollback | volver a código/configuración validada conservando resultados; no borrar tablas. |
| RSS / OOM | memoria física / terminación por falta de memoria. Render registró OOM; medir nuevo worker antes de dimensionar. |

Una ruta /tmp pertenece al proceso que la creó. Drive file_id permite recuperar
desde otro servicio. Confundirlas provoca fallos que una prueba en un único
proceso puede ocultar; por eso hay pruebas Redis, worker y sesión nueva.
