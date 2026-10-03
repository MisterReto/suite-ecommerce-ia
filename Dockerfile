FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade "pip>=26.2" "setuptools>=83" && pip install --no-cache-dir -r requirements.txt

COPY app.py gemini_gateway.py oauth_guard.py product_generation.py catalog_capture.py product_capture.py .
COPY ai_app.py .
COPY product_web_ai.py .
COPY single_product_auto.py .
COPY server.py .
COPY store_connection.py .
COPY app_security.py gradio_security.py bulk_product_upload.py inventory_hub.py .
COPY sync_bridge_protocol.py sync_gateway.py sync_service.py service_entrypoint.py .
COPY woocommerce_batch_sync.py woocommerce_catalog_light.py batch_web_v2.py .
COPY inventory_schema.py .
COPY inventory_operations.py .
COPY inventory_bulk.py .
COPY inventory_web.py .
COPY woocommerce_client.py woocommerce_stock.py .
COPY woocommerce_inventory.py .
COPY woocommerce_publish_preview.py .
COPY publication_web.py .
COPY wordpress_media.py .
COPY woocommerce_image_sync.py .
COPY woocommerce_media_prepare.py .
COPY woocommerce_product_sync.py .
COPY media_web.py .
COPY product_web.py .
COPY loyverse_client.py loyverse_sync.py loyverse_web.py loyverse_jobs.py ./
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

# Suite IA + Drive. La conexión a la tienda está aislada por defecto.
CMD ["uvicorn", "service_entrypoint:fastapi_app", "--host", "0.0.0.0", "--port", "7860", "--proxy-headers", "--no-access-log", "--workers", "1"]
