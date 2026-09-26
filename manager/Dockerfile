FROM python:3.12-slim

WORKDIR /app

# Patch OS packages — the base image ships fixable HIGH findings that the trivy
# gate in CI blocks on. (python:3.12-slim bundles no setuptools/wheel, so there
# is no build tooling to strip here.)
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data/db /data/registry /data/dead-letter

RUN addgroup --system app && adduser --system --ingroup app app
RUN chown -R app:app /app /data

USER app

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
