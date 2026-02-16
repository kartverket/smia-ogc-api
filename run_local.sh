#!/bin/bash
export PYGEOAPI_CONFIG=pygeoapi-config.yml
export PYGEOAPI_OPENAPI=pygeoapi-openapi.yml
export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$(dirname "$0")"

uv run pygeoapi openapi generate $PYGEOAPI_CONFIG --output-file $PYGEOAPI_OPENAPI
uv run pygeoapi serve
