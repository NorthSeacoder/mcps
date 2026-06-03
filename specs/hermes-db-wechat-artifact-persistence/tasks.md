# Tasks: hermes-db WeChat Artifact Persistence

**Workspace**: `hermes-db-wechat-artifact-persistence` | **Date**: 2026-06-03  
**Input**: `specs/hermes-db-wechat-artifact-persistence/spec.md` + `plan.md` + `data-model.md`  
**Prerequisites**: spec.md, plan.md, data-model.md

---

## 执行原则

- 按依赖顺序推进：schema 先于 repository，repository 先于 MCP tools，tools 先于端到端验证。
- 每个实现任务必须带对应测试或明确的验证任务。
- 不改变现有 topic/inspiration tools 的参数、返回结构和 transport 行为。
- `content_ref` MVP 只存储和返回引用，不读取外部文件或 URL。

---

## Phase 1: Migration and Schema Health

**目标**: 建立 PostgreSQL 存储结构，并让 health 能诊断新能力是否可用。

- [x] T001 [US1, US2] 新增 Alembic migration `0002_wechat_workflow_artifacts.py`
  - scope: `packages/hermes-db/migrations/versions/0002_wechat_workflow_artifacts.py`
  - maps_to: FR-001, FR-002, ADR-001, data-model.md
  - verify: migration 文件包含 `wechat_workflow_runs`、`workflow_artifacts`、FK、CHECK、UNIQUE、索引和 `down_revision = "0001_topic_revisit"`

- [x] T002 [US1, US2] 为新 migration 增加静态 SQL 测试
  - scope: `packages/hermes-db/tests/test_migration_sql.py`
  - maps_to: FR-001, FR-002, NFR-004
  - verify: `uv run pytest tests/test_migration_sql.py -q`

- [x] T003 [US4] 扩展 schema inspection 支持 workflow capability
  - scope: `packages/hermes-db/src/hermes_db_mcp/services/schema.py`
  - maps_to: FR-012, US4-2, 可诊断性
  - verify: 单元测试覆盖表缺失、约束缺失、完整 schema 三种结果

- [x] T004 [US4] 更新 `health` 合并 workflow capabilities
  - scope: `packages/hermes-db/src/hermes_db_mcp/tools/health.py`
  - maps_to: FR-012, US4-2, US4-3
  - verify: `health()["capabilities"]` 保留现有 topic keys，并新增 `workflow_runs`、`workflow_artifacts`

- [x] T005 [US4] 增加 workflow schema health 测试
  - scope: `packages/hermes-db/tests/test_workflow_schema_health.py`, existing health tests
  - maps_to: FR-012, NFR-003, 兼容性
  - verify: `uv run pytest tests/test_health.py tests/test_workflow_schema_health.py -q`

---

## Phase 2: Contracts and Validation

**目标**: 固化 MCP tool 入参、错误结构、content policy 和查询边界。

- [x] T006 [US1, US2, US3] 扩展 workflow 相关结构化错误和常量
  - scope: `packages/hermes-db/src/hermes_db_mcp/contracts.py`
  - maps_to: NFR-003, ADR-002, ADR-003, ADR-005
  - verify: error codes 包含 `content_too_large`、`content_missing`、`artifact_id_conflict`、`schema_drift`、`invalid_filter`

- [x] T007 [US1] 新增 workflow run payload validators
  - scope: `packages/hermes-db/src/hermes_db_mcp/contracts.py`
  - maps_to: FR-003, FR-004, NFR-001
  - verify: 校验 `run_id`、`phase`、`status`、JSON 字段默认值和 completed payload

- [x] T008 [US2] 新增 workflow artifact payload validators
  - scope: `packages/hermes-db/src/hermes_db_mcp/contracts.py`
  - maps_to: FR-005, FR-008, FR-009, FR-011, ADR-002, ADR-003
  - verify: 校验 256 KiB inline 限制、`content_text/content_ref` 至少一项、二进制图片正文拒绝策略、parent id 格式

- [x] T009 [US3] 新增 artifact query validators
  - scope: `packages/hermes-db/src/hermes_db_mcp/contracts.py`
  - maps_to: FR-006, FR-007, NFR-002
  - verify: 校验至少一个 filter 或显式 bounded limit，默认 limit 50，最大 limit 200

- [x] T010 [US1, US2, US3] 增加 workflow contract 测试
  - scope: `packages/hermes-db/tests/test_workflow_contracts.py`
  - maps_to: T006-T009
  - verify: `uv run pytest tests/test_workflow_contracts.py -q`

---

## Phase 3: Repository Layer

**目标**: 用 repository 封装 SQL，实现幂等写入、版本递增和摘要查询。

- [x] T011 [US1] 实现 `upsert_run`
  - scope: `packages/hermes-db/src/hermes_db_mcp/repositories/workflow_repo.py`
  - maps_to: FR-001, FR-003, US1-1, US1-3, NFR-001
  - verify: 同一 `run_id` 重复写入只更新一条记录，返回 `created`/`updated_at` 语义可被 tool 使用

- [x] T012 [US1] 实现 `finish_run`
  - scope: `packages/hermes-db/src/hermes_db_mcp/repositories/workflow_repo.py`
  - maps_to: FR-004, US1-2, US1-5
  - verify: 已存在 run 被更新；不存在 run 返回 `None`

- [x] T013 [US2] 实现 `upsert_artifact` 幂等与版本逻辑
  - scope: `packages/hermes-db/src/hermes_db_mcp/repositories/workflow_repo.py`
  - maps_to: FR-002, FR-005, FR-008, FR-011, ADR-004, ADR-005
  - verify: 同 `artifact_id/hash` 返回既有行；同 `(run_id, stage, name, content_hash)` 返回既有行；新 hash 插入下一 version

- [x] T014 [US2] 实现 parent artifact relation 写入与冲突处理
  - scope: `packages/hermes-db/src/hermes_db_mcp/repositories/workflow_repo.py`
  - maps_to: FR-010, US2-2
  - verify: transformed-draft 可保存 `parent_artifact_id`；不存在 parent 时返回 repository 可识别错误或由 FK 触发结构化 tool error

- [x] T015 [US3] 实现 `list_artifacts`
  - scope: `packages/hermes-db/src/hermes_db_mcp/repositories/workflow_repo.py`
  - maps_to: FR-006, US3-1, US3-2, US3-3, NFR-002
  - verify: 支持 `run_id/topic_id/account/type/stage/date_from/date_to/limit/offset`，返回字段不含 `content_text`

- [x] T016 [US3] 实现 `get_artifact`
  - scope: `packages/hermes-db/src/hermes_db_mcp/repositories/workflow_repo.py`
  - maps_to: FR-007, US3-4, ADR-003
  - verify: inline artifact 返回正文；ref artifact 返回 ref 字段；不存在返回 `None`

- [x] T017 [US1, US2, US3] 增加 repository 单元/SQL 测试
  - scope: `packages/hermes-db/tests/test_workflow_repo.py`, `packages/hermes-db/tests/test_workflow_repo_sql.py`
  - maps_to: T011-T016, 持久性, 幂等性, 版本性
  - verify: `uv run pytest tests/test_workflow_repo.py tests/test_workflow_repo_sql.py -q`

---

## Phase 4: MCP Tools

**目标**: 暴露下游 agents 可调用的 MCP tools，并保持 structured result/error 语义。

- [x] T018 [US1] 实现 `upsert_workflow_run` MCP tool
  - scope: `packages/hermes-db/src/hermes_db_mcp/tools/workflow_runs.py`
  - maps_to: FR-003, US1-1, US1-3, US1-4
  - verify: tool 测试覆盖 create、retry update、dry_run、blocked-before-start

- [x] T019 [US1] 实现 `finish_workflow_run` MCP tool
  - scope: `packages/hermes-db/src/hermes_db_mcp/tools/workflow_runs.py`
  - maps_to: FR-004, US1-2, US1-5
  - verify: tool 测试覆盖完成成功、missing run -> `not_found`

- [x] T020 [US2] 实现 `upsert_workflow_artifact` MCP tool
  - scope: `packages/hermes-db/src/hermes_db_mcp/tools/workflow_artifacts.py`
  - maps_to: FR-005, FR-008, FR-009, FR-010, FR-011, US2
  - verify: tool 测试覆盖 draft inline、transformed parent、same name new version、same hash retry、large content ref

- [x] T021 [US3] 实现 `list_workflow_artifacts` MCP tool
  - scope: `packages/hermes-db/src/hermes_db_mcp/tools/workflow_artifacts.py`
  - maps_to: FR-006, US3-1, US3-2, US3-3, US3-5, US3-7
  - verify: tool 测试确认默认不返回 `content_text`，无界查询被拒绝或强制 bounded limit

- [x] T022 [US3] 实现 `get_workflow_artifact_content` MCP tool
  - scope: `packages/hermes-db/src/hermes_db_mcp/tools/workflow_artifacts.py`
  - maps_to: FR-007, US3-4, US3-6, ADR-003
  - verify: tool 测试覆盖 inline 正文、ref metadata、not_found

- [x] T023 [US4] 注册新 tools 且不改变现有 tools
  - scope: `packages/hermes-db/src/hermes_db_mcp/server.py`, `packages/hermes-db/src/hermes_db_mcp/tools/__init__.py`
  - maps_to: FR-013, US4-1, US4-4
  - verify: 现有 topic/inspiration tests 仍通过；工具注册不影响 health/transport

- [x] T024 [US1, US2, US3] 增加 workflow tool 测试
  - scope: `packages/hermes-db/tests/test_workflow_tools.py`
  - maps_to: T018-T022, NFR-003
  - verify: `uv run pytest tests/test_workflow_tools.py -q`

---

## Phase 5: Documentation, Regression, and Evidence

**目标**: 补齐调用契约说明、兼容性验证和最终可交付证据。

- [x] T025 [US4] 更新 hermes-db README 或部署文档说明新 capability 和 migration
  - scope: `packages/hermes-db/README.md`, `docs/hermes-db-deployment.md`
  - maps_to: FR-012, artifact-handoff, release readiness
  - verify: 文档包含新 tools 名称、`capabilities.workflow_artifacts`、`alembic upgrade head` 提醒

- [x] T026 [US4] 跑现有 hermes-db 回归测试
  - scope: `packages/hermes-db/tests`
  - maps_to: FR-013, 兼容性
  - verify: `uv run pytest tests -q`

- [x] T027 [US1, US2, US3] 可选真实数据库集成验证
  - scope: `packages/hermes-db` with `DATABASE_URL`
  - maps_to: 持久性, artifact-handoff, Evidence Gate
  - verify: 创建 run -> 写入 draft -> list 摘要 -> get 正文，记录命令输出或跳过原因

- [x] T028 [Closeout Prep] 记录实现证据和残留风险
  - scope: `specs/hermes-db-wechat-artifact-persistence/acceptance.md`
  - maps_to: prior-closure-failure, Evidence Gate
  - verify: acceptance 记录测试命令、结果、未执行项、下游 agents 联调状态

---

## 依赖与顺序

- 关键路径：T001 -> T003/T004 -> T006-T010 -> T011-T017 -> T018-T024 -> T026 -> T028。
- T002 可在 T001 后立即完成。
- T003/T004 可以和 T006-T010 并行，但 health 最终验证依赖 migration schema 定义。
- T011/T012 可先于 artifact repository；T013-T016 依赖 T001 和 T006-T010。
- T018/T019 依赖 run repository；T020-T022 依赖 artifact repository。
- T025 可与 Phase 4 后半段并行，但内容应以最终 tool 名称为准。
- T027 依赖 migration 和 tool/repository 实现，可因缺少 `DATABASE_URL` 跳过，但必须在 T028 记录原因。

---

## 覆盖检查

| 场景 / 需求 | 对应任务 |
|-------------|----------|
| US1 run 主记录创建/完成/重试 | T001, T007, T011, T012, T018, T019, T024 |
| US2 artifact 保存、版本、parent、content policy | T001, T008, T013, T014, T020, T024 |
| US3 artifact 摘要查询与全文读取 | T009, T015, T016, T021, T022, T024 |
| US4 兼容现有 tools 和 health capability | T003, T004, T005, T023, T025, T026 |
| FR-001/FR-002 新表 | T001, T002 |
| FR-003/FR-004 run tools | T011, T012, T018, T019 |
| FR-005/FR-007 artifact tools | T013-T016, T020-T022 |
| FR-012 health capability | T003-T005 |
| FR-013 兼容性 | T023, T026 |

| 架构决策 / 质量属性 | 对应任务 | 验证任务 |
|----------------------|----------|----------|
| ADR-001 PostgreSQL storage | T001, T011-T017 | T002, T017, T027 |
| ADR-002 256 KiB inline threshold | T008, T020 | T010, T024 |
| ADR-003 `content_ref` 不 dereference | T008, T016, T022 | T010, T017, T024 |
| ADR-004 artifact versioning | T013 | T017, T024 |
| ADR-005 client artifact id optional | T008, T013, T020 | T010, T017, T024 |
| 持久性 | T001, T011-T017 | T017, T027 |
| 幂等性 | T011, T013, T018, T020 | T017, T024 |
| 查询性能 | T001, T009, T015, T021 | T002, T017, T024 |
| 可诊断性 | T006-T010, T003-T005 | T010, T005, T024 |
| 兼容性 | T023, T026 | T026 |

---

## Notes

- 当前任务数量较多，且横跨 migration、contracts、repository、tools、health、docs 和验收记录，不建议直接跳到一次性实现。
- 如果实现期发现 version assignment 需要锁，应优先选择 repository 内部事务或 advisory lock，不把锁语义暴露给 MCP client。
- 本 feature 不实现 agents 仓调用逻辑；下游联调证据可在 acceptance 中标记为待 agents feature 消费。

---

## Stage Readiness

- 推荐下一步：`execute-plan`
- 阻塞项：无
