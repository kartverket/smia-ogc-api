import importlib
from pathlib import Path

import pytest
import yaml

from deploy.openapi import add_styles_to_openapi


@pytest.fixture
def styles_client(monkeypatch, tmp_path):
    openapi_path = tmp_path / "openapi.yml"
    openapi_path.write_text(
        "openapi: 3.0.3\ninfo:\n  title: Test\n  version: 1.0.0\npaths: {}\n",
        encoding="utf-8",
    )

    project_root = Path(__file__).parents[2]
    monkeypatch.setenv("PYGEOAPI_CONFIG", str(project_root / "pygeoapi-config.yml"))
    monkeypatch.setenv("PYGEOAPI_OPENAPI", str(openapi_path))
    monkeypatch.setenv("PYGEOAPI_URL", "http://localhost:5000")
    monkeypatch.setenv("INNDELINGER_DB_HOST", "localhost")
    monkeypatch.setenv("INNDELINGER_DB_USER", "test")
    monkeypatch.setenv("INNDELINGER_DB_PASSWORD", "test")
    monkeypatch.setenv("OGC_API_KEY", "testkey")
    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", str(tmp_path))

    wsgi = importlib.import_module("deploy.wsgi")
    return wsgi.app.test_client()


def test_styles_require_api_key(styles_client):
    response = styles_client.get("/v1/collections/bopliktomraade/styles")

    assert response.status_code == 401


def test_lists_default_collection_style(styles_client):
    response = styles_client.get(
        "/v1/collections/bopliktomraade/styles",
        headers={"X-API-Key": "testkey"},
    )

    assert response.status_code == 200
    assert response.json["default"] == "bopliktomraade-default"
    assert response.json["styles"][0]["id"] == "bopliktomraade-default"
    assert response.json["styles"][0]["links"][0]["rel"] == "stylesheet"


def test_returns_mapbox_style(styles_client):
    response = styles_client.get(
        "/v1/collections/bopliktomraade/styles/bopliktomraade-default?f=mbs",
        headers={"X-API-Key": "testkey"},
    )

    assert response.status_code == 200
    assert response.mimetype == "application/vnd.mapbox.style+json"
    assert response.json["version"] == 8
    assert response.json["sources"]["bopliktomraade"]["data"] == (
        "http://localhost:5000/v1/collections/bopliktomraade/items?f=json&limit=50"
    )


def test_default_style_uses_bopliktomraade_cartography(styles_client):
    response = styles_client.get(
        "/v1/collections/bopliktomraade/styles/bopliktomraade-default?f=mbs",
        headers={"X-API-Key": "testkey"},
    )

    layers = response.json["layers"]
    assert [layer["id"] for layer in layers] == [
        "bopliktomraade-fill",
        "bopliktomraade-inner-band",
        "bopliktomraade-halo",
        "bopliktomraade-outline",
    ]
    assert layers[0]["paint"] == {
        "fill-color": "#1D4E89",
        "fill-opacity": 0.12,
    }
    assert layers[1]["paint"] == {
        "line-color": "#1D4E89",
        "line-opacity": 0.5,
        "line-width": 8,
        "line-offset": 4,
    }
    assert layers[2]["paint"] == {
        "line-color": "#FFFFFF",
        "line-width": 5,
    }
    assert layers[3]["paint"] == {
        "line-color": "#1D4E89",
        "line-width": 2,
    }
    assert all("minzoom" not in layer and "maxzoom" not in layer for layer in layers)


def test_rejects_unsupported_style_format(styles_client):
    response = styles_client.get(
        "/v1/collections/bopliktomraade/styles/bopliktomraade-default?f=sld",
        headers={"X-API-Key": "testkey"},
    )

    assert response.status_code == 400
    assert response.json["code"] == "InvalidParameterValue"


def test_advertises_styles_conformance(styles_client):
    response = styles_client.get("/v1/conformance")

    assert response.status_code == 200
    assert (
        "http://www.opengis.net/spec/ogcapi-styles-1/1.0/conf/core"
        in (response.json["conformsTo"])
    )


def test_adds_styles_endpoints_to_generated_openapi(tmp_path):
    openapi_path = tmp_path / "openapi.yml"
    config_path = tmp_path / "config.yml"
    openapi_path.write_text(
        yaml.safe_dump(
            {
                "paths": {
                    "/collections/bopliktomraade": {"get": {"tags": ["Bopliktområde"]}}
                }
            }
        ),
        encoding="utf-8",
    )
    config_path.write_text(
        yaml.safe_dump(
            {
                "resources": {
                    "bopliktomraade": {
                        "type": "collection",
                        "styles": [{"id": "standard"}],
                    },
                    "bopliktsjekk": {"type": "process"},
                }
            }
        ),
        encoding="utf-8",
    )

    add_styles_to_openapi(str(openapi_path), str(config_path))

    paths = yaml.safe_load(openapi_path.read_text(encoding="utf-8"))["paths"]
    styles_list = paths["/collections/bopliktomraade/styles"]["get"]
    style_document = paths["/collections/bopliktomraade/styles/{style_id}"]["get"]
    assert styles_list["tags"] == ["Bopliktområde"]
    assert styles_list["responses"]["200"]["content"]["application/json"]
    assert "/collections/bopliktsjekk/styles" not in paths
    assert style_document["parameters"][0]["name"] == "style_id"
    assert style_document["responses"]["200"]["content"][
        "application/vnd.mapbox.style+json"
    ]
    assert {"400", "404", "500"} <= set(style_document["responses"])
