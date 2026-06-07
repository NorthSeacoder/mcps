# Context Manifest: Hermes DB WeChat Retrospective Topic Optimizer

**Workspace**: `hermes-db-wechat-retrospective-topic-optimizer`  
**Created**: 2026-06-07  
**Status**: active

> 本文件用于记录 SDD 各阶段必须读取的高信号上下文。它不是待修改源文件清单，也不替代实现阶段按需阅读代码。

---

## Implement Context

| File / Source | Reason | Phase | Required |
|---|---|---|---|
| `specs/hermes-db-wechat-retrospective-topic-optimizer/spec.md` | Defines user scenarios, MCP tool contract, error contract, health capability contract, and acceptance evidence required. | implement | yes |
| `specs/hermes-db-wechat-retrospective-topic-optimizer/plan.md` | Defines architecture boundary, ADRs, module split, verification strategy, and MVP decisions for open questions. | implement | yes |
| `specs/hermes-db-wechat-retrospective-topic-optimizer/data-model.md` | Defines tables, fields, constraints, indexes, FKs, and status transitions required by migration/repository work. | implement | yes |
| `specs/hermes-db-wechat-retrospective-topic-optimizer/tasks.md` | Defines executable task order, task scope, dependency sequence, and verification points. | implement | yes |

---

## Check Context

| File / Source | Reason | Phase | Required |
|---|---|---|---|
| `specs/hermes-db-wechat-retrospective-topic-optimizer/spec.md` | Verify every US/FR and required acceptance evidence has fresh proof. | verify | yes |
| `specs/hermes-db-wechat-retrospective-topic-optimizer/plan.md` | Check architecture drift against ADRs, module boundaries, safety constraints, and health-gate design. | verify | yes |
| `specs/hermes-db-wechat-retrospective-topic-optimizer/data-model.md` | Check implemented schema, constraints, indexes, and status transitions match the planned model. | verify | yes |
| `specs/hermes-db-wechat-retrospective-topic-optimizer/tasks.md` | Check all task scopes are completed or explicitly deferred with rationale. | verify | yes |

---

## Research Context

| File / Source | Reason | Phase | Verified |
|---|---|---|---|
| `specs/hermes-db-wechat-analytics-ingestion/plan.md` | Closest completed hermes-db feature plan showing Alembic + repository + tools + schema health pattern. | implement / verify | yes |
| `specs/hermes-db-wechat-analytics-ingestion/tasks.md` | Closest completed task breakdown and verification sequencing pattern for this repo. | implement / verify | yes |
| `packages/hermes-db/src/hermes_db_mcp/tools/wechat_analytics.py` | Existing MCP tool pattern for validation, asyncpg error mapping, serialization, and annotations; read as pattern, not fixed write scope. | implement | yes |
| `packages/hermes-db/src/hermes_db_mcp/repositories/wechat_analytics_repo.py` | Existing repository pattern for JSONB params, fake-connection tests, upsert helpers, and transaction helpers; read as pattern, not fixed write scope. | implement | yes |
| `packages/hermes-db/src/hermes_db_mcp/services/schema.py` | Existing schema inspector pattern for capabilities; implementation must extend this file but still re-read current contents before editing. | implement / verify | yes |
| `packages/hermes-db/src/hermes_db_mcp/tools/health.py` | Existing capability aggregation behavior and default false values; implementation must re-read before editing. | implement / verify | yes |
| `packages/hermes-db/tests/test_wechat_analytics_schema_health.py` | Existing false/true/partial schema health test style. | implement / verify | yes |
| `packages/hermes-db/tests/test_wechat_analytics_tools.py` | Existing MCP tool unit test style for fake contexts, validation, error mapping, and serialization. | implement / verify | yes |
| `https://github.com/study8677/awesome-architecture/blob/main/tutorial/04-%E5%8D%81%E5%A4%A7%E6%A0%B8%E5%BF%83%E6%9E%B6%E6%9E%84%E6%A8%A1%E5%BC%8F.md` | Skill-provided architecture reference used only to justify layered architecture fit; local repo pattern remains source of truth. | plan / verify | yes |

---

## Rules

- 每条 entry 必须有 `Reason`；缺少 reason 的 manifest 不得通过 verify。
- `Required = yes` 的本地文件不存在时，当前阶段必须回退到 `plan` 或 `tasks` 更新 manifest。
- 不复制长文档；只记录路径、来源、用途和短摘要。
- 不引入 `.trellis/`、Trellis CLI、hook、task.py 或自动 context injection。
