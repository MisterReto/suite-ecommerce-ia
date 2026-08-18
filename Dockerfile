FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY server.py .
COPY inventory_schema.py .
COPY inventory_operations.py .
COPY inventory_web.py .
COPY woocommerce_client.py .
COPY woocommerce_inventory.py .
COPY static ./static

ENV PORT=7860
EXPOSE 7860

# Render termina HTTPS en su proxy. Esta opción permite que OAuth reconstruya
# correctamente la URL segura al volver desde Google.
# inventory_web.py carga la Suite + diagnóstico WooCommerce + inventario físico.
CMD ["uvicorn", "inventory_web:fastapi_app", "--host", "0.0.0.0", "--port", "7860", "--proxy-headers"]
