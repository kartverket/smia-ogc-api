# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:0.12.0@sha256:606e70c71c852d03f611b1e56a195d08648507018a7057fab82c4974c4eae105 AS uv

# ---------- Byggesteg ----------
FROM dhi.io/python:3.12-dev@sha256:a697bd67311699bb065673096bba18a5b648e4120971ccb4f2fc6962e6bace0d AS builder

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
FROM dhi.io/python:3.12@sha256:15908b7af6962c839820c1484a96b58fb24a9df749212796d01c3d7e1aae99bf AS runtime

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

