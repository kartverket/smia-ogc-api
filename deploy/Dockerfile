# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:0.12.21@sha256:a7aed3216253ee804de3e2d8afa5073baa1a177335345d43845cd4165e43b711 AS uv

# ---------- Byggesteg ----------
FROM dhi.io/python:3.12-dev@sha256:a20227af228d0fc661f2d6908622823c1b873b5b3f701726111d4c1e37ba3e9b AS builder

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
FROM dhi.io/python:3.12@sha256:813a6731053afb8731e78782c041c418b93d44847e46b7d26f76596b4a17b222 AS runtime

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

