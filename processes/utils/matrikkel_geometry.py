"""Geometribygging fra Matrikkel SOAP-respons."""

import logging

from shapely.geometry import shape
from shapely.validation import explain_validity

from processes.utils.matrikkel_client import hent_matrikkelenhet_med_teiger

LOGGER = logging.getLogger(__name__)


def hent_teiggeometri(client, kommunenummer, gardsnummer, bruksnummer):
    """Hent teiggeometri fra Matrikkel-API og returner som GeoJSON.

    Args:
        client: zeep SOAP-klient mot Matrikkel.
        kommunenummer (str): Kommunenummer (4 siffer).
        gardsnummer (int): Gardsnummer.
        bruksnummer (int): Bruksnummer.

    Returns:
        tuple: (geom, hjelpelinjetyper, validation, har_bue) der geom er GeoJSON-dict
            (Polygon eller MultiPolygon i EPSG:25833), hjelpelinjetyper er en
            sortert liste med hjelpelinjetypeId-verdier, validation er en
            dict med is_valid og reason fra shapely, og har_bue er bool.

    Raises:
        ProcessorExecuteError: Ved SOAP-feil eller nettverksfeil mot Matrikkel.
    """
    result_dict = hent_matrikkelenhet_med_teiger(
        client,
        kommunenummer,
        gardsnummer,
        bruksnummer,
    )
    geom, hjelpelinjetyper, har_bue = _extract_geometry(result_dict)

    if har_bue:
        LOGGER.warning(
            "Bue funnet for matrikkelenhet %s/%s/%s/%s/%s — buepunkt brukt som mellompunkt",
            kommunenummer,
            gardsnummer,
            bruksnummer,
            0,
            0,
        )

    validation = _validate_geometry(geom)
    if not validation["is_valid"]:
        LOGGER.warning(
            "Ugyldig geometri for matrikkelenhet %s/%s/%s/%s/%s: %s",
            kommunenummer,
            gardsnummer,
            bruksnummer,
            0,
            0,
            validation["reason"],
        )
    return geom, sorted(hjelpelinjetyper), validation, har_bue


def _validate_geometry(geom):
    """Returner dict med is_valid og reason fra shapely."""
    if geom is None:
        return {"is_valid": False, "reason": "Ingen geometri"}
    try:
        s = shape(geom)
        valid = s.is_valid
        return {"is_valid": valid, "reason": None if valid else explain_validity(s)}
    except Exception as e:
        return {"is_valid": False, "reason": str(e)}


def _build_polygon_ring(curve_directions, grenser, punkter):
    """Bygg en lukket polygon-ring fra en ordnet curveDirections-liste.

    Traverserer grensene i rekkefølge og samler koordinater. For hver grense
    legges startpunktet til, etterfulgt av eventuelle kurvepunkter.
    Retningen (signed) avgjør om grensen traverseres fremover eller baklengs.

    Args:
        curve_directions (list[dict]): Ordnet liste av curveDirection-objekter
            fra Matrikkel, med grenselinjeId og signed-flagg.
        grenser (dict): Oppslagstabell for grenselinjer (kant-id → grense-dict).
        punkter (dict): Oppslagstabell for punkter (punkt-id → [x, y]).

    Returns:
        list: Lukket koordinatring som liste av [x, y]-par.
            Tom liste hvis færre enn 3 punkter.
    """
    coords = []
    for retning in curve_directions:
        grenselinjeId = (retning.get("grenselinjeId") or {}).get("value")
        signed = retning.get("signed", False)
        grense = grenser.get(grenselinjeId)
        if grense is None:
            continue
        # signed=False → baklengs (endepunkt→startpunkt), signed=True → fremover (startpunkt→endepunkt)
        punkt_id = grense["endepunkt"] if not signed else grense["startpunkt"]
        punkt = punkter.get(punkt_id)
        if punkt:
            coords.append(punkt)
        # Legg til kurvepunkter — reversert rekkefølge ved baklengs traversering
        kurvepunkter = grense.get("kurvepunkter", [])
        if kurvepunkter:
            coords.extend(kurvepunkter if signed else kurvepunkter[::-1])
    if len(coords) >= 3:
        coords.append(coords[0])
    return coords


def _parse_matrikkel_objects(items):
    """Parse bubbleObjects-listen til oppslagstabeller.

    Args:
        items (list[dict]): Flat liste av objekter fra bubbleObjects.item.

    Returns:
        tuple: (punkter, grenser, teiger) der punkter er dict(id → [x, y]),
            grenser er dict(id → grense-info), og teiger er liste av teig-objekter.
    """
    punkter = {}
    grenser = {}
    teiger = []

    for item in items:
        posisjon = item.get("posisjon")
        object_id = item.get("id")
        if (
            isinstance(posisjon, dict)
            and isinstance(object_id, dict)
            and posisjon.get("x") is not None
        ):
            punkter[object_id["value"]] = [posisjon["x"], posisjon["y"]]

        kurve = item.get("kurve")
        if isinstance(kurve, dict):
            startpunkt = (kurve.get("startpunktId") or {}).get("value")
            endepunkt = (kurve.get("endpunktId") or {}).get("value")
            hjelpelinjetype = (item.get("hjelpelinjetypeId") or {}).get("value")
            har_bue = kurve.get("buepunktX") is not None
            raw_kurvepunkter = kurve.get("kurvepunkter")
            kurvepunkter = []
            if raw_kurvepunkter:
                kurvepunkter = [
                    [punkt["x"], punkt["y"]]
                    for punkt in raw_kurvepunkter.get("item", [])
                    if punkt.get("x") is not None
                ]
            if har_bue and not kurvepunkter:
                kurvepunkter = [[kurve["buepunktX"], kurve["buepunktY"]]]
            if startpunkt is not None and endepunkt is not None:
                grenser[object_id["value"]] = {
                    "startpunkt": startpunkt,
                    "endepunkt": endepunkt,
                    "hjelpelinjetype": hjelpelinjetype,
                    "bue": har_bue,
                    "kurvepunkter": kurvepunkter,
                }

        if "flate" in item:
            teiger.append(item)

    return punkter, grenser, teiger


def _build_teig_polygons(teiger, grenser, punkter):
    """Bygg polygoner og samle hjelpelinjetyper fra alle teiger.

    Args:
        teiger (list[dict]): Teig-objekter med flate.exterior.curveDirections.
        grenser (dict): Oppslagstabell for grenselinjer.
        punkter (dict): Oppslagstabell for punkter.

    Returns:
        tuple: (polygons, hjelpelinjetyper) der polygons er liste av
            koordinatlister og hjelpelinjetyper er et set med hjelpelinjetypeId-verdier.
    """
    hjelpelinjetyper = set()
    polygons = []

    for teig in teiger:
        flate = teig.get("flate") or {}
        exterior = flate.get("exterior") or {}
        ext_dirs = (exterior.get("curveDirections") or {}).get("item", [])
        polygon = _build_polygon_ring(ext_dirs, grenser, punkter)
        if len(polygon) >= 4:
            polygons.append(polygon)

        for retning in ext_dirs:
            grenselinjeId = (retning.get("grenselinjeId") or {}).get("value")
            grense = grenser.get(grenselinjeId)
            if grense and grense["hjelpelinjetype"] is not None:
                hjelpelinjetyper.add(grense["hjelpelinjetype"])

    return polygons, hjelpelinjetyper


def _extract_geometry(result):
    """Henter ut GeoJSON-geometri fra Matrikkel-svaret.

    Args:
        result (dict): Deserialisert SOAP-respons fra findMatrikkelenhetMedTeiger.

    Returns:
        tuple: (geom, hjelpelinjetyper, har_bue) der geom er en GeoJSON-dict
            (Polygon ved en teig, MultiPolygon ved flere), hjelpelinjetyper
            er et set med hjelpelinjetypeId-verdier fra kantene, og har_bue
            er en bool som indikerer om noen av kantene har buer.
            Returnerer (None, set(), False) om ingen brukbar geometri finnes.
    """
    items = result.get("bubbleObjects", {}).get("item", [])
    if not items:
        return None, set(), False

    punkter, grenser, teiger = _parse_matrikkel_objects(items)

    har_bue = any(g["bue"] for g in grenser.values())
    if not teiger or not punkter or not grenser:
        return None, set(), har_bue

    polygons, hjelpelinjetyper = _build_teig_polygons(teiger, grenser, punkter)

    if not polygons:
        return None, hjelpelinjetyper, har_bue
    if len(polygons) == 1:
        return {"type": "Polygon", "coordinates": polygons}, hjelpelinjetyper, har_bue
    return (
        {"type": "MultiPolygon", "coordinates": [[p] for p in polygons]},
        hjelpelinjetyper,
        har_bue,
    )
