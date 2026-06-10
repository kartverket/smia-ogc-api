import os
import subprocess

config = os.environ["PYGEOAPI_CONFIG"]
openapi = os.environ["PYGEOAPI_OPENAPI"]
wsgi_app = os.environ.get("WSGI_APP", "deploy.wsgi:app")

# Generer openapi-spec ved oppstart
subprocess.run(
    ["pygeoapi", "openapi", "generate", config, "--output-file", openapi],
    check=True,
)

os.execvp(
    "gunicorn",
    ["gunicorn", "--config", "/app/deploy/gunicorn_conf.py", wsgi_app],
)
