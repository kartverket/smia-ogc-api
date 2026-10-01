# smia-ogc-api

Read [README.md](README.md) before changing the service. It is the source of
truth for local setup, testing and validation commands.

- Treat `pygeoapi-config.yml`, process inputs and outputs, generated OpenAPI,
  authentication and published CRS/data as public contract surfaces.
- OpenAPI is generated at startup and requires the database; do not introduce
  a separately maintained specification.
- Run the relevant checks documented in the README. Include integration tests
  when changing database access or external-service integration.
