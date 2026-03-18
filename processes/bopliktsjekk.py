"""
Prosessor for bopliktsjekk med matrikkelnummer som input.

Fremgangsmåte:
  1. Sjekker først om kommunen til matrikkelenheten har boplikt.
  2. Hvis ingen boplikt: returnerer boplikt=nei.
  3. Hvis full boplikt: returnerer boplikt=ja uten å hente geometri.
  4. Hvis delvis boplikt: henter teiggeometri fra Matrikkel-API og gjør romlig sjekk mot bopliktområder.

Returnerer:
    - dict: boplikt (ja/nei/delvis) og materielle vilkår
"""

import logging

from pygeoapi.process.base import BaseProcessor, ProcessorExecuteError

from processes.utils.boplikt_db import (
    bygg_boplikt_resultat,
    sjekk_boplikt,
    sjekk_kommune_boplikt,
)
from processes.utils.boplikt_metadata import BOPLIKTSJEKK_OUTPUT
from processes.utils.matrikkel_client import get_matrikkel_client
from processes.utils.matrikkel_geometry import hent_teiggeometri

LOGGER = logging.getLogger(__name__)

PROCESS_METADATA = {
    "version": "0.1.0",
    "title": {"nb": "Bopliktsjekk"},
    "description": {
        "nb": "Henter teiggeometri til en Matrikkelenhet og sjekker om eiendommen "
        "er innenfor, delvis innenfor, eller utenfor bopliktområder."
    },
    "jobControlOptions": ["sync-execute"],
    "keywords": ["boplikt", "matrikkel"],
    "inputs": {
        "kommunenummer": {
            "title": "Kommunenummer",
            "description": "Kommunenummer (4 siffer, f.eks. '3024')",
            "schema": {"type": "string"},
            "minOccurs": 1,
            "maxOccurs": 1,
        },
        "gardsnummer": {
            "title": "Gårdsnummer",
            "description": "Gårdsnummer",
            "schema": {"type": "integer"},
            "minOccurs": 1,
            "maxOccurs": 1,
        },
        "bruksnummer": {
            "title": "Bruksnummer",
            "description": "Bruksnummer",
            "schema": {"type": "integer"},
            "minOccurs": 1,
            "maxOccurs": 1,
        },
        "festenummer": {
            "title": "Festenummer",
            "description": "Festenummer, 0 hvis ingen",
            "schema": {"type": "integer"},
            "minOccurs": 0,
            "maxOccurs": 1,
        },
        "seksjonsnummer": {
            "title": "Seksjonsnummer",
            "description": "Seksjonsnummer, 0 hvis ingen",
            "schema": {"type": "integer"},
            "minOccurs": 0,
            "maxOccurs": 1,
        },
    },
    "outputs": BOPLIKTSJEKK_OUTPUT,
    "example": {
        "inputs": {
            "kommunenummer": "4203",
            "gardsnummer": 306,
            "bruksnummer": 21,
        },
    },
}


class BopliktSjekkProcessor(BaseProcessor):
    """Sjekker boplikt for matrikkelenhet.

    1. Sjekker om kommunen har boplikt (full eller delvis).
    2. Hvis delvis boplikt: henter geometri og gjør romlig sjekk.
    3. Returnerer status og treff.
    """

    def __init__(self, processor_def):
        super().__init__(processor_def, PROCESS_METADATA)

    def execute(self, data, outputs=None):
        kommunenummer = data.get("kommunenummer")
        gardsnummer = data.get("gardsnummer")
        bruksnummer = data.get("bruksnummer")
        festenummer = data.get("festenummer", 0)
        seksjonsnummer = data.get("seksjonsnummer", 0)

        if not kommunenummer or gardsnummer is None or bruksnummer is None:
            raise ProcessorExecuteError(
                user_msg="Mangler påkrevde felt: kommunenummer, gardsnummer, bruksnummer"
            )

        mnr = f"{kommunenummer}-{gardsnummer}/{bruksnummer}/{festenummer}/{seksjonsnummer}"
        LOGGER.info("Bopliktsjekk startet for matrikkelenhet %s", mnr)

        kommune_med_boplikt = sjekk_kommune_boplikt(kommunenummer)

        if not kommune_med_boplikt:
            LOGGER.info("Kommune %s har ikke boplikt, returnerer INGEN", kommunenummer)
            return "application/json", {"iBopliktomrade": "NEI"}

        if all(not kommune["delvis_boplikt"] for kommune in kommune_med_boplikt):
            LOGGER.info("Kommune %s har full boplikt, returnerer FULL", kommunenummer)
            return "application/json", bygg_boplikt_resultat(
                "JA", kommune_med_boplikt[0]
            )

        LOGGER.info(
            "Kommune %s har delvis boplikt, henter teiggeometri fra Matrikkel-API",
            kommunenummer,
        )
        geom, hjelpelinjetyper, geom_validering, har_bue = hent_teiggeometri(
            get_matrikkel_client(),
            kommunenummer,
            gardsnummer,
            bruksnummer,
            festenummer,
            seksjonsnummer,
        )

        if geom is None:
            LOGGER.info("Fant ingen teiggeometri for %s", mnr)
            raise ProcessorExecuteError(
                user_msg="Fant ingen teiggeometri. "
                "Kontroller at kommunenummer, gårdsnummer og bruksnummer er korrekt."
            )

        result = sjekk_boplikt(geom, kommunenummer)
        LOGGER.info(
            "Bopliktsjekk fullført for %s, iBopliktomrade: %s",
            mnr,
            result.get("iBopliktomrade"),
        )
        return "application/json", result
