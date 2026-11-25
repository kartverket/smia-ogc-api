# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:0.13.10@sha256:a3ea1357342c1a4bf9a0c53a3deb1b55379aefa037338d8113d5771efa01774f AS uv

# ---------- Byggesteg ----------
FROM dhi.io/python:3.12-dev@sha256:3d1eaab3dc22037f133a28f6c5dcaf200361a60d0cc3af6163d7e8e9bcdf8578 AS builder

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
FROM dhi.io/python:3.12@sha256:db25b8f5f629bd258938873923bbdcba63387447aa8e3246fa2f0b4e9f084708 AS runtime

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY processes/ /app/processes/
COPY deploy/ /app/deploy/
COPY styles/ /app/styles/
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

