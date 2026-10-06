# Uso y desarrollo

La interfaz principal usa Next.js / React y FastAPI. Consulta
[README](README.md) para compilar y ejecutar, y
[activación gradual](docs/platform-rollout.md) antes de configurar Render.

La navegación tiene cinco apartados: Inicio, Productos, Generar, Inventario y Más.
Los archivos `static/tutorial.js` y `static/tutorial.css` se conservan como
compatibilidad de herramientas históricas; el flujo principal usa Más → Ayuda.

La generación aceptada queda documentada en
[su contrato de regresión](docs/current-image-generation-flow.md). No sustituir
prompts, modelos, proveedores o referencias como parte de una actualización de UI.
