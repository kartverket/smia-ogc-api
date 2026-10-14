"""Enhetstester for metrikkene rundt kallene mot Matrikkelen."""

from unittest.mock import MagicMock

import pytest
import requests
import zeep
from prometheus_client import REGISTRY
from pygeoapi.process.base import ProcessorExecuteError

from processes.utils import matrikkel_client
from processes.utils.matrikkel_client import (
    MatrikkelTokenAuth,
    get_matrikkel_client,
    hent_matrikkelenhet_med_teiger,
)


def antall_kall(outcome):
    verdi = REGISTRY.get_sample_value(
        "matrikkel_request_duration_seconds_count", {"outcome": outcome}
    )
    return verdi or 0


def antall_token(grant, outcome):
    verdi = REGISTRY.get_sample_value(
        "matrikkel_token_requests_total", {"grant": grant, "outcome": outcome}
    )
    return verdi or 0


def klient_som(svar=None, feil=None):
    klient = MagicMock(name="matrikkel_client")
    kall = klient.service.findMatrikkelenhetMedTeiger
    if feil is not None:
        kall.side_effect = feil
    else:
        kall.return_value = svar
    return klient


def test_vellykket_kall_telles_som_ok():
    foer = antall_kall("ok")

    hent_matrikkelenhet_med_teiger(klient_som(svar={}), "4602", 1, 1)

    assert antall_kall("ok") == foer + 1


@pytest.mark.parametrize(
    ("feil", "outcome"),
    [
        (zeep.exceptions.Fault("Matrikkelenheten finnes ikke"), "not_found"),
        (zeep.exceptions.Fault("Uventet feil"), "fault"),
        (requests.ConnectionError("nede"), "error"),
    ],
)
def test_feilet_kall_telles_med_riktig_utfall(feil, outcome):
    foer = antall_kall(outcome)

    with pytest.raises(ProcessorExecuteError):
        hent_matrikkelenhet_med_teiger(klient_som(feil=feil), "4602", 1, 1)

    assert antall_kall(outcome) == foer + 1


def test_kall_som_avbrytes_av_gunicorn_telles_som_error():
    """Ved worker-timeout avslutter gunicorn workeren med SystemExit midt i kallet."""
    foer_ok = antall_kall("ok")
    foer_error = antall_kall("error")

    with pytest.raises(SystemExit):
        hent_matrikkelenhet_med_teiger(klient_som(feil=SystemExit(1)), "4602", 1, 1)

    assert antall_kall("ok") == foer_ok
    assert antall_kall("error") == foer_error + 1


def test_klient_som_ikke_kan_opprettes_telles_som_error(monkeypatch):
    monkeypatch.setattr(matrikkel_client, "_matrikkel_client", None)
    monkeypatch.setattr(
        matrikkel_client,
        "create_matrikkel_client",
        MagicMock(side_effect=requests.ConnectionError("WSDL utilgjengelig")),
    )
    foer = antall_kall("error")

    with pytest.raises(ProcessorExecuteError):
        get_matrikkel_client()

    assert antall_kall("error") == foer + 1


def test_klientoppsett_som_avbrytes_av_gunicorn_telles_som_error(monkeypatch):
    monkeypatch.setattr(matrikkel_client, "_matrikkel_client", None)
    monkeypatch.setattr(
        matrikkel_client,
        "create_matrikkel_client",
        MagicMock(side_effect=SystemExit(1)),
    )
    foer = antall_kall("error")

    with pytest.raises(SystemExit):
        get_matrikkel_client()

    assert antall_kall("error") == foer + 1


def token_session(post_svar=None, post_feil=None):
    session = MagicMock(name="session")
    session.get.return_value.json.return_value = {"token_endpoint": "http://token"}
    if post_feil is not None:
        session.post.side_effect = post_feil
    else:
        session.post.return_value.json.return_value = post_svar
    return session


def test_vellykket_tokenhenting_telles():
    foer = antall_token("password", "ok")
    session = token_session(post_svar={"access_token": "abc", "expires_in": 300})
    auth = MatrikkelTokenAuth("bruker", "passord", "http://well-known", session)

    auth._get_token()

    assert antall_token("password", "ok") == foer + 1


def test_feilet_tokenhenting_telles():
    foer = antall_token("password", "error")
    session = token_session(post_feil=requests.HTTPError("401"))
    auth = MatrikkelTokenAuth("bruker", "passord", "http://well-known", session)

    with pytest.raises(requests.HTTPError):
        auth._get_token()

    assert antall_token("password", "error") == foer + 1


def test_tokenhenting_som_avbrytes_av_gunicorn_telles_som_error():
    foer = antall_token("password", "error")
    session = token_session(post_feil=SystemExit(1))
    auth = MatrikkelTokenAuth("bruker", "passord", "http://well-known", session)

    with pytest.raises(SystemExit):
        auth._get_token()

    assert antall_token("password", "error") == foer + 1


@pytest.mark.parametrize(
    ("svar", "feil"),
    [
        ({}, KeyError),
        ({"access_token": "abc", "expires_in": None}, TypeError),
        ({"access_token": "abc", "refresh_expires_in": None}, TypeError),
    ],
)
def test_ugyldig_tokensvar_telles_som_error_uten_halvt_token(svar, feil):
    foer_ok = antall_token("password", "ok")
    foer_error = antall_token("password", "error")
    session = token_session(post_svar=svar)
    auth = MatrikkelTokenAuth("bruker", "passord", "http://well-known", session)

    with pytest.raises(feil):
        auth._get_token()

    assert antall_token("password", "ok") == foer_ok
    assert antall_token("password", "error") == foer_error + 1
    assert auth._access_token is None


@pytest.mark.parametrize("outcome", ["ok", "not_found", "fault", "error"])
def test_kall_serien_finnes_foer_foerste_kall(outcome):
    verdi = REGISTRY.get_sample_value(
        "matrikkel_request_duration_seconds_count", {"outcome": outcome}
    )

    assert verdi is not None


@pytest.mark.parametrize("grant", ["password", "refresh_token"])
@pytest.mark.parametrize("outcome", ["ok", "error"])
def test_token_serien_finnes_foer_foerste_kall(grant, outcome):
    verdi = REGISTRY.get_sample_value(
        "matrikkel_token_requests_total", {"grant": grant, "outcome": outcome}
    )

    assert verdi is not None
