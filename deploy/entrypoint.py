import hmac
import logging
import os

from flask import abort, request
from prometheus_flask_exporter.multiprocess import GunicornPrometheusMetrics
from pygeoapi.flask_app import APP as app

logger = logging.getLogger(__name__)

API_KEY = os.environ.get("OGC_API_KEY")

OPEN_PATHS = {"/v1/", "/v1/openapi", "/v1/conformance", "/health"}


@app.before_request
def check_api_key():
    if request.path in OPEN_PATHS:
        return
    if not API_KEY:
        abort(503)
    provided = request.headers.get("X-API-Key", "")
    if not hmac.compare_digest(provided, API_KEY):
        logger.warning(
            "Ugyldig API key for %s fra %s", request.path, request.remote_addr
        )
        abort(401)


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


@app.route("/v1/health")
@metrics.do_not_track()
def health():
    return "", 200
