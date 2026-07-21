import hmac
import logging
import os

from flask import abort, jsonify, request
from prometheus_flask_exporter.multiprocess import GunicornPrometheusMetrics
from pygeoapi.flask_app import APP as app

from processes.bopliktsjekk import PROCESS_METADATA as _BOPLIKTSJEKK_METADATA

logger = logging.getLogger(__name__)

API_KEY = os.environ.get("OGC_API_KEY")

OPEN_PATHS = {"/v1/", "/v1", "/v1/openapi", "/v1/conformance", "/health"}

metrics = GunicornPrometheusMetrics(app)


_EXECUTION_PATH = "/v1/processes/bopliktsjekk/execution"
_BOPLIKTSJEKK_INPUT_KEYS: frozenset[str] = frozenset(_BOPLIKTSJEKK_METADATA["inputs"])
_BOPLIKTSJEKK_INPUT_SCHEMA: dict = {
    name: {
        "type": defn["schema"]["type"],
        "required": defn.get("minOccurs", 0) >= 1,
    }
    for name, defn in _BOPLIKTSJEKK_METADATA["inputs"].items()
}


def _bad_request(description: str):
    return jsonify({"code": "InvalidParameterValue", "description": description}), 400


@app.before_request
def check_bopliktsjekk_inputs():
    if request.path != _EXECUTION_PATH or request.method != "POST":
        return None

    body = request.get_json(silent=True)
    if body is None:
        return _bad_request(
            "Request body må være gyldig JSON med Content-Type: application/json."
        )

    inputs = body.get("inputs")
    if not isinstance(inputs, dict):
        return _bad_request("'inputs' må være et objekt.")

    unknown_inputs = set(inputs) - _BOPLIKTSJEKK_INPUT_KEYS
    if unknown_inputs:
        logger.warning("Ukjente felt i inputs for %s: %s", request.path, unknown_inputs)
        return _bad_request(
            f"Ukjente felt i inputs: {sorted(unknown_inputs)}. "
            f"Gyldige inputs: {_BOPLIKTSJEKK_INPUT_SCHEMA}."
        )
    return None


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


@app.route("/health")
@metrics.do_not_track()
def health():
    return "", 200
