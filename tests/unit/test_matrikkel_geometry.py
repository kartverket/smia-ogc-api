"""Enhetstester for geometrihenting fra Matrikkel."""

import logging
from unittest.mock import MagicMock

from processes.utils import matrikkel_geometry


def test_hent_teiggeometri_returnerer_geometri_og_logger_bue(monkeypatch, caplog):
    items = [
        {"id": {"value": 1}, "posisjon": {"x": 0, "y": 0}},
        {"id": {"value": 2}, "posisjon": {"x": 2, "y": 0}},
        {"id": {"value": 3}, "posisjon": {"x": 0, "y": 2}},
        {
            "id": {"value": 10},
            "kurve": {
                "startpunktId": {"value": 1},
                "endpunktId": {"value": 2},
                "buepunktX": 1,
                "buepunktY": 0,
            },
        },
        {
            "id": {"value": 11},
            "kurve": {"startpunktId": {"value": 2}, "endpunktId": {"value": 3}},
        },
        {
            "id": {"value": 12},
            "kurve": {"startpunktId": {"value": 3}, "endpunktId": {"value": 1}},
        },
        {
            "flate": {
                "exterior": {
                    "curveDirections": {
                        "item": [
                            {"grenselinjeId": {"value": edge_id}, "signed": True}
                            for edge_id in (10, 11, 12)
                        ]
                    }
                }
            }
        },
    ]
    monkeypatch.setattr(
        matrikkel_geometry,
        "hent_matrikkelenhet_med_teiger",
        lambda *args: {"bubbleObjects": {"item": items}},
    )

    with caplog.at_level(logging.WARNING, logger=matrikkel_geometry.__name__):
        geom = matrikkel_geometry.hent_teiggeometri(MagicMock(), "4203", 306, 21)

    assert geom == {
        "type": "Polygon",
        "coordinates": [[[0, 0], [1, 0], [2, 0], [0, 2], [0, 0]]],
    }
    assert "Bue funnet" in caplog.text
    assert "Ugyldig geometri" not in caplog.text


def test_hent_teiggeometri_uten_geometri_returnerer_none_og_logger_advarsel(
    monkeypatch, caplog
):
    monkeypatch.setattr(
        matrikkel_geometry,
        "hent_matrikkelenhet_med_teiger",
        lambda *args: {"bubbleObjects": {"item": []}},
    )

    with caplog.at_level(logging.WARNING, logger=matrikkel_geometry.__name__):
        geom = matrikkel_geometry.hent_teiggeometri(MagicMock(), "4203", 306, 21)

    assert geom is None
    assert "Ingen geometri" in caplog.text
