FROM python:3.11-slim

WORKDIR /app

# Patch OS packages — the base image ships fixable HIGH findings that the trivy
# gate in CI blocks on.
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Drop the build tooling once the dependencies are in: nothing here needs
# setuptools/wheel at runtime, and their vendored trees are a standing source of
# HIGH findings. Upgrading them instead just moves the findings around.
RUN pip install --no-cache-dir -r requirements.txt \
    && pip uninstall -y setuptools wheel

COPY . .

# Run as a non-root user (Step 4.1). The agent writes its id/secret file and
# retry queue under /data and touches /tmp/agent-alive for the liveness probe.
RUN mkdir -p /data && addgroup --system app && adduser --system --ingroup app app \
    && chown -R app:app /app /data
USER app

CMD ["python", "main.py"]
