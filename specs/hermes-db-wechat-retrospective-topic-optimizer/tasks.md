# Tasks: Hermes DB WeChat Retrospective Topic Optimizer

**Workspace**: `hermes-db-wechat-retrospective-topic-optimizer` | **Date**: 2026-06-07  
**Input**: `specs/hermes-db-wechat-retrospective-topic-optimizer/spec.md` + `plan.md` + `data-model.md`  
**Prerequisites**: spec.md, plan.md, data-model.md

---

## 执行原则

- 按依赖顺序推进：migration -> contracts -> repository -> tools -> health/docs -> integration/regression -> deployed evidence。
- 每个实现任务必须配套局部验证任务或被后续验证任务覆盖。
- 不实现 agents 侧 scoring/report composition/LLM narrative/pickNext；本仓只实现 hermes-db 持久化、MCP tools、schema health 和 smoke 支撑。
- 不自动修改 `topics.priority`、`topics.status` 或删除 topic；reviewed suggestions 只作为 ranking hints/read model 被消费。
- 所有新增 MCP 写入语义必须返回结构化错误，不能把 asyncpg 原始异常暴露给调用方。

---

## Phase 1: Migration and Schema Contract

**目标**: 建立 retrospective MVP 表、约束、索引和 migration SQL 测试基础。

- [x] T001 [FR-001..FR-004] 新增 Alembic revision `0005_wechat_retro_opt`
  - scope: `packages/hermes-db/migrations/versions/0005_wechat_retrospective_topic_optimizer.py`
  - maps_to: FR-001 / FR-002 / FR-003 / FR-004 / ADR-001 / 可用性
  - verify: migration declares `down_revision = "0004_wechat_analytics_ingestion"` and only adds retrospective tables.

- [x] T002 [FR-001] 创建 `hermes.topic_performance`
  - scope: `0005_wechat_retrospective_topic_optimizer.py`
  - maps_to: US1 / FR-001 / ADR-002 / 幂等性 / 一致性
  - verify: table includes article/topic FKs, unique `(account, article_id, window_label, scoring_version)`, score/confidence checks, JSONB evidence fields, and query indexes.

- [x] T003 [FR-002] 创建 `hermes.wechat_retrospective_reports`
  - scope: `0005_wechat_retrospective_topic_optimizer.py`
  - maps_to: US2 / FR-002 / 可诊断性
  - verify: table includes report type/status/generation mode checks, article FK, period check, JSONB report sections, and account/type/article/status indexes.

- [x] T004 [FR-003] 创建 `hermes.topic_optimization_suggestions`
  - scope: `0005_wechat_retrospective_topic_optimizer.py`
  - maps_to: US3 / FR-003 / FR-005 / ADR-003 / ADR-005
  - verify: table includes report FK, suggestion/target/review status checks, confidence check, target ref check, expiry fields, and approved ranking-hint index.

- [x] T005 [FR-004] 创建 `hermes.learning_candidates`
  - scope: `0005_wechat_retrospective_topic_optimizer.py`
  - maps_to: US4 / FR-004 / artifact-handoff
  - verify: table includes source report FK, candidate type/status checks, confidence check, policy/export fields, and account/status/type indexes.

- [x] T006 [FR-012] 实现 downgrade 依赖顺序
  - scope: `0005_wechat_retrospective_topic_optimizer.py`
  - maps_to: FR-012 / 可用性
  - verify: downgrade drops learning candidates -> suggestions -> reports -> performance and does not alter previous feature tables.

- [x] T007 [Migration Tests] 更新 migration SQL 测试覆盖 retrospective schema
  - scope: `packages/hermes-db/tests/test_migration_sql.py`
  - maps_to: T001-T006 / 查询性能 / 一致性
  - verify: tests assert revision id, down revision, table names, FK clauses, unique/check constraints, indexes, upgrade order, and downgrade drops.

---

## Phase 2: Contracts and Validation

**目标**: 在工具写入前固定输入边界、状态集合、分页规则和结构化错误语义。

- [x] T008 [FR-006] 增加 retrospective pagination constants
  - scope: `packages/hermes-db/src/hermes_db_mcp/contracts.py`
  - maps_to: FR-006 / ADR-006 / 查询性能
  - verify: contract tests assert default/max limits and negative offset/oversized limit rejection.

- [x] T009 [US1] 实现 topic performance payload/query validation
  - scope: `contracts.py`
  - maps_to: US1 / FR-001 / ADR-002
  - verify: tests cover required account/article/stat/window/version fields, UUID/date parsing, score 0..100, confidence 0..1, JSON object/array requirements, and list filters.

- [x] T010 [US2] 实现 retrospective report payload/query validation
  - scope: `contracts.py`
  - maps_to: US2 / FR-002
  - verify: tests cover report type/status/generation mode sets, inclusive period range, non-negative sample size, optional article id, JSON sections, and list filters.

- [x] T011 [US3] 实现 suggestion create/list/review validation
  - scope: `contracts.py`
  - maps_to: US3 / FR-003 / FR-005 / ADR-005
  - verify: tests cover suggestion type, target kind/ref rules, review status sets, confidence, expiry datetime parsing, pending create status, and review targets `approved/rejected/expired`.

- [x] T012 [US4] 实现 learning candidate create/list/review validation
  - scope: `contracts.py`
  - maps_to: US4 / FR-004
  - verify: tests cover candidate type/status sets, source report id, source suggestion id arrays, policy JSON objects, confidence, and review targets `approved/rejected/disabled`.

- [x] T013 [FR-011] 增加 retrospective structured error helpers/tests
  - scope: `contracts.py`, `packages/hermes-db/tests/test_wechat_retrospective_contracts.py`
  - maps_to: FR-011 / 可诊断性
  - verify: `rtk uv run pytest tests/test_wechat_retrospective_contracts.py -q` passes.

---

## Phase 3: Repository Layer

**目标**: 封装所有 retrospective SQL，保证 tools 只做 MCP 参数、错误和序列化边界。

- [x] T014 [Repository] 新增 `wechat_retrospective_repo.py`
  - scope: `packages/hermes-db/src/hermes_db_mcp/repositories/wechat_retrospective_repo.py`, `repositories/__init__.py`
  - maps_to: ADR-001 / Decision 1
  - verify: module imports cleanly and shared `_jsonb`/serialization style follows analytics repository.

- [x] T015 [US1] 实现 `upsert_topic_performance`
  - scope: `wechat_retrospective_repo.py`
  - maps_to: US1 / FR-001 / ADR-002 / 幂等性
  - verify: repo SQL tests assert `ON CONFLICT (account, article_id, window_label, scoring_version) DO UPDATE`, JSONB params, `updated_at=now()`, and returned row shape.

- [x] T016 [US1] 实现 `list_topic_performance` with total
  - scope: `wechat_retrospective_repo.py`
  - maps_to: US1 / FR-001 / FR-006 / ADR-006
  - verify: repo tests assert account/article/topic/window/scoring/date filters, count query, limit/offset, and stat-date ordering.

- [x] T017 [US2] 实现 report create/get/list repository helpers
  - scope: `wechat_retrospective_repo.py`
  - maps_to: US2 / FR-002 / 可诊断性
  - verify: repo tests assert insert fields, `get` by report id, account/type/article/date filters, total count, and no embedded performance rows.

- [x] T018 [US3] 实现 suggestion batch create/list helpers
  - scope: `wechat_retrospective_repo.py`
  - maps_to: US3 / FR-003 / ADR-003
  - verify: repo tests assert transaction use, append-only generated ids, report FK usage, target filters, status filters, total count, and JSONB proposed/current values.

- [x] T019 [US3] 实现 suggestion review helper
  - scope: `wechat_retrospective_repo.py`
  - maps_to: US3 / ADR-005 / Safety
  - verify: repo tests assert allowed review update touches only suggestion row, sets reviewed fields, updates `updated_at`, and does not update `topics`.

- [x] T020 [FR-005] 实现 approved ranking hints query helper
  - scope: `wechat_retrospective_repo.py`
  - maps_to: US3 / FR-005 / user-visible-output
  - verify: repo tests assert `review_status IN ('approved', 'applied')`, expiry filter `(expires_at IS NULL OR expires_at > now())`, account required, target filters, total count.

- [x] T021 [US4] 实现 learning candidate create/list helpers
  - scope: `wechat_retrospective_repo.py`
  - maps_to: US4 / FR-004 / artifact-handoff
  - verify: repo tests assert transaction use, source report FK, source suggestion id JSON array, status/type/domain filters, total count.

- [x] T022 [US4] 实现 learning candidate review helper
  - scope: `wechat_retrospective_repo.py`
  - maps_to: US4 / FR-004
  - verify: repo tests assert allowed review update sets reviewed fields and optional policy id without applying policy.

- [x] T023 [Repository Tests] 增加 retrospective repository SQL tests
  - scope: `packages/hermes-db/tests/test_wechat_retrospective_repo_sql.py`
  - maps_to: T014-T022 / ADR-006
  - verify: `rtk uv run pytest tests/test_wechat_retrospective_repo_sql.py -q` passes.

---

## Phase 4: MCP Tools

**目标**: 对 agents 暴露稳定 retrospective MCP contract，并保持 response JSON 类型兼容。

- [x] T024 [Tool Module] 新增 `tools/wechat_retrospective.py`
  - scope: `packages/hermes-db/src/hermes_db_mcp/tools/wechat_retrospective.py`
  - maps_to: FR-001..FR-005 / ADR-001
  - verify: module imports cleanly and defines shared date/UUID/datetime serialization helpers.

- [x] T025 [US1] 实现 `upsert_topic_performance`
  - scope: `tools/wechat_retrospective.py`
  - maps_to: US1 / FR-001 / ADR-002
  - verify: tool tests cover successful upsert response, JSON fields returned as arrays/objects, validation error no-write, FK -> `not_found`, schema drift mapping.

- [x] T026 [US1] 实现 `list_topic_performance`
  - scope: `tools/wechat_retrospective.py`
  - maps_to: US1 / FR-006
  - verify: tool tests cover filters, `{items,total,limit,offset}`, invalid UUID/date/limit errors, and empty result.

- [x] T027 [US2] 实现 report create/get/list tools
  - scope: `tools/wechat_retrospective.py`
  - maps_to: US2 / FR-002 / FR-006
  - verify: tool tests cover create response, get not_found, list filters/counts, JSON report sections, and schema_drift mapping.

- [x] T028 [US3] 实现 suggestion create/list/review tools
  - scope: `tools/wechat_retrospective.py`
  - maps_to: US3 / FR-003 / ADR-003 / ADR-005
  - verify: tool tests cover batch create, list filters, review approve/reject/expire, invalid transition for `applied`, DB not_found, and no topic mutation path.

- [x] T029 [FR-005] 实现 `list_approved_topic_ranking_hints`
  - scope: `tools/wechat_retrospective.py`
  - maps_to: US3 / FR-005 / user-visible-output
  - verify: tool tests cover account required, approved/applied only, expired exclusion, target filters, and pagination shape.

- [x] T030 [US4] 实现 learning candidate create/list/review tools
  - scope: `tools/wechat_retrospective.py`
  - maps_to: US4 / FR-004
  - verify: tool tests cover batch create, list filters, approve/reject/disable, invalid exported transition, optional policy id, and JSON policy fields.

- [x] T031 [FR-011] 实现 retrospective DB error mapping
  - scope: `tools/wechat_retrospective.py`
  - maps_to: FR-011 / 可诊断性
  - verify: tests cover `ForeignKeyViolationError -> not_found`, `UndefinedTableError`/`UndefinedColumnError -> schema_drift`, unsupported state -> `invalid_transition`, generic DB error -> `database_error`.

- [x] T032 [Tool Registration] 注册 retrospective tools
  - scope: `packages/hermes-db/src/hermes_db_mcp/server.py`
  - maps_to: artifact-handoff / FR-001..FR-005
  - verify: registration/import tests confirm retrospective tools are imported without breaking existing tool modules.

- [x] T033 [Tool Tests] 增加 retrospective MCP tool tests
  - scope: `packages/hermes-db/tests/test_wechat_retrospective_tools.py`
  - maps_to: T024-T032
  - verify: `rtk uv run pytest tests/test_wechat_retrospective_tools.py -q` passes.

---

## Phase 5: Health Capability and Documentation

**目标**: 暴露 schema-aware capability，并更新操作/契约文档。

- [x] T034 [FR-009/FR-010] 实现 schema inspector
  - scope: `packages/hermes-db/src/hermes_db_mcp/services/schema.py`
  - maps_to: US5 / FR-009 / FR-010 / ADR-007
  - verify: inspector checks four tables, required columns, PK/unique/check/FK constraints, and required indexes.

- [x] T035 [US5] 接入 health capability
  - scope: `packages/hermes-db/src/hermes_db_mcp/tools/health.py`, `packages/hermes-db/tests/test_health.py`
  - maps_to: US5 / FR-009 / 可用性
  - verify: health defaults `wechat_retrospective_topic_optimizer=false`; with complete mocked inspector returns true; PG unavailable keeps false.

- [x] T036 [Schema Health Tests] 增加 retrospective schema health tests
  - scope: `packages/hermes-db/tests/test_wechat_retrospective_schema_health.py`
  - maps_to: US5 / FR-010 / ADR-007
  - verify: tests cover complete schema true, missing table false, missing column false, missing constraint false, missing FK false, missing index false.

- [x] T037 [Docs] 更新 hermes-db README/部署说明
  - scope: `packages/hermes-db/README.md`, relevant deploy docs if present
  - maps_to: artifact-handoff / external-side-effects
  - verify: docs mention new tools, capability key, migration revision, and agents live-smoke dependency.

---

## Phase 6: Integration and Regression Verification

**目标**: 用本地/可选真实 DB 验证完整 retrospective 闭环，同时保护既有 MCP 能力。

- [x] T038 [Integration] 增加 retrospective DB integration smoke
  - scope: `packages/hermes-db/tests/test_wechat_retrospective_integration.py`
  - maps_to: US1-US4 / Acceptance Evidence
  - verify: with `DATABASE_URL`, migrated DB proves performance upsert -> report create/get/list -> suggestion create/review -> ranking hints -> learning candidate create/review/list; without DB skip cleanly.

- [x] T039 [Regression] 运行 retrospective focused suite
  - scope: local test run
  - maps_to: T007 / T013 / T023 / T033 / T036
  - verify: `rtk uv run pytest tests/test_migration_sql.py tests/test_wechat_retrospective_contracts.py tests/test_wechat_retrospective_repo_sql.py tests/test_wechat_retrospective_tools.py tests/test_wechat_retrospective_schema_health.py -q` passes.

- [x] T040 [Regression] 运行 existing capability regression suite
  - scope: existing topic/workflow/article/analytics/health tests
  - maps_to: NFR-004 / 可用性
  - verify: `rtk uv run pytest tests/test_health.py tests/test_wechat_analytics_tools.py tests/test_wechat_article_tools.py tests/test_workflow_tools.py tests/test_tools_updates.py -q` passes.

- [x] T041 [Quality] 运行 lint/type-equivalent checks
  - scope: `packages/hermes-db`
  - maps_to: maintainability
  - verify: `rtk uv run ruff check .` passes from `packages/hermes-db`.

- [ ] T042 [Local MCP Smoke] 执行本地 MCP smoke
  - scope: local hermes-db server and migrated test DB
  - maps_to: Acceptance Evidence Required
  - verify: capture command/result showing health capability true and all retrospective tool calls succeed in sequence.

---

## Phase 7: Deployment Evidence and Closeout Prep

**目标**: 准备真实部署证据、agents handoff 和 SDD 验收材料。

- [x] T043 [Release Prep] 准备 deployment/migration notes
  - scope: deployment docs, release notes, migration command notes
  - maps_to: external-side-effects / FR-012
  - verify: notes include revision id, downgrade caveat, capability key, and smoke commands.

- [ ] T044 [Deployed Smoke] 在 NAS/部署环境验证 capability
  - scope: deployed hermes-db MCP endpoint
  - maps_to: US5 / Acceptance Evidence Required
  - verify: deployed `health` reports `capabilities.wechat_retrospective_topic_optimizer=true`.

- [ ] T045 [Agents Handoff] 跑或记录 agents-side live smoke gate
  - scope: `/Users/yqg/personal/AI/agents` retrospective live smoke
  - maps_to: prior-closure-failure / artifact-handoff
  - verify: agents production adapter passes retrospective capability gate and can complete analytics -> performance -> report -> suggestion -> approved ranking hint smoke against deployed MCP.

- [x] T046 [Acceptance] 生成 SDD acceptance artifact
  - scope: `specs/hermes-db-wechat-retrospective-topic-optimizer/acceptance.md`
  - maps_to: Acceptance Evidence Required / closeout readiness
  - verify: acceptance records migration file, tests run, local MCP smoke, deployed health smoke, agents handoff status, and unresolved risks if any.

---

## 依赖与顺序

- **关键路径**: T001-T007 -> T008-T013 -> T014-T023 -> T024-T033 -> T034-T036 -> T038-T042 -> T043-T046.
- **可并行**:
  - T008-T012 can be implemented alongside migration after table/status names stabilize.
  - T034-T036 can start after migration names are stable, but final true/false behavior depends on T001-T007.
  - T037 docs can start after tool names and capability key are stable.
- **必须先完成**:
  - T001-T006 before integration tests can run against real DB.
  - T008-T013 before MCP tools should accept writes.
  - T014-T023 before tools can be fully wired.
  - T034-T036 before deployed smoke can unblock agents live smoke.
- **外部依赖**:
  - T044 needs deployed/NAS MCP access and migration execution.
  - T045 needs agents repo live smoke context and deployed capability.

---

## 覆盖检查

| 场景 / 需求 | 对应任务 |
|-------------|----------|
| US1 保存和查询 topic performance | T002, T009, T015, T016, T025, T026, T038 |
| US2 保存和查询 retrospective reports | T003, T010, T017, T027, T038 |
| US3 生成、审核和查询 suggestions / ranking hints | T004, T011, T018, T019, T020, T028, T029, T038 |
| US4 保存和审核 learning candidates | T005, T012, T021, T022, T030, T038 |
| US5 Health capability / schema drift gate | T034, T035, T036, T042, T044 |
| FR-001 `topic_performance` upsert/list | T002, T009, T015, T016, T025, T026 |
| FR-002 reports create/get/list | T003, T010, T017, T027 |
| FR-003 suggestions create/list/review | T004, T011, T018, T019, T028 |
| FR-004 learning candidates create/list/review | T005, T012, T021, T022, T030 |
| FR-005 approved ranking hints | T004, T011, T020, T029 |
| FR-006 list pagination with total | T008, T016, T017, T018, T020, T021, T026, T027, T028, T029, T030 |
| FR-007 JSON fields round-trip | T009-T012, T015, T017-T022, T025-T030 |
| FR-008 agents adapter compatibility | T024-T033, T038, T045 |
| FR-009/FR-010 health/schema inspector | T034-T036, T044 |
| FR-011 structured errors | T013, T031, T033 |
| FR-012 downgrade safety | T006, T007, T043 |

| 架构决策 / 质量属性 | 对应任务 | 验证任务 |
|----------------------|----------|----------|
| ADR-001 extend existing hermes-db service | T014, T024, T032 | T033, T040 |
| ADR-002 performance idempotency | T002, T015, T025 | T023, T033, T038 |
| ADR-003 suggestions/candidates append-only | T018, T021, T028, T030 | T023, T033 |
| ADR-004 JSONB relational-index MVP | T002-T005, T015-T022 | T007, T023, T036 |
| ADR-005 reserve applied status | T011, T019, T028 | T033, T038 |
| ADR-006 list response shape | T008, T016-T021, T026-T030 | T023, T033 |
| ADR-007 schema-aware health gate | T034-T036 | T040, T042, T044 |
| Safety: no automatic topic mutation | T019, T028, T029 | T033, T038 |
| Availability: existing tools unaffected | T032, T034, T035 | T040 |
| Explainability: compact evidence refs | T009-T012, T015-T022 | T013, T023, T033 |

---

## Context Manifest

- 已生成 [context-manifest.md](context-manifest.md)，因为该 feature 命中 `multi-stage-workflow`、`external-side-effects`、`artifact-handoff`、`user-visible-output` 和 `prior-closure-failure`。
- Implement 阶段必须读取 spec/plan/data-model/tasks，Check 阶段必须用同一组 SDD 产物核验架构漂移和验收覆盖。

---

## Notes

- 如果实现时发现 agents adapter 与本 spec/plan 不一致，应优先更新 mcps 侧 contract 文档，再做兼容实现或回到 agents 仓调整 downstream adapter。
- `applied` 和 `exported_to_policy` 是 future trace/export states；本 MVP 不通过 review tools 写入它们。
- `total` 是 retrospective list tools 的新 contract 要求，不应因旧 analytics list shape 缺少 total 而省略。

---

## Stage Readiness

- 推荐下一步：`execute-plan`
- 原因：任务数量较多，且存在 migration、MCP tools、schema health、部署 smoke、agents handoff 多个阶段依赖，直接 `implement` 容易丢失节奏。
- 阻塞项：无。部署 smoke 和 agents live smoke 是后续验证/收尾阶段的外部证据，不阻塞本地实现启动。
