"""Hjelpefunksjoner for kommunikasjon med Matrikkel-API via SOAP (zeep)."""

import json
import logging
import os
import threading
import time
import uuid

import jwt
import requests
import zeep
from pygeoapi.process.base import ProcessorExecuteError
from requests import Session
from requests.auth import AuthBase
from zeep import helpers
from zeep.transports import Transport

LOGGER = logging.getLogger(__name__)
WSDL_URL = "https://betatest.matrikkel.no/matrikkelapi/wsapi/v1/MatrikkelenhetServiceWS?WSDL"
MASKINPORTEN_SCOPE = "kartverk:matrikkel:brukernavn"

# Fornyer tokenet litt før det faktisk utløper
EXPIRY_MARGIN_SECONDS = 30

_matrikkel_client = None


class MatrikkelTokenAuth(AuthBase):
    """Legger ved Bearer-token fra Maskinporten og X-Matrikkel-Brukernavn på hver forespørsel.

    Tokenet caches til det utløper — Maskinporten har ingen refresh_token.
    """

    def __init__(self, username, client_id, jwk_json, token_endpoint, issuer, resource, session=None):
        self._username = username
        self._client_id = client_id
        self._jwk_json = jwk_json
        self._token_url = token_endpoint
        self._issuer = issuer
        self._resource = resource
        self._session = session or requests.Session()
        self._lock = threading.Lock()

        self._access_token = None
        self._access_expires_at = 0.0

    def __call__(self, request):
        request.headers["Authorization"] = f"Bearer {self._get_token()}"
        request.headers["X-Matrikkel-Brukernavn"] = self._username
        request.register_hook("response", self._handle_401)
        return request

    def _get_token(self):
        with self._lock:
            now = time.monotonic()
            if self._access_token and now < self._access_expires_at:
                return self._access_token
            return self._fetch_token()

    def _fetch_token(self):
        assertion = self._generate_jwt()
        response = self._session.post(
            self._token_url,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()

        now = time.monotonic()
        self._access_token = payload["access_token"]
        self._access_expires_at = (
            now + payload.get("expires_in", 120) - EXPIRY_MARGIN_SECONDS
        )
        LOGGER.debug("Hentet nytt Maskinporten-token")
        return self._access_token

    def _generate_jwt(self):
        jwk = json.loads(self._jwk_json)
        private_key = jwt.algorithms.RSAAlgorithm.from_jwk(jwk)
        now = int(time.time())
        return jwt.encode(
            {
                "iss": self._client_id,
                "sub": self._client_id,
                "aud": self._issuer,
                "scope": MASKINPORTEN_SCOPE,
                "resource": self._resource,
                "iat": now,
                "exp": now + 180,
                "jti": str(uuid.uuid4()),
            },
            private_key,
            algorithm="RS256",
            headers={"kid": jwk["kid"]},
        )

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
        try:
            _matrikkel_client = create_matrikkel_client()
        except Exception as e:  # noqa: BLE001
            LOGGER.error(
                "Kunne ikke opprette Matrikkel-klient "
                "(sjekk WSDL-URL, well-known-URL og credentials): %s",
                e,
            )
            raise ProcessorExecuteError(
                user_msg="En feil oppstod, prøv igjen senere."
            ) from None
    return _matrikkel_client


def create_matrikkel_client(wsdl=None):
    """Opprett en zeep SOAP-klient mot Matrikkel-API."""
    wsdl = wsdl or os.environ.get("MATRIKKELEN_WSDL_URL") or WSDL_URL
    username = os.environ.get("MATRIKKELEN_USERNAME")
    client_id = os.environ.get("MASKINPORTEN_CLIENT_ID")
    jwk_json = os.environ.get("MASKINPORTEN_CLIENT_JWK")
    token_endpoint = os.environ.get("MASKINPORTEN_TOKEN_ENDPOINT")
    issuer = os.environ.get("MASKINPORTEN_ISSUER")
    resource = os.environ.get("MASKINPORTEN_RESOURCE")

    LOGGER.info("token_endpoint=%s issuer=%s resource=%s", token_endpoint, issuer, resource)
    if not all([username, client_id, jwk_json, token_endpoint, issuer, resource]):
        LOGGER.warning(
            "En eller flere Maskinporten-variabler er ikke satt — autentisering vil feile."
        )

    settings = zeep.Settings(strict=False, xml_huge_tree=True)
    session = Session()
    session.auth = MatrikkelTokenAuth(username, client_id, jwk_json, token_endpoint, issuer, resource)
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
    except zeep.exceptions.Fault as e:
        if "finnes ikke" in (e.message or "").lower():
            LOGGER.info("Matrikkelenhet ikke funnet: %s", e.message)
            raise ProcessorExecuteError(
                user_msg="Matrikkelenheten ble ikke funnet. "
                "Kontroller at kommunenummer, gårdsnummer og bruksnummer er korrekt."
            ) from None
        LOGGER.error("SOAP fault: %s", e)
        raise ProcessorExecuteError(
            user_msg="En feil oppstod, prøv igjen senere."
        ) from None
    except Exception as e:  # noqa: BLE001
        LOGGER.error("SOAP error (%s): %s", type(e).__name__, e)
        raise ProcessorExecuteError(
            user_msg="En feil oppstod, prøv igjen senere."
        ) from None

    result_dict = helpers.serialize_object(result, dict)
    return json.loads(json.dumps(result_dict, default=str))
