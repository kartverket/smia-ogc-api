"""Integrasjonstester for boplikt_db mot ekte PostGIS."""

import pytest

from processes.utils import boplikt_db
from processes.utils.boplikt_db import (
    _COLUMNS,
    sjekk_boplikt,
    sjekk_kommune_boplikt,
)

pytestmark = pytest.mark.integration

HELT_INNENFOR = {
    "type": "Polygon",
    "coordinates": [
        [
            [68987, 6627342],
            [69037, 6627347],
            [69040, 6627321],
            [68987, 6627342],
        ]
    ],
}

KRYSSER_GRENSE = {
    "type": "Polygon",
    "coordinates": [
        [
            [68850, 6627340],
            [68950, 6627340],
            [68950, 6627360],
            [68850, 6627360],
            [68850, 6627340],
        ]
    ],
}

UTENFOR = {
    "type": "Polygon",
    "coordinates": [
        [
            [300000, 7000000],
            [300100, 7000000],
            [300100, 7000100],
            [300000, 7000000],
        ]
    ],
}

KRYSSER_TO_OMRADER = {
    "type": "Polygon",
    "coordinates": [
        [
            [68950, 6627320],
            [69150, 6627320],
            [69150, 6627360],
            [68950, 6627360],
            [68950, 6627320],
        ]
    ],
}


def test_kolonner_matcher_koden():
    rader = boplikt_db._execute_query(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = %s AND table_name = %s",
        ("inndelinger", "bopliktomraade"),
    )

    faktiske_kolonner = {rad[0] for rad in rader}

    assert set(_COLUMNS) <= faktiske_kolonner


def test_kommune_uten_boplikt_gir_tom_liste():
    assert sjekk_kommune_boplikt("9999") == []


def test_kommune_med_full_boplikt():
    rader = sjekk_kommune_boplikt("0301")

    assert len(rader) == 1
    assert rader[0]["gjelderKunDelAvKommunen"] is False


def test_geometri_helt_innenfor_gir_ja():
    resultat = sjekk_boplikt(HELT_INNENFOR)

    assert resultat["iBopliktomrade"] == "JA"
    assert "gjelderKunDelAvKommunen" not in resultat


def test_geometri_utenfor_gir_nei():
    assert sjekk_boplikt(UTENFOR) == {"iBopliktomrade": "NEI"}


def test_geometri_krysser_grense_gir_delvis():
    resultat = sjekk_boplikt(KRYSSER_GRENSE)

    assert resultat["iBopliktomrade"] == "DELVIS"


def test_geometri_krysser_to_omrader_gir_delvis():
    resultat = sjekk_boplikt(KRYSSER_TO_OMRADER)

    assert resultat["iBopliktomrade"] == "DELVIS"


def test_filtrering_paa_kommunenummer_utelukker_naboomrade():
    assert sjekk_boplikt(HELT_INNENFOR, kommunenummer="4602")["iBopliktomrade"] == "NEI"
    assert sjekk_boplikt(HELT_INNENFOR, kommunenummer="4601")["iBopliktomrade"] == "JA"
