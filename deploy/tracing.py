import logging
import os

import flask
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

logger = logging.getLogger(__name__)

UTELATTE_URLER = r"^https?://[^/?#]+/health(\?|$)"


def _navngi_ukjent_rute(span, environ):
    """Samler kall som ikke treffer en rute under ett span-navn"""
    if span.is_recording() and flask.request.url_rule is None:
        span.update_name(f"{flask.request.method} ukjent")


def setup_tracing() -> None:
    """
    Slå på tracing når et OTLP-endepunkt er konfigurert.
    Kalles øverst i deploy/wsgi.py, som gunicorn laster i hver worker. Det
    plasserer oppsettet:
    """
    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return

    provider = TracerProvider()
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)

    FlaskInstrumentor().instrument(
        excluded_urls=UTELATTE_URLER, request_hook=_navngi_ukjent_rute
    )
    RequestsInstrumentor().instrument()
    Psycopg2Instrumentor().instrument()
    logger.info("Tracing aktivert i worker %s", os.getpid())
