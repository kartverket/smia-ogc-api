# API-nøkkel

## Oversikt

API-nøkkelen er en midlertidig løsning for testperioden med LDIR. Når APIet er klart for lansering vil nøkkelen fjernes og APIet blir helt åpent.

## Hvordan det fungerer

Middleware i `deploy/entrypoint.py` sjekker env-variabelen `OGC_API_KEY`. Hvis den er satt, kreves en gyldig API-nøkkel i `X-API-Key`-headeren for alle forespørsler unntatt åpne endepunkter.

Hvis `OGC_API_KEY` ikke er satt (tom streng eller mangler), returnerer alle beskyttede endepunkter `503 Service Unavailable`.

### Åpne endepunkter (krever ikke nøkkel)

- `/` — landingsside
- `/openapi` — OpenAPI-spec og Swagger UI
- `/conformance` — OGC conformance
- `/health` — helsesjekk (k8s-prober)

### Beskyttede endepunkter (krever nøkkel)

- `/collections/*` — OGC API Features
- `/processes/*` — prosesser (f.eks. bopliktsjekk)
- Alt annet

## Bruk

Legg til `X-API-Key`-header i forespørselen:

```bash
curl -H 'X-API-Key: din-nøkkel-her' \
    <url>
```

## Konfigurasjon

API-nøkkelen lagres i Google Secret Manager som `ogc-api-key` og mountes som env `OGC_API_KEY` via `smia-ogc-api-db-secret` i k8s.

- **Prod**: Nøkkel satt i GSM → auth aktivert
- **Dev**: Nøkkel satt i GSM → auth aktivert
