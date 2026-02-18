import json
import logging
import os

import psycopg2
from pygeoapi.process.base import BaseProcessor, ProcessorExecuteError

LOGGER = logging.getLogger(__name__)

RESPONSE_COLUMNS = [
    "kommunenummer",
    "fylkesnummer",
    "delvis_boplikt",
    "forskriftsreferanse",
    "informasjon",
    "opphav",
]

PROCESS_METADATA = {
    "version": "0.1.0",
    "title": {"nb": "Sjekk boplikt for geometri"},
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
        }
    },
}


def _get_connection():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=os.environ.get("DB_PORT", "5432"),
        dbname=os.environ.get("DB_NAME", "postgres"),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD"),
    )


class BopliktsjekkGeometriProcessor(BaseProcessor):
    def __init__(self, processor_def):
        super().__init__(processor_def, PROCESS_METADATA)

    def execute(self, data, outputs=None):
        geojson_geom = data.get("geometri")
        if geojson_geom is None:
            raise ProcessorExecuteError("Mangler input: geometri")

        geom_type = geojson_geom.get("type", "")
        if geom_type not in ("Point", "Polygon", "MultiPolygon"):
            raise ProcessorExecuteError(
                f"Ugyldig geometritype: {geom_type}. "
                "Må være Point, Polygon eller MultiPolygon."
            )

        geojson_str = json.dumps(geojson_geom)
        cols = ", ".join(RESPONSE_COLUMNS)

        sql = f"""
            SELECT {cols},
                   ST_Within(
                       ST_SetSRID(ST_GeomFromGeoJSON(%s), 25833),
                       omrade
                   ) AS is_within
            FROM kommuneinfo.bopliktomraade
            WHERE ST_Intersects(
                ST_SetSRID(ST_GeomFromGeoJSON(%s), 25833),
                omrade
            )
        """

        try:
            conn = _get_connection()
            with conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (geojson_str, geojson_str))
                    rows = cur.fetchall()
            conn.close()
        except Exception as e:
            LOGGER.error("Database error: %s", e)
            raise ProcessorExecuteError(f"Databasefeil: {e}")

        treff = []
        for row in rows:
            props = dict(zip(RESPONSE_COLUMNS, row[:-1]))
            props["relasjon"] = "INNENFOR" if row[-1] else "DELVIS_OVERLAPP"
            treff.append(props)

        if not treff:
            status = "UTENFOR"
        elif all(t["relasjon"] == "INNENFOR" for t in treff):
            status = "INNENFOR"
        else:
            status = "DELVIS_OVERLAPP"

        result = {
            "status": status,
            "treff": treff,
        }

        return "application/json", result
