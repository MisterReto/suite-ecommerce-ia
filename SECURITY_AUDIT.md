# Estado de la auditoría de seguridad

Este archivo registra alcance, evidencia y pendientes. No es un informe final de Codex Security ni una certificación de la aplicación.

## Evidencia verificable

| Control | Código/prueba | Alcance de la evidencia |
| --- | --- | --- |
| Roles y aislamiento por tenant | `catalog_platform/security.py`, `rbac.py`, `test_catalog_platform.py` | Pruebas con sesiones/proveedores simulados. |
| Cifrado de conexiones persistidas | `catalog_platform/accounts.py`, `security.py` | Fernet; clave servidor compartida API/worker. |
| Firma y deduplicación de webhooks | `catalog_platform/webhooks.py`, pruebas de plataforma | WooCommerce con dobles; Loyverse permanece inactivo. |
| Archivos privados y propiedad de carpeta | `DriveService.owns`, API de imágenes, pruebas de plataforma/studio | IDs privados y autorización servidor. |
| Origin y Host en separación frontend/API | `app_security.py`, `test_frontend_separation.py` | Origen exacto configurado, rechazo de otro origen/Host y fallo cerrado por configuración inválida. |
| Cookies y transporte del proxy | `test_frontend_proxy.cjs` | Next real y backend TLS local; cookies, redirects y 12 MB. |
| Dependencias | `pip-audit`, `npm audit` en CI | Vulnerabilidades conocidas según los índices en la fecha del run. |
| Recuperación y duplicados | Tests de cola y PostgreSQL real | Checkpoints, leases, solicitudes repetidas y resultados inciertos. |

## Pendientes antes de producción

- Comprobar valores operativos sin imprimir secretos: correos permitidos, roles, origen, callback OAuth, claves servidor y flags de escritura.
- El guard histórico `email_allowed` admite cualquier correo Google verificado si `APP_ALLOWED_EMAILS` está vacío. No confundirlo con la lista de miembros del catálogo `APP_ROLE_MAP`.
- Medir límites integrales de RAM/disco y retención; los límites por archivo/petición no prueban un límite integral de recursos.
- Revisar módulos históricos, variantes de arranque, redirects externos, credenciales de tienda, logs y acciones destructivas en el alcance completo.
- Probar OAuth, Drive, publicación, webhooks y recuperación con conexiones reales antes del cambio de entrada.
- Completar la auditoría formal y guardar sus hallazgos y cobertura.

## Limitación del entorno de esta continuación

La terminal y la descarga de adjuntos fallaron con `setup refresh had errors`; la comprobación previa del flujo formal de Codex Security no pudo ejecutarse. El repositorio y CI se trabajaron mediante GitHub y Render se inspeccionó con su conector. No se declara una auditoría integral completada.

La instrucción textual adjunta tampoco pudo descargarse. Se incorporó el contexto recuperado de “Investigar apps similares”: recuperar control mediante documentación, preservar la generación, mantener Drive/Sheet y separar servicios. El texto literal requiere lectura cuando el adjunto esté disponible.
