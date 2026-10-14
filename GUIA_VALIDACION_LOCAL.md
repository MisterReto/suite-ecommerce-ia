# Validación en VS Code antes del deploy

## Proyecto y cambios locales

La versión actual está en `feature/woocommerce-and-product-removal-20261009`, basada en `7856c0d`. Incluye correcciones para leer los encabezados reales de Sheets, guardar categorías como `categoría>subcategoría`, sincronizar la tabla con el catálogo SQL y refrescar la lista de productos. La eliminación confirmada respalda la hoja, quita la fila y envía las imágenes propias a la papelera de Drive; conserva imágenes compartidas e historial.

Esta guía registra la validación local previa a la publicación y al despliegue. Ninguna prueba local modificó el inventario real. Las verificaciones usan servicios simulados salvo que ejecutes expresamente la tarea de Neon con tu conexión. Comprueba el commit publicado y el estado del deploy en GitHub y Render.

## Abrir y seleccionar el entorno

Abre en VS Code esta carpeta completa:

```text
C:\Users\areta\OneDrive\Documentos\ChatGPT\Rincon de asia local
```

Con la extensión Python de Microsoft, abre `Ctrl+Shift+P`, ejecuta **Python: Select Interpreter** y elige `.venv-platform\Scripts\python.exe`. Es un entorno preparado específicamente para esta rama. Se utilizó Python 3.12 y Node 24 en este equipo; los contenedores de Render utilizan Python 3.11 y Node 22.

Para reinstalar dependencias, usa PowerShell en la raíz sin activar el entorno:

```powershell
.\.venv-platform\Scripts\python.exe -m pip install -r requirements.txt pytest
Push-Location frontend
npm ci --no-audit --no-fund
Pop-Location
```

## Pruebas automáticas

En `Ctrl+Shift+P` elige **Tasks: Run Task** y ejecuta estas tareas:

1. **Rincon: pruebas locales sin servicios reales**.
2. **Rincon: comprobar dependencias Python**.
3. **Rincon: compilar frontend export**.
4. **Rincon: comprobar TypeScript**.
5. **Rincon: compilar frontend separado** para comprobar también el modo de los tres servicios de Render.

Ejecuta los builds uno después del otro: ambos escriben en `frontend/.next`. El build separado usa `https://api.example.test` únicamente para verificar compilación; no representa tu API de Render. Para arrancar ese build con conexión real, utiliza el origen HTTPS exacto del servicio API.

El equivalente principal en la terminal es:

```powershell
.\.venv-platform\Scripts\python.exe scripts/validar_local.py
.\.venv-platform\Scripts\python.exe -m pip check
```

El script ejecuta grupos aislados como la CI, elimina las conexiones operativas de su entorno de pruebas y guarda `validacion-*.log`. No ejecutes toda la suite en un único proceso: algunos grupos históricos usan módulos sintéticos. En Windows habilita UTF-8 y prepara `C:\tmp`, que el código existente utiliza para archivos de prueba.

Para repetir solo las correcciones de Sheets/Drive:

```powershell
$env:PYTHONUTF8='1'
.\.venv-platform\Scripts\python.exe -m pytest test_sheet_catalog_sync.py -q -p no:cacheprovider
```

`pip check` debe responder `No broken requirements found.` Las omisiones de PostgreSQL/Redis real no certifican concurrencia ni recuperación con esos servicios. Usa las conexiones de bases de pruebas dedicadas en CI para esa validación; nunca `TEST_DATABASE_URL` o `TEST_REDIS_URL` con datos operativos.

## Arranque local de la API y la interfaz

Después del build export, ejecuta **Rincon: iniciar API local sin servicios reales**. En otra terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:7860/service-health
(Invoke-WebRequest http://127.0.0.1:7860/ -UseBasicParsing).StatusCode
```

El health debe devolver `ok=True`, `backend=fastapi`, `interface=nextjs` y `session_backend=memory`; la página debe responder `200`. Abre `http://127.0.0.1:7860/`. Ese modo permite revisar el arranque, pero no completar OAuth ni utilizar el catálogo SQL, porque usa credenciales ficticias y no conecta a Neon. Detén el proceso con `Ctrl+C`.

El punto de entrada correcto es `service_entrypoint:fastapi_app`, no el `server:fastapi_app` de la rama `main` antigua.

## Comprobar Neon sin modificar datos

Crea `.env` en la raíz, que Git ya ignora, y agrega únicamente tu cadena real de Neon:

```dotenv
DATABASE_URL=postgresql://USUARIO:CONTRASEÑA@TU_ENDPOINT.neon.tech/BASE?sslmode=require
```

Conserva la cadena completa proporcionada por Neon, incluidos sus parámetros. No compartas el secreto en el chat ni lo subas a Git. Las variables ya exportadas al proceso tienen prioridad sobre `.env`.

Ejecuta **Rincon: comprobar Neon en solo lectura**, o:

```powershell
.\.venv-platform\Scripts\python.exe scripts/comprobar_neon.py
```

El script comprueba el endpoint Neon, `SELECT 1`, TLS en la conexión del cliente y presencia de las tablas/columnas del catálogo dentro de una transacción de solo lectura. No crea tablas, no importa productos y no modifica filas. El resultado debe terminar con código `0` y confirmar conexión, TLS y esquema completo. No demuestra que todas las filas coincidan con la antigua base de Render ni valida Redis o el worker.

No uses `catalog_platform.migrate` para esta comprobación: ese comando sí aplica cambios de esquema. Para una base ya migrada, revisa `INITIALIZE_EMPTY_DATABASE=false` en API y worker.

## Pase funcional con una cuenta y datos de prueba

La app no carga `.env` automáticamente. Para iniciar la API con configuración real utiliza `python -m uvicorn service_entrypoint:fastapi_app --env-file .env` y las opciones de puerto/proxy que correspondan a tu entorno HTTPS. OAuth requiere el callback exacto registrado en Google y el mismo origen HTTPS del frontend en `APP_PUBLIC_ORIGIN`. Conserva la misma `CREDENTIAL_ENCRYPTION_KEY` de la base migrada en API y worker; una clave distinta no descifra las credenciales guardadas.

Con una carpeta/hoja de pruebas y una cuenta autorizada, verifica:

1. Una fila con `Bebidas>Jugos y Sodas` y otra con `Bebidas > Tés e Infusiones` ofrecen categoría `Bebidas` y sus subcategorías correctas.
2. Al guardar un producto, la columna `categorias` contiene `categoría>subcategoría` en una sola celda. Los datos antiguos no se reescriben masivamente.
3. En Inventario → Conteo, carga el inventario de Drive y pulsa **Sincronizar catálogo de la app**. Sin selección se sincronizan las filas visibles; con selección, esos SKU y sus padres. Después de confirmar, los SKU aparecen en Productos con nombre, precio, existencias, categoría y familia. Repetir no crea duplicados ni nuevos movimientos por stock idéntico. Los conteos y movimientos guardados también actualizan el catálogo. Si Drive quedó guardado y falla el espejo, usa Sincronizar catálogo: no repitas el movimiento.
4. Después de confirmar una importación, espera a que el proceso termine; la lista se refresca. Sin un worker conectado, una importación en cola no implica que los productos ya estén incorporados.
5. Al eliminar un SKU de prueba, desaparece de la app y de `Lista completa`; sus imágenes propias están en la papelera y existen respaldos. Una imagen compartida por otro SKU permanece disponible. Un fallo de Drive debe mostrar error y mantener el producto en la app para reintentar.

## Revisar Render antes de desplegar

`deploy/render-platform.yaml` conserva `DATABASE_URL` con `sync: false` para que el Blueprint no sustituya la conexión Neon configurada en el Dashboard. API y worker deben usar la base migrada y la misma clave de cifrado.

El Blueprint apunta a `feature/woocommerce-and-product-removal-20261009` en frontend, API y worker, y mantiene `INITIALIZE_EMPTY_DATABASE=false` para la base ya migrada. Verifica el mismo commit en los tres servicios.

Docker no está disponible en este equipo: los builds locales no certifican la imagen Docker ni el pase real de los proveedores. Revisa el deploy y su commit en el Dashboard de Render después de publicar.

## Resultados observados en esta carpeta

`scripts/validar_local.py` ejecuta los grupos de inventario, plataforma, recuperación y Sheets/Drive por separado. Los grupos se solapan: las cifras no deben sumarse como pruebas únicas. Las omisiones requieren PostgreSQL/Redis reales. Los resultados actualizados se guardan en `validacion-*.log`, excluidos de Git.

Comprueba `pip check`, TypeScript, builds export/standalone, pruebas Node de sonidos y `git diff --check`. Los builds deben terminar con código `0`; el servidor local debe responder `200` en `/service-health`, `/` y `/api/session?auth_only=true`.

El comprobador de Neon requiere tu `DATABASE_URL` real; si falta, termina sin abrir una conexión. Realiza el pase de OAuth y operaciones de Drive con datos de prueba. Las pruebas aisladas no modifican el inventario real ni ejecutan generaciones pagadas.
