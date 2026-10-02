# Optimización sobre la rama desplegada

La producción usa `agent/woocommerce-inventory-foundation`, no `main`.
Se portan las mejoras de consumo de PR #15 conservando los adaptadores de inventario,
la separación principal/sync, las defensas HTTP existentes y `gemini-3.1-flash-image`.

- Extracción y etiquetas en una llamada; pricing en otra (antes tres llamadas).
- Caché JSON en memoria durante 30 minutos por API key, modelo, contenido y configuración;
  máximo 256 entradas; no cachea imágenes, errores ni respuestas truncadas.
- Límites de salida por tarea, prompts/feedback acotados y thinking desactivado en 2.5 Flash.
- `GEMINI_IMAGE_ATTEMPTS=1` por defecto (admite 1–3); QA visual y detección de imágenes
  vacías siguen obligatorios. Un fallo técnico de QA no dispara otra imagen de pago.
- `GEMINI_CALLS_PER_MINUTE=20`, `GEMINI_CALLS_PER_DAY=500` por clave y proceso;
  sin reintentos del SDK. Son límites de llamadas, no de dinero, y se reinician al desplegar.
- PKCE, state de un solo uso, validación de correo verificado y `APP_ALLOWED_EMAILS`
  (correos separados por coma; vacío permite cualquier correo verificado).
- Las rutas temporales de generación usan un identificador distinto del token de sesión.
  El SKU y la pertenencia de las referencias a la sesión se validan antes de generar.

Mantener un proceso/instancia por servicio. `gemini_gateway` registra contadores de tokens
sin secretos a nivel INFO. No se modifica el worker de WooCommerce ni sus permisos.

Pruebas: ejecutar las tres suites unittest existentes de CI y
`python -m pytest test_gemini_costs.py -q`. Las pruebas usan proveedores simulados.
La fidelidad de los prompts y el ahorro monetario necesitan medición con generación real.
