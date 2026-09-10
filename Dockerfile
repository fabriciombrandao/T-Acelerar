FROM python:3.12-slim

WORKDIR /app

# Dependências de sistema mínimas (psycopg2 precisa de libpq no build)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ backend/
COPY frontend/ frontend/
COPY mappings/ mappings/

ENV PYTHONPATH=/app/backend
ENV TACELERAR_DB_URL=sqlite:////app/data/tacelerar.db

RUN mkdir -p /app/data /app/output/scripts

EXPOSE 8000

CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "backend"]
