"""Hjelpefunksjoner for bopliktsjekk mot PostGIS-database."""

import json
import logging
import os
from enum import StrEnum

from psycopg2 import InterfaceError, OperationalError
from psycopg2.pool import ThreadedConnectionPool
from pygeoapi.process.base import ProcessorExecuteError

LOGGER = logging.getLogger(__name__)


class Column(StrEnum):
    GJELDER_KUN_DEL_AV_KOMMUNEN = "gjelderKunDelAvKommunen"
    GJELDER_FOR_BRUKT_SOM_HELARSBOLIG = "gjelderForBruktSomHelarsbolig"
    GJELDER_FOR_BOLIG_IKKE_TATT_I_BRUK = "gjelderForBoligIkkeTattIBruk"
    GJELDER_FOR_UBEBYGD_BOLIGTOMT = "gjelderForUbebygdBoligtomt"
    HAR_UNNTAK_FRA_SLEKTSKAPSUNNTAK = "harUnntakFraSlektskapsunntak"
    ANDRE_LOKALE_AVGRENSNINGER = "andreLokaleAvgrensninger"
    HAR_USIKKER_AVGRENSNING = "harUsikkerAvgrensning"


_COLUMNS = [
    Column.GJELDER_KUN_DEL_AV_KOMMUNEN.value,
    Column.GJELDER_FOR_BRUKT_SOM_HELARSBOLIG.value,
    Column.GJELDER_FOR_BOLIG_IKKE_TATT_I_BRUK.value,
    Column.GJELDER_FOR_UBEBYGD_BOLIGTOMT.value,
    Column.HAR_UNNTAK_FRA_SLEKTSKAPSUNNTAK.value,
    Column.ANDRE_LOKALE_AVGRENSNINGER.value,
    Column.HAR_USIKKER_AVGRENSNING.value,
]


def bygg_boplikt_resultat(boplikt, row_dict):
    """Bygg flat response-dict med boplikt-status og materielle vilkår."""
    result = {"iBopliktomrade": boplikt}
    result.update(row_dict)
    result.pop(Column.GJELDER_KUN_DEL_AV_KOMMUNEN.value, None)
    return result


_STATEMENT_TIMEOUT = os.environ.get("DB_STATEMENT_TIMEOUT", "15s")

_db_pool = None


def _get_pool():
    global _db_pool
    if _db_pool is None:
        try:
            _db_pool = ThreadedConnectionPool(
                minconn=1,
                maxconn=int(os.environ.get("DB_POOL_MAX", "10")),
                host=os.environ.get("DB_HOST", "localhost"),
                port=os.environ.get("DB_PORT", "5432"),
                dbname=os.environ.get("DB_NAME", "postgres"),
                user=os.environ.get("DB_USER", "postgres"),
                password=os.environ.get("DB_PASSWORD", "postgres"),
            )
        except Exception as e:
            LOGGER.error("Kunne ikke opprette databasetilkobling: %s", e)
            raise ProcessorExecuteError(
                user_msg="En feil oppstod, prøv igjen senere."
            ) from None
    return _db_pool


def _execute_query(sql, params):
    db_pool = _get_pool()
    for attempt in range(2):
        conn = db_pool.getconn()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(f"SET LOCAL statement_timeout = '{_STATEMENT_TIMEOUT}'")
                    cur.execute(sql, params)
                    return cur.fetchall()
        except (OperationalError, InterfaceError) as e:
            LOGGER.warning(
                "Ugyldig databasetilkobling (forsøk %d/2): %s", attempt + 1, e
            )
        except Exception as e:
            LOGGER.error("Databasefeil: %s", e)
            raise ProcessorExecuteError(
                user_msg="En feil oppstod, prøv igjen senere."
            ) from None
        finally:
            db_pool.putconn(conn, close=bool(conn.closed))

    raise ProcessorExecuteError(
        user_msg="En feil oppstod, prøv igjen senere."
    ) from None


def get_cols():
    """Returnerer listen med kolonnenavn i bopliktomraade-tabellen."""
    return ", ".join(f'"{c}"' for c in _COLUMNS)


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
    cols = get_cols()
    sql = f"SELECT {cols} FROM kommuneinfo.bopliktomraade WHERE kommunenummer = %s"
    rows = _execute_query(sql, (kommunenummer,))
    return [dict(zip(_COLUMNS, row)) for row in rows]


def sjekk_boplikt(geojson_geom, kommunenummer=None):
    """Sjekk om en GeoJSON-geometri treffer bopliktområder i databasen.

    Kjører ST_Intersects og ST_Within mot kommuneinfo.bopliktomraade.
    Returnerer flat dict med boplikt (ja/nei/delvis) og materielle vilkår
    fra første treff.
    """
    geojson_str = json.dumps(geojson_geom)
    cols = get_cols()

    sql = f"""
        WITH input AS (
            SELECT ST_SetSRID(ST_GeomFromGeoJSON(%s), 25833) AS geom
        )
        SELECT {cols},
               ST_Within(input.geom, omrade) AS is_within
        FROM kommuneinfo.bopliktomraade, input
        WHERE omrade && input.geom
          AND ST_Intersects(input.geom, omrade)
    """
    params = [geojson_str]

    if kommunenummer is not None:
        sql += " AND kommunenummer = %s"
        params.append(kommunenummer)

    rows = _execute_query(sql, params)

    if not rows:
        return {"iBopliktomrade": "NEI"}

    all_within = all(row[-1] for row in rows)
    if len(rows) > 1 or not all_within:
        boplikt = "DELVIS"
    else:
        boplikt = "JA"

    first = dict(zip(_COLUMNS, rows[0][:-1]))
    return bygg_boplikt_resultat(boplikt, first)
