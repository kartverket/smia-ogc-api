"""Prosessor for bopliktsjekk basert på innsendt GeoJSON-geometri."""

import logging

from pygeoapi.process.base import BaseProcessor, ProcessorExecuteError

from processes.utils.boplikt_db import sjekk_boplikt
from processes.utils.boplikt_metadata import BOPLIKTSJEKK_OUTPUT

LOGGER = logging.getLogger(__name__)

PROCESS_METADATA = {
    "version": "0.1.0",
    "title": {"nb": "Bopliktsjekk for geometri"},
    "description": {
        "nb": "Sjekker om en geometri (Point, Polygon, MultiPolygon) "
        "er innenfor, delvis innenfor, eller utenfor bopliktområder. "
        "Koordinater må være i EPSG:25833."
    },
    "jobControlOptions": ["sync-execute"],
    "keywords": ["boplikt", "spatial"],
    "inputs": {
        "geometri": {
            "title": "Geometri",
            "description": "GeoJSON-geometri (Point, Polygon eller MultiPolygon) i EPSG:25833",
            "schema": {
                "type": "object",
                "contentMediaType": "application/geo+json",
            },
            "minOccurs": 1,
            "maxOccurs": 1,
        }
    },
    "outputs": BOPLIKTSJEKK_OUTPUT,
    "example": {
        "inputs": {
            "geometri": {
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
        },
    },
}


class BopliktSjekkGeometriProcessor(BaseProcessor):
    """Prosessor som sjekker om en geometri er innenfor bopliktområder."""

    def __init__(self, processor_def):
        super().__init__(processor_def, PROCESS_METADATA)

    def execute(self, data, outputs=None):
        """Valider innsendt geometri og kjør bopliktsjekk mot databasen."""
        geojson_geom = data.get("geometri")
        if geojson_geom is None:
            raise ProcessorExecuteError(user_msg="Mangler input: geometri")

        geom_type = geojson_geom.get("type", "")
        if geom_type not in ("Point", "Polygon", "MultiPolygon"):
            raise ProcessorExecuteError(
                user_msg=f"Ugyldig geometritype: {geom_type}. "
                "Må være Point, Polygon eller MultiPolygon."
            )

        result = sjekk_boplikt(geojson_geom)
        return "application/json", result
