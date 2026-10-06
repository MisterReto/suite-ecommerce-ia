# Acciones pendientes para activar

## Resultado preparado

El PR #25 contiene código, configuración de tres procesos, contrato del generador, documentación y checks. Ningún servicio nuevo ni base se crea automáticamente por estos commits. Los dos servicios existentes siguen en la rama histórica.

| Acción | Dónde | Dependencia |
| --- | --- | --- |
| Completar auditoría formal | Entorno de ejecución funcional | Esta sesión falla al iniciar terminal/leer adjuntos. |
| Revisar coste y autorizar recursos | Render | Worker `0.5c-512mb`, PostgreSQL `0.1c-256mb` + disco; confirmar presupuesto real antes de Apply. |
| Aplicar Blueprint | Render, `deploy/render-platform.yaml`, rama revisada | No adoptar ni borrar servicios históricos. |
| Configurar API/worker | Render Environment | Base interna, misma Fernet, Google y roles reales. |
| Inicializar base nueva | Worker/shell de Render | Una sola ejecución de `catalog_platform.migrate`; no DDL automático al arranque. |
| Configurar frontend | Render build | Origen HTTPS real de API; reconstruir cuando cambie. |
| Registrar callback y origen | Google + Render API | URL real del frontend; sin comodines. |
| Validación real acotada | UI/Drive/Gemini/tienda | Producto conocido, confirmación de consumo, revisión y publicación de prueba. |
| Cambio de entrada y sync | Render | Después del pase real; conservar URLs/variables anteriores para rollback. |
| Leer instrucción literal adjunta | Conversación/archivo | No fue accesible; comprobar requisitos adicionales contra esta entrega. |

Los costes se revisan en [Render Pricing](https://render.com/pricing). No se fija una cifra sin verificar el plan y el presupuesto del workspace. La configuración usa web free para frontend/API; base y worker tienen coste recurrente.

No declarar activa la generación masiva durable antes de que PostgreSQL, esquema y heartbeat estén listos. Ver [DEPLOYMENT.md](DEPLOYMENT.md) y [ROLLBACK.md](ROLLBACK.md).
