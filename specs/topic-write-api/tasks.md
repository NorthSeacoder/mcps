# Tasks: hermes-db MCP topic write API

**Workspace**: `topic-write-api` | **Date**: 2026-05-30  
**Input**: `specs/topic-write-api/spec.md` + `plan.md`  
**Prerequisites**: spec.md, plan.md
**Status**: Implemented & Verified

---

## 执行原则

- 按依赖顺序执行：契约与常量 -> repository -> cache -> tools -> 验证。
- 每个任务必须能映射到 spec 的用户场景、功能需求、ADR 或质量属性。
- 写接口相关任务必须先补验证，再补实现或同步补验证，避免 schema/缓存行为漂移。

---

## Phase 1: Contract And Validation Foundation

**目标**: 建立稳定工具契约、字段集合和错误 code，作为后续 repo/tool 实现的边界。

- [x] T001 定义 topic 写接口常量和字段集合
  - scope: `packages/hermes-db/src/hermes_db_mcp/contracts.py` 或 `tools/contracts.py`
  - maps_to: FR-010, FR-010a, NFR-005, ADR-002, ADR-004
  - verify: 单测断言 priority/resonance/clearable/editable/bulk 字段集合符合 spec

- [x] T002 定义结构化结果和错误模型
  - scope: contract module；`ToolError`, `TopicUpdateResult`, `BatchTopicUpdateResult`, `TopicListResult`
  - maps_to: US4, FR-009, FR-014, ADR-005
  - verify: 单测验证成功和错误结果字段稳定，错误包含 code/message/details

- [x] T003 定义通用校验 helper
  - scope: contract/validation helper
  - maps_to: US1 edge cases, US2 edge cases, FR-010, NFR-001
  - verify: 单测覆盖非法 priority、非法 resonance、空 title、title 超长、非法 clear_fields、批量 ids 为空/超限

---

## Phase 2: Repository Layer

**目标**: 在数据层补齐安全、可测试、参数化的单条和批量更新能力。

- [x] T004 扩展 `topic_repo.get_by_id` / 完整行返回约定
  - scope: `packages/hermes-db/src/hermes_db_mcp/repositories/topic_repo.py`
  - maps_to: US1, FR-003, FR-011, Decision 2
  - verify: 单测确认完整行字段与 `get_topic` 需要的字段一致

- [x] T005 实现 `update_topic_fields`
  - scope: `topic_repo.py`
  - maps_to: US1, FR-001, FR-003, FR-003a, NFR-005, ADR-003
  - verify: repo 单测覆盖动态 SET 子句、参数顺序、字段白名单、embedding 更新/置空、RETURNING 完整行

- [x] T006 实现 `batch_update_fields`
  - scope: `topic_repo.py`
  - maps_to: US2, FR-004, FR-005, FR-006, NFR-002, ADR-004
  - verify: repo 单测覆盖 `WHERE id = ANY(...)`、只允许 bulk 字段、RETURNING updated ids、not_found diff 输入支持

- [x] T007 增强 `list_by_filter`
  - scope: `topic_repo.py`
  - maps_to: US3, FR-007, FR-008
  - verify: repo 单测覆盖 priority 条件、exclude_published 条件、SELECT 包含 resonance/column_name

---

## Phase 3: Cache Layer

**目标**: 封装批量缓存删除能力，并确保写后读不使用陈旧 topic 缓存。

- [x] T008 增加 `delete_cached`
  - scope: `packages/hermes-db/src/hermes_db_mcp/services/cache.py`
  - maps_to: FR-011, FR-012, Decision 3, 一致性
  - verify: 单测或 fake redis 验证多 key 删除，Redis 异常不抛出

- [x] T009 定义 topic 行序列化 helper
  - scope: `tools/topics.py` 或 contract/helper module
  - maps_to: FR-011, Decision 2
  - verify: 单测确认 id/created_at/updated_at 转字符串，字段集与 `get_topic` 返回一致

---

## Phase 4: MCP Tool Implementation

**目标**: 实现新增工具、增强列表工具，并给工具补 MCP 行为注解。

- [x] T010 给 topic tools 添加 ToolAnnotations
  - scope: `packages/hermes-db/src/hermes_db_mcp/tools/topics.py`
  - maps_to: US4, FR-013, ADR-005
  - verify: 单测或工具注册检查确认 list/get/find 为 read-only，create/update/batch/status/publish 为写工具语义

- [x] T011 实现 `update_topic`
  - scope: `tools/topics.py`
  - maps_to: US1, FR-001, FR-002, FR-003, FR-003a, FR-010a, ADR-002, ADR-003
  - verify: tool 单测覆盖成功更新、clear_fields、非法字段、not_found、UUID 错误、embedding success/pending、缓存重写

- [x] T012 实现 `batch_update_topics`
  - scope: `tools/topics.py`
  - maps_to: US2, FR-004, FR-005, FR-006, NFR-001, Decision 3
  - verify: tool 单测覆盖成功批量、重复 id 去重、空 ids、超限、非法 UUID、not_found_ids、缓存删除

- [x] T013 增强 `list_topics`
  - scope: `tools/topics.py`
  - maps_to: US3, FR-007, FR-008
  - verify: tool 单测覆盖 priority/exclude_published 参数传递、limit/offset 校验、返回项包含运营字段

- [x] T014 保持现有 topic 行为兼容
  - scope: `tools/topics.py`
  - maps_to: regression, ADR-001
  - verify: 现有 `create_topic`, `find_similar_topics`, `update_topic_status`, `publish_topic`, `get_topic` 测试仍通过

---

## Phase 5: Verification And Drift Control

**目标**: 确认实现满足 spec/plan，不引入架构漂移。

- [x] T015 扩展 test suite
  - scope: `packages/hermes-db/tests/test_topic_repo.py`, `test_topics_tools.py`, `test_validation.py`, cache tests
  - maps_to: NFR-006, Verification Strategy
  - verify: 新增测试覆盖所有 US1-US4 关键验收点

- [x] T016 运行格式、lint 和测试
  - scope: `packages/hermes-db`
  - maps_to: Stage readiness
  - verify: `uv run ruff check .` 和 `uv run pytest` 通过

- [x] T017 做 SDD verify 准备记录
  - scope: `specs/topic-write-api/acceptance.md` 后续阶段输入，可先记录验证证据清单
  - maps_to: Evidence Gate, 三维 Verdict
  - verify: 列出 Component / Workflow / MCP Contract 三类证据来源

---

## 依赖与顺序

- T001-T003 是基础，必须先完成。
- T004-T007 可在 T001-T003 后并行推进，但 T005/T006 依赖字段白名单。
- T008-T009 可与 repository 层并行。
- T011 依赖 T004/T005/T008/T009。
- T012 依赖 T006/T008。
- T013 依赖 T007。
- T015 应随实现同步补齐，T016/T017 在实现完成后执行。

**关键路径**: T001 -> T002/T003 -> T005 -> T011 -> T015 -> T016。

---

## 覆盖检查

| 场景 / 需求 | 对应任务 |
|-------------|----------|
| US1 单条字段更新 | T001, T002, T003, T004, T005, T009, T011, T015 |
| US2 批量修正 | T001, T002, T003, T006, T008, T012, T015 |
| US3 列表复核 | T003, T007, T013, T015 |
| US4 MCP 工具契约 | T002, T010, T011, T012, T013, T015 |
| FR-011/FR-012 缓存一致性 | T008, T009, T011, T012, T015 |
| NFR-001/NFR-002 批量上限和性能 | T003, T006, T012, T015 |

| 架构决策 / 质量属性 | 对应任务 | 验证任务 |
|----------------------|----------|----------|
| ADR-001 分层单体增强 | T004-T014 | T016 |
| ADR-002 `clear_fields` | T001, T003, T011 | T015 |
| ADR-003 embedding pending | T005, T011 | T015 |
| ADR-004 批量只支持运营字段 | T001, T006, T012 | T015 |
| ADR-005 structured output + annotations | T002, T010 | T015 |
| 一致性 | T008, T009, T011, T012 | T015 |
| 安全性 | T001, T003, T005, T006 | T015 |
| 性能 | T006, T012 | T015 |

---

## Notes

- 不创建 `data-model.md`，因为本期不改数据库 schema。
- 不实现 `batch_update_topic_status`，只保留为后续演进项。
- 不追查“全部为 A”的上游误写来源，除非实现中发现 `create_topic` 默认值或调用约定与 spec 冲突。

---

## Stage Readiness

- 状态：已实现并验证，证据见 [`IMPLEMENTATION.md`](IMPLEMENTATION.md)。
- 后续：无需继续开发；若要扩展批量状态更新，另开 feature。
- 阻塞项：无。
