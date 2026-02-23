from prometheus_flask_exporter.multiprocess import GunicornPrometheusMetrics
from pygeoapi.flask_app import APP as app

metrics = GunicornPrometheusMetrics(app)


@app.route('/health')
@metrics.do_not_track()
def health():
    return '', 200
