FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as a non-root user (Step 4.1). The agent writes its id/secret file and
# retry queue under /data and touches /tmp/agent-alive for the liveness probe.
RUN mkdir -p /data && addgroup --system app && adduser --system --ingroup app app \
    && chown -R app:app /app /data
USER app

CMD ["python", "main.py"]
