"""Hjelpefunksjoner for bopliktsjekk mot PostGIS-database."""

import json
import logging
import os

from psycopg2.pool import SimpleConnectionPool
from pygeoapi.process.base import ProcessorExecuteError

LOGGER = logging.getLogger(__name__)

RESPONSE_COLUMNS = [
    "kommunenummer",
    "fylkesnummer",
    "delvis_boplikt",
    "forskriftsreferanse",
    "opphav",
    "bebygd_eiendom",
    "helaarsbolig",
    "ubebygd_tomt",
    "slektskapsunntak",
    "andre_avgrensninger",
]

_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        _pool = SimpleConnectionPool(
            minconn=1,
            maxconn=5,
            host=os.environ.get("DB_HOST", "localhost"),
            port=os.environ.get("DB_PORT", "5432"),
            dbname=os.environ.get("DB_NAME", "postgres"),
            user=os.environ.get("DB_USER"),
            password=os.environ.get("DB_PASSWORD"),
        )
    return _pool


def sjekk_kommune_boplikt(kommunenummer):
    """Sjekk om en kommune har boplikt, uten geometrioppslag.

    Returnerer liste med treff fra bopliktomraade-tabellen (tom liste = ingen boplikt).
    """
    cols = ", ".join(RESPONSE_COLUMNS)
    sql = f"SELECT {cols} FROM kommuneinfo.bopliktomraade WHERE kommunenummer = %s"

    pool = _get_pool()
    conn = pool.getconn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql, (kommunenummer,))
                rows = cur.fetchall()
    except Exception as e:
        LOGGER.error("Database error: %s", e)
        raise ProcessorExecuteError(f"Databasefeil: {e}")
    finally:
        pool.putconn(conn)

    return [dict(zip(RESPONSE_COLUMNS, row)) for row in rows]


def sjekk_boplikt(geojson_geom, kommunenummer=None):
    """Sjekk om en GeoJSON-geometri treffer bopliktområder i databasen.

    Kjører ST_Intersects og ST_Within mot kommuneinfo.bopliktomraade
    og returnerer et dict med 'status' (UTENFOR/INNENFOR/DELVIS_OVERLAPP)
    og 'treff'.
    """
    geojson_str = json.dumps(geojson_geom)
    cols = ", ".join(RESPONSE_COLUMNS)

    sql = f"""
        WITH input AS (
            SELECT ST_SetSRID(ST_GeomFromGeoJSON(%s), 25833) AS geom
        )
        SELECT {cols},
               ST_Within(input.geom, omrade) AS is_within
        FROM kommuneinfo.bopliktomraade, input
        WHERE ST_Intersects(input.geom, omrade)
    """
    params = [geojson_str]

    if kommunenummer is not None:
        sql += " AND kommunenummer = %s"
        params.append(kommunenummer)

    pool = _get_pool()
    conn = pool.getconn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
    except Exception as e:
        LOGGER.error("Database error: %s", e)
        raise ProcessorExecuteError(f"Databasefeil: {e}")
    finally:
        pool.putconn(conn)

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

    return {"status": status, "treff": treff}
