# Acceptance Record: hermes-db topic bucket & revisit_of

**Feature**: `hermes-db-topic-bucket-revisit`  
**Date**: 2026-06-01  
**Status**: Code verified; release evidence pending

---

## Verification Evidence

| Check | Result | Evidence |
|---|---|---|
| Full unit/integration test suite | PASS | `uv run pytest -q` -> 115 passed, 19 skipped |
| Ruff static check | PASS | `uv run ruff check .` -> All checks passed |
| Alembic SQL generation | PASS | `uv run alembic upgrade head --sql` generated `0001_topic_revisit` SQL |
| Whitespace check | PASS | `git diff --check` produced no output |
| Release manifest resolution | PASS | `node scripts/resolve-mcp-release.mjs hermes-db-v0.2.5` resolved migration entrypoint `alembic`, command `upgrade head`, and MCP health smoke capabilities |
| Release image immutability gate | PASS | `v0.2.0` and `v0.2.1` were rejected because their GHCR image tags already exist; `docker buildx imagetools inspect` also found `v0.2.2` occupied; `v0.2.3` built successfully but NAS pull was denied before deploy; `v0.2.4` pulled but migration failed because `PG_DSN` used non-owner `hermes_user`, so release was bumped to `v0.2.5` with `MIGRATION_PG_DSN` support |
| Deploy script syntax | PASS | `bash -n scripts/nas-deploy-mcp.sh` and workflow deploy shell body parsed successfully |
| NAS baseline health | PASS | Current NAS `hermes-db-mcp` is still `v0.1.13`; `pg=ok`, `redis=ok`, no `version/schema_revision/capabilities` yet |
| Local Docker build | BLOCKED | Build reached Docker Hub metadata resolution, then `python:3.12-slim` timed out; Dockerfile still covered by release workflow build |
| Dirty generated artifacts | PASS | `.pytest_cache`, `.ruff_cache`, `.venv`, `dist`, `__pycache__`, `uv.lock` are ignored and not in `git status --short` |
| Dead-code scan | PASS | Only expected cache exception `pass` blocks and test no-op mocks found |

---

## Reviewed Risks

| Risk | Verdict |
|---|---|
| Migration bound to service startup | Mitigated: Docker `ENTRYPOINT` remains `hermes-db-mcp`; migration is documented as explicit release step |
| `revisit_of` self-reference | Mitigated: tool-layer self-check plus DB `chk_topics_revisit_of_not_self` |
| FK idempotency | Mitigated: migration checks `pg_constraint` before adding `fk_topics_revisit_of` |
| UUID serialization | Mitigated: `id` / `revisit_of` conversion skips null values in cache and tool responses |
| bucket threshold drift | Mitigated: thresholds live in server config fields |
| capabilities false positive | Mitigated: `health` now derives capabilities from DB schema and exposes `schema_revision` |
| deploy health too shallow | Mitigated in code/config: deploy manifest now declares release migration plus MCP health smoke; target evidence still pending |
| HTTP auth diagnostics | Mitigated: 401 responses include `WWW-Authenticate: Bearer realm="hermes-db"` |
| inspiration tool annotations / error shape drift | Mitigated: inspiration tools now carry read/write annotations and use shared `ToolError` helper for common failures |

---

## Remaining Work

- T019 is not complete. Target environment still needs release migration and runtime verification:
  - `docker compose run --rm --entrypoint alembic hermes-db-mcp upgrade head`
  - `docker compose up -d hermes-db-mcp`
  - verify `health().version == "0.2.5"`
  - verify `health().schema_revision == "0001_topic_revisit"`
  - verify `health().capabilities.topic_bucket/topic_revisit_of/list_revisit_chain == true`
  - verify DB has `revisit_of`, `mother_theme`, `fk_topics_revisit_of`, `chk_topics_revisit_of_not_self`
