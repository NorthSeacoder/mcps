# Implementation Plan: hermes-db WeChat Artifact Persistence

**Workspace**: `hermes-db-wechat-artifact-persistence` | **Date**: 2026-06-03 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/hermes-db-wechat-artifact-persistence/spec.md`

---

## Summary

Add workflow run and artifact persistence to `packages/hermes-db` by extending the existing Alembic + repository + MCP tools pattern. The recommended MVP stores text artifacts directly up to a fixed threshold, stores external references as metadata-backed `content_ref`, and exposes run/artifact tools with idempotent write semantics and summary-first reads.

This plan intentionally keeps orchestration in the downstream `agents` repository. `hermes-db` owns durable storage, validation, query contracts, health capabilities, and diagnostics only.

---

## Architecture Overview

The change fits the current hermes-db layered design:

```text
wechat-agent / other MCP clients
        |
        v
MCP tools: workflow_runs.py, workflow_artifacts.py
        |
        v
contracts.py validators and structured errors
        |
        v
repositories/workflow_repo.py
        |
        v
PostgreSQL hermes.wechat_workflow_runs
PostgreSQL hermes.workflow_artifacts

health.py -> services/schema.py -> capability flags
```

Write flow:

1. `upsert_workflow_run` validates the run identity and lifecycle fields, then creates or updates `hermes.wechat_workflow_runs` by `run_id`.
2. `finish_workflow_run` updates the existing run completion fields by `run_id`; missing run returns structured `not_found`.
3. `upsert_workflow_artifact` validates content policy, resolves version/idempotency, writes `hermes.workflow_artifacts`, and returns the persisted summary.

Read flow:

1. `list_workflow_artifacts` requires at least one filter or an explicit bounded limit and returns summaries only.
2. `get_workflow_artifact_content` returns `content_text` for inline artifacts. For `content_ref` artifacts, MVP returns the stored reference and metadata, not external file contents.

---

## Architecture Reference

| 参考模式 / 模板 | 来源 URL | 适配点 | 不适配点 | 当前阶段 |
|-----------------|----------|--------|----------|----------|
| Layered architecture | https://github.com/study8677/awesome-architecture/blob/main/tutorial/04-%E5%8D%81%E5%A4%A7%E6%A0%B8%E5%BF%83%E6%9E%B6%E6%9E%84%E6%A8%A1%E5%BC%8F.md | 当前代码已按 tools / services / repositories 分层，新增能力应沿用 | 不引入额外 service mesh、queue 或 event bus | MVP |
| Artifact registry / audit log style storage | UNVERIFIED | run 和 artifact 需要可追溯、可查询、可复盘 | 不把 hermes-db 扩展成通用对象存储或 workflow engine | MVP |

跳过候选方案讨论：用户已批准继续，且在当前代码现实下只有一个合理主方向，即沿用现有 hermes-db 分层和 PostgreSQL 持久化模式。架构选择的可变部分在 ADR 中记录。

---

## Producer-Consumer Matrix

| Producer | Artifact | Consumer | Consumption Proof |
|---|---|---|---|
| `wechat-agent` workflow start | `wechat_workflow_runs` row | `wechat-agent` retry/finish path, retrospective queries | Repeated `upsert_workflow_run(run_id=...)` updates one row; `finish_workflow_run` updates the same row |
| `wechat-agent` draft stage | `draft` artifact | human editor, transformed-draft stage, retrospective agent | `list_workflow_artifacts(run_id)` returns draft summary; `get_workflow_artifact_content(artifact_id)` returns Markdown |
| `wechat-agent` transform stage | `transformed-draft` artifact | publish/review stage, retrospective agent | Artifact has `parent_artifact_id` pointing to original draft and readable Markdown |
| `wechat-agent` review/validation/image prep stages | `review`, `validation`, `image-plan`, `image-manifest` summaries | downstream review, publish, and retrospective flows | Summary list returns type/name/stage/hash/metadata without content body |
| `wechat-agent` publish stage | `publish-result` artifact | publication ledger and analytics ingestion features | Query by `topic_id`, `account`, and date returns publish result summary |

**孤儿 artifact 处理**: No planned artifact is accepted as orphaned. Publication ledger, analytics ingestion, and retrospective optimization are downstream consumers, but this feature's own proof is limited to persistence and query availability.

---

## Quality Attribute Targets

| 属性 | 目标 | 设计影响 | 验证方式 |
|------|------|----------|----------|
| 持久性 | run/artifact survives process restart | Store in PostgreSQL tables under `hermes` schema | migration tests + repository integration tests |
| 幂等性 | client retries do not create unrelated duplicates | `run_id` primary key; artifact id/hash retry detection | repeated write unit/integration tests |
| 版本性 | same run/stage/name with changed content keeps history | artifact `version` per `(run_id, stage, name)` | version increment tests |
| 查询性能 | list returns summary rows only and uses indexes | indexes on run/topic/account/type/date; no `content_text` in list output | SQL tests and tool tests |
| 可诊断性 | validation, not found, schema drift are structured | reuse `ToolError` style and add workflow-specific error codes | tool tests for error payloads |
| 兼容性 | existing topic/inspiration tools unchanged | new modules registered additively; health capability merged | existing test suite remains passing |

---

## Capacity / Scale Notes

- **规模假设**: MVP handles hundreds to low thousands of workflow runs and artifacts per account per month.
- **读写特征**: write bursts during workflow execution; read queries are mostly retrospective and filtered by run/topic/account/date.
- **正文大小**: inline `content_text` maximum is 256 KiB for MVP. Larger text must use `content_ref`.
- **失败代价**: duplicate artifact versions are acceptable only when content changed; losing or overwriting a draft is not acceptable.

---

## Lightweight ADR

| 决策 | 背景 | 候选 | 结论 | 代价 | 来源 |
|------|------|------|------|------|------|
| ADR-001: Storage ownership | Need durable run/artifact persistence | A. PostgreSQL tables in hermes-db; B. external object store; C. downstream agents local files | A for MVP | Large bodies need `content_ref`; no object storage abstraction yet | Local code reality |
| ADR-002: Inline body threshold | MCP responses can become too large | A. no limit; B. 256 KiB inline limit; C. always use refs | B | Some large drafts require caller-side ref handling | UNVERIFIED |
| ADR-003: `content_ref` behavior | Spec allows content refs but no object storage is in scope | A. hermes-db reads external refs; B. hermes-db only stores refs; C. reject refs | B | `get_workflow_artifact_content` may return ref metadata instead of body | Spec out-of-scope |
| ADR-004: Artifact versioning | Same name can be regenerated | A. overwrite; B. append new version on changed hash; C. require caller version | B | More rows and cleanup work later | Spec FR-011 |
| ADR-005: Artifact identity | Retries need stable idempotency | A. server-only ids; B. client may pass `artifact_id`, server generates if missing | B | Tool validation becomes stricter | Spec unclear question |

---

## Key Design Decisions

### Decision 1: Store workflow persistence in two dedicated PostgreSQL tables

- **背景**: Existing topics tables are domain records; workflow runs and generated artifacts are audit/persistence records with different lifecycle and query patterns.
- **选项**:
  - A: Dedicated `wechat_workflow_runs` and `workflow_artifacts` tables.
  - B: Reuse `topics` metadata or create generic key-value records.
- **结论**: Choose A. It provides clear indexes, constraints, and schema health checks without overloading topic semantics.
- **影响**: Requires a new Alembic revision and repository tests, but keeps future publication ledger and analytics features easier to join.
- **来源**: Local code evidence in `packages/hermes-db/migrations`, `repositories`, and `tools`.

### Decision 2: Use `run_id` as the run primary key

- **背景**: The downstream workflow already has a stable run identity and needs retry-safe writes.
- **选项**:
  - A: Use client-provided `run_id` as primary key.
  - B: Generate internal UUID and separately index external run id.
- **结论**: Choose A. It gives direct idempotency and simpler MCP contracts.
- **影响**: `run_id` must be validated as non-empty bounded text, but does not need UUID format.
- **来源**: Spec US1 and NFR-001.

### Decision 3: Version artifacts by content change, not by blind overwrite

- **背景**: Same run/stage/name can be regenerated, and old drafts must remain recoverable.
- **选项**:
  - A: Upsert overwrites the previous row.
  - B: If `(run_id, stage, name, content_hash)` already exists, return it; otherwise insert `max(version)+1`.
  - C: Require caller to provide every version number.
- **结论**: Choose B.
- **影响**: Repository insert must happen in a transaction or single SQL statement to avoid race conditions.
- **来源**: Spec US2-3 and US2-7.

### Decision 4: MVP stores `content_ref` but does not dereference it

- **背景**: `content_ref` is needed for large bodies, but object storage is out of scope.
- **选项**:
  - A: hermes-db reads files/URLs from `content_ref`.
  - B: hermes-db stores and returns the reference plus preview/hash/metadata.
  - C: reject large artifacts.
- **结论**: Choose B.
- **影响**: Consumers remain responsible for resolving external refs; errors are explicit instead of hidden I/O failures.
- **来源**: Spec Out of Scope and Unclear Questions.

---

## Module Design

### Module: Alembic Migration

**职责**: Add durable workflow tables, constraints, and indexes under the existing `hermes` schema.

**改动概述**:

- Add `migrations/versions/0002_wechat_workflow_artifacts.py`.
- Set `down_revision = "0001_topic_revisit"`.
- Use idempotent SQL patterns consistent with the existing migration.

**关键接口 / 行为**:

```text
upgrade:
  create hermes.wechat_workflow_runs if not exists
  create hermes.workflow_artifacts if not exists
  add FK workflow_artifacts.run_id -> wechat_workflow_runs.run_id
  add self FK workflow_artifacts.parent_artifact_id -> workflow_artifacts.artifact_id
  add indexes for run/topic/account/type/date queries
```

**注意事项**:

- Migration must not modify existing `hermes.topics` behavior.
- `topic_id` may be nullable, but if present should reference `hermes.topics(id)` with `ON DELETE SET NULL`.

### Module: Data Contracts and Validation

**职责**: Define workflow-specific constants, structured result shapes, and validation helpers.

**改动概述**:

- Extend `contracts.py` with workflow error codes and validators.
- Keep existing topic contracts stable.
- Add validators for non-empty ids, content policy, pagination/filter constraints, date range, and max inline content size.

**关键接口 / 行为**:

```text
validate_workflow_run_payload(...)
validate_artifact_payload(...)
validate_artifact_query(...)
error("content_too_large", details={...})
error("schema_drift", details={...})
```

### Module: Workflow Repository

**职责**: Encapsulate all SQL for workflow run and artifact persistence.

**改动概述**:

- Add `repositories/workflow_repo.py`.
- Provide repository methods for run upsert, run finish, artifact upsert, artifact list, and artifact content lookup.

**关键接口 / 行为**:

```text
upsert_run(pool, payload) -> row
finish_run(pool, run_id, payload) -> row | None
upsert_artifact(pool, payload) -> row
list_artifacts(pool, filters, limit, offset) -> list[row]
get_artifact(pool, artifact_id) -> row | None
```

**注意事项**:

- Artifact upsert should treat same `artifact_id` or same `(run_id, stage, name, content_hash)` as retry/idempotency.
- Changed content for the same `(run_id, stage, name)` inserts a new version.
- Version assignment must be transaction-safe.

### Module: MCP Workflow Tools

**职责**: Expose stable MCP tool contracts to downstream agents.

**改动概述**:

- Add `tools/workflows.py` or two files: `tools/workflow_runs.py` and `tools/workflow_artifacts.py`.
- Register the new module(s) in `server.register_tools()`.
- Annotate read tools with `readOnlyHint=True`; write tools with non-destructive/idempotency hints where accurate.

**关键接口 / 行为**:

```text
upsert_workflow_run(...)
finish_workflow_run(...)
upsert_workflow_artifact(...)
list_workflow_artifacts(...)
get_workflow_artifact_content(...)
```

**注意事项**:

- List results must omit `content_text`.
- `get_workflow_artifact_content` returns body only when stored inline.
- Errors use the existing structured dict style.

### Module: Health and Schema Inspection

**职责**: Surface workflow persistence availability without breaking existing health fields.

**改动概述**:

- Extend `services/schema.py` with `inspect_workflow_schema`.
- Merge workflow capability keys into `health()["capabilities"]`.

**关键接口 / 行为**:

```text
capabilities.workflow_artifacts = tables, constraints, and indexes are present
capabilities.workflow_runs = run table is present
```

**注意事项**:

- Existing capability keys must remain present.
- Missing migration should not crash `health`; it should expose false capability or `schema_error`.

---

## Data Model

Detailed schema is defined in [data-model.md](data-model.md).

Core entities:

- `hermes.wechat_workflow_runs`: one row per downstream workflow execution.
- `hermes.workflow_artifacts`: versioned generated artifacts associated with a run and optionally with a topic/account.

---

## Project Structure

```text
packages/hermes-db/
  migrations/versions/
    0002_wechat_workflow_artifacts.py
  src/hermes_db_mcp/
    contracts.py
    repositories/
      workflow_repo.py
    services/
      schema.py
    tools/
      workflow_runs.py
      workflow_artifacts.py
      health.py
    server.py
  tests/
    test_workflow_contracts.py
    test_workflow_repo.py
    test_workflow_repo_sql.py
    test_workflow_tools.py
    test_workflow_schema_health.py
    test_migration_sql.py
```

---

## Risks and Tradeoffs

- `content_ref` MVP does not dereference external content. This keeps hermes-db focused but pushes reference resolution to consumers.
- Version assignment can race if implemented as read-max-then-insert without locking. Repository code should use a transaction and a scoped advisory lock or an atomic SQL pattern.
- Inline Markdown storage increases PostgreSQL row size. The 256 KiB limit and summary-first list contract mitigate this.
- Downstream agents are not implemented here. Final closure requires a later cross-repo integration evidence gate.

---

## Evolution Path

- **MVP**: PostgreSQL-only run/artifact persistence, inline text up to 256 KiB, stored `content_ref`, summary list, explicit content read.
- **成长期**: Add object storage adapter if large artifacts become common, plus retention/cleanup policy.
- **成熟期**: Add publication ledger, analytics snapshots, and retrospective joins as separate features, not by expanding this feature into a workflow engine.

---

## Anti-Pattern Check

- 是否把成熟期架构套到了 MVP：否。No queue, object store, event bus, or workflow engine is introduced.
- 是否引用了外部模式但没有适配检查：否。Layered architecture is used because it matches current code.
- 是否新增未记录的状态、依赖、缓存、队列或失败模式：否。New state is limited to run/artifact tables and is documented in `data-model.md`.

---

## Verification Strategy

Implementation should verify in this order:

1. Migration static tests: new revision, table names, constraints, indexes, and down revision are present.
2. Contract tests: validators cover required fields, content policy, pagination/filter rules, id parsing, and structured errors.
3. Repository tests: run upsert idempotency, finish behavior, artifact retry idempotency, version increment, parent relation, and query filters.
4. Tool tests: MCP functions return expected success/error payloads and list output omits `content_text`.
5. Schema health tests: `health` includes existing topic capabilities plus workflow capability keys.
6. Regression tests: existing hermes-db test suite remains green.
7. Optional integration evidence: with `DATABASE_URL`, write a run and draft artifact, then list/read it through repository or tool layer.

---

## Stage Readiness

- 是否需要 `data-model.md`：需要。This feature adds persistent entities, relationships, constraints, indexes, and version semantics.
- 下一步建议：`tasks`
- 阻塞项：无。Open design choices from `spec.md` are resolved in ADRs above.

---

## Design Artifacts

| 产物 | 是否需要 | 说明 |
|------|---------|------|
| plan.md | 必须 | 主实现计划 |
| data-model.md | 必须 | PostgreSQL schema, relationships, constraints, indexes |
| tasks.md | 后续阶段生成 | Break implementation into executable steps |
| acceptance.md | 后续阶段生成 | Record final evidence and closure |

---

## Sources

| 决策 | 来源 URL | 备注 |
|------|---------|------|
| Layered architecture reference | https://github.com/study8677/awesome-architecture/blob/main/tutorial/04-%E5%8D%81%E5%A4%A7%E6%A0%B8%E5%BF%83%E6%9E%B6%E6%9E%84%E6%A8%A1%E5%BC%8F.md | General reference only |
| Storage and MCP tool pattern | `packages/hermes-db/src/hermes_db_mcp` | Local code evidence |
| Migration pattern | `packages/hermes-db/migrations/versions/0001_add_revisit_of_mother_theme.py` | Local code evidence |
| Content threshold | UNVERIFIED | Product-level MVP default |
