#!/bin/bash
unset VIRTUAL_ENV
export PYGEOAPI_CONFIG=pygeoapi-config.yml
export PYGEOAPI_OPENAPI=pygeoapi-openapi.yml
export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$(dirname "$0")"
export PYGEOAPI_LOGLEVEL=DEBUG

uv run pygeoapi openapi generate $PYGEOAPI_CONFIG --output-file $PYGEOAPI_OPENAPI
uv run pygeoapi serve
