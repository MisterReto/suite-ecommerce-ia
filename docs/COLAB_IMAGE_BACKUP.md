# Respaldo autónomo de generación en Colab

El notebook del usuario incorpora el motor del commit `4e04b738a5f228ed3a56c50c4d891625f76c9e48`. Se genera con `tools/build_colab_generation.py`; `colab/generation_backup.py` adapta únicamente archivos, CSV, checkpoints y revisión al entorno de Colab.

## Qué se conserva

- Copias íntegras de `creative_pipeline.py`, `gemini_gateway.py` y `product_generation.py`, con SHA-256.
- `PROMPT_HD`, `ERRORES_IA`, el inspector de fidelidad y sus auxiliares extraídos del mismo commit sin reescribir sus funciones.
- Una copia de referencia de `studio_api.creative_plan` y `make_image`, el contrato de regresión y el logo oficial.
- Modelos `gemini-2.5-flash` y `gemini-3.1-flash-image`; referencia inline, un brief por producto y hasta dos ejemplos comerciales.
- Tres slots: `1_hd`, `2_uso`, `3_comercial`; imágenes cuadradas de al menos 1024 px; JPEG raw a calidad 95 y con marca a calidad 94.
- Correcciones sobre el raw anterior y hasta ocho indicaciones acumuladas. QA opcional sin regeneración automática.

La salida concreta de un modelo generativo puede variar. La preservación garantiza el código, los prompts y las reglas del flujo, no igualdad de píxeles entre ejecuciones.

## Uso del notebook

1. Montar Drive e instalar las dependencias fijadas; restaurar el motor y verificar el manifiesto.
2. Indicar la carpeta que contiene `inventario_completo.csv`. La auditoría conserva SKU como texto y no usa IA.
3. Seleccionar SKU, slots, límite de productos y concurrencia de 1 a 4; confirmar la generación.
4. Revisar candidatos y, si hace falta, corregirlos o regenerarlos explícitamente.
5. Indicar los SKU y slots aprobados y confirmar el guardado en `imagenes_generadas`.

Los candidatos, versiones y checkpoints viven en `colab_respaldo_generacion`. Antes de sustituir un archivo canónico se respalda el anterior. Un resultado incierto no se repite sin autorización explícita en el formulario. Un SKU o referencia incorrectos no detienen los demás productos.

El adaptador lee el CSV y guarda imágenes; el sincronizado del catálogo y la publicación a WooCommerce siguen perteneciendo a la app. El notebook conserva la herramienta anterior de compresión de PNG, desactivada por defecto, y se mantiene una copia de Drive anterior a la actualización.

## Actualizar este respaldo deliberadamente

Cambiar `SOURCE_COMMIT` solo después de revisar el nuevo contrato creativo. Generar el notebook desde una copia del original del usuario:

```sh
python tools/build_colab_generation.py original.ipynb respaldo.ipynb
python -m pytest -q test_colab_generation.py test_generation_contract.py
```

No subir notebooks del usuario con outputs, secretos o datos privados al repositorio público. El builder elimina salidas y widgets guardados. La app no importa el adaptador de Colab y estos archivos no alteran su runtime.
