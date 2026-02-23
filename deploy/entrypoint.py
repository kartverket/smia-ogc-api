import os

from prometheus_flask_exporter.multiprocess import GunicornPrometheusMetrics
from pygeoapi.flask_app import APP as app

API_KEY = os.environ.get("OGC_API_KEY")

OPEN_PATHS = {'/', '/openapi', '/conformance', '/health'}

if API_KEY:
    @app.before_request
    def check_api_key():
        from flask import request, abort
        if request.path not in OPEN_PATHS and request.headers.get("X-API-Key") != API_KEY:
            abort(401)

metrics = GunicornPrometheusMetrics(app)


@app.route('/health')
@metrics.do_not_track()
def health():
    return '', 200
