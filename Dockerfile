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

# Ajustes conservadores para Render Free: rápido en éxito, tolerante a picos lentos.
ENV WC_TIMEOUT=60
ENV WP_TIMEOUT=90
ENV WC_METADATA_WORKERS=3
ENV WP_MEDIA_METADATA_ENABLED=false
ENV SYNC_INVENTORY_CACHE_TTL=600
ENV SYNC_DRIVE_CACHE_TTL=1800
ENV SYNC_MEDIA_CACHE_TTL=1800

EXPOSE 7860

CMD ["uvicorn", "sync_lite_app:app", "--host", "0.0.0.0", "--port", "7860", "--proxy-headers", "--workers", "1"]
