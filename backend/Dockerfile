FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y gcc postgresql-client && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Run as a non-root user (Step 4.1). The backend only reads the DuckDB mount
# (read-only) and writes nothing to disk, so owning /app is sufficient.
RUN addgroup --system app && adduser --system --ingroup app app && chown -R app:app /app
USER app

EXPOSE 8000
CMD alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
