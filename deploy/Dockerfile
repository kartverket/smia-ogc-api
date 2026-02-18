FROM geopython/pygeoapi:latest

COPY deploy/requirements.txt /tmp/requirements.txt
RUN /venv/bin/pip install -r /tmp/requirements.txt

COPY pygeoapi-config.yml /pygeoapi/local.config.yml
COPY processes/ /pygeoapi/processes/
COPY deploy/entrypoint.py /pygeoapi/pygeoapi/entrypoint.py
COPY deploy/gunicorn_conf.py /pygeoapi/gunicorn_conf.py

RUN chown -R 150:150 /pygeoapi

ENV WSGI_APP=pygeoapi.entrypoint:app
ENV PROMETHEUS_MULTIPROC_DIR=/tmp
ENV PYGEOAPI_OPENAPI=/tmp/local.openapi.yml
ENV CONTAINER_PORT=5000

USER 150:150

EXPOSE 5000 8181
