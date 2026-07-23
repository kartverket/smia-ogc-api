"""Prosessor for bopliktsjekk basert på innsendt GeoJSON-geometri."""

import logging
import os

from pygeoapi.process.base import BaseProcessor, ProcessorExecuteError
from shapely import get_num_coordinates
from shapely.geometry import shape

from processes.utils.boplikt_db import sjekk_boplikt
from processes.utils.boplikt_metadata import BOPLIKTSJEKK_OUTPUT

LOGGER = logging.getLogger(__name__)

# Node og områdebegrensninger for å unngå Denial-of-Service
_MAX_VERTICES = int(os.environ.get("GEOM_MAX_VERTICES", "10000"))
_MAX_BBOX_AREA_KM2 = float(os.environ.get("GEOM_MAX_BBOX_AREA_KM2", "1000"))
_MAX_BBOX_AREA_M2 = _MAX_BBOX_AREA_KM2 * 1e6

_X_MIN, _X_MAX = -500_000, 1_100_000
_Y_MIN, _Y_MAX = 6_000_000, 9_000_000

_ALLOWED_TYPES = ("Point", "Polygon", "MultiPolygon")

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

        _valider_geometri(geojson_geom)

        result = sjekk_boplikt(geojson_geom)
        return "application/json", result


def _valider_geometri(geojson_geom: dict) -> None:
    """Kaster ProcessorExecuteError hvis geometrien ikke passerer validering."""
    try:
        geom = shape(geojson_geom)
    except Exception:
        raise ProcessorExecuteError(
            user_msg="Kunne ikke tolke geometrien som gyldig GeoJSON."
        ) from None

    if geom.geom_type not in _ALLOWED_TYPES:
        raise ProcessorExecuteError(
            user_msg=f"Ugyldig geometritype: '{geom.geom_type}'. "
            f"Må være {', '.join(_ALLOWED_TYPES)}."
        )

    if geom.is_empty:
        raise ProcessorExecuteError(user_msg="Geometrien er tom.")

    num_coords = get_num_coordinates(geom)
    if num_coords > _MAX_VERTICES:
        raise ProcessorExecuteError(
            user_msg=f"For mange koordinater ({num_coords:,}). "
            f"Maksimalt tillatt: {_MAX_VERTICES:,}."
        )

    minx, miny, maxx, maxy = geom.bounds
    if minx < _X_MIN or maxx > _X_MAX or miny < _Y_MIN or maxy > _Y_MAX:
        raise ProcessorExecuteError(
            user_msg="Geometrien er utenfor gyldig område for EPSG:25833. "
            f"Forventet X: [{_X_MIN}, {_X_MAX}], Y: [{_Y_MIN}, {_Y_MAX}]."
        )

    if (maxx - minx) * (maxy - miny) > _MAX_BBOX_AREA_M2:
        raise ProcessorExecuteError(
            user_msg="Geometrien dekker et for stort område. "
            f"Maksimalt tillatt: {_MAX_BBOX_AREA_KM2:.0f} km²."
        )

    if not geom.is_valid:
        raise ProcessorExecuteError(user_msg="Geometrien er ikke topologisk gyldig.")
