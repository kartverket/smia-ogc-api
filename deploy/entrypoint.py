import logging
import os

from prometheus_flask_exporter.multiprocess import GunicornPrometheusMetrics
from pygeoapi.flask_app import APP as app

logger = logging.getLogger(__name__)

API_KEY = os.environ.get("OGC_API_KEY")

OPEN_PATHS = {"/v1/", "/v1/openapi", "/v1/conformance", "/health"}


@app.after_request
def set_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains"
    )
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://unpkg.com https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://unpkg.com; "
        "img-src 'self' https://kartverket.no https://www.kartverket.no https://cache.kartverket.no data:; "
        "font-src 'self'; "
        "connect-src 'self' https://schemas.opengis.net https://raw.githubusercontent.com"
    )
    response.headers.pop("X-Powered-By", None)
    response.headers.pop("Server", None)
    return response


metrics = GunicornPrometheusMetrics(app)


@app.route("/health")
@metrics.do_not_track()
def health():
    return "", 200
