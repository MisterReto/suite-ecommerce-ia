# Acciones para cerrar la aceptación real

La restauración de código y CI no equivalen a completar el tutorial en un
teléfono conectado a Google/Gemini. Registrar el resultado de las 16 pruebas
en TEST_PLAN.md, sin convertir pendientes en aprobadas.

La rama `agent/restore-functional-parity-20261008` está publicada en
[PR #27](https://github.com/MisterReto/suite-ecommerce-ia/pull/27). El flujo táctil
Chromium/WebKit pasó a 360/390/430 px en CI; el pase focal posterior de paridad,
contrato y separación terminó con 30 pruebas correctas. La evidencia y el
fallo PostgreSQL corregido se registran en `docs/VERIFICATION.md`. Exigir todos
los checks del commit final verdes antes de actualizar los tres servicios
staging existentes y comprobar sus versiones/salud.

1. **Cuenta y teléfono.** Conectar la cuenta autorizada en el frontend staging;
   probar Chrome Android, Safari iPhone y PWA instalada con cámara/galería,
   EXIF, navegación y recuperación. El navegador de trabajo inicialmente abre
   el sitio sin sesión. No enviar contraseñas, MFA ni API keys por chat.
2. **Clave propia.** Guardarla en Más → Ajustes, comprobar modelos mediante la
   acción de metadatos, salir/entrar y verificar que siga configurada. PostgreSQL
   y el cifrado API/worker ya forman parte de la arquitectura; no hace falta
   introducir la clave personal en Render. Claves Render antiguas no se adoptan.
3. **Presupuesto de prueba Gemini.** Autorizar un tope explícito antes de analizar
   con proveedor real, generar tres imágenes, corregir una y probar lote de 2–3
   productos. Verificar identidad/escena contra fotos. Hasta entonces, CI usa mocks.
4. **Inventario aislado.** Para guardado real elegir una carpeta/Sheet de pruebas
   con permisos, productos y familia TEST-INTEGRATION. Revisar padre/hijo,
   imágenes y reparación sin cambios en WooCommerce o stock reales. El modo solo
   Drive queda respetado. La carpeta original y sus imágenes no se reorganizan.
5. **Pase y publicación.** Tras CI y staging, completar matriz de tutorial,
   registrar commit/deploy y aprobar aceptación antes de la promoción final.
   Conservar los deploys previos de ROLLBACK.md y los servicios históricos.

No se requiere un plan pagado nuevo ni una migración masiva. HEIC requiere
instalar/verificar el decoder opcional; de lo contrario usar JPG/PNG con el
mensaje que ya ofrece la app. Consultas Woo opcionales requieren asociación
de tenant y credenciales existentes, sin habilitar escrituras para estas pruebas.
