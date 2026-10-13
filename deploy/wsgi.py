import hmac
import json
import logging
import os
from pathlib import Path

from flask import Response, abort, jsonify, request
from prometheus_flask_exporter.multiprocess import GunicornPrometheusMetrics
from pygeoapi import l10n
from pygeoapi.api import APIRequest
from pygeoapi.flask_app import APP as app
from pygeoapi.flask_app import api_

from processes.bopliktsjekk import PROCESS_METADATA as _BOPLIKTSJEKK_METADATA

logger = logging.getLogger(__name__)

API_KEY = os.environ.get("OGC_API_KEY")
PYGEOAPI_URL = os.environ.get("PYGEOAPI_URL", "http://localhost:5000").rstrip("/")
STYLE_MEDIA_TYPE = "application/vnd.mapbox.style+json"
STYLES_CONFORMANCE_CLASSES = {
    "http://www.opengis.net/spec/ogcapi-styles-1/1.0/conf/core",
    "http://www.opengis.net/spec/ogcapi-styles-1/1.0/conf/mapbox-styles",
    "http://www.opengis.net/spec/ogcapi-styles-1/1.0/conf/resources",
}

OPEN_PATHS = {
    "/v1/",
    "/v1",
    "/v1/openapi",
    "/v1/conformance",
    "/health",
}

metrics = GunicornPrometheusMetrics(app)


def _input_spec(metadata: dict) -> tuple[frozenset, dict]:
    keys = frozenset(metadata["inputs"])
    schema = {
        name: {
            "type": defn["schema"]["type"],
            "required": defn.get("minOccurs", 0) >= 1,
        }
        for name, defn in metadata["inputs"].items()
    }
    return keys, schema


_PROCESS_INPUT_SPECS: dict[str, tuple[frozenset, dict]] = {
    "/v1/processes/bopliktsjekk/execution": _input_spec(_BOPLIKTSJEKK_METADATA),
}


def _bad_request(description: str):
    return jsonify({"code": "InvalidParameterValue", "description": description}), 400


def _configured_styles(collection_id: str) -> list[dict] | None:
    collection = api_.config["resources"].get(collection_id)
    if collection is None or collection.get("type") != "collection":
        return None
    return collection.get("styles", [])


def _find_style(collection_id: str, style_id: str) -> dict | None:
    styles = _configured_styles(collection_id)
    if styles is None:
        return None
    return next((style for style in styles if style.get("id") == style_id), None)


def _style_links(collection_id: str, style_id: str) -> list[dict]:
    return [
        {
            "rel": "stylesheet",
            "href": (
                f"{PYGEOAPI_URL}/v1/collections/{collection_id}/styles/{style_id}?f=mbs"
            ),
            "type": STYLE_MEDIA_TYPE,
        }
    ]


def _expand_style_urls(style: dict) -> dict:
    for source in style.get("sources", {}).values():
        if isinstance(source.get("data"), str):
            source["data"] = source["data"].replace("${PYGEOAPI_URL}", PYGEOAPI_URL)
        if "tiles" in source:
            source["tiles"] = [
                f"{PYGEOAPI_URL}{url}" if url.startswith("/") else url
                for url in source["tiles"]
            ]
    return style


@app.before_request
def check_bopliktsjekk_inputs():
    spec = _PROCESS_INPUT_SPECS.get(request.path.rstrip("/"))
    if spec is None or request.method != "POST":
        return None

    input_keys, input_schema = spec

    body = request.get_json(silent=True)
    if body is None:
        return _bad_request(
            "Request body må være gyldig JSON med Content-Type: application/json."
        )
    if not isinstance(body, dict):
        return _bad_request("Request body må være et JSON-objekt.")

    unknown_fields = set(body) - {"inputs", "outputs", "response", "subscriber"}
    if unknown_fields:
        logger.warning("Ukjente toppnivåfelt for %s: %s", request.path, unknown_fields)
        return _bad_request(f"Ukjente felt i request body: {sorted(unknown_fields)}.")

    inputs = body.get("inputs")
    if not isinstance(inputs, dict):
        return _bad_request("'inputs' må være et objekt.")

    unknown_inputs = set(inputs) - input_keys
    if unknown_inputs:
        logger.warning("Ukjente felt i inputs for %s: %s", request.path, unknown_inputs)
        return _bad_request(
            f"Ukjente felt i inputs: {sorted(unknown_inputs)}. "
            f"Gyldige inputs: {input_schema}."
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


@app.after_request
def add_styles_conformance_classes(response):
    if request.path != "/v1/conformance" or request.method != "GET":
        return response
    media_type = (response.content_type or "").partition(";")[0].strip().lower()
    if response.status_code != 200 or media_type != "application/json":
        return response

    try:
        payload = json.loads(response.get_data(as_text=True))
    except (TypeError, ValueError):
        return response

    payload["conformsTo"] = sorted(
        set(payload.get("conformsTo", [])) | STYLES_CONFORMANCE_CLASSES
    )
    response.set_data(json.dumps(payload))
    return response


@app.route("/health")
@metrics.do_not_track()
def health():
    return "", 200


@app.get("/v1/collections/<collection_id>/styles")
def get_collection_styles(collection_id: str):
    styles = _configured_styles(collection_id)
    if styles is None:
        return jsonify(
            {"code": "NotFound", "description": f"Unknown collection: {collection_id}"}
        ), 404

    locale = APIRequest.from_flask(request, api_.locales).locale
    response = {
        "styles": [
            {
                "id": style["id"],
                "title": l10n.translate(style.get("title") or style["id"], locale),
                "description": l10n.translate(style.get("description") or "", locale),
                "links": _style_links(collection_id, style["id"]),
            }
            for style in styles
        ]
    }
    default_style = next(
        (style["id"] for style in styles if style.get("default") is True), None
    )
    if default_style is not None:
        response["default"] = default_style
    return jsonify(response)


@app.get("/v1/collections/<collection_id>/styles/<style_id>")
def get_collection_style(collection_id: str, style_id: str):
    style = _find_style(collection_id, style_id)
    if style is None:
        return jsonify(
            {"code": "NotFound", "description": f"Unknown style: {style_id}"}
        ), 404

    requested_format = request.args.get("f", "mbs")
    if requested_format not in {"mapbox", "mbs"}:
        return _bad_request(f"Unsupported style format: {requested_format}")

    try:
        style_document = json.loads(Path(style["path"]).read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.exception("Style file not found: %s", style["path"])
        return jsonify(
            {
                "code": "NotFound",
                "description": f"Style file not found: {style_id}",
            }
        ), 404
    except json.JSONDecodeError:
        logger.exception("Invalid style JSON: %s", style["path"])
        return jsonify(
            {
                "code": "InternalServerError",
                "description": "Style document is not valid JSON",
            }
        ), 500

    return Response(
        json.dumps(_expand_style_urls(style_document), ensure_ascii=False),
        content_type=STYLE_MEDIA_TYPE,
    )
