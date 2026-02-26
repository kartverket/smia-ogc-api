"""
Prosessor for bopliktsjekk via matrikkelnummer.

Fremgangsmåte:
  1. Sjekker først om kommunen til matrikkelenheten har boplikt.
  2. Hvis ingen boplikt: returnerer "UTENFOR".
  3. Hvis full boplikt: returnerer "INNENFOR" uten å hente geometri.
  4. Hvis delvis boplikt: henter teiggeometri fra Matrikkel-API og gjør romlig sjekk mot bopliktområder.

Parametre:
    - kommunenummer (str): Kommunenummer (4 siffer, f.eks. '3024')
    - gaardsnummer (int): Gårdsnummer (gnr)
    - bruksnummer (int): Bruksnummer (bnr)
    - festenummer (int, valgfri): Festenummer (fnr), 0 hvis ingen
    - seksjonsnummer (int, valgfri): Seksjonsnummer (snr), 0 hvis ingen

Returnerer:
    - dict: Status og treff mot bopliktområder
"""

import logging

from pygeoapi.process.base import BaseProcessor, ProcessorExecuteError

from processes.matrikkel_client import get_matrikkel_client, hent_teiggeometri
from processes.boplikt_check import sjekk_boplikt, sjekk_kommune_boplikt

LOGGER = logging.getLogger(__name__)

PROCESS_METADATA = {
    "version": "0.1.0",
    "title": {"nb": "Bopliktsjekk via matrikkelnummer"},
    "description": {
        "nb": "Henter teiggeometri fra Matrikkel og sjekker om eiendommen "
        "er innenfor, delvis innenfor, eller utenfor bopliktområder."
    },
    "jobControlOptions": ["sync-execute"],
    "keywords": ["boplikt", "matrikkel", "spatial"],
    "inputs": {
        "kommunenummer": {
            "title": "Kommunenummer",
            "description": "Kommunenummer (4 siffer, f.eks. '3024')",
            "schema": {"type": "string"},
            "minOccurs": 1,
            "maxOccurs": 1,
        },
        "gaardsnummer": {
            "title": "Gårdsnummer",
            "description": "Gårdsnummer (gnr)",
            "schema": {"type": "integer"},
            "minOccurs": 1,
            "maxOccurs": 1,
        },
        "bruksnummer": {
            "title": "Bruksnummer",
            "description": "Bruksnummer (bnr)",
            "schema": {"type": "integer"},
            "minOccurs": 1,
            "maxOccurs": 1,
        },
        "festenummer": {
            "title": "Festenummer",
            "description": "Festenummer (fnr), 0 hvis ingen",
            "schema": {"type": "integer"},
            "minOccurs": 0,
            "maxOccurs": 1,
        },
        "seksjonsnummer": {
            "title": "Seksjonsnummer",
            "description": "Seksjonsnummer (snr), 0 hvis ingen",
            "schema": {"type": "integer"},
            "minOccurs": 0,
            "maxOccurs": 1,
        },
    },
    "outputs": {
        "resultat": {
            "title": "Bopliktsjekk-resultat",
            "description": "Status og treff mot bopliktområder",
            "schema": {
                "type": "object",
                "contentMediaType": "application/json",
            },
        }
    },
    "example": {
        "inputs": {
            "kommunenummer": "4203",
            "gaardsnummer": 306,
            "bruksnummer": 21,
        }
    },
}



class BopliktsjekkMatrikkelenhetsnummerProcessor(BaseProcessor):
    """Sjekker boplikt for matrikkelenhet.

    1. Sjekker om kommunen har boplikt (full eller delvis).
    2. Hvis delvis boplikt: henter geometri og gjør romlig sjekk.
    3. Returnerer status og treff.
    """

    def __init__(self, processor_def):
        super().__init__(processor_def, PROCESS_METADATA)

    def execute(self, data, outputs=None):
        kommunenummer = data.get("kommunenummer")
        gardsnummer = data.get("gaardsnummer")
        bruksnummer = data.get("bruksnummer")
        festenummer = data.get("festenummer", 0)
        seksjonsnummer = data.get("seksjonsnummer", 0)

        if not kommunenummer or gardsnummer is None or bruksnummer is None:
            raise ProcessorExecuteError(
                "Mangler påkrevde felt: kommunenummer, gaardsnummer, bruksnummer"
            )

        # Først sjekk om kommunen har boplikt og om det er delvis boplikt
        kommune_treff = sjekk_kommune_boplikt(kommunenummer)

        if not kommune_treff:
            return "application/json", {"status": "UTENFOR", "treff": []}

        if all(not t["delvis_boplikt"] for t in kommune_treff):
            return "application/json", {
                "status": "INNENFOR",
                "treff": [{**t, "relasjon": "INNENFOR"} for t in kommune_treff],
            }

        # Delvis boplikt — må hente geometri og gjøre romlig sjekk
        geom, hjelpelinjetyper = hent_teiggeometri(
            get_matrikkel_client(), kommunenummer, gardsnummer, bruksnummer,
            festenummer, seksjonsnummer,
        )

        if geom is None:
            raise ProcessorExecuteError(
                f"Fant ingen teiggeometri for matrikkelenhet i kommune {kommunenummer}. "
                "Kontroller at kommunenummer, gårdsnummer og bruksnummer er korrekt."
            )

        result = sjekk_boplikt(geom, kommunenummer)
        result["teig"] = {"hjelpelinjetyper": hjelpelinjetyper}
        return "application/json", result
