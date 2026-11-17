# smia-ogc-api

Public API in production, used by external consumers. Read [README.md](README.md) before changing
the service. It is the source of truth for local setup, testing and validation commands.

- Treat `pygeoapi-config.yml`, process inputs and outputs, status codes, error bodies, generated
  OpenAPI, authentication and published CRS/data as public contract surfaces. Say in the PR
  description when one of them changes.
- `api_version` in `pygeoapi-config.yml` is SemVer and shown as OpenAPI `info.version`. Bump MAJOR
  only for breaking changes, after a deprecation period of at least 3 months. `url_prefix` is a fixed
  `v1`; never derive it from `api_version` or change it. See README "Versjonering".
- Prefer standard pygeoapi behaviour; document and test necessary deviations.
- OpenAPI is generated at startup and requires the database; do not introduce a separately
  maintained specification.
- Run the relevant checks documented in the README. Test at the smallest meaningful boundary; add
  integration tests for database or external-service behavior when mocks cannot verify the important
  behavior. Avoid redundant tests.
- Reviewing a pull request? Use the `code-review` skill in `.github/skills/`.
