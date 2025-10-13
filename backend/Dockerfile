FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# psycopg2 için derleme bağımlılıkları
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Gereksinimler
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Uygulama
COPY . /app
ENV PYTHONPATH=/app

EXPOSE 8000
CMD ["sh","-c","alembic upgrade head && uvicorn backend.main:app --host 0.0.0.0 --port 8000"]
