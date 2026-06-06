# Acceptance Record: Hermes DB WeChat Analytics Ingestion

**Workspace**: `hermes-db-wechat-analytics-ingestion` | **Date**: 2026-06-06 | **Spec**: [spec.md](spec.md)  
**Status**: Conditional Pass - local implementation verified, external deployment evidence pending

---

## Evidence Table

| Requirement | Evidence | Test or File | Verdict |
|---|---|---|---|
| FR-001 Database tables | Alembic revision creates `analytics_import_runs`, `wechat_article_metric_snapshots`, `wechat_article_channel_daily_metrics`; excludes P2 audience table | `packages/hermes-db/migrations/versions/0004_wechat_analytics_ingestion.py`; `uv run pytest tests/test_migration_sql.py ... -q` -> included in 46 passed / 1 skipped | PASS |
| FR-002 Bulk upsert tool | Tool validates payload, resolves article refs, supports dry-run, writes valid rows through repository, returns import summary | `packages/hermes-db/src/hermes_db_mcp/tools/wechat_analytics.py`; `tests/test_wechat_analytics_tools.py` | PASS |
| FR-003 Snapshot query tool | Tool validates account/article/date/window filters and omits `raw_json` unless `include_raw=true` | `list_wechat_article_metric_snapshots`; `tests/test_wechat_analytics_tools.py`; `tests/test_wechat_analytics_repo_sql.py` | PASS |
| FR-004 Health capability | Health defaults `wechat_analytics_ingestion=false` and schema inspector returns true only when required columns/constraints/indexes exist | `packages/hermes-db/src/hermes_db_mcp/services/schema.py`; `tests/test_wechat_analytics_schema_health.py`; `tests/test_health.py` | PASS |
| FR-005 Article resolution | Repository resolver supports direct article id, URL/canonical/external reference, external ref pair, and 0/1/>1 semantics; tool maps unknown to `unmatched` and ambiguous to row error | `resolve_article`; `tests/test_wechat_analytics_repo_sql.py`; `tests/test_wechat_analytics_tools.py` | PASS |
| P1 channel daily metrics | Repository/tool accept channel rows and upsert on `(article_id, metric_date, channel, source)` without server-side summing | `upsert_channel_daily_metrics`; `tests/test_wechat_analytics_repo_sql.py`; `tests/test_wechat_analytics_tools.py` | PASS |
| P2 audience profiles non-blocking | MVP does not create audience table; payload is skipped with explicit summary reason | `data-model.md`; `contracts.py`; `tests/test_wechat_analytics_contracts.py`; `tests/test_wechat_analytics_tools.py` | PASS |
| Real DB analytics smoke | Integration test exists and skips cleanly without `DATABASE_URL`; no real DB evidence in this run | `tests/test_wechat_analytics_integration.py`; focused suite -> `38 passed, 1 skipped` earlier and `46 passed, 1 skipped` in verify | PARTIAL |
| NAS MCP runtime smoke | Not run in this verify pass; requires deploy/migration to NAS runtime | T039 remains unchecked in `tasks.md` | PARTIAL |
| Agents handoff/live smoke | Not run in this verify pass; requires agents repo MCP live call after NAS deployment | T040 remains unchecked in `tasks.md` | PARTIAL |

---

## Fresh Verification

| Check | Result | Evidence |
|---|---|---|
| Analytics focused suite | PASS | `uv run pytest tests/test_migration_sql.py tests/test_wechat_analytics_schema_health.py tests/test_wechat_analytics_contracts.py tests/test_wechat_analytics_repo_sql.py tests/test_wechat_analytics_tools.py tests/test_wechat_analytics_integration.py -q` -> 46 passed, 1 skipped |
| Existing health/article/workflow regression | PASS | `uv run pytest tests/test_health.py tests/test_wechat_article_contracts.py tests/test_wechat_article_repo_sql.py tests/test_wechat_article_tools.py tests/test_wechat_article_schema_health.py tests/test_workflow_tools.py -q` -> 32 passed |
| Static check | PASS | `uv run ruff check .` -> All checks passed |
| Manual review | PASS with fix | Review found `resolve_article` used `.fetch` directly on a pool in the live tool path. Fixed via `_fetch(pool_or_conn, ...)` and added `test_resolve_article_accepts_pool_and_acquires_connection`. |

---

## Architecture Drift Check

| Boundary / ADR | Verdict | Notes |
|---|---|---|
| Layered architecture | PASS | New code follows migration -> contracts -> repository -> tools -> health. |
| No file parsing in hermes-db | PASS | Tool accepts normalized dict payloads only. |
| No queue/CDC/OLAP/dashboard | PASS | No new async infrastructure or UI added. |
| Import run persistence | PASS | `analytics_import_runs` is mandatory for non-dry-run repository import path. |
| P2 audience deferral | PASS | No audience profile table in migration; skipped with explicit reason. |
| External side effects | PARTIAL | Local migration and health logic implemented; NAS migration/runtime health not verified yet. |
| Artifact handoff | PARTIAL | MCP tools implemented locally; downstream agents live consumption not verified yet. |

---

## Verdict Summary

| Dimension | Verdict | Notes |
|---|---|---|
| Component capability | PASS | Local schema, contracts, repository, tools, health, docs, focused tests, regression tests, and ruff all pass. |
| Workflow closure | PARTIAL | NAS runtime smoke and agents live handoff remain open. |
| User-visible outcome | N/A | Feature has no UI/user-visible output trait; CLI-facing structured MCP output is covered by tool tests. |

**Overall**: CONDITIONAL PASS

**三维不一致说明**: 本地组件能力足以进入部署验证，但 spec 命中 `external-side-effects` 和 `artifact-handoff`。在 NAS migration/MCP endpoint smoke 与 agents live smoke 之前，不能宣称完整 PASS 或进入最终 closeout。剩余项对应 `tasks.md` T038-T041。

---

## Remaining Evidence Gates

- T038: PASS - 准备发布 `hermes-db-v0.2.12`；`hermes-db-v0.2.11` 已构建但 NAS deploy 因 self-hosted runner 下载 `docker/login-action@v3` 超时失败；`deploy/mcp-services.json` health smoke 已加入 `wechat_analytics_ingestion`；README 已记录 `0004_wechat_analytics_ingestion`、新 capability 和 analytics tools。
- T039: 部署后执行 NAS/真实 MCP smoke，确认 `schema_revision=0004_wechat_analytics_ingestion` 和 `capabilities.wechat_analytics_ingestion=true`。
- T040: agents `wechat-analytics-ingestion` 通过真实 MCP endpoint 完成 sample import/query。
- T041: NAS/agents 证据补齐后更新本文件为 final acceptance。
