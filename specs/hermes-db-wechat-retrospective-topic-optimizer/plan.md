# Implementation Plan: Hermes DB WeChat Retrospective Topic Optimizer

**Workspace**: `hermes-db-wechat-retrospective-topic-optimizer` | **Date**: 2026-06-07 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/hermes-db-wechat-retrospective-topic-optimizer/spec.md`

---

## Summary

Add the mcps/hermes-db upstream contract for the already implemented agents-side WeChat retrospective topic optimizer. The recommended design extends the existing hermes-db Alembic + contracts + repository + FastMCP tools + schema health pattern with four retrospective tables, typed MCP tools, review workflows, ranking-hint query support, and a schema-aware `wechat_retrospective_topic_optimizer` capability.

This plan keeps scoring, report composition, LLM narrative work, and topic-picking policy in the agents repository. `hermes-db` owns durable storage, validation, idempotent performance upsert, review-state persistence, query contracts, and readiness signals.

---

## Architecture Overview

The feature fits the current hermes-db layered architecture:

```text
agents retrospective services / CLI / production adapter
        |
        v
MCP tools: wechat_retrospective.py
        |
        v
contracts.py validators and structured errors
        |
        v
repositories/wechat_retrospective_repo.py
        |
        v
PostgreSQL hermes.topic_performance
PostgreSQL hermes.wechat_retrospective_reports
PostgreSQL hermes.topic_optimization_suggestions
PostgreSQL hermes.learning_candidates

health.py -> services/schema.py -> capabilities.wechat_retrospective_topic_optimizer
```

Write flow:

1. Agents calculates retrospective input, scoring, report body, suggestions, and learning candidates.
2. MCP tools validate normalized payloads and map caller strings to UUID/date/datetime values.
3. Repository functions write PostgreSQL rows using one transaction per batch-style create/review operation where consistency requires it.
4. Tools serialize UUID/date/datetime/JSONB values back into plain JSON-compatible objects.

Read flow:

1. List tools validate bounded filters and pagination.
2. Repository functions return `items`, `total`, `limit`, and `offset`.
3. `list_approved_topic_ranking_hints` only exposes approved/applied, unexpired suggestions for downstream ranking.

Health flow:

1. `health()` initializes `capabilities.wechat_retrospective_topic_optimizer=false`.
2. If PostgreSQL is reachable, `inspect_wechat_retrospective_topic_optimizer_schema()` checks required tables, columns, constraints, FKs, and indexes.
3. The capability becomes true only when the full schema contract is present.

---

## Architecture Reference

| 参考模式 / 模板 | 来源 URL | 适配点 | 不适配点 | 当前阶段 |
|-----------------|----------|--------|----------|----------|
| Layered architecture | https://github.com/study8677/awesome-architecture/blob/main/tutorial/04-%E5%8D%81%E5%A4%A7%E6%A0%B8%E5%BF%83%E6%9E%B6%E6%9E%84%E6%A8%A1%E5%BC%8F.md | 当前 hermes-db 已按 tools / contracts / repositories / services / migrations 分层，本 feature 应沿用 | 不引入独立 retrospective service、队列、事件流或 OLAP store | MVP |
| Durable review ledger | UNVERIFIED | suggestions 和 learning candidates 是人审状态记录，需要可追溯持久化 | 不实现完整 policy engine、自动应用策略或审计后台 | MVP |

跳过候选方案讨论：当前 spec 已被 agents 侧 adapter/service/CLI 形状和本仓 hermes-db 既有实现模式强约束。只有一个合理方向，即在现有 Python MCP 服务内增量添加 migration、repository、tools、contracts 和 schema health capability。主要权衡不在架构方向，而在 schema 粒度、幂等范围、review 状态语义和 JSONB 索引策略；这些在 ADR 中记录。

---

## Producer-Consumer Matrix

| Producer | Artifact / Record | Consumer | Consumption Proof |
|---|---|---|---|
| agents retrospective input loader/scorer | `TopicPerformance` payload | `upsert_topic_performance` | repeated call with same `(account, article_id, window_label, scoring_version)` returns one updated performance row |
| hermes-db analytics ingestion | `wechat_article_metric_snapshots.snapshot_id` refs | agents scorer and retrospective evidence | `topic_performance.metric_snapshot_ids_json` stores compact ids and list query returns them as arrays |
| hermes-db publication ledger | `wechat_articles.article_id` and optional `topic_id` | topic performance and report tables | FK-backed write succeeds for existing article and returns `not_found` on missing FK |
| hermes-db retrospective persistence | `wechat_retrospective_reports` | suggestion generator and operators | create/get/list report tools return stable report ids and period filters |
| agents suggestion service | `TopicOptimizationSuggestion` payloads | operator review CLI and topic radar/pickNext | create/list/review tools persist state; approved ranking hints query returns only approved/applied unexpired rows |
| agents learning candidate service | `LearningCandidate` payloads | future policy export / self-evolution foundation | create/list/review tools preserve source report and suggestion ids without auto-applying policy |
| hermes-db schema inspector | `capabilities.wechat_retrospective_topic_optimizer` | agents production factory/live smoke | health reports false for missing/partial schema and true after complete migration |

**孤儿 artifact 处理**: No orphan artifact is accepted. Learning candidates are a deliberate compatibility layer for future policy export, but MVP still includes create/list/review tools so candidates are queryable and auditable. `applied` suggestion status is reserved for future trace writeback and is not produced by the MVP review tool.

---

## Quality Attribute Targets

| 属性 | 目标 | 设计影响 | 验证方式 |
|------|------|----------|----------|
| 一致性 | Retrospective rows reference existing articles/reports where applicable | Use FK constraints for article/report/suggestion links and structured DB error mapping | repo/tool tests for FK failures and `not_found` errors |
| 幂等性 | Performance upsert is safe to retry | Unique key on `(account, article_id, window_label, scoring_version)` and `ON CONFLICT DO UPDATE` | repo tests repeat upsert and assert one row |
| 安全性 | Review suggestions never mutate `topics` automatically | No repository path updates topic priority/status; ranking hints are read-only suggestions | tests assert review tool only updates suggestion row |
| 可诊断性 | Evidence chain can be replayed without large content blobs | JSONB compact `evidence_refs` and id arrays; warnings remain explicit | tool tests assert JSON fields round-trip as objects/arrays |
| 可用性 | Missing retrospective schema must not break existing tools | Additive migration, isolated tool module, health fail-closed capability | existing topic/article/analytics regression tests plus health false/true cases |
| 查询性能 | Common account/date/status/report filters are bounded and index-backed | relational indexes for account/date/status/target/report; no deep JSON indexes in MVP | migration SQL tests and repository SQL inspection |
| 可演进性 | Future policy application can be added without breaking current adapter | Keep `applied`, `application_trace_id`, `exported_to_policy`, and `policy_id` fields, but do not auto-write them in MVP | data-model review and future tool extension path |

---

## Capacity / Scale Notes

- **规模假设**: MVP supports manual or scheduled retrospective writes for hundreds to low thousands of articles per account per month.
- **读写特征**: Write volume is low and batch-like after analytics snapshots are collected; reads are filtered by account, article, report, review status, target, and date.
- **失败代价**: Wrong review state can affect topic ranking; duplicate performance rows can distort reports; missing capability blocks agents live smoke but must not block unrelated MCP tools.
- **Retention**: No deletion or archival policy in MVP. Retrospective reports and review rows are audit records.

---

## Lightweight ADR

| 决策 | 背景 | 候选 | 结论 | 代价 | 来源 |
|------|------|------|------|------|------|
| ADR-001: Implementation shape | Need unblock agents live smoke inside existing mcps repo | A. extend hermes-db service; B. build sidecar MCP; C. persist in agents repo | A | More code in hermes-db, but follows existing deployment and health model | Local repo pattern |
| ADR-002: Performance idempotency | Scoring can be retried for same article/window/version | A. always insert; B. upsert by account/article/window/scoring_version; C. upsert by metric snapshot ids | B | Baseline changes require explicit `scoring_version` or overwrite same identity | Spec FR-001 |
| ADR-003: Suggestions/candidates idempotency | Batch create can be retried, but suggestions are human-review records | A. unique idempotency key; B. append-only generated ids; C. dedupe by JSON payload | B for MVP | Caller may create duplicates; operators/agents must dedupe if needed | Spec recommended MVP decision |
| ADR-004: JSONB indexing | Many payload fields are explanatory and not query filters | A. GIN indexes on JSONB; B. relational indexes only; C. plain TEXT JSON | B | Deep JSON search may need future migration | Spec recommended MVP decision |
| ADR-005: Suggestion applied status | `applied` needs trace of downstream policy/ranking application | A. review tool can set applied; B. reserve for future mark-applied tool; C. remove field | B | MVP cannot record final application from review flow | Spec recommended MVP decision |
| ADR-006: List response shape | agents adapter expects stable pagination | A. return only items; B. return items/total/limit/offset; C. stream cursor | B | Repository needs count queries | Spec FR-006 |
| ADR-007: Health gate | agents production factory fails closed on capability | A. revision check only; B. schema inspector checks columns/constraints/indexes; C. runtime tool errors | B | More schema tests to maintain | Existing `services/schema.py` pattern |

---

## Key Design Decisions

### Decision 1: Add one retrospective tool module and one repository module

- **背景**: Existing hermes-db features keep MCP input/error/serialization logic in tools and SQL in repositories.
- **选项**:
  - A: Add `tools/wechat_retrospective.py` and `repositories/wechat_retrospective_repo.py`.
  - B: Put SQL directly in tools.
  - C: Extend analytics/article repositories with retrospective SQL.
- **结论**: Choose A.
- **影响**: Tests can separately cover SQL generation/repository behavior and MCP contract mapping. Server registration adds one import in `server.py`.
- **来源**: Local repo pattern in `tools/wechat_analytics.py` and `repositories/wechat_analytics_repo.py`.

### Decision 2: Store explanatory structures as JSONB but query on relational columns

- **背景**: Reports, diagnosis, proposed values, evidence refs, warnings, and policy candidates are heterogeneous and mostly returned, not filtered deeply.
- **选项**:
  - A: Normalize every nested field into relational child tables.
  - B: Use JSONB for nested objects/arrays and relational columns for filters/statuses.
  - C: Store JSON strings in TEXT fields.
- **结论**: Choose B.
- **影响**: MVP schema remains compact and adapter-compatible. Future deep analytics may add JSONB GIN indexes or child tables only with query evidence.
- **来源**: Spec FR-007 and current analytics `raw_json` pattern.

### Decision 3: Make review tools explicit state-transition gates

- **背景**: Approved suggestions affect topic ranking hints; learning candidates can feed future policy export.
- **选项**:
  - A: Let create tools set any status.
  - B: Create pending rows, then review tools move to allowed target statuses.
  - C: Allow direct DB updates from agents.
- **结论**: Choose B.
- **影响**: Validation must reject unsupported transitions. `review_topic_optimization_suggestion` supports `approved`, `rejected`, and `expired`; `applied` remains future. `review_learning_candidate` supports `approved`, `rejected`, and `disabled`.
- **来源**: Spec tool contract.

### Decision 4: Count queries are part of every list repository method

- **背景**: Spec requires `{ items, total, limit, offset }`, while some older hermes-db list tools only return items/limit/offset.
- **选项**:
  - A: Follow older list shape.
  - B: Implement count queries for retrospective list tools.
  - C: Return `total=null`.
- **结论**: Choose B.
- **影响**: Each list method should share filter construction between item query and count query to avoid drift.
- **来源**: Spec FR-006.

### Decision 5: Capability stays false on any partial retrospective schema

- **背景**: Downstream live smoke should not proceed against partial tables or missing constraints.
- **选项**:
  - A: true if tables exist.
  - B: true only if required tables, columns, constraints, FKs, and indexes exist.
  - C: true if migration revision string is latest.
- **结论**: Choose B, optionally also exposing revision in existing `schema_revision`.
- **影响**: Schema inspector tests must include complete, missing table, missing column, missing constraint, and missing index cases.
- **来源**: Existing schema-aware health pattern.

---

## Module Design

### Module: Alembic Migration

**职责**: Add retrospective persistence tables, constraints, and indexes under `hermes` schema.

**改动概述**:

- Add `packages/hermes-db/migrations/versions/0005_wechat_retrospective_topic_optimizer.py`.
- Set `down_revision = "0004_wechat_analytics_ingestion"`.
- Create:
  - `hermes.topic_performance`
  - `hermes.wechat_retrospective_reports`
  - `hermes.topic_optimization_suggestions`
  - `hermes.learning_candidates`

**关键接口 / 行为**:

```text
upgrade:
  create topic_performance with score/confidence checks and unique performance identity
  create wechat_retrospective_reports with report/status/type checks
  create topic_optimization_suggestions with review status/type/target checks
  create learning_candidates with candidate status/type checks
  add FKs to wechat_articles, topics, reports where applicable
  add relational indexes for account/date/status/report/target filters

downgrade:
  drop learning_candidates
  drop topic_optimization_suggestions
  drop wechat_retrospective_reports
  drop topic_performance
```

**注意事项**:

- Migration is additive and must not alter existing analytics, publication ledger, workflow, or topic schemas.
- Use repository-generated UUIDs to match current project style.
- Use `TIMESTAMPTZ NOT NULL DEFAULT now()` for timestamps.

### Module: Data Contracts and Validation

**职责**: Centralize retrospective constants, pagination limits, status sets, score/range validators, UUID/date parsing helpers, and structured error payloads.

**改动概述**:

- Extend `contracts.py` with:
  - retrospective limit constants
  - report types and statuses
  - suggestion types, target kinds, review statuses
  - learning candidate types and statuses
  - score/confidence/date/UUID validation helpers
  - input validation for all MCP tools

**关键接口 / 行为**:

```text
validate_topic_performance_payload(...)
validate_topic_performance_query(...)
validate_retrospective_report_payload(...)
validate_retrospective_report_query(...)
validate_topic_suggestions_payload(...)
validate_suggestion_review(...)
validate_approved_ranking_hint_query(...)
validate_learning_candidates_payload(...)
validate_learning_candidate_review(...)
```

**注意事项**:

- Validation failures return structured `error("validation", ...)` and must not write rows.
- JSON-like inputs must remain objects/arrays in responses, not serialized strings.
- Empty string IDs should be rejected rather than treated as NULL unless the field is explicitly optional.

### Module: Retrospective Repository

**职责**: Encapsulate all SQL for retrospective writes, reads, counts, and state updates.

**改动概述**:

- Add `packages/hermes-db/src/hermes_db_mcp/repositories/wechat_retrospective_repo.py`.
- Provide one function per MCP tool, plus shared filter builders where useful.

**关键接口 / 行为**:

```text
upsert_topic_performance(pool, record) -> dict
list_topic_performance(pool, filters) -> {items, total}

create_wechat_retrospective_report(pool, record) -> dict
get_wechat_retrospective_report(pool, report_id) -> dict | None
list_wechat_retrospective_reports(pool, filters) -> {items, total}

create_topic_optimization_suggestions(pool, account, report_id, items) -> list[dict]
list_topic_optimization_suggestions(pool, filters) -> {items, total}
review_topic_optimization_suggestion(pool, suggestion_id, review) -> dict | None
list_approved_topic_ranking_hints(pool, filters) -> {items, total}

create_learning_candidates(pool, account, source_report_id, items) -> list[dict]
list_learning_candidates(pool, filters) -> {items, total}
review_learning_candidate(pool, candidate_id, review) -> dict | None
```

**注意事项**:

- Use `json.dumps(..., ensure_ascii=False)` for JSONB params, consistent with analytics repo.
- Batch create operations should run in a transaction and return the created rows.
- Review updates must update `reviewed_at=now()` and `updated_at=now()`.

### Module: Retrospective MCP Tools

**职责**: Expose the public MCP contract consumed by agents.

**改动概述**:

- Add `packages/hermes-db/src/hermes_db_mcp/tools/wechat_retrospective.py`.
- Register it in `server.py`.
- Add `ToolAnnotations`:
  - read-only for list/get/ranking-hint tools
  - idempotent write for `upsert_topic_performance`
  - non-destructive non-idempotent write for create/review tools

**关键接口 / 行为**:

```text
upsert_topic_performance(...)
list_topic_performance(...)
create_wechat_retrospective_report(...)
get_wechat_retrospective_report(...)
list_wechat_retrospective_reports(...)
create_topic_optimization_suggestions(...)
list_topic_optimization_suggestions(...)
review_topic_optimization_suggestion(...)
list_approved_topic_ranking_hints(...)
create_learning_candidates(...)
list_learning_candidates(...)
review_learning_candidate(...)
```

**注意事项**:

- Map `asyncpg.ForeignKeyViolationError` to `not_found`.
- Map undefined table/column errors to `schema_drift`.
- Map unsupported status transitions to `invalid_transition`.
- Serialize UUID/date/datetime recursively before returning responses.

### Module: Health Schema Inspector

**职责**: Make the retrospective capability schema-aware and fail-closed.

**改动概述**:

- Add `inspect_wechat_retrospective_topic_optimizer_schema(pool)` in `services/schema.py`.
- Import and merge its result in `tools/health.py`.
- Add default capability key with false value.

**关键接口 / 行为**:

```text
health().capabilities.wechat_retrospective_topic_optimizer == true
only when required tables, columns, constraints, FKs, and indexes exist
```

**注意事项**:

- Inspector should mirror the existing publication/analytics style.
- Partial schema must be false even if tools are registered.

### Module: Tests and Smoke

**职责**: Prove migration SQL, repository behavior, MCP contract, schema health, regressions, and live-smoke readiness.

**改动概述**:

- Extend `test_migration_sql.py`.
- Add focused tests:
  - `test_wechat_retrospective_contracts.py`
  - `test_wechat_retrospective_repo_sql.py`
  - `test_wechat_retrospective_tools.py`
  - `test_wechat_retrospective_schema_health.py`
  - optional integration tests if `DATABASE_URL` is present
- Extend `test_health.py` expected capability map.

**关键接口 / 行为**:

```text
rtk uv run pytest tests/test_migration_sql.py tests/test_wechat_retrospective_schema_health.py -q
rtk uv run pytest tests/test_wechat_retrospective_contracts.py tests/test_wechat_retrospective_repo_sql.py tests/test_wechat_retrospective_tools.py -q
rtk uv run pytest tests/test_health.py tests/test_wechat_analytics_tools.py tests/test_wechat_article_tools.py -q
rtk uv run ruff check .
```

**注意事项**:

- Integration tests should skip cleanly without `DATABASE_URL`, matching current repo behavior.
- Live smoke remains a later acceptance evidence step after implementation/deployment.

---

## Data Model

Detailed schema is in [data-model.md](data-model.md).

Core model:

- `topic_performance`: one idempotent score row per article/window/scoring version.
- `wechat_retrospective_reports`: durable report records for article/period retrospectives.
- `topic_optimization_suggestions`: reviewable suggestions and ranking hints.
- `learning_candidates`: reviewable strategy/policy candidates for future export.

---

## Project Structure

```text
packages/hermes-db/
  migrations/versions/
    0005_wechat_retrospective_topic_optimizer.py
  src/hermes_db_mcp/
    contracts.py
    repositories/
      __init__.py
      wechat_retrospective_repo.py
    services/
      schema.py
    tools/
      __init__.py
      health.py
      wechat_retrospective.py
    server.py
  tests/
    test_health.py
    test_migration_sql.py
    test_wechat_retrospective_contracts.py
    test_wechat_retrospective_repo_sql.py
    test_wechat_retrospective_schema_health.py
    test_wechat_retrospective_tools.py
    test_wechat_retrospective_integration.py

specs/hermes-db-wechat-retrospective-topic-optimizer/
  spec.md
  plan.md
  data-model.md
  tasks.md
  acceptance.md
```

---

## Risks and Tradeoffs

- Duplicate suggestions/candidates are possible in MVP because only topic performance is idempotent. This keeps review records append-only but requires caller/operator dedupe discipline.
- JSONB without deep indexes is adequate for MVP query patterns, but future reporting over nested evidence or policy fields may need new indexes or normalized child tables.
- Count queries add SQL complexity to list methods. Shared filter construction should avoid item/count drift.
- FK constraints improve correctness but make order-of-operations visible: article/report rows must exist before dependent retrospective rows.
- `applied` and `exported_to_policy` are modeled but not fully operated by MVP tools; future trace/export tools must own those transitions.

---

## Evolution Path

- **MVP**: PostgreSQL persistence, MCP tools, schema health, local smoke, and deployed capability gate for agents live smoke.
- **成长期**: Add explicit `mark_topic_optimization_suggestion_applied`, idempotency keys for batch suggestions/candidates, deeper report search, and optional JSONB indexes when query evidence exists.
- **成熟期**: Introduce policy export/application workflows, richer audit history, dashboard/read models, or async eventing only if retrospective volume and operational needs justify it.

---

## Anti-Pattern Check

- 是否把成熟期架构套到了 MVP：否。No queue, sidecar service, dashboard, event bus, OLAP store, or policy engine is introduced.
- 是否引用了外部模式但没有适配检查：否。Layered architecture is only used as a local repo-aligned reference.
- 是否新增未记录的状态、依赖、缓存、队列或失败模式：否。New states are documented in spec/data-model; no cache/queue/external service is added.
- 是否让 MCP 自动改 topic：否。Suggestions are persisted and reviewed; downstream ranking consumption is read-only.

---

## Verification Strategy

1. **Migration SQL**: Assert revision id, down revision, table DDL, required constraints, FKs, indexes, and downgrade drops.
2. **Contracts**: Validate score/confidence bounds, enum sets, pagination limits, JSON object/array requirements, and invalid transitions.
3. **Repository SQL**: Fake-connection tests for upsert identity, list filters/counts, batch create transactions, review updates, and ranking-hint filters.
4. **MCP tools**: Tool-level tests for success responses, serialization, validation errors, not_found mapping, schema_drift mapping, and conflict/invalid transition behavior.
5. **Schema health**: Complete schema returns true; missing table/column/constraint/index/FK returns false; PostgreSQL unavailable keeps every schema capability false.
6. **Regression**: Existing topic, workflow, publication ledger, and analytics tests still pass.
7. **Local smoke**: Using a local migrated DB, prove performance upsert -> report create/get/list -> suggestion create/review -> approved ranking hint list -> learning candidate create/review/list.
8. **Deployed smoke**: After deployment, health reports `wechat_retrospective_topic_optimizer=true` and agents-side live smoke passes the retrospective capability gate.

---

## Stage Readiness

- 是否需要 `data-model.md`: 需要。This feature adds four persisted entities, review statuses, FKs, uniqueness rules, and schema health checks.
- 下一步建议：`tasks`
- 阻塞项：无。The open questions in `spec.md` have MVP decisions reflected in this plan.

---

## Design Artifacts

| 产物 | 是否需要 | 说明 |
|------|---------|------|
| plan.md | 必须 | 当前文件，定义实现方案 |
| data-model.md | 需要 | 新增表、状态、关系和迁移约束 |
| tasks.md | 后续阶段生成 | 由 `tasks` 阶段拆分执行项 |
| acceptance.md | 后续阶段生成 | 用于最终验收结论 |

---

## Notes

- The plan intentionally mirrors the agents-side contract but keeps mcps/hermes-db as upstream truth for storage and MCP tool semantics.
- If implementation discovers an agents adapter mismatch, update the mcps spec/plan first, then adjust agents adapter only as downstream compatibility work.
- `specs/.active` already points to `hermes-db-wechat-retrospective-topic-optimizer`.

---

## Sources

| 决策 | 来源 URL | 备注 |
|------|---------|------|
| Layered implementation shape | Local: `packages/hermes-db/src/hermes_db_mcp/tools/wechat_analytics.py`, `repositories/wechat_analytics_repo.py`, `services/schema.py` | Existing repo pattern |
| Architecture quality gate | https://github.com/study8677/awesome-architecture/blob/main/tutorial/04-%E5%8D%81%E5%A4%A7%E6%A0%B8%E5%BF%83%E6%9E%B6%E6%9E%84%E6%A8%A1%E5%BC%8F.md | Skill-provided reference |
| Retrospective MCP contract | Local: `specs/hermes-db-wechat-retrospective-topic-optimizer/spec.md` | Upstream feature specification |
| JSONB relational-index MVP choice | UNVERIFIED | Local design judgment based on current query filters |
