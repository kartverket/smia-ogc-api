"""Enhetstester for BopliktSjekkProcessor."""

from types import SimpleNamespace
from unittest.mock import MagicMock, create_autospec

import pytest
from pygeoapi.process.base import ProcessorExecuteError

from processes import bopliktsjekk
from processes.bopliktsjekk import BopliktSjekkProcessor
from processes.utils.boplikt_db import _COLUMNS

KOMMUNENUMMER = "4203"
GARDSNUMMER = 306
BRUKSNUMMER = 21

INPUT = {
    "kommunenummer": KOMMUNENUMMER,
    "gardsnummer": GARDSNUMMER,
    "bruksnummer": BRUKSNUMMER,
}

TEIG = {
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

DELVIS_RESULTAT = {"iBopliktomrade": "DELVIS"}


def kommune_rad(gjelder_kun_del_av_kommunen):
    """Én rad slik sjekk_kommune_boplikt returnerer dem."""
    return {
        "gjelderKunDelAvKommunen": gjelder_kun_del_av_kommunen,
        "gjelderForBruktSomHelarsbolig": True,
        "gjelderForBoligIkkeTattIBruk": False,
        "gjelderForUbebygdBoligtomt": False,
        "harUnntakFraSlektskapsunntak": True,
        "andreLokaleAvgrensninger": None,
        "harUsikkerAvgrensning": False,
    }


def stub(monkeypatch, navn, return_value):
    mock = create_autospec(getattr(bopliktsjekk, navn), return_value=return_value)
    monkeypatch.setattr(bopliktsjekk, navn, mock)
    return mock


@pytest.fixture
def prosessor():
    # BaseProcessor.__init__ krever processor_def["name"].
    # Resten av configen er irrelevant for disse testene, så bruker minste gyldige oppsett.
    return BopliktSjekkProcessor({"name": "bopliktsjekk"})


@pytest.fixture
def db(monkeypatch):
    """Stubber databasekallene."""
    return SimpleNamespace(
        sjekk_kommune_boplikt=stub(monkeypatch, "sjekk_kommune_boplikt", []),
        sjekk_boplikt=stub(monkeypatch, "sjekk_boplikt", DELVIS_RESULTAT),
    )


@pytest.fixture
def matrikkel(monkeypatch):
    """Stubber hele Matrikkel-siden."""
    client = MagicMock(name="matrikkel_client")
    return SimpleNamespace(
        client=client,
        get_matrikkel_client=stub(monkeypatch, "get_matrikkel_client", client),
        hent_teiggeometri=stub(
            monkeypatch,
            "hent_teiggeometri",
            (TEIG, [], {"is_valid": True, "reason": None}, False),
        ),
    )


def test_fake_rad_har_samme_kolonner_som_koden():
    """Sjekker om testdataene har samme kolonner som produksjonskoden forventer."""

    assert set(kommune_rad(False)) == set(_COLUMNS)


@pytest.mark.parametrize(
    "manglende_felt", ["kommunenummer", "gardsnummer", "bruksnummer"]
)
def test_manglende_paakrevd_felt_gir_feil(prosessor, manglende_felt):
    data = {k: v for k, v in INPUT.items() if k != manglende_felt}

    with pytest.raises(ProcessorExecuteError, match="Mangler påkrevde felt"):
        prosessor.execute(data)


def test_tomt_kommunenummer_gir_feil(prosessor):
    with pytest.raises(ProcessorExecuteError, match="Mangler påkrevde felt"):
        prosessor.execute({**INPUT, "kommunenummer": ""})


def test_kommune_uten_boplikt_gir_nei(prosessor, db, matrikkel):
    db.sjekk_kommune_boplikt.return_value = []

    mimetype, resultat = prosessor.execute(INPUT)

    assert mimetype == "application/json"
    assert resultat == {"iBopliktomrade": "NEI"}
    db.sjekk_kommune_boplikt.assert_called_once_with(KOMMUNENUMMER)
    db.sjekk_boplikt.assert_not_called()
    matrikkel.get_matrikkel_client.assert_not_called()


def test_full_boplikt_gir_ja_med_materielle_vilkaar(prosessor, db, matrikkel):
    db.sjekk_kommune_boplikt.return_value = [kommune_rad(False)]

    mimetype, resultat = prosessor.execute(INPUT)

    materielle_vilkaar = {
        k: v for k, v in kommune_rad(False).items() if k != "gjelderKunDelAvKommunen"
    }

    assert mimetype == "application/json"
    assert resultat == {"iBopliktomrade": "JA", **materielle_vilkaar}


def test_full_boplikt_kaller_ikke_matrikkel(prosessor, db, matrikkel):
    db.sjekk_kommune_boplikt.return_value = [kommune_rad(False)]

    prosessor.execute(INPUT)

    matrikkel.get_matrikkel_client.assert_not_called()
    matrikkel.hent_teiggeometri.assert_not_called()
    db.sjekk_boplikt.assert_not_called()


def test_delvis_boplikt_henter_teiggeometri(prosessor, db, matrikkel):
    db.sjekk_kommune_boplikt.return_value = [kommune_rad(True)]

    _, resultat = prosessor.execute(INPUT)

    matrikkel.hent_teiggeometri.assert_called_once_with(
        matrikkel.client, KOMMUNENUMMER, GARDSNUMMER, BRUKSNUMMER
    )
    assert resultat == DELVIS_RESULTAT


def test_delvis_boplikt_filtrerer_paa_kommunenummer(prosessor, db, matrikkel):
    db.sjekk_kommune_boplikt.return_value = [kommune_rad(True)]

    prosessor.execute(INPUT)

    db.sjekk_boplikt.assert_called_once_with(TEIG, KOMMUNENUMMER)


def test_manglende_teiggeometri_gir_feil(prosessor, db, matrikkel):
    db.sjekk_kommune_boplikt.return_value = [kommune_rad(True)]
    matrikkel.hent_teiggeometri.return_value = (
        None,
        [],
        {"is_valid": False, "reason": None},
        False,
    )

    with pytest.raises(ProcessorExecuteError, match="Fant ingen teiggeometri"):
        prosessor.execute(INPUT)

    db.sjekk_boplikt.assert_not_called()
