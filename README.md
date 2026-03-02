# Boplikt OGC API

OGC API Features-tjeneste for bopliktområder, bygd med [pygeoapi](https://pygeoapi.io/).

## Oppsett

### 1. Installer uv

Se docs: https://docs.astral.sh/uv/

### 2. Installer avhengigheter

```bash
uv sync
```

Dette installerer riktig Python-versjon (3.12+) og alle avhengigheter.

## Lokal Kjøring

```bash
./run_local.sh
```

Serveren starter på http://localhost:5000.

Scriptet gjør to ting:
1. Genererer OpenAPI-spesifikasjonen fra `pygeoapi-config.yml`
2. Starter pygeoapi-serveren

## Konfigurasjon

All konfigurasjon ligger i `pygeoapi-config.yml`. Her defineres:

- Databasetilkobling (PostgreSQL/PostGIS)
- Hvilke collections som serveres
- Koordinatsystem (EPSG:25833 / UTM33)

Data lagres og serveres i EPSG:25833 (EUREF89 UTM sone 33) uten transformasjon.

## Linting og formatering

Prosjektet bruker [Ruff](https://docs.astral.sh/ruff/) for linting og formatering.

```bash
uv run ruff check     # lint
uv run ruff format    # formater
```

For VS Code-brukere finnes det ferdig oppsett i `.vscode/settings.json` som formaterer og fikser imports ved lagring. Bruker du en annen editor, se [Ruff editor-integrasjoner](https://docs.astral.sh/ruff/editors/).

## Monitorering

Det finnes et dashboard i Grafana for dette APIet. Gå til [Smia: Matrikkeltjenester](https://monitoring.kartverket.cloud/d/ad6ed173-cb04-48ee-add2-6b3d5538fdec/smia3a-matrikkeltjenester?orgId=1&from=now-1h&to=now&timezone=browser&var-prometheus=P3C08CCCD0A204B5D&var-tjeneste=smia-ogc-api&var-loki=PC49BB3D5AB252A94&var-loglevel=INFO&var-loglevel=WARN&var-loglevel=ERROR&var-namespace=smia-tjenester-main) i Grafana, og velg smia-ogc-api under "tjeneste". Husk å justere om du skal se prod eller dev aktivitet. 

Det finnes også er dashboard for databasene denne applikasjonen bruker i de forskjellige miljøene. Gå til [denne lenken](https://rin-ap1450.statkart.no/d/kommuneinfoapi_pg_details/postgresql-details?orgId=1) for å se dashboardet. Logg in med Microsoft-bruker. 
