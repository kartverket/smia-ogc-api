FROM geopython/pygeoapi@sha256:0eb9a192dc14260b11c9cd05f80d21e779ea43645a0fa0fa6cd460f1b8c7acce

COPY deploy/requirements.txt /tmp/requirements.txt
RUN /venv/bin/pip install -r /tmp/requirements.txt

COPY pygeoapi-config.yml /pygeoapi/local.config.yml
COPY processes/ /pygeoapi/processes/
COPY deploy/entrypoint.py /pygeoapi/pygeoapi/entrypoint.py
COPY deploy/gunicorn_conf.py /pygeoapi/gunicorn_conf.py

RUN chown -R 150:150 /pygeoapi

ENV PYTHONPATH=/pygeoapi
ENV WSGI_APP=pygeoapi.entrypoint:app
ENV PROMETHEUS_MULTIPROC_DIR=/tmp
ENV PYGEOAPI_OPENAPI=/tmp/local.openapi.yml
ENV CONTAINER_PORT=5000
ENV GUNICORN_CMD_ARGS="--config /pygeoapi/gunicorn_conf.py"

USER 150:150

EXPOSE 5000 8181
