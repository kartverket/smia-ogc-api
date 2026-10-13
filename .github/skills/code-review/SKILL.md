---
name: code-review
description: Review a pull request in smia-ogc-api. Use for every code review in this repository.
---

# Reviewing smia-ogc-api

Public API in production, used by external consumers. The most expensive mistake here is a breaking
change that nobody noticed.

## Breaking changes come first

The OpenAPI document is generated at startup, so it is not in the diff. Check for breaking changes
including in `pygeoapi-config.yml`, process metadata and response construction under `processes/`
(such as `processes/utils/boplikt_metadata.py` and `processes/utils/boplikt_db.py`), `deploy/wsgi.py`,
and pygeoapi upgrades in `uv.lock`.

Treat the following as breaking. Flag them as blocking unless the PR description explains the
intent and how affected consumers can migrate:

- A path, collection, process, parameter or response field removed or renamed.
- A type or format changed, or an optional input made required.
- A status code or the shape of an error body changed.
- Authentication, CRS or published data changed.
- A new deviation from standard pygeoapi behaviour.

Say what breaks and for which kind of consumer. Adding an optional field or a new endpoint is not
breaking.

## Then

- Error paths: timeouts, Matrikkelen down, database down, empty or malformed input. Does it fail
  loudly with the right status code?
- Look for regression coverage that would fail without the fix. Flag missing coverage when it
  leaves a concrete, important failure case untested; don't require a separate test for every
  small change.
- Skip formatting and anything Ruff catches.

Few comments. Each one has file, line and a concrete failing case, marked blocking or non-blocking.
