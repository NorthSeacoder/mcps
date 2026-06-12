# Feature Specification: Hermes DB Agent Self Evolution Foundation

**Workspace**: `hermes-db-agent-self-evolution-foundation`  
**Created**: 2026-06-11  
**Status**: Ready for Plan  
**Input**: agents 仓 `agent-self-evolution-foundation` 已完成 SDD plan/tasks；需要在 mcps/hermes-db 侧固定 runtime policy store、MCP tools、schema-aware health capability 和 live smoke 支撑。

---

## Feature Traits

| Trait | 是否命中 | 依据 |
|---|---|---|
| `multi-stage-workflow` | yes | `learning_candidates -> agent_policies -> get_applicable_policies -> policy_applications -> retrospective` 多阶段闭环 |
| `external-side-effects` | yes | 新增 DB tables/migration、MCP tools、health capability，并被 agents 生产 CLI 调用 |
| `artifact-handoff` | yes | 消费 retrospective `learning_candidates`，产出 policies/application traces 给业务 agent 消费 |
| `user-visible-output` | yes | policy list、promotion/disable/rollback 结果和 application trace 会进入 CLI/验收输出 |
| `prior-closure-failure` | yes | agents 已有 learning candidates，但缺通用 policy engine，复盘经验无法稳定影响下一次任务 |
| `bugfix-loop-breaker` | no | 本 feature 是新增 runtime policy foundation，不是针对具体 regression 或重复失败 bugfix 的 root-cause 修复 |

**结论**: 本 feature 必须覆盖 migration contract、MCP tool contract、status transition、schema-aware health gate、agents adapter compatibility 和 live smoke。

---

## Problem Statement

`agents` 仓的公众号复盘闭环已经能生成并审核 `learning_candidates`，但这些候选经验目前只停留在兼容层：

- 没有通用 `agent_policies` runtime store。
- 没有按 domain/scope/task_type/decision_point 查询 applicable policies 的 MCP tool。
- 没有记录某次任务实际应用了哪个 policy version 的 `policy_applications` trace。
- 没有 disable/rollback 机制来安全撤销错误策略。
- health capability 无法证明 self-evolution schema/tools 已部署。

本 feature 在 hermes-db 侧补齐最小 runtime policy contract，让 agents 侧可以完成：

```text
approved learning_candidate
  -> promote to active agent_policy
  -> query applicable policy before task
  -> business agent applies read-only influence
  -> record policy_application trace
```

---

## Goals

- 新增 `agent_policies` 持久化表，保存 versioned、scoped、reviewed policies。
- 新增 `policy_applications` 持久化表，记录每次 policy 被 applied/skipped/failed 的 trace。
- 复用并扩展既有 `learning_candidates`，支持 approved candidate promote 为 policy，并写回 `status=exported_to_policy` 与 `policy_id`。
- 暴露 MCP tools：promote、list policies、get applicable policies、disable、rollback、record application。
- 增加 schema-aware health capability：`agent_self_evolution_foundation=true`。
- 保证 status transition、scope isolation、idempotency 和 rollback 历史可审计。

---

## Non-Goals

- 不实现 agents 侧 topic ranking、writer prompt 或 reviewer gate 业务逻辑。
- 不实现 UI。
- 不自动修改本地 Codex/Claude skills、config 或 prompt 文件。
- 不把 Nowledge Mem 作为 runtime policy store。
- 不要求本 feature 首版实现完整 `agent_runs` / `agent_observations` 表；policy applications 可引用现有 workflow/run id。
- 不自动高风险生效 pending/rejected candidates。

---

## User Scenarios & Testing

### User Story 1 - Promote approved learning candidate (Priority: P1)

作为 agents operator，我希望把已审核的 learning candidate 提升为 active policy，使它能被下一次任务查询。

**Acceptance Scenarios**:

1. **[US1-1] approved candidate promotes to policy**  
   **Given** `learning_candidates.status='approved'`  
   **When** 调用 `promote_learning_candidate_to_policy`  
   **Then** 创建 `agent_policies` active version，写入 `source_candidate_id`，并将 candidate 更新为 `exported_to_policy` + `policy_id`。

2. **[US1-2] pending/rejected candidate fail closed**  
   **Given** candidate status 是 `pending_review`、`rejected` 或 `disabled`  
   **When** promote  
   **Then** 返回 validation/invalid_state error，不创建 policy。

3. **[US1-3] duplicate promote is idempotent**  
   **Given** candidate 已经 exported to policy  
   **When** 重复 promote 同一 candidate  
   **Then** 返回已有 policy 或明确 duplicate/idempotent response，不创建重复 active policy。

### User Story 2 - Query applicable policies (Priority: P1)

作为业务 agent，我希望按 domain/scope/task_type/decision_point 查询当前可用 policy。

**Acceptance Scenarios**:

1. **[US2-1] active policy query**  
   **Given** 存在 active、disabled、superseded、expired policies  
   **When** 调用 `get_applicable_agent_policies`  
   **Then** 只返回 active 且 scope/task/decision/time 匹配的 policies。

2. **[US2-2] scope isolation**  
   **Given** 两个账号有同类 policy  
   **When** 查询 account A  
   **Then** 不返回 account B 的 policy。

3. **[US2-3] conflict surfaced**  
   **Given** 同一 precedence 下存在冲突 policy  
   **When** query  
   **Then** 返回 conflict metadata 或 warnings，不静默任选。

### User Story 3 - Disable and rollback policies (Priority: P1)

作为 operator，我希望错误策略能被禁用或回滚，同时保留历史。

**Acceptance Scenarios**:

1. **[US3-1] disable policy**  
   **Given** active policy  
   **When** 调用 `disable_agent_policy`  
   **Then** 当前 active version 变为 `disabled`，后续 applicable query 不返回。

2. **[US3-2] rollback policy**  
   **Given** policy 有多个 version  
   **When** 调用 `rollback_agent_policy` 指向旧 version  
   **Then** 当前 version 标记为 rolled_back/superseded，并创建或恢复一个 active rollback version。

### User Story 4 - Record policy application trace (Priority: P1)

作为 retrospective consumer，我希望知道某次任务是否应用了某个 policy version。

**Acceptance Scenarios**:

1. **[US4-1] record application**  
   **Given** agent 查询并应用了 policy  
   **When** 调用 `record_policy_application`  
   **Then** 保存 run_id、domain、agent_name、task_type、decision_point、policy_id、policy_version_id、status、applied_action 和 outcome summary。

2. **[US4-2] query application history**  
   **Given** DB 中存在多个 application traces  
   **When** 调用 `list_policy_applications`  
   **Then** 可按 policy_id、run_id、domain、task_type 查询。

### User Story 5 - Health capability gate (Priority: P1)

作为 agents production factory，我需要知道 self-evolution capability 是否真的可用。

**Acceptance Scenarios**:

1. **[US5-1] schema complete**  
   **Given** migration、tables、indexes 和 tools 都可用  
   **When** 调用 health  
   **Then** `capabilities.agent_self_evolution_foundation=true`。

2. **[US5-2] schema incomplete**  
   **Given** table/tool/critical column 缺失  
   **When** 调用 health  
   **Then** capability false 或返回 schema drift，不应半可用。

---

## Functional Requirements

- **FR-001**: MCP 必须新增 `agent_policies` 持久化实体，支持 version、status、scope、task_types、decision_points、policy_body、evidence_refs。
- **FR-002**: MCP 必须新增 `policy_applications` 持久化实体，支持 append-only application trace。
- **FR-003**: MCP 必须支持 `promote_learning_candidate_to_policy`，只允许 approved candidate promote。
- **FR-004**: MCP 必须支持 `list_agent_policies` 和 `get_applicable_agent_policies`。
- **FR-005**: MCP 必须支持 `disable_agent_policy` 和 `rollback_agent_policy`。
- **FR-006**: MCP 必须支持 `record_policy_application` 和 `list_policy_applications`。
- **FR-007**: MCP 必须在 health 暴露 `capabilities.agent_self_evolution_foundation`。
- **FR-008**: 所有 tools 必须返回结构化错误，不泄露原始数据库异常。
- **FR-009**: policy query 必须执行 scope isolation，避免跨账号/项目误用。
- **FR-010**: long content、full reports、draft bodies 和 logs 不得内联进 policy/application；只保存 compact refs。

---

## Non-Functional Requirements

- **NFR-001 Safety**: pending/rejected/disabled/superseded/expired policies 不得被 applicable query 返回。
- **NFR-002 Traceability**: policy 必须能追溯到 source candidate 或 reviewer/evidence。
- **NFR-003 Rollbackability**: disable/rollback 不删除历史。
- **NFR-004 Compatibility**: agents adapter 能使用稳定 field names；JSONB 字段返回 object/array，不返回字符串化 JSON。
- **NFR-005 Availability**: capability false 不影响已有 topic/analytics/retrospective tools。

---

## Key Entities

- **agent_policies**: versioned runtime policy store。
- **policy_applications**: append-only policy application traces。
- **learning_candidates**: existing upstream producer；本 feature 只扩展 promote/export 语义。

---

## Stage Readiness

- 下一步建议：`plan`
- 阻塞项：无；本 spec 足以生成 data-model、plan 和 tasks。
