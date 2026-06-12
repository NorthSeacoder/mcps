# Tasks: Hermes DB Agent Self Evolution Foundation

**Workspace**: `hermes-db-agent-self-evolution-foundation` | **Date**: 2026-06-11  
**Input**: `spec.md` + `plan.md` + `data-model.md`

---

## 执行原则

- 按 migration -> contracts -> repository -> tools -> health -> live smoke 推进。
- 本仓只实现 hermes-db persistence/MCP/capability，不实现 agents 侧消费逻辑。
- promotion 只能消费 approved learning candidates；pending/rejected/disabled fail closed。
- disable/rollback 和 application traces 必须保留历史。

---

## Phase 1: Migration and Schema Contract

- [x] T001 新增 Alembic revision `0006_agent_self_evolution_foundation`
  - scope: `packages/hermes-db/migrations/versions/0006_agent_self_evolution_foundation.py`
  - maps_to: FR-001 / FR-002 / data-model.md
  - verify: `down_revision = "0005_wechat_retro_opt"` and migration is additive.

- [x] T002 创建 `hermes.agent_policies`
  - scope: migration
  - maps_to: FR-001 / rollbackability / traceability
  - verify: fields, unique `(policy_id, version)`, source candidate id index, status/type checks and JSON fields exist.

- [x] T003 创建 `hermes.policy_applications`
  - scope: migration
  - maps_to: FR-002 / FR-006
  - verify: FK to `agent_policies(policy_version_id)`, run/policy/domain indexes and append-only fields exist.

- [x] T004 更新 migration SQL tests
  - scope: `packages/hermes-db/tests/test_migration_sql.py`
  - maps_to: T001-T003
  - verify: tests assert revision id, down revision, table names, indexes, checks and downgrade order.

## Phase 2: Contracts and Validation

- [x] T005 增加 self-evolution constants and validation helpers
  - scope: `packages/hermes-db/src/hermes_db_mcp/contracts.py`
  - maps_to: FR-003..FR-006
  - verify: status/type/pagination/scope/application validation tests pass.

- [x] T006 增加 structured error helpers/tests
  - scope: `contracts.py`, `tests/test_agent_self_evolution_contracts.py`
  - maps_to: FR-008
  - verify: invalid_state, invalid_scope, validation_error cases covered.

## Phase 3: Repository Layer

- [x] T007 新增 `agent_self_evolution_repo.py`
  - scope: `packages/hermes-db/src/hermes_db_mcp/repositories/agent_self_evolution_repo.py`
  - maps_to: ADR-001
  - verify: module imports cleanly and serialization follows existing repo style.

- [x] T008 实现 `promote_learning_candidate_to_policy`
  - scope: repository
  - maps_to: US1 / FR-003
  - verify: approved candidate creates policy and updates candidate with `policy_id` as string for existing `learning_candidates.policy_id TEXT`; pending/rejected fail closed; repeated promote returns existing policy.

- [x] T009 实现 `list_agent_policies` and `get_applicable_agent_policies`
  - scope: repository
  - maps_to: US2 / FR-004 / scope isolation
  - verify: active/time/task/decision/scope filters and cross-account negative cases.

- [x] T010 实现 `disable_agent_policy` and `rollback_agent_policy`
  - scope: repository
  - maps_to: US3 / FR-005
  - verify: active query excludes disabled/rolled-back current version; rollback copies target payload into a new active monotonic version; historical target version remains unchanged.

- [x] T011 实现 `record_policy_application` and `list_policy_applications`
  - scope: repository
  - maps_to: US4 / FR-006
  - verify: append-only insert and list filters by policy/run/domain/task.

- [x] T012 增加 repository SQL tests
  - scope: `tests/test_agent_self_evolution_repo_sql.py`
  - maps_to: T007-T011
  - verify: SQL text and fake DB tests cover all repository methods.

## Phase 4: MCP Tools

- [x] T013 新增 `tools/agent_self_evolution.py`
  - scope: `packages/hermes-db/src/hermes_db_mcp/tools/agent_self_evolution.py`
  - maps_to: FR-003..FR-006
  - verify: module imports cleanly.

- [x] T014 实现 promotion/list/query/disable/rollback/application tools
  - scope: tool module
  - maps_to: US1-US4
  - verify: tool tests cover success, validation errors, not_found, schema_drift and database_error.

- [x] T015 注册 MCP tools
  - scope: `packages/hermes-db/src/hermes_db_mcp/server.py`
  - maps_to: artifact-handoff
  - verify: registration/import tests confirm existing tools still import.

## Phase 5: Health and Capability

- [x] T016 增加 schema-aware capability check
  - scope: health tool / schema inspection
  - maps_to: US5 / FR-007
  - verify: capability true when required tables/columns/checks/indexes and `learning_candidates` compatibility columns exist, false when missing; tool registration is covered by T015 tests, not runtime health introspection.

- [x] T017 增加 health tests
  - scope: health tests
  - maps_to: US5
  - verify: true/false paths for `agent_self_evolution_foundation`.

## Phase 6: Verification and Live Smoke

- [x] T018 Run targeted tests
  - scope: hermes-db tests
  - maps_to: verification
  - verify: contracts/repo/tools/health targeted tests pass.

- [ ] T019 Deployed live smoke
  - scope: NAS/deployed MCP endpoint
  - maps_to: workflow replay
  - verify: approved candidate -> promote policy -> query applicable policy -> record application -> list application.

- [ ] T020 Acceptance record
  - scope: `specs/hermes-db-agent-self-evolution-foundation/acceptance.md`
  - maps_to: closeout
  - verify: Evidence Table, Verdict Summary, Workflow Replay and Completion Record complete.

---

## 依赖与顺序

- T001-T004 before repository/tools.
- T005-T006 before tools validation.
- T007-T012 before MCP tools.
- T013-T017 before deployed smoke.
- T018-T020 are final evidence gate.

---

## Stage Readiness

- 推荐下一步：`execute-plan`
- 阻塞项：无；可先从 migration/contract tests 开始。
