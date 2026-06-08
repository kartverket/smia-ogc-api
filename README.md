# Administrative inndelinger OGC API

OGC API for Administrative inndelinger bygd med [pygeoapi](https://pygeoapi.io/). Tjenesten deler
data fra Kartverket som OGC API Features og tilbyr en OGC API Process for bopliktsjekk — sjekk om en
eiendom eller geometri ligger innenfor et bopliktområde.

## Oppsett

### Pre requs

- [uv](https://docs.astral.sh/uv/) (Python 3.12, styres av `.python-version`)
- Docker med Compose
- Bruker til dockerhub (for å hente Docker Hardened Image i prod-bygget)

### Virtuelt miljø (venv)

For å sette opp et lokalt virtuelt miljø for bruk i f.eks. Neovim eller VS Code:

```bash
uv sync
```

Dette oppretter en `.venv`-mappe og installerer alle avhengigheter.

#### Manuell aktivering

Hvis du ønsker å aktivere miljøet manuelt i terminalen:

```bash
source .venv/bin/activate
```

## Lokal kjøring

Appen kjøres med samme image som i prod (`deploy/Dockerfile`), mot en PostGIS-database som fylles
med mockdata fra `dev/init-db.sql`. Alt er definert i `compose.yaml`:

```bash
docker compose up --build
```

Dette starter to tjenester:

| Tjeneste | Adresse                 | Beskrivelse                   |
| -------- | ----------------------- | ----------------------------- |
| `api`    | <http://localhost:5000> | OGC API (pygeoapi + gunicorn) |
| `api`    | <http://localhost:8181> | Prometheus-metrikker          |
| `db`     | `localhost:5432`        | PostGIS med mockdata          |

Databasen og API-et er forhåndskonfigurert med brukeren `boplikt` og API-nøkkelen settes til
`testkey` lokalt. Disse verdiene ligger i `compose.yaml` og trenger ikke å endres for lokal
utvikling.

### Live reload under utvikling

Bruk `--watch` for å bygge api-tjenesten om automatisk når du endrer kode. Compose ser etter
endringer i `processes/`, `pygeoapi-config.yml`, `deploy/`, `pyproject.toml` og `uv.lock`:

```bash
docker compose up --build --watch
```

## Konfigurasjon

All konfigurasjon ligger i `pygeoapi-config.yml`. Her defineres:

- Databasetilkobling (PostgreSQL/PostGIS)
- Hvilke collections som serveres
- Koordinatsystem (EPSG:25833 / UTM33)

Data lagres og serveres i EPSG:25833 (EUREF89 UTM sone 33) uten transformasjon.

## Bygg og deploy

Produksjonsimagen bygges fra `deploy/Dockerfile` med et uv multi-steg-bygg, slik at **både lokalt og
deploy bruker samme `uv.lock` som kilde**.

Runtime-imagen er ett [Docker Hardened Image](https://docs.docker.com/dhi/)

```bash
docker build -f deploy/Dockerfile -t smia-ogc-api:test .
```

Ved oppstart genererer `deploy/start.py` OpenAPI-spesifikasjonen mot databasen (krever at databasen
er tilgjengelig) og starter gunicorn.

## Linting og formatering

Prosjektet bruker [Ruff](https://docs.astral.sh/ruff/) for linting og formatering.

```bash
uv run ruff check     # lint
uv run ruff format    # formater
```

For VS Code-brukere finnes det ferdig oppsett i `.vscode/settings.json` som formaterer og fikser
imports ved lagring. Bruker du en annen editor, se
[Ruff editor-integrasjoner](https://docs.astral.sh/ruff/editors/).

## Monitorering

Det finnes et dashboard i Grafana for dette APIet. Gå til
[Smia: Matrikkeltjenester](https://monitoring.kartverket.cloud/d/ad6ed173-cb04-48ee-add2-6b3d5538fdec/smia3a-matrikkeltjenester?orgId=1&from=now-1h&to=now&timezone=browser&var-prometheus=P3C08CCCD0A204B5D&var-tjeneste=smia-ogc-api&var-loki=PC49BB3D5AB252A94&var-loglevel=INFO&var-loglevel=WARN&var-loglevel=ERROR&var-namespace=smia-tjenester-main)
i Grafana, og velg smia-ogc-api under "tjeneste". Husk å justere om du skal se prod eller dev
aktivitet.

Det finnes også er dashboard for databasene denne applikasjonen bruker i de forskjellige miljøene.
Gå til
[denne lenken](https://rin-ap1450.statkart.no/d/kommuneinfoapi_pg_details/postgresql-details?orgId=1)
for å se dashboardet. Logg in med Microsoft-bruker.

Det er satt opp syntetisk overvåking for API-et. Se
[dashboardet her](https://monitoring.kartverket.cloud/d/olb644d/oppetid-syntetisk-overvaking?var-interval=$__auto&orgId=1&from=now-30d&to=now&timezone=browser&var-metrics=P0A5FFD43F759AAC7&var-deployment_environment_name=prod&var-team=smia&var-env=$__all&var-job=http_2xx_get_10s&var-instance=https:%2F%2Finndelinger.api.kartverket.no%2Fhealth&var-_instances_all=$__all&var-slo=0.99).
