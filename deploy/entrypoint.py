import hmac
import os

from flask import abort, request
from prometheus_flask_exporter.multiprocess import GunicornPrometheusMetrics
from pygeoapi.flask_app import APP as app

API_KEY = os.environ.get("OGC_API_KEY")

OPEN_PATHS = {"/", "/openapi", "/conformance", "/health"}


@app.before_request
def check_api_key():
    if request.path in OPEN_PATHS:
        return
    if not API_KEY:
        abort(503)
    provided = request.headers.get("X-API-Key", "")
    if not hmac.compare_digest(provided, API_KEY):
        abort(401)


metrics = GunicornPrometheusMetrics(app)


@app.route("/health")
@metrics.do_not_track()
def health():
    return "", 200
