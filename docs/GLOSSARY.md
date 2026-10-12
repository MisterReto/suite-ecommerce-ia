# Glosario

| Término | Significado |
|---|---|
| Tenant | Carpeta raíz autorizada que acota datos y credenciales |
| Actor | Usuario autenticado, correo normalizado |
| UUID | Identidad SQL; distinta de SKU/barcode |
| Padre / variante | Familia variable y producto hijo con atributos |
| Job / lote | Operación durable / grupo de operaciones confirmadas |
| Asset | Candidato generado, con raw, slot, revisión y modelo |
| Lease / checkpoint | Propiedad de ejecución y avance seguro persistidos en SQL |
| Incierto | Llamada que pudo consumir; no repetir automáticamente |
| OAuth / Fernet | Autorización Google / cifrado servidor de credenciales |
| RQ / Redis | Ejecutor y transporte de IDs de trabajos |
| Stock local | Existencia SQL; conteos/movimientos del maestro Sheet mantienen rutas existentes |
| Archivado | Estado recuperable del producto; conserva datos, stock, imágenes e historial |
