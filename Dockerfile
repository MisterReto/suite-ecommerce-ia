FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

ENV PORT=7860
EXPOSE 7860

# --proxy-headers: para que uvicorn confíe en el header X-Forwarded-Proto que
# manda el proxy del hosting, y así detecte correctamente que la conexión
# original del usuario es https (importante para que el login de Google funcione).
CMD ["uvicorn", "app:fastapi_app", "--host", "0.0.0.0", "--port", "7860", "--proxy-headers"]
