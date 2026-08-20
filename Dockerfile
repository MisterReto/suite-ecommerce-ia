FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY server.py .
COPY inventory_schema.py .
COPY inventory_operations.py .
COPY inventory_bulk.py .
COPY inventory_web.py .
COPY woocommerce_client.py .
COPY woocommerce_inventory.py .
COPY woocommerce_publish_preview.py .
COPY publication_web.py .
COPY wordpress_media.py .
COPY woocommerce_image_sync.py .
COPY media_web.py .
COPY static ./static

ENV PORT=7860
# Render tiene RAM limitada: una sola ejecución pesada de Gradio a la vez.
ENV GRADIO_DEFAULT_CONCURRENCY_LIMIT=1
# Evita arenas extra de glibc por thread y limita librerías numéricas internas.
ENV MALLOC_ARENA_MAX=2
ENV OMP_NUM_THREADS=1
ENV OPENBLAS_NUM_THREADS=1
ENV MKL_NUM_THREADS=1
ENV NUMEXPR_NUM_THREADS=1
ENV PYTHONUNBUFFERED=1
EXPOSE 7860

# Un solo worker de Uvicorn; la concurrencia I/O interna ya está controlada en código.
CMD ["uvicorn", "media_web:fastapi_app", "--host", "0.0.0.0", "--port", "7860", "--proxy-headers", "--workers", "1"]
