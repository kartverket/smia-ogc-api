# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:0.9.2@sha256:6dbd7c42a9088083fa79e41431a579196a189bcee3ae68ba904ac2bf77765867 AS uv

# ---------- Byggesteg ----------
FROM dhi.io/python:3.12-dev@sha256:f0eee7746876caf2ecd823293f2424af594f2d9ec7edcba26e083d3d16181213 AS builder

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
FROM dhi.io/python:3.12@sha256:c72de729c2deaa578f54ef74d75a2973dcb3d70d020fd3b649f7f1191237ea3e AS runtime

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

