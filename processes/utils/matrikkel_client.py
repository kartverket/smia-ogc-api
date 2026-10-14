"""Hjelpefunksjoner for kommunikasjon med Matrikkel-API via SOAP (zeep)."""

import json
import logging
import os
import threading
import time

import requests
import zeep
from prometheus_client import Counter, Histogram
from pygeoapi.process.base import ProcessorExecuteError
from requests import Session
from requests.auth import AuthBase
from zeep import helpers
from zeep.transports import Transport

LOGGER = logging.getLogger(__name__)

# outcome: ok, not_found (matrikkelenheten finnes ikke), fault (annen SOAP-fault)
# eller error (nettverk, tidsavbrudd, token, eller at klienten ikke lar seg opprette).
# not_found er ikke en feil hos Matrikkelen.
MATRIKKEL_KALL = Histogram(
    "matrikkel_request_duration_seconds",
    "Varighet på SOAP-kall mot Matrikkelen",
    ["outcome"],
    # Standardbøttene stopper på 10 s, og et kall kan vare til gunicorn dreper workeren.
    buckets=(0.1, 0.25, 0.5, 1, 2.5, 5, 10, 15, 30),
)
MATRIKKEL_TOKEN = Counter(
    "matrikkel_token_requests_total",
    "Tokenforespørsler mot Matrikkelen",
    ["grant", "outcome"],
)

# Oppretter seriene med verdi 0 ved oppstart. Ellers dukker en serie først opp ved
# første feil, og rate() og increase() ser ikke økningen fra ingenting til én.
for _outcome in ("ok", "not_found", "fault", "error"):
    MATRIKKEL_KALL.labels(_outcome)
for _grant in ("password", "refresh_token"):
    for _outcome in ("ok", "error"):
        MATRIKKEL_TOKEN.labels(_grant, _outcome)

WSDL_URL = "https://matrikkel.no/matrikkelapi/wsapi/v1/MatrikkelenhetServiceWS?WSDL"
WELL_KNOWN_URL = (
    "https://auth.matrikkel.no/auth/realms/matrikkelen-prod/"
    ".well-known/openid-configuration"
)
CLIENT_ID = "matrikkel-token-exchange"

# Fornyer tokenet litt før det faktisk utløper
EXPIRY_MARGIN_SECONDS = 30

_matrikkel_client = None


class MatrikkelTokenAuth(AuthBase):
    """Legger ved `Authorization: Bearer <access_token>` på hver forespørsel.

    Tokenet caches og fornyes automatisk:
      1. Gjenbruk access_token hvis det fortsatt er gyldig.
      2. Forny med refresh_token hvis access_token er utløpt.
      3. Nytt password grant hvis begge er utløpt.
    """

    def __init__(self, username, password, well_known_url, session=None):
        self._username = username
        self._password = password
        self._well_known_url = well_known_url
        self._session = session or requests.Session()
        self._lock = threading.Lock()

        self._token_endpoint = None
        self._access_token = None
        self._access_expires_at = 0.0
        self._refresh_token = None
        self._refresh_expires_at = 0.0

    def __call__(self, request):
        request.headers["Authorization"] = f"Bearer {self._get_token()}"
        # Hvis serveren likevel avviser tokenet, tving fornying og prøv én gang til.
        request.register_hook("response", self._handle_401)
        return request

    def _get_token(self):
        with self._lock:
            now = time.monotonic()
            if self._access_token and now < self._access_expires_at:
                return self._access_token
            if self._refresh_token and now < self._refresh_expires_at:
                try:
                    return self._request_token(
                        {
                            "grant_type": "refresh_token",
                            "client_id": CLIENT_ID,
                            "refresh_token": self._refresh_token,
                        }
                    )
                except requests.RequestException as e:
                    LOGGER.warning(
                        "Kunne ikke forny token med refresh_token, "
                        "faller tilbake til password grant: %s",
                        e,
                    )
            return self._request_token(
                {
                    "grant_type": "password",
                    "client_id": CLIENT_ID,
                    "username": self._username,
                    "password": self._password,
                }
            )

    def _request_token(self, data):
        """Utfører selve token-kallet. Kalles med _lock holdt."""
        grant = data["grant_type"]
        try:
            endpoint = self._get_token_endpoint()
            response = self._session.post(endpoint, data=data, timeout=30)
            response.raise_for_status()
            payload = response.json()
            # Hele svaret leses her, så et ugyldig svar telles som feil og ikke
            # etterlater et halvt oppdatert token.
            now = time.monotonic()
            access_token = payload["access_token"]
            access_expires_at = (
                now + payload.get("expires_in", 300) - EXPIRY_MARGIN_SECONDS
            )
            refresh_token = payload.get("refresh_token")
            refresh_expires_at = (
                now + payload.get("refresh_expires_in", 0) - EXPIRY_MARGIN_SECONDS
            )
        except BaseException:
            # BaseException: ved worker-timeout avslutter gunicorn workeren med SystemExit.
            MATRIKKEL_TOKEN.labels(grant, "error").inc()
            raise
        MATRIKKEL_TOKEN.labels(grant, "ok").inc()

        self._access_token = access_token
        self._access_expires_at = access_expires_at
        self._refresh_token = refresh_token
        self._refresh_expires_at = refresh_expires_at
        LOGGER.debug("Hentet nytt Matrikkel-token (grant_type=%s)", grant)
        return self._access_token

    def _get_token_endpoint(self):
        """Henter token_endpoint dynamisk fra well-known-URL og cacher det."""
        if self._token_endpoint is None:
            response = self._session.get(self._well_known_url, timeout=30)
            response.raise_for_status()
            self._token_endpoint = response.json()["token_endpoint"]
        return self._token_endpoint

    def _invalidate(self):
        with self._lock:
            self._access_token = None
            self._access_expires_at = 0.0

    def _handle_401(self, response, **kwargs):
        if response.status_code != 401 or response.request.headers.get(
            "X-Matrikkel-Token-Retry"
        ):
            return response

        LOGGER.info("Fikk 401 fra Matrikkel — henter nytt token og prøver på nytt.")
        self._invalidate()

        _ = response.content  # tømmer socketen så tilkoblingen kan gjenbrukes
        response.close()

        retry = response.request.copy()
        retry.headers["X-Matrikkel-Token-Retry"] = "1"
        retry.headers["Authorization"] = f"Bearer {self._get_token()}"

        new_response = response.connection.send(retry, **kwargs)
        new_response.history.append(response)
        new_response.request = retry
        return new_response


def get_matrikkel_client():
    """Returnerer en singleton SOAP-klient."""
    global _matrikkel_client
    if _matrikkel_client is None:
        start = time.monotonic()
        try:
            _matrikkel_client = create_matrikkel_client()
        except Exception as e:  # noqa: BLE001
            # Uten klient kommer vi aldri til SOAP-kallet, så feilen telles her.
            MATRIKKEL_KALL.labels("error").observe(time.monotonic() - start)
            LOGGER.error(
                "Kunne ikke opprette Matrikkel-klient "
                "(sjekk WSDL-URL, well-known-URL og credentials): %s",
                e,
            )
            raise ProcessorExecuteError(
                user_msg="En feil oppstod, prøv igjen senere."
            ) from None
        except BaseException:
            # Ved worker-timeout avslutter gunicorn workeren med SystemExit.
            MATRIKKEL_KALL.labels("error").observe(time.monotonic() - start)
            raise
    return _matrikkel_client


def create_matrikkel_client():
    """Opprett en zeep SOAP-klient mot Matrikkel-API."""
    wsdl = os.environ.get("MATRIKKEL_WSDL_URL", WSDL_URL)
    well_known_url = os.environ.get("MATRIKKELEN_WELLKNOWN_URL", WELL_KNOWN_URL)
    username = os.environ.get("MATRIKKELEN_USERNAME")
    password = os.environ.get("MATRIKKELEN_PASSWORD")

    if not username or not password:
        LOGGER.warning(
            "MATRIKKELEN_USERNAME eller MATRIKKELEN_PASSWORD er ikke satt "
            "— autentisering vil feile."
        )

    settings = zeep.Settings(strict=False, xml_huge_tree=True)
    session = Session()
    session.auth = MatrikkelTokenAuth(username, password, well_known_url)
    transport = Transport(session=session)
    return zeep.Client(wsdl=wsdl, settings=settings, transport=transport)


def hent_matrikkelenhet_med_teiger(client, kommunenummer, gardsnummer, bruksnummer):
    """Kall findMatrikkelenhetMedTeiger og returner svaret som dict.

    Args:
        client: zeep SOAP-klient mot Matrikkel.
        kommunenummer (str): Kommunenummer (4 siffer).
        gardsnummer (int): Gardsnummer.
        bruksnummer (int): Bruksnummer.

    Returns:
        dict: Deserialisert SOAP-respons.

    Raises:
        ProcessorExecuteError: Ved SOAP-feil eller nettverksfeil mot Matrikkel.
    """
    EPSG_25833_VALUE = 11
    start = time.monotonic()
    # Starter som error: ved worker-timeout avslutter gunicorn workeren med
    # SystemExit, som går forbi except-grenene under, men ikke forbi finally.
    outcome = "error"
    try:
        result = client.service.findMatrikkelenhetMedTeiger(
            matrikkelenhetIdent={
                "kommuneIdent": {"kommunenummer": kommunenummer},
                "gardsnummer": int(gardsnummer),
                "bruksnummer": int(bruksnummer),
                "festenummer": 0,
                "seksjonsnummer": 0,
            },
            matrikkelContext={
                "locale": "no_NO_B",
                "brukOriginaleKoordinater": False,
                "koordinatsystemKodeId": {"value": EPSG_25833_VALUE},
                "systemVersion": "4.25.0.0",
                "klientIdentifikasjon": "ogc-api",
                "snapshotVersion": {"timestamp": "9999-01-01T00:00:00+01:00"},
            },
        )
        outcome = "ok"
    except zeep.exceptions.Fault as e:
        if "finnes ikke" in (e.message or "").lower():
            outcome = "not_found"
            LOGGER.info("Matrikkelenhet ikke funnet: %s", e.message)
            raise ProcessorExecuteError(
                user_msg="Matrikkelenheten ble ikke funnet. "
                "Kontroller at kommunenummer, gårdsnummer og bruksnummer er korrekt."
            ) from None
        outcome = "fault"
        LOGGER.error("SOAP fault: %s", e)
        raise ProcessorExecuteError(
            user_msg="En feil oppstod, prøv igjen senere."
        ) from None
    except Exception as e:  # noqa: BLE001
        LOGGER.error("SOAP error (%s): %s", type(e).__name__, e)
        raise ProcessorExecuteError(
            user_msg="En feil oppstod, prøv igjen senere."
        ) from None
    finally:
        MATRIKKEL_KALL.labels(outcome).observe(time.monotonic() - start)

    result_dict = helpers.serialize_object(result, dict)
    return json.loads(json.dumps(result_dict, default=str))
