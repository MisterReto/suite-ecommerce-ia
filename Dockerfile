FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY ai_app.py .
COPY product_web_ai.py .
COPY single_product_auto.py .
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
COPY woocommerce_media_prepare.py .
COPY woocommerce_product_sync.py .
COPY media_web.py .
COPY product_web.py .
COPY static ./static

ENV PORT=7860
ENV GRADIO_DEFAULT_CONCURRENCY_LIMIT=1
ENV MALLOC_ARENA_MAX=2
ENV OMP_NUM_THREADS=1
ENV OPENBLAS_NUM_THREADS=1
ENV MKL_NUM_THREADS=1
ENV NUMEXPR_NUM_THREADS=1
ENV PYTHONUNBUFFERED=1
EXPOSE 7860

# Suite IA + publicación de un solo SKU al guardar. Sin workers/rutas de lotes.
CMD ["uvicorn", "product_web_ai:fastapi_app", "--host", "0.0.0.0", "--port", "7860", "--proxy-headers", "--workers", "1"]
