# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:0.11.29@sha256:eb2843a1e56fd9e30c7276ce1a52cba86e64c7b385f5e3279a0e08e02dd058fc AS uv

# ---------- Byggesteg ----------
FROM dhi.io/python:3.12-dev@sha256:1ceaf6ce9bbb03c9e27462f408599fc3e5c8a4bf863354513c050b66e289265f AS builder

USER root

COPY --from=uv /uv /uvx /bin/

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=0 \
    UV_CACHE_DIR=/tmp/uv-cache

WORKDIR /app

# Cache her kun for lokal utvikling
RUN --mount=type=cache,target=/tmp/uv-cache \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --locked --no-dev --no-install-project

# ---------- Runtime-steg ----------
FROM dhi.io/python:3.12@sha256:61c0a8d0e38495a7f0d6f43d751c7e3ef4c59dcf379374bc47f1b9a650da285f AS runtime

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY processes/ /app/processes/
COPY deploy/ /app/deploy/
COPY pygeoapi-config.yml /app/pygeoapi-config.yml

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PROMETHEUS_MULTIPROC_DIR=/tmp \
    PYGEOAPI_CONFIG=/app/pygeoapi-config.yml \
    PYGEOAPI_OPENAPI=/tmp/openapi.yml \
    WSGI_APP=deploy.wsgi:app \
    CONTAINER_HOST=0.0.0.0 \
    CONTAINER_PORT=5000

USER nonroot
EXPOSE 5000 8181

ENTRYPOINT ["/app/.venv/bin/python", "/app/deploy/start.py"]

