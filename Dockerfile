FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py ./
COPY static ./static

RUN useradd --create-home --uid 10001 suite
USER suite

ENV PORT=7860
EXPOSE 7860

# Render termina HTTPS en su proxy. Esta opción permite que OAuth reconstruya
# correctamente la URL segura al volver desde Google.
CMD ["uvicorn", "server:fastapi_app", "--host", "0.0.0.0", "--port", "7860", "--proxy-headers", "--workers", "1", "--no-access-log"]
