# Acceptance Record: hermes-db WeChat Artifact Persistence

**Feature**: `hermes-db-wechat-artifact-persistence`  
**Date**: 2026-06-03  
**Status**: Implemented locally; NAS PG migrated for integration verification

---

## Verification Evidence

| Check | Result | Evidence |
|---|---|---|
| Ruff static check | PASS | `uv run ruff check .` -> All checks passed |
| Full hermes-db test suite | PASS | `uv run pytest tests -q` -> 134 passed, 19 skipped |
| NAS PG migration | PASS | Via SSH tunnel to NAS `shared-postgres`, `alembic upgrade head` ran `0001_topic_revisit -> 0002_wechat_workflow_artifacts` |
| Existing NAS PG integration tests | PASS | `DATABASE_URL=<NAS tunnel DSN> uv run pytest tests/test_topic_repo.py tests/test_topic_repo_updates.py -q` -> 21 passed |
| Workflow persistence integration | PASS | `DATABASE_URL=<NAS tunnel DSN> uv run pytest tests/test_workflow_integration.py -q` -> 1 passed |
| Workflow artifact list contract | PASS | Tests assert `list_workflow_artifacts` and repository list output omit `content_text` |
| Content reference policy | PASS | Tool/contract tests enforce `content_text` or `content_ref`; `content_ref` is returned as metadata and not dereferenced |

---

## Reviewed Risks

| Risk | Verdict |
|---|---|
| `DATABASE_URL` confusion | Mitigated: service uses `PG_DSN`; tests use `DATABASE_URL`. For NAS validation, the container `PG_DSN` was mapped through an SSH tunnel and passed as both variables. |
| Docker DNS hostname from local machine | Mitigated: NAS `PG_DSN` used `shared-postgres`, which is only resolvable inside Docker; validation used SSH local forwarding to `10.30.0.2:5432`. |
| JSONB asyncpg encoding | Mitigated: repository now JSON-encodes `metadata` and `missing_inputs` before passing to asyncpg. This was caught by real NAS PG integration. |
| Artifact version race | Mitigated for MVP: repository uses transaction-scoped advisory lock keyed by `run_id:stage:name` before computing next version. |
| `content_ref` external IO ambiguity | Mitigated: MVP explicitly stores and returns refs only; no external file or URL dereference is attempted. |
| Existing topic/inspiration compatibility | Mitigated: full hermes-db suite passes after adding tools and capabilities. |
| Runtime container image not updated | Open: NAS PG schema is migrated, but `hermes-db-mcp` running container image still needs a release/deploy to expose the new tools at runtime. The current old container cannot resolve `0002_wechat_workflow_artifacts` with `alembic current` because that revision file is not in the image. |
| Downstream agents integration | Open: agents repo adapter/service is out of scope for this feature and remains the next consumer-side step. |

---

## Release / Deployment Follow-up

- Build and release a new `hermes-db` image containing the `0002_wechat_workflow_artifacts` migration and new MCP tools.
- Deploy/recreate `hermes-db-mcp` so runtime `health` can report `schema_revision=0002_wechat_workflow_artifacts` and `capabilities.workflow_runs/workflow_artifacts=true`.
- Continue downstream implementation in `agents/specs/wechat-artifact-persistence`.
