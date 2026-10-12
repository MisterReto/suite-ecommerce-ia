# Despliegue de la limpieza

La rama limpia es revisable; **no se ha desplegado ni fusionado**. Se conservan los tres servicios existentes y los dos históricos intactos. No contratar ni crear infraestructura para esta entrega.

1. Esperar CI verde: build/typecheck, proxy/OAuth/móvil, contrato creativo, schema Render y PostgreSQL/Redis de prueba.
2. Completar la aceptación real de Google, Drive/Sheet y servicios privados en REGRESSION_RESULTS.md. No gastar Gemini sin autorización.
3. Verificar nombres/orígenes del entorno real en privado y respaldar configuraciones/credenciales sin publicarlas. No cambiar CREDENTIAL_ENCRYPTION_KEY, DATABASE_URL, REDIS_URL, carpeta, Sheet ni modelos.
4. Revisar manualmente deploy/render-platform.yaml contra servicios existentes; autodeployTrigger está off en la propuesta. No aplicar como un nuevo Blueprint que cree recursos.
5. Preparar el corte coordinado API/worker/frontend y conservar el commit anterior exacto. Usar los Dockerfiles existentes.
6. Cuando el código limpio esté verificado, retirar variables obsoletas y credenciales WC/WP únicamente de los tres procesos activos, después de archivarlas de forma recuperable. No modificar grupos compartidos/históricos automáticamente.
7. Verificar health, OAuth, catálogo, heartbeat y ausencia de llamadas ecommerce. Registrar SHA/deploy y resultados.

API → Redis/RQ y PostgreSQL → Image Worker permanecen. IMAGE_WORKER_ORIGIN mantiene el despertar. El servicio de imágenes sigue siendo web Docker para conservar el health/supervisor existente; esta entrega no cambia tipo/plan ni crea un worker nuevo.

Rollback exacto y deploys anteriores: [ROLLBACK.md](../ROLLBACK.md). Tabla de secretos/defaults/aliases y límites de evidencia: [ENVIRONMENT_VARIABLES.md](ENVIRONMENT_VARIABLES.md).
