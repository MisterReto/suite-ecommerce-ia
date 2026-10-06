# Generación de imágenes que se conserva

La referencia de esta continuación es el commit `3ba6a2f9aeb65265a6165ee6c48b7ab273256d7f`, con el generador aceptado del primer prompt. El detalle histórico está en [docs/current-image-generation-flow.md](docs/current-image-generation-flow.md).

| Fase | Función | Qué conserva |
| --- | --- | --- |
| Datos del producto | `creative_pipeline.product_data` | Identidad, marca, categoría y descripción. |
| Dirección creativa | `studio_api.creative_plan`, `creative_pipeline.brief` | Lifestyle con interacción humana y comercial artístico; referencias de estilo actuales. |
| Imagen | `studio_api.make_image`, `creative_pipeline.generate` | Fotos originales como autoridad; modelo y prompts existentes. |
| Corrección | `studio_api.correct_image` y worker | Raw anterior sin marca, fotos originales e historial. |
| Archivo final | Validación local y marca determinista | JPEG cuadrado, dimensiones mínimas y logo aplicado por código. |
| Revisión | API de imágenes/assets | Generación, aprobación y publicación como operaciones distintas. |

## Captura individual y lote

Captura: el contexto de `studio_api.py` pertenece a una sesión. Lote: `catalog_platform/worker.py` prepara su propio contexto y usa `ImageGenerationService` para llamar a las mismas funciones. La cola no implementa un generador alternativo.

La sesión temporal usa `/tmp`; el resultado durable y el raw se guardan en Drive y se relacionan en SQL. El worker conserva claves de cada imagen completada. Al cerrar el navegador el trabajo persistente sigue; al perder una respuesta del proveedor se marca una operación incierta y exige revisión.

## Nombres y carpetas

El guardado compatible conserva `<SKU>_1_hd.jpg`, `<SKU>_2_uso.jpg`, `<SKU>_3_comercial.jpg`. Los nombres históricos `_1.png`, `_2.png`, `_3.png` siguen siendo referencias compatibles. El worker usa identificadores de job/muestra para los resultados nuevos y conserva metadata y raws. No renombra imágenes históricas.

## Prueba que congela el generador

`test_generation_contract.py` compara el AST actual de las funciones protegidas con el mismo código extraído del commit aceptado mediante `git show`. Ambos se procesan con el mismo intérprete. La CI comprueba Python 3.11 y 3.14.

El hash AST anterior fallaba al verificar la migración. Su valor se conserva como procedencia, pero no se sustituye por el hash del código actual para hacer pasar la prueba. La referencia ahora es el commit inmutable. Cambiar un prompt o eliminar una función sigue invalidando la protección.

El contrato protege `creative_pipeline.py` completo, `studio_api.make_image`, `studio_api.creative_plan`, `app.PROMPT_HD`, `app._validar_con_vision`, `gemini_gateway.image_part` y `gemini_gateway.text_config`. Las nuevas configuraciones de despliegue no cambian esas funciones.

## Verificación real pendiente

Se necesita un producto conocido, conexión autorizada y generación acotada: catálogo/lifestyle/comercial, corrección con raw previo, guardado en Drive y recuperación tras cerrar navegador. Las pruebas con dobles y el build no prueban calidad artística ni disponibilidad de Gemini.
