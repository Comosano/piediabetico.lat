# ╔══════════════════════════════════════════════════════════════════════╗
# ║  DOCKERFILE — piediabetico.lat v1.1.0                              ║
# ║  Incluye: Alembic automático al arrancar + healthcheck PostgreSQL  ║
# ╚══════════════════════════════════════════════════════════════════════╝

FROM python:3.11-slim

LABEL maintainer="piediabetico.lat"
LABEL version="1.1.0"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# postgresql-client → para pg_isready en el entrypoint
# curl → para healthcheck de MinIO
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias Python
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copiar código
COPY . .

# Entrypoint ejecuta migraciones automáticamente al arrancar
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

RUN mkdir -p /workspace/scratch /app/modelos

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
