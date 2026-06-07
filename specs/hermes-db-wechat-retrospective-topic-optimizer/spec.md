# Feature Specification: Hermes DB WeChat Retrospective Topic Optimizer

**Workspace**: `hermes-db-wechat-retrospective-topic-optimizer`  
**Created**: 2026-06-07  
**Status**: Draft  
**Input**: 用户描述: "agents 仓已实现公众号复盘和选题优化 adapter/service/CLI/mock tests；需要在 mcps/hermes-db 侧实现真实持久化、MCP tools、health capability 和 live smoke 支撑。"

---

## Feature Traits

| Trait | 是否命中 | 依据 |
|---|---|---|
| `multi-stage-workflow` | yes | analytics snapshots -> topic performance -> retrospective report -> suggestions -> learning candidates -> downstream ranking hints |
| `external-side-effects` | yes | 需要新增 DB tables/migration、MCP tools、health capability，并被 agents 生产 CLI 调用 |
| `artifact-handoff` | yes | 消费已有 `wechat_articles`、analytics snapshots、topic records；产出 reports/suggestions/candidates 给 agents 消费 |
| `user-visible-output` | yes | reports、suggestions、review status 和 ranking hints 会直接影响 CLI 输出和选题排序 |
| `prior-closure-failure` | yes | agents 侧 mock 和 adapter 已完成，但 live smoke 被 hermes-db retrospective MCP capability 阻塞 |

**结论**: 本 feature 必须按 SDD 主链推进到 plan/tasks/verify，且必须包含 migration contract、MCP tool contract、schema-aware health gate、adapter compatibility tests、live smoke 和 rollback 说明。

---

## Problem Statement

`apps/wechat-agent` 已完成公众号复盘选题优化的 agents 侧实现：

- retrospective typed adapter 已期待 hermes-db 暴露 retrospective MCP tools。
- report/suggestion/learning services 已能在 mock persistence 下生成结果。
- topic radar 和 `pickNext` 已能消费 approved/applied ranking hints。
- production service factory 已尝试创建 Hermes retrospective tools。

当前缺口在 mcps/hermes-db 侧：

- 没有 retrospective 数据表和 migration。
- 没有真实 MCP tools 存储/查询 `topic_performance`、`wechat_retrospective_reports`、`topic_optimization_suggestions`、`learning_candidates`。
- `health.capabilities.wechat_retrospective_topic_optimizer` 不存在或不能 schema-aware 返回 true。
- agents 侧 live smoke 无法证明 analytics snapshot -> performance -> report -> suggestion -> approved ranking hint 的完整闭环。

本 PRD 定义 mcps/hermes-db 必须实现的功能边界和验收语义。

---

## Current Dependency State

本 feature 依赖 hermes-db 现有能力：

- `topics` 基础表和 topic MCP tools 已存在。
- `topic_bucket`、`topic_revisit_of`、`list_revisit_chain` capability 已由 topic bucket/revisit feature 提供。
- `wechat_workflow_runs`、`workflow_artifacts` 已由 artifact persistence feature 提供。
- `wechat_articles`、`wechat_article_external_refs` 已由 publication ledger feature 提供。
- `wechat_article_metric_snapshots`、`wechat_article_channel_daily_metrics` 和 `wechat_analytics_ingestion` capability 已由 analytics ingestion feature 提供。

本 feature 不重新定义上述 schema，只通过 FK 或 compact evidence refs 关联。

---

## Goals

- 新增 retrospective 持久化 schema，保存单篇表现分、复盘报告、选题优化建议和 learning candidates。
- 暴露 agents adapter 已约定的 MCP tools，使用统一 `{ ok/result/error }` 兼容 envelope 或现有 Hermes MCP response style。
- 增加 schema-aware health capability：`wechat_retrospective_topic_optimizer=true` 只有在 migration、关键字段、约束和 indexes 完整时才返回。
- 支持 approved/applied ranking hints 查询，供 agents 的 topic radar 和 `pickNext` 只读消费。
- 支持 suggestion 和 learning candidate 的人工审核状态流转。
- 保证 schema drift 和不完整 schema fail closed，不返回半结构化数据。

---

## Non-Goals

- 不在 MCP 侧计算评分、baseline 或 LLM narrative。评分和报告生成由 agents service 完成，MCP 只持久化结构化输入。
- 不实现公众号 analytics 文件导入。
- 不自动修改 topic priority、删除 topic 或批量改 topic 状态。
- 不实现通用 agent policy engine。`learning_candidates` 只作为未来自进化底座的兼容层。
- 不内联保存完整草稿、正文或大块 artifact 内容；只保存 compact refs。

---

## User Scenarios & Testing

### User Story 1 - 保存和查询单篇 topic performance (Priority: P1)

作为 wechat-agent，我需要把单篇文章相对账号 baseline 的表现分保存到 hermes-db，以便后续报告和建议能引用稳定事实源。

**Acceptance Scenarios**:

1. **[US1-1] 幂等 upsert performance**  
   **Given** agents 提交同一 `account + article_id + window_label + scoring_version`  
   **When** 调用 `upsert_topic_performance`  
   **Then** MCP 返回同一唯一记录语义，更新分数/诊断/证据字段，不创建重复 performance。

2. **[US1-2] 按条件查询 performance**  
   **Given** DB 中已有多账号、多窗口、多评分版本记录  
   **When** 调用 `list_topic_performance` 传入 account、article_id、topic_id、window_label、date range、limit/offset  
   **Then** 只返回匹配记录，并按稳定时间顺序分页。

**Edge Cases**:

- 缺少必填字段返回 validation error。
- `normalized_score` 不在 0-100 或 `confidence` 不在 0-1 时拒绝。
- `metric_snapshot_ids` 为空应拒绝，除非后续明确支持无 metrics 的人工记录。

### User Story 2 - 保存和查询 retrospective reports (Priority: P1)

作为运营者和 agents CLI，我需要保存单篇/周期复盘报告，并能按账号、日期、报告类型查询。

**Acceptance Scenarios**:

1. **[US2-1] 创建 report**  
   **Given** agents 生成 article/weekly/monthly/custom_period report  
   **When** 调用 `create_wechat_retrospective_report`  
   **Then** DB 保存 report，返回 `report_id`、summary、performance_ids、evidence refs、status、updated_at。

2. **[US2-2] 查询 report 列表**  
   **Given** 已存在多个 report  
   **When** 调用 `list_wechat_retrospective_reports` 传入 account、report_type、article_id、date range、limit/offset  
   **Then** 返回匹配 `{ items, total, limit, offset }`。

3. **[US2-3] 获取单个 report**  
   **Given** 已知 `report_id`  
   **When** 调用 `get_wechat_retrospective_report`  
   **Then** 返回完整 report；不存在时返回 not_found。

**Edge Cases**:

- article report 必须有 `article_id`。
- period report 必须有 `period_start` 和 `period_end`，且 `period_start <= period_end`。
- `performance_ids` 可为空只允许在 failed/draft report；completed report 应至少关联一个 performance。

### User Story 3 - 生成、审核和查询 topic optimization suggestions (Priority: P1)

作为运营者，我需要让复盘建议进入人工审核，只有 approved/applied 的建议才被后续 topic radar 和 `pickNext` 消费。

**Acceptance Scenarios**:

1. **[US3-1] 批量创建 suggestions**  
   **Given** agents 从 report 生成 revisit/cooldown/ranking_hint/priority_adjust 建议  
   **When** 调用 `create_topic_optimization_suggestions`  
   **Then** DB 批量保存 suggestions，默认 `review_status=pending`。

2. **[US3-2] 查询 suggestions**  
   **Given** DB 中存在不同 status/type/target 的 suggestions  
   **When** 调用 `list_topic_optimization_suggestions`  
   **Then** 可按 account、report_id、review_status、suggestion_type、target_kind、target_id、target_key 分页查询。

3. **[US3-3] 审核 suggestion**  
   **Given** suggestion 为 pending/approved/applied/expired  
   **When** 调用 `review_topic_optimization_suggestion` 设置 approved/rejected/expired  
   **Then** DB 写入 `review_status`、`reviewed_by`、`reviewed_at`、`review_note`，非法状态流转返回 validation error。

4. **[US3-4] approved ranking hints 查询**  
   **Given** 存在 pending、approved、applied、rejected、expired suggestions  
   **When** 调用 `list_approved_topic_ranking_hints`  
   **Then** 只返回 account scope 匹配、review_status in (`approved`, `applied`)、未过期的 suggestions。

**Edge Cases**:

- `target_kind=topic` 时应允许 `target_id` 指向 topics.id。
- `target_kind` 为 mother_theme/column/title_pattern/account 时至少要有 `target_key` 或明确 account-level target。
- `expires_at <= now` 的 approved suggestion 不应出现在 approved ranking hints。
- rejected/expired suggestion 不得被 ranking hint 查询返回。

### User Story 4 - 保存和审核 learning candidates (Priority: P2)

作为 agent 自进化链路，我需要将稳定复盘结论保存为可审查的 learning candidates，供未来 policy engine 使用。

**Acceptance Scenarios**:

1. **[US4-1] 批量创建 learning candidates**  
   **Given** agents 从 approved suggestions 生成 candidates  
   **When** 调用 `create_learning_candidates`  
   **Then** DB 保存 candidate，默认 `status=pending_review`。

2. **[US4-2] 查询 learning candidates**  
   **Given** 存在不同 domain/status/type 的 candidates  
   **When** 调用 `list_learning_candidates`  
   **Then** 可按 account、domain、source_report_id、status、candidate_type 分页查询。

3. **[US4-3] 审核 learning candidate**  
   **Given** candidate 存在  
   **When** 调用 `review_learning_candidate` 设置 approved/rejected/disabled，并可选 `policy_id`  
   **Then** DB 写入 review fields；非法状态流转返回 validation error。

**Edge Cases**:

- candidate 必须带 `scope_json`、`trigger_conditions_json`、`proposed_policy_json`、`evidence_refs_json`。
- `confidence` 不在 0-1 时拒绝。
- `source_suggestion_ids` 可为空但建议保留；若提供，应保存为 JSON array。

### User Story 5 - Health capability 和 schema drift gate (Priority: P1)

作为 agents production factory，我需要在运行前知道 retrospective schema 是否真的可用。

**Acceptance Scenarios**:

1. **[US5-1] capability false by default**  
   **Given** migration 未执行或 schema 不完整  
   **When** 调用 health MCP tool  
   **Then** `capabilities.wechat_retrospective_topic_optimizer=false`。

2. **[US5-2] capability true only when complete**  
   **Given** migration 已执行且关键 tables/columns/checks/indexes/tools 可用  
   **When** 调用 health MCP tool  
   **Then** `capabilities.wechat_retrospective_topic_optimizer=true`。

3. **[US5-3] schema drift fail closed**  
   **Given** DB 缺少任一关键字段、约束或 index  
   **When** 调用 health 或 retrospective tools  
   **Then** health false 或 tool 返回结构化 schema/validation error，不返回半结构化成功数据。

---

## Functional Requirements

- **FR-001**: MCP 必须新增 `topic_performance` 持久化实体，支持 upsert/list。
- **FR-002**: MCP 必须新增 `wechat_retrospective_reports` 持久化实体，支持 create/get/list。
- **FR-003**: MCP 必须新增 `topic_optimization_suggestions` 持久化实体，支持 create/list/review。
- **FR-004**: MCP 必须新增 `learning_candidates` 持久化实体，支持 create/list/review。
- **FR-005**: MCP 必须提供 `list_approved_topic_ranking_hints`，只返回 approved/applied 且未过期 suggestions。
- **FR-006**: 所有 list tools 必须支持 `limit`、`offset`，并返回 `{ items, total, limit, offset }`。
- **FR-007**: 所有 JSON 字段必须以 JSON/JSONB 保存，并在 MCP response 中还原为 object/array，不要求 agents 解析 `*_json` 字符串。
- **FR-008**: MCP response 必须兼容 agents adapter 当前解析逻辑：直接 object、`{ result }` wrapper、或 text JSON fallback 均可，但推荐结构化 object。
- **FR-009**: health tool 必须暴露 `capabilities.wechat_retrospective_topic_optimizer`。
- **FR-010**: schema inspector 必须检查 tables、required columns、check constraints、unique constraints、foreign keys、indexes。
- **FR-011**: validation error、not_found、invalid_transition、schema_drift 必须返回结构化 error payload。
- **FR-012**: 迁移必须可 downgrade，且 downgrade 不破坏既有 analytics/topic/publication ledger schema。

---

## Non-Functional Requirements

- **NFR-001 Consistency**: score/report/suggestion/candidate 保存后查询返回字段名和类型必须稳定，避免 agents adapter schema drift。
- **NFR-002 Safety**: MCP 不得自动修改 `topics.priority`、`topics.status` 或删除 topic；suggestions 只保存建议和 review 状态。
- **NFR-003 Explainability**: performance/report/suggestion/candidate 必须保留 compact `evidence_refs`。
- **NFR-004 Availability**: retrospective capability 不可用时不能影响已有 topic、analytics、publication ledger tools。
- **NFR-005 Idempotency**: `upsert_topic_performance` 必须按唯一键幂等；批量 create suggestions/candidates 至少应支持安全重试或清晰记录重复行为。
- **NFR-006 Time Semantics**: server-generated timestamps 使用 UTC；date range 查询边界必须明确包含开始和结束日期。

---

## Key Entities

### Entity: Topic Performance

**Table / Resource**: `topic_performance`  
**Purpose**: 单篇文章相对账号 baseline 的表现评分和诊断事实源。

Required fields:

- `performance_id`
- `account`
- `article_id`
- `topic_id`
- `stat_date`
- `window_label`
- `scoring_version`
- `baseline_version`
- `normalized_score`
- `read_score`
- `engagement_score`
- `share_score`
- `conversion_score`
- `confidence`
- `provisional`
- `low_sample_size`
- `metric_snapshot_ids_json`
- `baseline_snapshot_json`
- `diagnosis_json`
- `evidence_refs_json`
- `warnings_json`
- `created_at`
- `updated_at`

Uniqueness:

```text
unique(account, article_id, window_label, scoring_version)
```

Validation:

- `normalized_score` and component scores are 0-100 when present.
- `confidence` is 0-1.
- `metric_snapshot_ids_json` is an array.
- `baseline_snapshot_json`、`diagnosis_json`、`evidence_refs_json` are objects.

### Entity: Retrospective Report

**Table / Resource**: `wechat_retrospective_reports`  
**Purpose**: 账号级或单篇复盘报告，可查询、可审计、可作为建议生成输入。

Required fields:

- `report_id`
- `account`
- `report_type`: `article` | `weekly` | `monthly` | `custom_period`
- `period_start`
- `period_end`
- `article_id`
- `scoring_version`
- `generation_mode`: `structured_only` | `structured_plus_llm`
- `status`: `draft` | `completed` | `completed_with_warnings` | `failed`
- `sample_size`
- `low_sample_size`
- `performance_ids_json`
- `summary_json`
- `narrative_markdown`
- `high_performing_themes_json`
- `low_performing_themes_json`
- `title_patterns_json`
- `recommendations_json`
- `evidence_refs_json`
- `warnings_json`
- `created_at`
- `updated_at`

Indexes:

```text
index(account, period_start, period_end)
index(account, report_type, created_at)
index(article_id)
```

### Entity: Topic Optimization Suggestion

**Table / Resource**: `topic_optimization_suggestions`  
**Purpose**: 可审核的选题优化建议。审批前只展示，不影响生产链路。

Required fields:

- `suggestion_id`
- `account`
- `report_id`
- `suggestion_type`: `revisit` | `cooldown` | `priority_adjust` | `ranking_hint` | `seed_prompt_hint`
- `target_kind`: `topic` | `mother_theme` | `column` | `title_pattern` | `account`
- `target_id`
- `target_key`
- `current_value_json`
- `proposed_value_json`
- `rationale`
- `confidence`
- `evidence_refs_json`
- `review_status`: `pending` | `approved` | `rejected` | `expired` | `applied`
- `reviewed_by`
- `reviewed_at`
- `review_note`
- `applied_at`
- `application_trace_id`
- `expires_at`
- `created_at`
- `updated_at`

Indexes:

```text
index(account, review_status, target_kind)
index(account, target_kind, target_key)
index(account, target_kind, target_id)
index(report_id)
index(expires_at)
```

Consumption rule:

```text
topic radar / pickNext may only consume review_status in ("approved", "applied")
```

### Entity: Learning Candidate

**Table / Resource**: `learning_candidates`  
**Purpose**: 公众号复盘沉淀出的待确认策略，兼容未来 `agent-self-evolution-foundation`。

Required fields:

- `candidate_id`
- `account`
- `domain`
- `source_report_id`
- `source_suggestion_ids_json`
- `candidate_type`: `topic_strategy` | `title_strategy` | `column_strategy` | `writing_constraint` | `review_gate`
- `scope_json`
- `trigger_conditions_json`
- `proposed_policy_json`
- `confidence`
- `evidence_refs_json`
- `status`: `pending_review` | `approved` | `rejected` | `exported_to_policy` | `disabled`
- `policy_id`
- `reviewed_by`
- `reviewed_at`
- `review_note`
- `created_at`
- `updated_at`

Indexes:

```text
index(account, status, candidate_type)
index(source_report_id)
index(domain)
```

---

## MCP Tool Contract

### `upsert_topic_performance(input) -> TopicPerformance`

Input:

```json
{
  "account": "qiaomu",
  "article_id": "article-1",
  "topic_id": "topic-1",
  "stat_date": "2026-06-07",
  "window_label": "D+7",
  "scoring_version": "wechat-retro-v1",
  "baseline_version": "account-rolling-v1",
  "normalized_score": 86.4,
  "read_score": 90,
  "engagement_score": 80,
  "share_score": 88,
  "conversion_score": 70,
  "confidence": 0.82,
  "provisional": false,
  "low_sample_size": false,
  "metric_snapshot_ids": ["snapshot-1"],
  "baseline_snapshot": {},
  "diagnosis": {},
  "evidence_refs": {},
  "warnings": []
}
```

### `list_topic_performance(input) -> { items, total, limit, offset }`

Supported filters:

- `account`
- `article_id`
- `topic_id`
- `window_label`
- `scoring_version`
- `date_from`
- `date_to`
- `limit`
- `offset`

### `create_wechat_retrospective_report(input) -> RetrospectiveReport`

Input includes the report fields listed above. Server generates `report_id`、`created_at`、`updated_at`.

### `get_wechat_retrospective_report(report_id) -> RetrospectiveReport`

Missing record returns not_found.

### `list_wechat_retrospective_reports(input) -> { items, total, limit, offset }`

Supported filters:

- `account`
- `report_type`
- `article_id`
- `date_from`
- `date_to`
- `limit`
- `offset`

### `create_topic_optimization_suggestions(input) -> { items, total, limit, offset }`

Input:

```json
{
  "account": "qiaomu",
  "report_id": "report-1",
  "items": [
    {
      "account": "qiaomu",
      "report_id": "report-1",
      "suggestion_type": "cooldown",
      "target_kind": "mother_theme",
      "target_key": "food",
      "proposed_value": {
        "action": "cooldown",
        "ranking_weight_delta": -0.2,
        "source": "retrospective"
      },
      "rationale": "This theme underperformed the account baseline.",
      "confidence": 0.76,
      "evidence_refs": {},
      "review_status": "pending"
    }
  ]
}
```

### `list_topic_optimization_suggestions(input) -> { items, total, limit, offset }`

Supported filters:

- `account`
- `report_id`
- `review_status`
- `suggestion_type`
- `target_kind`
- `target_id`
- `target_key`
- `limit`
- `offset`

### `review_topic_optimization_suggestion(input) -> TopicOptimizationSuggestion`

Input:

```json
{
  "suggestion_id": "suggestion-1",
  "review_status": "approved",
  "reviewed_by": "operator",
  "review_note": "Looks supported by weekly report.",
  "application_trace_id": null
}
```

Allowed target statuses for this tool:

- `approved`
- `rejected`
- `expired`

The tool should not set `applied` directly unless plan stage explicitly decides to support application tracing in MCP. MVP may leave `applied` for future downstream trace writeback.

### `list_approved_topic_ranking_hints(input) -> { items, total, limit, offset }`

Supported filters:

- `account` required
- `target_kind`
- `target_id`
- `target_key`
- `limit`
- `offset`

Filter rule:

```text
account matches
AND review_status IN ('approved', 'applied')
AND (expires_at IS NULL OR expires_at > now())
AND optional target filters match
```

### `create_learning_candidates(input) -> { items, total, limit, offset }`

Input:

```json
{
  "account": "qiaomu",
  "source_report_id": "report-1",
  "items": [
    {
      "account": "qiaomu",
      "domain": "wechat",
      "source_report_id": "report-1",
      "source_suggestion_ids": ["suggestion-1"],
      "candidate_type": "topic_strategy",
      "scope": {},
      "trigger_conditions": {},
      "proposed_policy": {},
      "confidence": 0.78,
      "evidence_refs": {},
      "status": "pending_review"
    }
  ]
}
```

### `list_learning_candidates(input) -> { items, total, limit, offset }`

Supported filters:

- `account`
- `domain`
- `source_report_id`
- `status`
- `candidate_type`
- `limit`
- `offset`

### `review_learning_candidate(input) -> LearningCandidate`

Input:

```json
{
  "candidate_id": "candidate-1",
  "status": "approved",
  "reviewed_by": "operator",
  "review_note": "Approved for future policy export.",
  "policy_id": null
}
```

Allowed target statuses:

- `approved`
- `rejected`
- `disabled`

---

## Error Contract

All tools must return structured errors compatible with existing Hermes MCP patterns.

Expected error codes:

- `validation`
- `not_found`
- `invalid_transition`
- `schema_drift`
- `mcp_error`
- `transport`

Recommended payload shape:

```json
{
  "error": "validation",
  "message": "normalized_score must be between 0 and 100",
  "field": "normalized_score"
}
```

Validation failures must not write partial rows.

---

## Evidence Reference Shape

All retrospective entities should use compact evidence refs:

```json
{
  "articles": [
    {
      "article_id": "article-1",
      "topic_id": "topic-1",
      "title": "optional short title"
    }
  ],
  "metric_snapshots": ["snapshot-1"],
  "artifacts": [
    {
      "artifact_id": "artifact-1",
      "name": "transformed-draft"
    }
  ],
  "performances": ["performance-1"],
  "reports": ["report-1"]
}
```

Rules:

- Do not inline full draft content.
- Do include enough ids to replay the evidence chain.
- Missing evidence should be explicit in `warnings_json`.

---

## Health Capability Contract

Health response must include:

```json
{
  "capabilities": {
    "wechat_retrospective_topic_optimizer": true
  }
}
```

The capability may be true only if all are true:

- `topic_performance` table exists.
- `wechat_retrospective_reports` table exists.
- `topic_optimization_suggestions` table exists.
- `learning_candidates` table exists.
- Required columns exist with expected nullability and types.
- Required JSON columns exist.
- Required unique constraints and indexes exist.
- Required FK constraints exist where applicable.
- The active migration revision includes this feature's revision.

If partial schema is detected, capability must be false and tests should expose exact missing element.

---

## Data Integrity Rules

- `topic_performance.article_id` should reference `wechat_articles.article_id` if the current schema supports FK.
- `topic_performance.topic_id` should reference `topics.id` when non-null.
- `wechat_retrospective_reports.performance_ids_json` stores performance ids, not full embedded performance rows.
- `topic_optimization_suggestions.report_id` should reference `wechat_retrospective_reports.report_id`.
- `learning_candidates.source_report_id` should reference `wechat_retrospective_reports.report_id`.
- `source_suggestion_ids_json` stores ids and may be validated opportunistically, but lack of FK array support must not block MVP.
- JSON columns must default to empty object/array only when that is semantically valid; otherwise validation should require explicit input.

---

## Acceptance Evidence Required

Before closeout, the mcps-side agent must produce:

- Migration file path and revision id.
- DB migration SQL test evidence.
- Tool unit/integration tests for every MCP tool listed above.
- Health schema inspector tests for false/true/partial-schema cases.
- Local MCP smoke showing:
  - upsert topic performance
  - create report
  - create pending suggestion
  - approve suggestion
  - list approved topic ranking hints returns it
  - create/list/review learning candidate
- NAS or deployed MCP smoke showing:
  - health reports `wechat_retrospective_topic_optimizer=true`
  - agents-side live smoke can pass retrospective capability gate

---

## Out of Scope

- UI/dashboard.
- Automatic topic mutation.
- Full self-evolution policy application.
- LLM report generation inside MCP.
- Analytics import parsing.
- Large artifact content duplication.

---

## Open Questions

- Should `applied` status be writable by `review_topic_optimization_suggestion`, or reserved for a future explicit `mark_topic_optimization_suggestion_applied` trace tool?
- Should `create_topic_optimization_suggestions` enforce idempotency keys, or accept duplicate suggestions and rely on agents dedupe?
- Should JSON columns be PostgreSQL `JSONB` with GIN indexes for selected query fields, or plain JSONB without deep indexes for MVP?
- Should MCP expose `get_topic_performance(performance_id)` or is list by filters enough for agents MVP?

These are not blockers for writing plan/tasks. Recommended MVP decisions:

- Reserve `applied` for future trace tool; do not write it via review tool yet.
- Use idempotency only for `topic_performance`; suggestions/candidates can be append-only records.
- Use JSONB; add conventional relational indexes first, deep JSON indexes later only if query evidence appears.
- Skip `get_topic_performance` unless agents live smoke needs it.

---

## Stage Readiness

- Recommended next stage: `plan`
- Blocking dependency: none inside mcps repo if existing analytics/publication/topic migrations are present.
- Blocking downstream evidence: agents-side live smoke remains blocked until this MCP feature is implemented, deployed, and health capability returns true.
