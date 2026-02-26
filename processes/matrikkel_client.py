"""Hjelpefunksjoner for kommunikasjon med Matrikkel-API via SOAP (zeep)."""

import json
import logging
import os
from collections import Counter

import zeep
from zeep import helpers
from pygeoapi.process.base import ProcessorExecuteError

LOGGER = logging.getLogger(__name__)

WSDL_URL = "https://matrikkel.no/matrikkelapi/wsapi/v1/MatrikkelenhetServiceWS?WSDL"

_matrikkel_client = None


def get_matrikkel_client():
    """Returnerer en lazy-initialisert singleton SOAP-klient."""
    global _matrikkel_client
    if _matrikkel_client is None:
        _matrikkel_client = create_matrikkel_client()
    return _matrikkel_client


def create_matrikkel_client(wsdl=None):
    """Opprett en zeep SOAP-klient mot Matrikkel-API med valgfri autentisering."""
    wsdl = wsdl or os.environ.get("MATRIKKEL_WSDL_URL", WSDL_URL)
    username = os.environ.get("MATRIKKELEN_USERNAME")
    password = os.environ.get("MATRIKKELEN_PASSWORD")

    settings = zeep.Settings(strict=False, xml_huge_tree=True)

    if username and password:
        from requests import Session
        from requests.auth import HTTPBasicAuth
        from zeep.transports import Transport

        session = Session()
        session.auth = HTTPBasicAuth(username, password)
        transport = Transport(session=session)
        return zeep.Client(wsdl=wsdl, settings=settings, transport=transport)

    return zeep.Client(wsdl=wsdl, settings=settings)


def hent_teiggeometri(client, kommunenummer, gardsnummer, bruksnummer,
                      festenummer=0, seksjonsnummer=0):
    """Hent teiggeometri fra Matrikkel-API og returnér som GeoJSON.

    Kaller findMatrikkelenhetMedTeiger og ekstraherer polygongeometri
    fra det triangulerte svaret. Returnerer None om ingen geometri finnes.
    """
    try:
        result = client.service.findMatrikkelenhetMedTeiger(
            matrikkelenhetIdent={
                "kommuneIdent": {"kommunenummer": kommunenummer},
                "gardsnummer": int(gardsnummer),
                "bruksnummer": int(bruksnummer),
                "festenummer": int(festenummer),
                "seksjonsnummer": int(seksjonsnummer),
            },
            matrikkelContext={
                "locale": "no_NO_B",
                "brukOriginaleKoordinater": False,
                "koordinatsystemKodeId": {"value": 11},
                "systemVersion": os.environ.get("MATRIKKEL_SYSTEM_VERSION", "trunk"),
                "klientIdentifikasjon": "ogc-api",
                "snapshotVersion": {"timestamp": "9999-01-01T00:00:00+01:00"},
            },
        )
    except zeep.exceptions.Fault as e:
        LOGGER.error("SOAP fault: %s", e)
        raise ProcessorExecuteError(
            "Kunne ikke hente matrikkelenhet. Kontroller at oppgitte verdier er korrekte."
        )
    except Exception as e:
        LOGGER.error("SOAP error: %s", e)
        raise ProcessorExecuteError(
            "Feil ved oppslag mot Matrikkel. Prøv igjen senere."
        )

    result_dict = helpers.serialize_object(result, dict)
    result_dict = json.loads(json.dumps(result_dict, default=str))
    geom, hjelpelinjetyper = _extract_geometry(result_dict)
    return geom, sorted(hjelpelinjetyper)


def _extract_geometry(result):
    """Ekstraher GeoJSON-geometri fra Matrikkel-svarets triangulerte struktur.

    Matrikkel returnerer triangulerte flater der indre kanter enten
    finnes i begge retninger (A→B og B→A) eller dupliseres i samme retning.
    Funksjonen filtrerer bort indre kanter og bygger polygonringer
    fra de gjenværende ytterkantene.
    """
    points = {}  # id_value -> [x, y]
    edges = []   # (start_id, end_id)

    def scan(obj):
        """Rekursivt søk gjennom nestet dict/liste-struktur etter punkter og kanter."""
        if isinstance(obj, dict):
            kurve = obj.get("kurve")
            if isinstance(kurve, dict):
                s = kurve.get("startpunktId", {})
                e = kurve.get("endpunktId", {})
                if isinstance(s, dict) and isinstance(e, dict):
                    sid, eid = s.get("value"), e.get("value")
                    if sid is not None and eid is not None:
                        hjtype = None
                        hj = obj.get("hjelpelinjetypeId")
                        if isinstance(hj, dict):
                            hjtype = hj.get("value")
                        edges.append((sid, eid, hjtype))

            pos = obj.get("posisjon")
            oid = obj.get("id")
            if isinstance(pos, dict) and isinstance(oid, dict) and pos.get("x") is not None:
                points[oid["value"]] = [pos["x"], pos["y"]]

            for v in obj.values():
                scan(v)
        elif isinstance(obj, list):
            for item in obj:
                scan(item)

    scan(result)

    if not points or not edges:
        return None, set()

    LOGGER.debug("_extract_geometry: %d kanter totalt, %d unike punkter", len(edges), len(points))

    # Fjern indre kanter:
    # 1. Konsistent vikling: indre kant (A→B) har revers (B→A)
    # 2. Inkonsistent vikling: indre kant (A→B) finnes flere ganger i samme retning
    edge_keys = [(s, e) for s, e, _ in edges]
    hjtype_by_edge = {(s, e): hj for s, e, hj in edges}
    edge_counts = Counter(edge_keys)
    edge_set = set(edge_keys)
    boundary_edges = [
        (s, e) for (s, e) in edge_counts
        if edge_counts[(s, e)] == 1 and (e, s) not in edge_set
    ]

    LOGGER.debug("_extract_geometry: %d ytterkanter etter filtrering", len(boundary_edges))

    if not boundary_edges:
        boundary_edges = list(edge_counts.keys())

    # Samle unike hjelpelinjetyper fra ytterkantene
    hjelpelinjetyper = {
        hjtype_by_edge.get((s, e))
        for s, e in boundary_edges
        if hjtype_by_edge.get((s, e)) is not None
    }

    adj = {s: e for s, e in boundary_edges}
    rings = []
    visited = set()

    for start in list(adj.keys()):
        if start in visited:
            continue
        ring_ids = []
        current = start
        while current not in visited:
            visited.add(current)
            ring_ids.append(current)
            current = adj.get(current)
            if current is None or current == start:
                break

        coords = [[points[pid][0], points[pid][1]] for pid in ring_ids if pid in points]
        if len(coords) >= 3:
            coords.append(coords[0])  # lukk ringen
            rings.append(coords)

    if not rings:
        return None, hjelpelinjetyper
    if len(rings) == 1:
        return {"type": "Polygon", "coordinates": rings}, hjelpelinjetyper
    return {"type": "MultiPolygon", "coordinates": [[r] for r in rings]}, hjelpelinjetyper
