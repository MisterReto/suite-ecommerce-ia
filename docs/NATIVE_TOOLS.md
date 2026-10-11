# Herramientas integradas y retirada de Gradio

Solicitud del 10 de octubre de 2026 (México). Base de la app nueva: `a7869dc`.
La única interfaz pública es `https://rincon-frontend.onrender.com`.

Las herramientas se eligen en el lateral de escritorio o en la franja desplazable
sobre los cinco accesos inferiores del celular. Se retiraron las pestañas de sección
que estaban en el contenido y los enlaces que abrían otra aplicación. Los filtros
de productos y las acciones de una ficha siguen junto a sus datos.

| Herramienta | Ubicación / enlace | Código |
| --- | --- | --- |
| Captura | Productos o Generar → Capturar; `/#generate/capture` | `CaptureStudio.tsx`, lógica existente |
| Generación masiva, revisión, trabajos | Generar → herramienta lateral/inferior | `Platform`, `page.tsx`, APIs SQL existentes |
| Conteo, movimientos, historial, comparación | Inventario → Conteo y movimientos; `/#inventory/count` | `InventoryTools`, modo `count` |
| Imágenes Drive y WordPress | Más → Revisar Drive y WordPress; `/#more/media` | `InventoryTools`, modo `media` |
| Publicación por lotes, pausa, reanudación | Más → Publicación masiva; `/#more/publication` | `InventoryTools`, modo `publication`; `batch_web_v2` |
| Conexiones, sincronización, importar/exportar, ajustes, ayuda | Más → herramienta lateral/inferior | APIs y lógica existentes de `Platform` |

## Dónde corregir un fallo

| Síntoma | Archivo / función | Regla que conservar |
| --- | --- | --- |
| Menú mal colocado o enlace incorrecto | `page.tsx`: `sectionTools`, `selectedTool`, listener `change`; `globals.css`: `.p-subnavigation` | Un menú compartido, lateral/inferior, botones de al menos 44 px |
| Formulario o conteo nativo falla | `InventoryTools`: `request`, `loadInventory`, `inspectHistory`, `confirm` | Consultar no publica; cada escritura requiere confirmación |
| Pausar inicia otro grupo | `InventoryTools.runBatch`; refs `pause`, `mounted`, `activeTool` | Comprobar pausa después del GET de estado y antes de cada POST; no repetir resultados inciertos |
| API devuelve HTML / abre una página separada | `native_tools.register` / `execute`; `server.pause_store_tools` | `/api/tools/*` devuelve JSON, nunca redirige a la interfaz antigua |
| Falla la integración firmada | `sync_gateway.forward_tool`, `sync_service.tools`, `sync_bridge_protocol.TOOL_PATHS` | HMAC, expiración, nonce único y contexto por solicitud; sin refresh token, clave Gemini ni secreto OAuth |
| Dominio antiguo vuelve a Gradio | `retired_service.py`, `Dockerfile.retired`, rama histórica | GET/HEAD redirige al frontend; no se monta ninguna interfaz vieja ni OAuth antiguo |

## API de las herramientas

`native_tools.register` expone el mismo contrato en la API y en el ejecutor firmado.
La API usa la sesión durable y los roles existentes. La integración comercial sigue
respetando `SUITE_DRIVE_ONLY`, `WC_WRITE_ENABLED` y `WP_MEDIA_WRITE_ENABLED`; esta
entrega no modifica sus valores, sus clientes ni la lógica comercial.

| Operación bajo `/api/tools/` | Método | Función / permiso |
| --- | --- | --- |
| `inventory?q=...` | GET | Inventario, conteos pendientes, reglas de portadas |
| `history?sku=...` | GET | Hasta 50 movimientos; historial vacío sin crear su hoja |
| `review` | GET | Comparar Sheets/WooCommerce, sin modificar la tienda |
| `media-preview` | GET | Coincidencias Drive/WordPress/WooCommerce y permisos públicos |
| `batch-status?batch_id=...` | GET | Consultar lote, sin reanudarlo |
| `counts`, `movement` | POST | Admin/editor y `confirm: true`; callbacks anteriores |
| `media-sync`, `product-sync` | POST | Admin y `confirm: true`; sincronización individual anterior |
| `batch-create`, `batch-step`, `batch-resume` | POST | Admin y `confirm: true`; lote, grupo o reanudación |

El navegador no reintenta automáticamente un POST. Solo envía el siguiente grupo
tras consultar el estado y comprobar que el usuario sigue en la herramienta y no
pidió pausa. Cambiar/cerrar la pantalla impide otro grupo; el ya iniciado termina
y conserva su resultado. Se guarda el ID por cuenta y carpeta en el navegador.
Consultar un lote recuperado no inicia publicaciones. En una respuesta perdida,
se muestra el error y se exige revisar el resultado antes de reanudar.

## Orígenes históricos

`suite-ecommerce-ia` y `suite-ecommerce-ia-ai` usan una imagen de retirada basada en
`Dockerfile.retired`, sin construir una interfaz ni instalar Gradio. Sus variables
se conservan porque el Blueprint referencia credenciales existentes.
`retired_service.app` redirige al frontend y responde 410 a escrituras públicas
antiguas. Nunca copia cookies, códigos OAuth, state ni parámetros entre dominios.

El servicio con rol `sync` conserva únicamente `/internal/tools`, con la firma
existente: es el backend de integración de la app nueva, no otra aplicación
pública. No eliminar ese contrato o las referencias de credenciales para corregir
un menú. La ruta pública `/service-health` indica `interface: redirect` y
`gradio: false`. Los enlaces antiguos en Next/FastAPI también llevan a las
pantallas nativas. La PWA cambia de caché; no guarda respuestas ni fotos privadas.

## Pruebas y reversión

Pruebas sintéticas: 360/390/430 px y 1280 px, herramientas laterales/inferiores,
conteos confirmados y portadas sin stock, pausa durante un grupo, proxy de
cookies, roles/confirmación, puente firmado y su nonce, historial vacío sin
creación. También deben pasar OAuth, sesión, clasificación, códigos de barras,
sonidos y el contrato del generador. No se generan imágenes de pago ni se escriben
productos, archivos Drive o inventarios personales como prueba automática.

Base de frontend/API: `a7869dc9ed7204de838f268efa6da96051907783`.
Base de servicios históricos: `41d0599a45dda1edca13b1c253a68524e3567ad2`.
Revertir los commits de esta entrega en sus ramas, sin reset ni force push.
Coordinar ambos reverts: la UI nativa necesita el adaptador JSON del ejecutor.
Pausar y esperar el grupo actual; restaurar primero el backend histórico y después
frontend/API al par anterior. Los lotes permanecen en Sheets. No hay schema,
secretos ni migraciones que deshacer. El rollback vuelve a exponer la interfaz
histórica y debe usarse solo para recuperación deliberada.
