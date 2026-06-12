# Implementation Plan: Hermes DB Agent Self Evolution Foundation

**Workspace**: `hermes-db-agent-self-evolution-foundation` | **Date**: 2026-06-11 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/hermes-db-agent-self-evolution-foundation/spec.md`

---

## Summary

Implement Hermes DB as the runtime policy store for agent self-evolution. The first slice promotes existing approved `learning_candidates` into versioned `agent_policies`, supports applicable policy queries, and records append-only `policy_applications`.

---

## Architecture Overview

```text
hermes.learning_candidates
  -> policy repository validation
  -> hermes.agent_policies
  -> get_applicable_agent_policies
  -> agents consumer
  -> record_policy_application
  -> hermes.policy_applications
```

Boundaries:

- Migration owns tables, checks and indexes.
- Contract layer owns validation, pagination and structured errors.
- Repository layer owns SQL, idempotency and serialization.
- Tool layer owns MCP inputs/outputs and error mapping.
- Health layer owns schema-aware capability.

---

## Producer-Consumer Matrix

| Producer | Artifact | Consumer | Consumption Proof |
|---|---|---|---|
| `learning_candidates` | approved candidate | `promote_learning_candidate_to_policy` | approved candidate creates active policy |
| policy promotion tool | `agent_policies` | agents adapter / applicable query | query returns active in-scope policy |
| business agent | `policy_applications` | retrospective/operator | list applications returns run/policy trace |
| disable/rollback tool | policy status/version history | applicable query | disabled/rolled-back policy not returned |

**Orphan artifact handling**: `agent_policies` without application trace are allowed after promotion, but live smoke must record at least one application to prove the handoff.

---

## Lightweight ADR

| Decision | Context | Options | Conclusion | Cost | Source |
|---|---|---|---|---|---|
| ADR-001: Store policies in Hermes DB | Runtime policy lookup needs audit, rollback and scope filtering | Hermes DB / local files / Nowledge Mem | Hermes DB | Requires migration and tools | agents SDD plan |
| ADR-002: Candidate-first MVP | `learning_candidates` already exist | full agent_runs first / candidate promotion first | candidate promotion first | generic observations deferred | agents roadmap |
| ADR-003: Idempotent promote | Agents may retry mutation | append duplicate / return existing | return existing policy for same candidate | unique source candidate semantics | data-model |
| ADR-004: Application trace append-only | Trace history must be auditable | update rows / append only | append only | repair requires new trace or admin action | data-model |

---

## Module Design

### Migration

- Add Alembic revision id `0006_agent_self_evolution` (file `0006_agent_self_evolution_foundation.py`).
- Create `hermes.agent_policies`.
- Create `hermes.policy_applications`.
- Do not destructively alter `hermes.learning_candidates`.

### Contracts

- Add status/type sets and validation helpers.
- Validate JSON object/array fields.
- Validate UUID/date/datetime, pagination, scope object and application status.
- Return structured validation errors.

### Repository

- `promote_learning_candidate_to_policy`
- `list_agent_policies`
- `get_applicable_agent_policies`
- `disable_agent_policy`
- `rollback_agent_policy`
- `record_policy_application`
- `list_policy_applications`

### MCP Tools

- Expose the repository methods with current Hermes MCP response style.
- Map FK/not-found/schema drift/invalid transition/database errors consistently.

### Health

- Add schema-aware capability `agent_self_evolution_foundation`.
- Capability false must not affect existing WeChat retrospective capability.

---

## Data Model

Detailed schema is in [data-model.md](data-model.md).

---

## Risks and Tradeoffs

- Existing retrospective files in mcps may have uncommitted acceptance updates; keep this feature isolated.
- Scope matching in SQL/JSONB can be subtle; contract tests need negative cross-account cases.
- Rollback semantics can grow complex; MVP should implement clear active-version behavior without UI.
- Agents side may implement adapter before deployed capability; live smoke must wait for deployment.

---

## Verification Strategy

- Migration SQL tests for table names, constraints, indexes, down revision and downgrade order.
- Contract tests for validation and structured errors.
- Repository SQL tests for idempotent promote, active query filters, disable/rollback and append-only application traces.
- Tool tests for MCP response shapes and error mapping.
- Health tests for true/false capability.
- Deployed smoke: approved candidate -> promote -> applicable query -> record application -> list application.

---

## Stage Readiness

- 是否需要 `data-model.md`: 需要，涉及新增 DB tables、状态转换、scope matching 和 MCP contracts。
- 下一步建议：`tasks`
- 阻塞项：无。

