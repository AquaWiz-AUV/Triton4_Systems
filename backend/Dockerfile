FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY server/requirements.txt /app/server/requirements.txt

RUN python -m pip install --upgrade pip \
    && pip install -r /app/server/requirements.txt

COPY server /app/server

WORKDIR /app/server

EXPOSE 8000

ENV DATABASE_URL=postgresql+asyncpg://triton:triton@db:5432/triton_com \
    LOG_LEVEL=INFO

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
