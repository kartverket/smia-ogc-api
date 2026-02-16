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
