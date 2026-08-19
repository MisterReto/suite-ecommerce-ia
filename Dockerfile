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
COPY static ./static

ENV PORT=7860
EXPOSE 7860

# Render termina HTTPS en su proxy. Esta opción permite que OAuth reconstruya
# correctamente la URL segura al volver desde Google.
# publication_web.py carga Suite + diagnóstico + inventario + preview de publicación.
CMD ["uvicorn", "publication_web:fastapi_app", "--host", "0.0.0.0", "--port", "7860", "--proxy-headers"]
