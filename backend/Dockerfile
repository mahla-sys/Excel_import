FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps kept minimal; we use psycopg[binary] so no build toolchain needed.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Create an unprivileged user up-front so the mounted volumes and static
# directory can be chowned in entrypoint if needed.
RUN groupadd --system app && useradd --system --gid app --home /app app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

RUN mkdir -p /data/private_files /app/staticfiles \
    && chown -R app:app /app /data \
    && chmod +x /app/entrypoint.sh

EXPOSE 8000

USER app

ENTRYPOINT ["/app/entrypoint.sh"]
