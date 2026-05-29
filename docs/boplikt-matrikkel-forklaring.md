# Bopliktsjekk med Matrikkelnummer — Detaljert forklaring

Dette dokumentet forklarer hvordan bopliktsjekken med matrikkelnummer fungerer, fra API-kall til geometri-bygging og romlig sjekk.

---

## 1. Systemarkitektur

```Klient
  │
  │  POST /v1/processes/bopliktsjekk/execution
  │  { kommunenummer, gardsnummer, bruksnummer, ... }
  ▼
pygeoapi (Flask)
  │
  ├─ API-nøkkel validering (X-API-Key header)
  │
  ▼
BopliktSjekkProcessor
  │
  ├─── 1. Kommuneoppslag (PostGIS DB)
  ├─── 2. Tidlig retur hvis ingen / full boplikt
  ├─── 3. Hent geometri fra Matrikkel SOAP API
  └─── 4. Romlig sjekk mot bopliktområder (PostGIS DB)
```

---

## 2. OGC API Process — Hvordan det er koblet opp

pygeoapi registrerer prosessorer i `pygeoapi-config.yml`:

```yaml
resources:
  bopliktsjekk:
    type: process
    processor:
      name: processes.bopliktsjekk.BopliktSjekkProcessor
```

Alle prosessorer følger dette mønsteret:

```python
# processes/bopliktsjekk.py

class BopliktSjekkProcessor(BaseProcessor):

    def __init__(self, processor_def):
        super().__init__(processor_def, PROCESS_METADATA)
        # PROCESS_METADATA beskriver inputs/outputs til OGC API

    def execute(self, data, outputs=None):
        # data = parsed JSON body fra POST-request
        # returnerer ("application/json", result_dict)
        ...
```

OGC API-standarden eksponerer prosessen på:

- `GET /v1/processes/bopliktsjekk` — metadata
- `POST /v1/processes/bopliktsjekk/execution` — kjør

---

## 3. Flyt i bopliktsjekk.py

```Input: { kommunenummer, gardsnummer, bruksnummer }

Step 1: sjekk_kommune_boplikt(kommunenummer)
        │
        ▼
        Har kommunen boplikt i det hele tatt?
        │
        ├── NEI ──→ { iBopliktomrade: "NEI" }  ← FERDIG (ingen geometrisjekk)
        │
        └── JA ──→ Har alle bopliktområder full boplikt (delvis_boplikt = false)?
                   │
                   ├── JA (alle fulle) ──→ { iBopliktomrade: "JA", ...vilkår }  ← FERDIG (ingen geometri)
                   │
                   └── NEI (noen delvis) ──→ Hent geometri fra Matrikkel
                                             │
                                             ▼
                                        sjekk_boplikt(geom, kommunenummer)
                                             │
                                             ▼
                               { iBopliktomrade: "JA/NEI/DELVIS", ...vilkår }
```

**Viktig optimalisering:** Geometrioppslag mot Matrikkel SOAP er kun nødvendig ved delvis boplikt. Full boplikt betyr hele kommunen er innenfor — ingen grunn til å sjekke koordinater.

---

## 4. Matrikkel SOAP API

Se docs: <https://kartverket.github.io/api-dokumentasjon/docs/eiendom/matrikkel/matrikkelen/matrikkelapi/>
**Fil:** `processes/utils/matrikkel_client.py`

### Klienten

```python
# Lazy-initialisert singleton — lages kun første gang den trengs
client = zeep.Client(
    wsdl="https://matrikkel.no/matrikkelapi/wsapi/v1/MatrikkelenhetServiceWS?WSDL",
    settings=zeep.Settings(strict=False, xml_huge_tree=True),
)
```

### SOAP-kallet

```python
client.service.findMatrikkelenhetMedTeiger(
    matrikkelenhetIdent={
        "kommuneIdent": {"kommunenummer": kommunenummer},
        "gardsnummer":   int(gardsnummer),
        "bruksnummer":   int(bruksnummer),
        "festenummer":   0,
        "seksjonsnummer": 0,
    },
    matrikkelContext={
        "koordinatsystemKodeId": {"value": 11},  # ← 11 = UTM33N (EPSG:25833)
        "locale": "no_NO_B",
        "brukOriginaleKoordinater": False,
        ...
    }
)
```

> **KRITISK:** `koordinatsystemKodeId = 11` betyr UTM33N (EPSG:25833).
> Bruk av `10` (UTM32N) er FEIL og vil gi koordinater i feil projeksjons-sone.
> PostGIS-databasen lagrer bopliktområder i SRID 25833 — koordinatsystemene må matche.

### Hva Matrikkel returnerer

Svaret er en flat liste (`bubbleObjects.item`) med alle objekter blandet:

```bubbleObjects.item (flat liste, 24 objekter for en enkel eiendom):
  ├── matrikkelenhet     ← metadata (gardsnummer, bruksnummer, uuid, osv.)
  ├── teig               ← har "flate" → selve polygon-definisjonen
  ├── grenselinjer (×N)  ← har "kurve" med startpunktId / endpunktId
  └── grensepunkter (×N) ← har "posisjon" med x / y
```

Polygon-ringen er eksplisitt definert i teig-objektet via `flate.exterior.curveDirections` — en **ordnet liste** av kantreferanser.

---

## 5. Geometribygging — \_extract_geometry()

**Fil:** `processes/utils/matrikkel_geometry.py`, funksjon `_extract_geometry()`

### Grenselinjetyper

En grenselinjer i Matrikkel kan være én av tre geometriske typer:

| Type            | Beskrivelse                                                       | Felt i API-svaret                        |
| --------------- | ----------------------------------------------------------------- | ---------------------------------------- |
| **Linjestykke** | Rett linje mellom start- og endepunkt                             | `kurve.startpunktId`, `kurve.endpunktId` |
| **Bue**         | Sirkelbue mellom to punkt, med et tredje punkt som definerer buen | `kurve.buepunktX/Y/Z`                    |
| **Kurve**       | Frekurve med flere mellompunkter (naturlige terrengdetaljer)      | `kurve.kurvepunkter`                     |

> **Nåværende implementasjon:** Vi håndterer **linjestykker**, **kurver** (kurvepunkter)
> og **buer** (buepunktet brukes som et mellompunkt, ikke som en ekte sirkelbue).
> Buer forekommer sjelden, og tilnærmingen gir tilstrekkelig nøyaktighet for bopliktsjekk.

### curveDirections — nøkkelstrukturen

```json
"flate": {
  "exterior": {
    "curveDirections": {
      "item": [
        { "grenselinjeId": {"value": 234367975}, "signed": false },
        { "grenselinjeId": {"value": 234367972}, "signed": false },
        ...
      ]
    }
  },
  "interior": null
}
```

Hvert element refererer til en kant og sier hvilken retning den skal traverseres:

```signed=False → traverser kanten BAKLENGS: endpunktId → startpunktId
signed=True  → traverser kanten fremover: startpunktId → endpunktId
```

### Eksempel fra respons (4203/306/21)

```curveDirection  grenselinjeId   signed   start        end          traversert som
[ 1]            234367975       False    234367971    234367974    234367974 → 234367971  ✓
[ 2]            234367972       False    234364438    234367971    234367971 → 234364438  ✓
[ 3]            234367984       False    234367981    234364438    234364438 → 234367981  ✓
[ 4]            234367982       False    234367978    234367981    234367981 → 234367978  ✓
...
[11]            234367999       False    234367974    234367998    234367998 → 234367974  ✓ (lukker)
```

Alle 11 kanter kobler seg perfekt til en lukket ring.

### Algoritmen i \_extract_geometry()

#### Fase 1 — Bygg oppslagstabeller

Én enkelt iterasjon over `bubbleObjects.item` kategoriserer alle objekter:

```python
for item in items:
    if "posisjon" in item:   → points[id] = [x, y]
    if "kurve"    in item:   → edges[id]  = {start, end, hjtype, kurvepunkter, bue}
    if "flate"    in item:   → teiger.append(item)
```

#### Fase 2 — Bygg ring fra curveDirections

```python
def build_ring(curve_directions):
    for cd in curve_directions:
        edge = edges[cd["grenselinjeId"]]
        # signed=False → ta endepunktet (baklengs traversering)
        node = edge["end"] if not cd["signed"] else edge["start"]
        coords.append(points[node])
        # Legg til kurvepunkter mellom start/end (reversert ved baklengs)
        if edge["kurvepunkter"]:
            coords.extend(edge["kurvepunkter"] if cd["signed"] else reversed(edge["kurvepunkter"]))
    coords.append(coords[0])  # lukk ringen
```

Hver kant kan være enten en rett linje (kun start- og endepunkt) eller en kurve (med ekstra punkter mellom). En polygon kan inneholde en blanding av begge typer.

```Visuelt for eksempeleiendommen:

  234367974 ────── 234367971
  /                         \
234367998               234364438
  |                           |
234367995               234367981
  \                         /
  234367989 ─── 234367990 ── 234367986 ─── 234367977 ─── 234367978

(11 punkter, koordinater i UTM33N)
```

#### Fase 3 — Håndter flere teiger

Én teig → `Polygon`. Flere teiger → `MultiPolygon` (én ring per teig).

```python
if len(polygons) == 1:
    return {"type": "Polygon", "coordinates": polygons}, hjelpelinjetyper, har_bue
return {"type": "MultiPolygon", "coordinates": [[p] for p in polygons]}, hjelpelinjetyper, har_bue
```

Funksjonen returnerer også:

- `hjelpelinjetyper` — set med hjelpelinjetypeId-verdier fra kantene
- `har_bue` — `True` hvis noen kanter har buegeometri (logges som advarsel)

`hent_teiggeometri()` wrapper legger til shapely-validering og returnerer:
`(geom, hjelpelinjetyper, geom_validering, har_bue)`

> `interior: null` her — støtte for hull i polygoner er tilgjengelig i strukturen men ikke implementert (ikke nødvendig for bopliktsjekk).

---

## 6. Romlig sjekk i PostGIS

**Fil:** `processes/utils/boplikt_db.py`

### sjekk_kommune_boplikt() — Rask kommunesjekk

```sql
SELECT kommunenummer, fylkesnummer, delvis_boplikt, ...
FROM kommuneinfo.bopliktomraade
WHERE kommunenummer = %s
```

Ingen geometri involvert — bare et enkelt tabelloppslag.

### sjekk_boplikt() — Full romlig sjekk

```sql
WITH input AS (
    SELECT ST_SetSRID(ST_GeomFromGeoJSON(%s), 25833) AS geom
    --      ↑ Parse GeoJSON    ↑ Sett SRID eksplisitt til 25833
)
SELECT
    kommunenummer, delvis_boplikt, ...,
    ST_Within(input.geom, omrade) AS is_within
    --  ↑ Er geometrien HELT innenfor bopliktområdet?
FROM kommuneinfo.bopliktomraade, input
WHERE ST_Intersects(input.geom, omrade)
--    ↑ Finn alle bopliktområder som overlapper (inkl. delvis)
AND kommunenummer = %s
```

### Statustolkning

```Ingen treff fra ST_Intersects  →  boplikt: "nei"

Alle treff har is_within=true og nøyaktig ett treff  →  boplikt: "ja"
(geometrien ligger helt inni ett bopliktområde)

Flere treff eller minst ett treff med is_within=false  →  boplikt: "delvis"
(geometrien overlapper flere områder eller krysser grense)
```

```Eksempel — boplikt=ja:         Eksempel — boplikt=delvis:

  ┌──────────────────┐           ┌──────────────────┐
  │  Bopliktområde   │           │  Bopliktområde   │
  │                  │           │           ┌──────┼──────┐
  │   ┌────────┐     │           │           │Eien- │      │
  │   │Eiendom │     │           │           │dom   │      │
  │   └────────┘     │           └───────────┼──────┘      │
  └──────────────────┘                       └─────────────┘
```

---

## 7. Koordinatsystem

Hele systemet bruker **EPSG:25833 (UTM Zone 33N)**:

| Komponent         | Innstilling                  |
| ----------------- | ---------------------------- |
| Matrikkel API     | `koordinatsystemKodeId = 11` |
| PostGIS lagring   | `SRID = 25833`               |
| PostGIS-operasjon | `ST_SetSRID(..., 25833)`     |
| pygeoapi-config   | `storage_crs: EPSG:25833`    |

---

## 8. Hjelpelinjetyper

Matrikkel-kanter kan ha en `hjelpelinjetypeId` — en kode som sier noe om grensens rettslige status (f.eks. påvist, ikke påvist, midlertidig). Disse samles opp internt i geometrihentingen for analyse/logging, men returneres ikke i API-responsen fra bopliktsjekk-endepunktet i dagens implementasjon.

---

## 9. Feilhåndtering

| Situasjon                    | Håndtering                                                      |
| ---------------------------- | --------------------------------------------------------------- |
| Matrikkelenheten finnes ikke | SOAP fault → `ProcessorExecuteError` med norsk feilmelding      |
| Nettverksfeil mot Matrikkel  | Exception fanget → feilmelding                                  |
| Ingen geometri i svaret      | `_extract_geometry` returnerer `None` → feilmelding             |
| DB-feil                      | Exception fanget, logget, re-raised som `ProcessorExecuteError` |
