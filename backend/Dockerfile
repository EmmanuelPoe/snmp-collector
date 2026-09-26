FROM python:3.11-slim
WORKDIR /app
# Patch OS packages — the base image ships fixable HIGH findings that the trivy
# gate in CI blocks on.
RUN apt-get update && apt-get upgrade -y && apt-get install -y gcc postgresql-client \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
# Drop the build tooling once the dependencies are in: nothing here needs
# setuptools/wheel at runtime, and their vendored trees are a standing source of
# HIGH findings. Upgrading them instead just moves the findings around.
RUN pip install --no-cache-dir -r requirements.txt \
    && pip uninstall -y setuptools wheel
COPY . .

# Run as a non-root user (Step 4.1). The backend only reads the DuckDB mount
# (read-only) and writes nothing to disk, so owning /app is sufficient.
RUN addgroup --system app && adduser --system --ingroup app app && chown -R app:app /app
USER app

EXPOSE 8000
CMD alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
