# Acciones manuales pendientes

El código se prepara en cleanup/remove-store-integrations-20261012. Producción y servicios históricos siguen intactos.

1. Revisar el diff del PR #28. CI del código 63c1b511 está verde (run 38320147296), incluidos PostgreSQL/Redis de prueba; no fusionar ni desplegar automáticamente.
2. Inventariar por nombre/origen las variables y grupos de los cinco servicios en Render, sin compartir valores. Comparar con docs/ENVIRONMENT_VARIABLES.md.
3. Confirmar presencia real de WC/WP y aliases. Guardar una copia única recuperable en el gestor de secretos existente, fuera de grupos activos; documentar solo ubicación/nombre de entrada. No borrar ni rotar esas credenciales.
4. Preparar la rotación coordinada del secreto expuesto SYNC_SERVICE_SHARED_KEY si aún sirve a los históricos; no modificar esos servicios en esta entrega.
5. Comprobar OAuth real, lectura de imagen existente y Lista completa de inventario_completo, SQL/Redis privados y heartbeat API/worker. No abrir la red ni cambiar destinos.
6. Completar aceptación de catálogo, inventario, archive/restore y móvil/cámara. Usar datos de prueba aprobados y operaciones puntuales, conservando historia.
7. Autorizar por separado cualquier análisis/generación/corrección Gemini real. Hasta entonces esas pruebas siguen pendientes.
8. Después de aceptar el código limpio y autorizar el corte, desplegar los tres servicios coordinadamente y retirar variables C/D solo de su runtime, tras archivo seguro. No tocar históricos.
9. Registrar SHA/deploy/pruebas y ubicación del archivo; usar ROLLBACK.md si falla el corte.

El conector disponible no puede enumerar el entorno completo ni archivarlo de forma segura sin conocer un almacén existente. No se presenta esa tarea como completada. No hay migración de PostgreSQL ni infraestructura nueva.
