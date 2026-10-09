"""HTTP-tester for bopliktsjekkens request-validering."""

import importlib
from pathlib import Path

import pytest

from processes.bopliktsjekk import BopliktSjekkProcessor

ROOT = Path(__file__).parents[2]
EXECUTION = "/v1/processes/bopliktsjekk/execution"


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    with pytest.MonkeyPatch.context() as mp:
        tmp_path = tmp_path_factory.mktemp("wsgi")
        openapi = tmp_path / "openapi.yml"
        openapi.write_text("{}")
        mp.setenv("PYGEOAPI_CONFIG", str(ROOT / "pygeoapi-config.yml"))
        mp.setenv("PYGEOAPI_OPENAPI", str(openapi))
        mp.setenv("PROMETHEUS_MULTIPROC_DIR", str(tmp_path))
        mp.setenv("INNDELINGER_DB_HOST", "localhost")
        mp.setenv("INNDELINGER_DB_USER", "test")
        mp.setenv("INNDELINGER_DB_PASSWORD", "test")
        mp.setenv("OGC_API_KEY", "testkey")

        wsgi = importlib.import_module("deploy.wsgi")
        wsgi.app.config["TESTING"] = True
        yield wsgi.app.test_client()


@pytest.fixture
def api_headers():
    return {"X-API-Key": "testkey"}


def test_health_er_aapen(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.data == b""


def test_beskyttet_endepunkt_krever_api_noekkel(client):
    response = client.post(EXECUTION, json={"inputs": {}})

    assert response.status_code == 401


def test_sikkerhetsheadere(client):
    response = client.get("/health")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert response.headers["Strict-Transport-Security"].startswith("max-age=")
    assert response.headers["Permissions-Policy"]
    assert response.headers["Content-Security-Policy"]


def test_gyldig_request_kjoerer_prosessen(client, api_headers, monkeypatch):
    monkeypatch.setattr(
        BopliktSjekkProcessor,
        "execute",
        lambda self, data, outputs=None: (
            "application/json",
            {"iBopliktomrade": "NEI"},
        ),
    )

    response = client.post(
        EXECUTION,
        json={"inputs": {"kommunenummer": "0301", "gardsnummer": 1, "bruksnummer": 1}},
        headers=api_headers,
    )

    assert response.status_code == 200
    assert response.json == {"iBopliktomrade": "NEI"}


@pytest.mark.parametrize("body", [[], 5, "x"])
def test_json_som_ikke_er_objekt_gir_400(client, api_headers, body):
    response = client.post(EXECUTION, json=body, headers=api_headers)

    assert response.status_code == 400
    assert response.json["code"] == "InvalidParameterValue"


@pytest.mark.parametrize(
    "body",
    [
        {
            "inputs": {"kommunenummer": "0301", "gardsnummer": 1, "bruksnummer": 1},
            "subscriber": {
                "successUri": "https://example.org/success",
                "inProgressUri": "https://example.org/progress",
            },
        },
        {"inputs": {}, "extra": True},
    ],
)
def test_ukjent_toppnivaafelt_gir_400(client, api_headers, body):
    response = client.post(EXECUTION, json=body, headers=api_headers)

    assert response.status_code == 400
    assert response.json["code"] == "InvalidParameterValue"
    assert "Ukjente felt" in response.json["description"]


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ('{"inputs": ', "Request body"),
        ('{"inputs": []}', "'inputs' må være et objekt"),
        ('{"inputs": {"ukjent": 1}}', "Ukjente felt i inputs"),
    ],
)
def test_ugyldig_request_gir_400(client, api_headers, body, expected):
    response = client.post(
        EXECUTION, data=body, content_type="application/json", headers=api_headers
    )

    assert response.status_code == 400
    assert response.json["code"] == "InvalidParameterValue"
    assert expected in response.json["description"]
