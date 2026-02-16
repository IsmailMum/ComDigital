FROM python:3.14-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup appuser

COPY . .

RUN chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

CMD ["bash", "scripts/prestart.sh"]
