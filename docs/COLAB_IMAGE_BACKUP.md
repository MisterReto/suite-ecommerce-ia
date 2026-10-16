# Colab de generación masiva: ajuste de prompts

El notebook conserva sus **cinco celdas originales**. Solo se edita la celda de generación, con ID `-vY-eouWVDOt`. Las otras cuatro celdas, incluido el código de compresión de los 134 PNG, se conservan completas.

Se mantienen el montaje y las rutas de Drive, `inventario_completo.csv`, `faltantes.csv`, `imagenes_generadas`, la descarga de referencias, los nombres de archivo, el estampado del logo, la auditoría de faltantes y el procesamiento por hilos. Las imágenes se guardan directamente como antes; las existentes se omiten.

## Ajustes dentro de la celda existente

- `investigar_lifestyle` y `investigar_comercial` usan el brief y las reglas de la app: personas adultas usando o consumiendo el producto, y una composición comercial artística sin cambiar su identidad.
- El brief se comparte entre las dos escenas del mismo producto. Se usan hasta dos ejemplos comerciales de la misma carpeta como referencias de estilo.
- El producto limpio usa `PROMPT_HD` de la app.
- `generar_imagen` adjunta la foto original inline, emplea la configuración cuadrada 1:1 y valida una imagen no vacía de al menos 1024 px con los mismos métodos de `creative_pipeline.py`.
- El modelo sigue siendo `gemini-3.1-flash-image`; texto usa `gemini-2.5-flash`. Una llamada fallida no bloquea las demás imágenes.

Las funciones auxiliares y prompts se copian como Python legible dentro de la misma celda. No se agrega otra aplicación, motor empaquetado, interfaz de revisión ni paso de aprobación.

`colab/generation_backup.py` contiene el código de esa celda. `tools/build_colab_generation.py` aplica el ajuste a una copia del notebook original; no necesita sus salidas ni datos privados en el repositorio. El código fuente usado para la comparación de prompts es `4e04b73`.

Las pruebas comprueban que los 18 métodos ajenos al ajuste permanecen idénticos, que los métodos de imagen coinciden con la app y que la generación masiva conserva su guardado y auditoría originales. El notebook previo a cualquier edición permanece respaldado en Drive.
