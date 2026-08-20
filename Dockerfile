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
EXPOSE 7860

# media_web.py carga Suite + inventario + diagnósticos + preview/sync de imágenes.
CMD ["uvicorn", "media_web:fastapi_app", "--host", "0.0.0.0", "--port", "7860", "--proxy-headers"]
