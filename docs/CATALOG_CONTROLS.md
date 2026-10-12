# Controles del catálogo local

Crear/editar conserva validaciones, SKU/barcode, padres/variantes, fotografías, marcas/categorías y control de versión. Los campos de stock externos e IDs de tiendas ya no se exponen; los datos SQL históricos permanecen.

| Control | Permiso | Protección |
|---|---|---|
| Consultar/buscar | Miembro autorizado; viewer/editor/admin | Tenant/carpeta y sesión |
| Crear/editar/stock | Editor/admin | Validación y versión existente |
| Archivar/restaurar | Editor/admin | confirm, versión, sin jobs activos; familia auditable |
| Eliminar local | Admin | confirm + versión; soft delete y cancelación conservada |
| Cancelar jobs | Según actor/rol existente | Confirmación y checkpoints |
| Reintentar | Según actor/rol existente | Idempotencia; tipos retirados responden 410 |

El filtro Archivados permite recuperar fichas. Restaurar conserva el estado anterior registrado en AuditLog, salvo valores inválidos/deleted que vuelven a pending. Archivar no cambia stock ni borra imágenes, Drive, Sheet o historia. La versión previa no ofrece ese control: consultar el paso específico de rollback.

Aprobar una imagen, guardarla en Drive y revisar una ficha siguen siendo operaciones explícitas. No hay publicación a tiendas ni sincronizadores externos.
