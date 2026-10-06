FROM node:22-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade "pip>=26.2" "setuptools>=83" && pip install --no-cache-dir -r requirements.txt
COPY *.py ./
COPY catalog_platform/ ./catalog_platform/
COPY static/ ./static/
COPY --from=frontend /build/out/ ./frontend/out/
RUN useradd --create-home --uid 10001 suite
USER suite
ENV PORT=7860 MALLOC_ARENA_MAX=2 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONUNBUFFERED=1
EXPOSE 7860
CMD ["sh", "-c", "exec uvicorn service_entrypoint:fastapi_app --host 0.0.0.0 --port ${PORT:-7860} --proxy-headers --no-access-log --workers 1"]
