FROM python:3.11-slim

WORKDIR /app

COPY requirements-sync.txt .
RUN pip install --no-cache-dir -r requirements-sync.txt

# Solo módulos necesarios para sincronización. No copiamos app.py/Gradio/Gemini.
COPY sync_lite_app.py .
COPY inventory_schema.py .
COPY inventory_operations.py .
COPY woocommerce_client.py .
COPY woocommerce_catalog_light.py .
COPY woocommerce_batch_sync.py .
COPY wordpress_media.py .
COPY woocommerce_image_sync.py .
COPY woocommerce_media_prepare.py .
COPY woocommerce_product_sync.py .

ENV PORT=7860
ENV MALLOC_ARENA_MAX=2
ENV OMP_NUM_THREADS=1
ENV OPENBLAS_NUM_THREADS=1
ENV MKL_NUM_THREADS=1
ENV NUMEXPR_NUM_THREADS=1
ENV PYTHONUNBUFFERED=1
EXPOSE 7860

CMD ["uvicorn", "sync_lite_app:app", "--host", "0.0.0.0", "--port", "7860", "--proxy-headers", "--workers", "1"]
