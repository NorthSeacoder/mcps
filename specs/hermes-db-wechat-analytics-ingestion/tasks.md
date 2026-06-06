# Tasks: Hermes DB WeChat Analytics Ingestion

**Workspace**: `hermes-db-wechat-analytics-ingestion` | **Date**: 2026-06-06  
**Input**: `specs/hermes-db-wechat-analytics-ingestion/spec.md` + `plan.md` + `data-model.md`  
**Prerequisites**: spec.md, plan.md, data-model.md

---

## 执行原则

- 按依赖顺序推进：migration -> contracts -> repository -> tools -> health/docs -> verification/evidence。
- 每个实现任务必须配套局部验证任务或被后续验证任务覆盖。
- 不引入队列、CDC、OLAP、dashboard、文件解析或 agents 侧逻辑；这些都不属于本仓 MVP。
- 所有新增 MCP 写入语义必须保留结构化错误，不能把 asyncpg 原始异常暴露给调用方。

---

## Phase 1: Migration and Schema Contract

**目标**: 建立 analytics MVP 表、约束、索引和 migration 测试基础。

- [x] T001 [FR-001] 新增 Alembic revision `0004_wechat_analytics_ingestion`
  - scope: `packages/hermes-db/migrations/versions/0004_wechat_analytics_ingestion.py`
  - maps_to: FR-001 / ADR-001 / ADR-003 / 幂等性 / 查询性能
  - verify: migration file declares `down_revision = "0003_wechat_publication_ledger"` and creates only additive analytics tables.

- [x] T002 [FR-001] 创建 `hermes.analytics_import_runs`
  - scope: `0004_wechat_analytics_ingestion.py`
  - maps_to: ADR-003 / 可诊断性
  - verify: table includes status CHECK, non-negative count checks, JSONB unmatched/errors/metadata, and account/source/status indexes.

- [x] T003 [FR-001] 创建 `hermes.wechat_article_metric_snapshots`
  - scope: `0004_wechat_analytics_ingestion.py`
  - maps_to: US1 / US3 / ADR-001 / ADR-006
  - verify: table includes FK to `wechat_articles`, unique `(article_id, stat_date, window_label, source)`, P1 metric fields, `raw_json`, `missing_fields`, and date/source/article indexes.

- [x] T004 [FR-001] 创建 `hermes.wechat_article_channel_daily_metrics`
  - scope: `0004_wechat_analytics_ingestion.py`
  - maps_to: US2 / ADR-001
  - verify: table includes FK to `wechat_articles`, unique `(article_id, metric_date, channel, source)`, count checks, `raw_json`, `import_run_id`, and channel/date indexes.

- [x] T005 [P2 boundary] 明确不在 MVP migration 创建 audience profile 表
  - scope: `0004_wechat_analytics_ingestion.py`, `data-model.md` alignment
  - maps_to: ADR-004 / Non-Goals
  - verify: migration does not create `wechat_article_audience_profiles`; later contract/tool tests prove P2 payload is skipped with summary.

- [x] T006 [FR-001] 更新 migration SQL 测试覆盖 analytics tables
  - scope: `packages/hermes-db/tests/test_migration_sql.py`
  - maps_to: FR-001 / 查询性能 / 兼容性
  - verify: tests assert table names, FK clauses, unique constraints, CHECK constraints, indexes, upgrade order, and downgrade drops.

---

## Phase 2: Contracts and Validation

**目标**: 在工具写入前先固定输入/输出边界和结构化错误语义。

- [x] T007 [FR-002] 增加 analytics constants 和 allowed source/status/query limits
  - scope: `packages/hermes-db/src/hermes_db_mcp/contracts.py`
  - maps_to: FR-002 / FR-003 / 可诊断性
  - verify: contract tests assert accepted sources include `manual_json`, `manual_csv`, `manual_xls`, `wechat_api`, `browser_automation`, `manual_patch`.

- [x] T008 [FR-002] 实现 snapshot record validation
  - scope: `contracts.py`
  - maps_to: US1 / Data Validation / ADR-001
  - verify: tests cover required `stat_date`, `window_label`, article/ref presence, ISO date parsing, non-negative integer metrics, and `completion_rate` in `0..1`.

- [x] T009 [FR-002] 实现 channel daily validation
  - scope: `contracts.py`
  - maps_to: US2
  - verify: tests cover required `metric_date`, `channel`, non-negative counts, source/account inheritance, and `全部` channel accepted.

- [x] T010 [FR-002] 实现 bulk payload validation and P2 audience skip signal
  - scope: `contracts.py`
  - maps_to: ADR-002 / ADR-004 / 可诊断性
  - verify: tests cover empty records rejection, `dry_run`, `import_metadata`, `audience_profiles` skip reason, and no silent P2 success.

- [x] T011 [FR-003] 实现 snapshot list query validation
  - scope: `contracts.py`
  - maps_to: US3 / FR-003 / 查询性能
  - verify: tests cover account/article/date/window filters, `include_raw`, limit/offset bounds, and invalid date range.

- [x] T012 [Error Semantics] 增加 analytics contract tests
  - scope: `packages/hermes-db/tests/test_wechat_analytics_contracts.py`
  - maps_to: Error Semantics / 可诊断性
  - verify: `uv run pytest tests/test_wechat_analytics_contracts.py -q` passes.

---

## Phase 3: Repository Layer

**目标**: 封装所有 analytics SQL，保证 tools 不直接拼复杂 SQL。

- [x] T013 [US4] 实现 reusable article resolver
  - scope: `packages/hermes-db/src/hermes_db_mcp/repositories/wechat_analytics_repo.py`
  - maps_to: US4 / FR-005 / ADR-005 / 一致性
  - verify: repo tests cover direct `article_id`, `published_url`, `canonical_url`, `external_reference`, `(ref_type, ref_value)`, not found, and ambiguous results.

- [x] T014 [ADR-003] 实现 import run create/update helpers
  - scope: `wechat_analytics_repo.py`
  - maps_to: ADR-003 / 可诊断性
  - verify: tests assert JSONB serialization, status/count fields, and generated `import_run_id`.

- [x] T015 [US1] 实现 snapshot upsert helper
  - scope: `wechat_analytics_repo.py`
  - maps_to: US1 / ADR-001 / 幂等性
  - verify: repo SQL tests assert `ON CONFLICT (article_id, stat_date, window_label, source)` and created/updated count behavior.

- [x] T016 [US2] 实现 channel daily upsert helper
  - scope: `wechat_analytics_repo.py`
  - maps_to: US2 / ADR-001 / 幂等性
  - verify: repo SQL tests assert `ON CONFLICT (article_id, metric_date, channel, source)` and no server-side channel sum/expansion.

- [x] T017 [US3] 实现 snapshot list query helper
  - scope: `wechat_analytics_repo.py`
  - maps_to: US3 / ADR-006 / 查询性能
  - verify: repo SQL tests assert account/article/date/window filters, bounded limit/offset, and `raw_json` selected only when requested.

- [x] T018 [ADR-002] 实现 transaction-level import orchestration helper
  - scope: `wechat_analytics_repo.py`
  - maps_to: ADR-002 / 一致性 / 可诊断性
  - verify: tests prove accepted rows + import run write in one transaction; DB failure maps to failed summary without partial committed accepted rows.

- [x] T019 [Repository Tests] 增加 analytics repository tests
  - scope: `packages/hermes-db/tests/test_wechat_analytics_repo_sql.py`
  - maps_to: T013-T018
  - verify: `uv run pytest tests/test_wechat_analytics_repo_sql.py -q` passes.

---

## Phase 4: MCP Tools

**目标**: 对 agents 暴露稳定的 bulk upsert 和 list snapshots contract。

- [x] T020 [FR-002] 新增 `tools/wechat_analytics.py`
  - scope: `packages/hermes-db/src/hermes_db_mcp/tools/wechat_analytics.py`
  - maps_to: FR-002 / ADR-002 / ADR-003
  - verify: module imports cleanly and uses MCP annotations `idempotentHint=True`, `destructiveHint=False`, `openWorldHint=True`.

- [x] T021 [US1] 实现 `bulk_upsert_wechat_article_metric_snapshots`
  - scope: `tools/wechat_analytics.py`
  - maps_to: US1 / FR-002 / ADR-001 / ADR-002
  - verify: tool tests cover successful import response with `import_run_id`, `total_rows`, `created`, `updated`, `skipped`, `unmatched`, `errors`, `status`.

- [x] T022 [US2] 在 bulk tool 中接入 channel daily metrics
  - scope: `tools/wechat_analytics.py`
  - maps_to: US2
  - verify: tool tests cover two channel rows, repeat import idempotency summary, and channel errors recorded without silent success.

- [x] T023 [Dry Run] 实现 dry-run no-write path
  - scope: `tools/wechat_analytics.py`
  - maps_to: FR-002 / ADR-002 / ADR-003
  - verify: tests monkeypatch repository write helpers and assert they are not called; response status is `dry_run`.

- [x] T024 [Article Resolution] 接入 row-level article resolver semantics
  - scope: `tools/wechat_analytics.py`, `wechat_analytics_repo.py`
  - maps_to: US4 / FR-005 / ADR-005 / 一致性
  - verify: tool tests cover unknown article in `unmatched`, ambiguous article in `errors`, and no title-based matching.

- [x] T025 [FR-003] 实现 `list_wechat_article_metric_snapshots`
  - scope: `tools/wechat_analytics.py`
  - maps_to: US3 / FR-003 / ADR-006
  - verify: tool tests cover response `{items,total?,limit,offset}`, default raw omission, and `include_raw=true`.

- [x] T026 [Error Semantics] 映射 DB/schema errors
  - scope: `tools/wechat_analytics.py`
  - maps_to: Error Semantics / 可诊断性
  - verify: tests cover `UndefinedTableError`/`UndefinedColumnError -> schema_drift`, FK violation -> `not_found`, unique conflict -> `conflict`, generic DB error -> `database_error`.

- [x] T027 [Tool Registration] 注册 analytics tools
  - scope: `packages/hermes-db/src/hermes_db_mcp/server.py`
  - maps_to: artifact-handoff / FR-002 / FR-003
  - verify: tools registration tests or tool import tests confirm `bulk_upsert_wechat_article_metric_snapshots` and `list_wechat_article_metric_snapshots` appear in MCP tool list path.

- [x] T028 [Tool Tests] 增加 analytics MCP tool tests
  - scope: `packages/hermes-db/tests/test_wechat_analytics_tools.py`
  - maps_to: T020-T027
  - verify: `uv run pytest tests/test_wechat_analytics_tools.py -q` passes.

---

## Phase 5: Health Capability and Documentation

**目标**: 下游可通过 health fail-closed，部署文档说明 schema revision 和 tools contract。

- [x] T029 [FR-004] 实现 `inspect_wechat_analytics_ingestion_schema`
  - scope: `packages/hermes-db/src/hermes_db_mcp/services/schema.py`
  - maps_to: FR-004 / ADR-005 / 兼容性
  - verify: schema health tests cover false on missing tables, false on partial indexes/constraints, true when MVP structures exist.

- [x] T030 [FR-004] 在 health tool 暴露 `wechat_analytics_ingestion`
  - scope: `packages/hermes-db/src/hermes_db_mcp/tools/health.py`
  - maps_to: FR-004 / Producer-Consumer Matrix
  - verify: health tests assert default false and merged true output with existing capabilities unchanged.

- [x] T031 [Health Tests] 增加 analytics schema health tests
  - scope: `packages/hermes-db/tests/test_wechat_analytics_schema_health.py`, `test_health.py` if needed
  - maps_to: T029-T030
  - verify: `uv run pytest tests/test_wechat_analytics_schema_health.py tests/test_health.py -q` passes.

- [x] T032 [Docs] 更新 hermes-db deployment docs
  - scope: `docs/hermes-db-deployment.md`, possibly `packages/hermes-db/README.md`
  - maps_to: artifact-handoff / release readiness
  - verify: docs mention revision `0004_wechat_analytics_ingestion`, capability `wechat_analytics_ingestion`, and tool names.

---

## Phase 6: Integration and Regression Verification

**目标**: 证明本地实现满足 spec，并且没有破坏现有 publication ledger/workflow/topic 功能。

- [x] T033 [Integration] 增加 real DB analytics integration test
  - scope: `packages/hermes-db/tests/test_wechat_analytics_integration.py`
  - maps_to: US1 / US2 / US3 / US4 / Verification Requirements
  - verify: with `DATABASE_URL`, create/reuse article, import D+1 snapshot + two channel rows, repeat import, query exactly one snapshot; skip cleanly without `DATABASE_URL`.

- [x] T034 [Migration Regression] 跑 migration/schema focused tests
  - scope: test command
  - maps_to: FR-001 / FR-004
  - verify: `uv run pytest tests/test_migration_sql.py tests/test_wechat_analytics_schema_health.py -q`.

- [x] T035 [Analytics Local Tests] 跑 analytics unit/integration focused suite
  - scope: test command
  - maps_to: T012 / T019 / T028 / T033
  - verify: `uv run pytest tests/test_wechat_analytics_contracts.py tests/test_wechat_analytics_repo_sql.py tests/test_wechat_analytics_tools.py tests/test_wechat_analytics_integration.py -q`.

- [x] T036 [Regression] 跑相关现有 wechat article/workflow tests
  - scope: test command
  - maps_to: 兼容性 / prior-closure-failure
  - verify: `uv run pytest tests/test_wechat_article_contracts.py tests/test_wechat_article_repo_sql.py tests/test_wechat_article_tools.py tests/test_wechat_article_schema_health.py tests/test_workflow_tools.py -q`.

- [x] T037 [Lint] 跑 hermes-db ruff
  - scope: test command
  - maps_to: delivery hygiene
  - verify: `uv run ruff check .` from `packages/hermes-db`.

---

## Phase 7: Deployment Evidence and Closeout Prep

**目标**: 为后续 verify/closeout 准备真实环境和下游消费证据。

- [x] T038 [Release Prep] 记录待发布 schema/tool contract
  - scope: `specs/hermes-db-wechat-analytics-ingestion/acceptance.md` later, release notes if used
  - maps_to: artifact-handoff / external-side-effects
  - verify: acceptance draft or release note captures new revision, tables, tools, health capability.

- [x] T039 [NAS Smoke] 部署后执行 NAS/真实 MCP smoke
  - scope: NAS hermes-db deployment, MCP `/mcp` endpoint
  - maps_to: Verification Requirements / external-side-effects
  - verify: MCP Release run `27063819452` deployed `ghcr.io/north-sea/hermes-db-mcp:v0.2.12`; Alembic upgraded `0003_wechat_publication_ledger -> 0004_wechat_analytics_ingestion`; health smoke reported `version=0.2.12`, `schema_revision=0004_wechat_analytics_ingestion`, and `capabilities.wechat_analytics_ingestion=true`.

- [ ] T040 [Agents Handoff] 与 agents `wechat-analytics-ingestion` live smoke 对齐
  - scope: `/Users/yqg/personal/AI/agents/specs/wechat-analytics-ingestion/`, agents MCP adapter
  - maps_to: Producer-Consumer Matrix / artifact-handoff / prior-closure-failure
  - verify: agents side can replace mock/dry-run path with real MCP call for one sample import and query.

- [ ] T041 [Acceptance] 写最终验收记录
  - scope: `specs/hermes-db-wechat-analytics-ingestion/acceptance.md`
  - maps_to: verify / closeout
  - verify: acceptance records local tests, integration skips/pass, NAS migration, MCP health, live smoke, and any residual risks.

---

## 依赖与顺序

- T001-T006 是数据库基础，必须先于 repository/tool live 行为。
- T007-T012 是 contract 基础，必须先于 tools 正式实现。
- T013-T019 可在 T007-T012 后推进；repository 可先用 SQL-level fake tests，再接 real DB integration。
- T020-T028 依赖 contracts 和 repository helper。
- T029-T031 依赖 migration 命名和 required structures 固定，但可与 tool tests 并行。
- T032 可在 tool names 和 schema revision 固定后完成。
- T033-T037 是本地验证关键路径。
- T038-T041 属于实现后 verify/closeout 输入，不应在本地实现未完成时强行勾选。

关键路径：

```text
T001-T006 -> T007-T012 -> T013-T019 -> T020-T028 -> T029-T037 -> T038-T041
```

可并行项：

- T006 可和 T007-T012 并行。
- T029-T031 可和 T020-T028 后半段并行。
- T032 可在 T020/T027/T030 明确后并行。

---

## 覆盖检查

| 场景 / 需求 | 对应任务 |
|-------------|----------|
| US1 导入单篇文章 D+1/D+3/D+7 指标 | T003, T008, T015, T021, T033, T035 |
| US2 写入阅读趋势渠道明细 | T004, T009, T016, T022, T033, T035 |
| US3 查询已导入指标 | T011, T017, T025, T033, T035 |
| US4 文章稳定引用解析 | T013, T024, T033, T040 |
| FR-001 Database Tables | T001-T006 |
| FR-002 bulk upsert tool | T007-T010, T020-T024, T028 |
| FR-003 list snapshots tool | T011, T017, T025, T028 |
| FR-004 health capability | T029-T031, T039 |
| FR-005 article resolution | T013, T024, T040 |
| P2 audience non-blocking | T005, T010, T021, T028 |

| 架构决策 / 质量属性 | 对应任务 | 验证任务 |
|----------------------|----------|----------|
| ADR-001 Snapshot identity | T003, T015, T016 | T019, T033, T035 |
| ADR-002 Partial success with summary | T018, T021, T023 | T028, T033, T035 |
| ADR-003 Import run persistence | T002, T014, T021 | T019, T028, T033 |
| ADR-004 Audience P2 skip | T005, T010, T021 | T012, T028 |
| ADR-005 Resolver inside bulk | T013, T024 | T019, T028, T040 |
| ADR-006 Raw JSON opt-in | T003, T017, T025 | T019, T028 |
| 幂等性 | T003, T004, T015, T016 | T019, T033 |
| 一致性 | T013, T018, T024 | T028, T033 |
| 可诊断性 | T002, T010, T014, T021, T026 | T012, T028 |
| 兼容性 | T029-T032 | T036 |
| 查询性能 | T006, T011, T017 | T019, T034 |

---

## Notes

- `analytics_import_runs.status` 不包含 `dry_run`，dry-run 是 MCP response status，不持久化。
- `wechat_article_audience_profiles` 是 future/P2，不在 MVP migration 创建；如果实现阶段决定扩大范围，必须先更新 plan/data-model。
- `source` 若选择开放文本而非 allowed set，必须同步更新 contract tests 和 docs，不能留下隐式行为。
- Live smoke 和 agents handoff 是 verify/closeout evidence，不是纯单元测试替代品。

---

## Stage Readiness

- 推荐下一步：`execute-plan`
- 阻塞项：无。任务数量较多且包含 migration、MCP contract、真实环境 smoke，建议通过 `execute-plan` 控制节奏，而不是一次性直接实现全部。
