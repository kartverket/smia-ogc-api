"""Hjelpefunksjoner for bopliktsjekk mot PostGIS-database."""

import json
import logging
import os

from psycopg2 import InterfaceError, OperationalError
from psycopg2.pool import ThreadedConnectionPool
from pygeoapi.process.base import ProcessorExecuteError

LOGGER = logging.getLogger(__name__)

_KOMMUNE_COLUMNS = [
    "kommunenummer",
    "delvis_boplikt",
]

_VILKAAR_COLUMNS = [
    "bebygd_eiendom",
    "helaarsbolig",
    "ubebygd_tomt",
    "slektskapsunntak",
    "andre_avgrensninger",
]

_VILKAAR_RENAME = {
    "bebygd_eiendom": "bebygdEiendom",
    "helaarsbolig": "ikkeHelarsboligUnderOppforing",
    "ubebygd_tomt": "ubebygdTomt",
    "slektskapsunntak": "unntakFraSlektskapsunntak",
    "andre_avgrensninger": "andreAvgrensninger",
}

_ALL_COLUMNS = _KOMMUNE_COLUMNS + _VILKAAR_COLUMNS


def _gjelder_to_bool(value):
    if isinstance(value, str):
        return value.lower() == "gjelder"
    return bool(value)


def _map_vilkaar(row_dict):
    result = {}
    for db_col, api_name in _VILKAAR_RENAME.items():
        val = row_dict.get(db_col)
        if db_col == "andre_avgrensninger":
            result[api_name] = val
        else:
            result[api_name] = _gjelder_to_bool(val)
    return result


def bygg_boplikt_resultat(boplikt, row_dict):
    """Bygg flat response-dict med boplikt-status og materielle vilkår."""
    result = {"boplikt": boplikt}
    result.update(_map_vilkaar(row_dict))
    return result

_db_pool = None


def _get_pool():
    global _db_pool
    if _db_pool is None:
        _db_pool = ThreadedConnectionPool(
            minconn=1,
            maxconn=2,
            host=os.environ.get("DB_HOST", "localhost"),
            port=os.environ.get("DB_PORT", "5432"),
            dbname=os.environ.get("DB_NAME", "postgres"),
            user=os.environ.get("DB_USER", "postgres"),
            password=os.environ.get("DB_PASSWORD", "postgres"),
        )
    return _db_pool


def _execute_query(sql, params):
    db_pool = _get_pool()
    last_err = None

    for attempt in range(2):
        conn = db_pool.getconn()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    return cur.fetchall()
        except (OperationalError, InterfaceError) as e:
            last_err = e
            LOGGER.warning(
                "Ugyldig databasetilkobling (forsøk %d/2): %s", attempt + 1, e
            )
        except Exception as e:
            LOGGER.error("Databasefeil: %s", e)
            raise ProcessorExecuteError("Databasefeil, prøv igjen senere.") from e
        finally:
            db_pool.putconn(conn, close=bool(conn.closed))

    raise ProcessorExecuteError("Databasefeil, prøv igjen senere.") from last_err


def sjekk_kommune_boplikt(kommunenummer):
    """Finn om en kommune har boplikt.

    Args:
        kommunenummer (str): Kommunenummer (4 siffer).

    Returns:
        list[dict]: Treff fra bopliktomraade-tabellen. Mulige utfall:
            - Tom liste: kommunen har ingen boplikt.
            - Én dict med delvis_boplikt=False: full boplikt for hele kommunen.
            - Én dict med delvis_boplikt=True: delvis boplikt, krever geometrisjekk.
            En kommune vil aldri ha både True og False — det garanteres av datagrunnlaget.

    Raises:
        ProcessorExecuteError: Ved databasefeil.
    """
    cols = ", ".join(_ALL_COLUMNS)
    sql = f"SELECT {cols} FROM kommuneinfo.bopliktomraade WHERE kommunenummer = %s"
    rows = _execute_query(sql, (kommunenummer,))
    return [dict(zip(_ALL_COLUMNS, row)) for row in rows]


def sjekk_boplikt(geojson_geom, kommunenummer=None):
    """Sjekk om en GeoJSON-geometri treffer bopliktområder i databasen.

    Kjører ST_Intersects og ST_Within mot kommuneinfo.bopliktomraade.
    Returnerer flat dict med boplikt (ja/nei/delvis) og materielle vilkår
    fra første treff.
    """
    geojson_str = json.dumps(geojson_geom)
    cols = ", ".join(_ALL_COLUMNS)

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

    rows = _execute_query(sql, params)

    if not rows:
        return {"boplikt": "nei"}

    all_within = all(row[-1] for row in rows)
    if len(rows) > 1 or not all_within:
        boplikt = "delvis"
    else:
        boplikt = "ja"

    first = dict(zip(_ALL_COLUMNS, rows[0][:-1]))
    return bygg_boplikt_resultat(boplikt, first)
