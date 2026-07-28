"""Hjelpefunksjoner for kommunikasjon med Matrikkel-API via SOAP (zeep)."""

import json
import logging
import os

import zeep
from pygeoapi.process.base import ProcessorExecuteError
from requests import Session
from requests.auth import HTTPBasicAuth
from zeep import helpers
from zeep.transports import Transport

LOGGER = logging.getLogger(__name__)
WSDL_URL = "https://matrikkel.no/matrikkelapi/wsapi/v1/MatrikkelenhetServiceWS?WSDL"

_matrikkel_client = None


def get_matrikkel_client():
    """Returnerer en singleton SOAP-klient."""
    global _matrikkel_client
    if _matrikkel_client is None:
        try:
            _matrikkel_client = create_matrikkel_client()
        except Exception as e:
            LOGGER.error(
                "Kunne ikke opprette Matrikkel-klient (sjekk WSDL-URL og credentials): %s",
                e,
            )
            raise ProcessorExecuteError(
                user_msg="En feil oppstod, prøv igjen senere."
            ) from None
    return _matrikkel_client


def create_matrikkel_client(wsdl=None):
    """Opprett en zeep SOAP-klient mot Matrikkel-API."""
    wsdl = wsdl or os.environ.get("MATRIKKEL_WSDL_URL", WSDL_URL)
    username = os.environ.get("MATRIKKELEN_USERNAME")
    password = os.environ.get("MATRIKKELEN_PASSWORD")

    if not username or not password:
        LOGGER.warning(
            "MATRIKKELEN_USERNAME eller MATRIKKELEN_PASSWORD er ikke satt — autentisering vil feile."
        )

    settings = zeep.Settings(strict=False, xml_huge_tree=True)
    session = Session()
    session.auth = HTTPBasicAuth(username, password)
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
        LOGGER.error("SOAP fault: %s", e)
        raise ProcessorExecuteError(
            user_msg="En feil oppstod, prøv igjen senere."
        ) from None
    except Exception as e:
        LOGGER.error("SOAP error (%s): %s", type(e).__name__, e)
        raise ProcessorExecuteError(
            user_msg="En feil oppstod, prøv igjen senere."
        ) from None

    result_dict = helpers.serialize_object(result, dict)
    return json.loads(json.dumps(result_dict, default=str))
