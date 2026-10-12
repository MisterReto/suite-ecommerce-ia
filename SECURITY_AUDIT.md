# Revisión de seguridad de la limpieza

Alcance: retirada de rutas/clientes/jobs ecommerce, protección de credenciales y conservación de controles OAuth/roles/origen. No se ejecutó un escaneo de seguridad exhaustivo.

Resultados: rutas retiradas 404; retry de jobs históricos 410; worker rechaza antes de cargar OAuth/Gemini; producto JSON sin IDs externos; SQL histórico conserva datos; clave personal cifrada por usuario; middleware y sesión conservados. Los tests usan red externa bloqueada.

Pendientes: inventario real de entorno, archivo WC/WP, rotación coordinada del secreto del puente expuesto, aceptación OAuth/servicios reales y auditoría de dependencias en CI. No se cambia ninguna credencial real.

Ver docs/INTEGRATION_REMOVAL_AUDIT.md y docs/REGRESSION_RESULTS.md.
