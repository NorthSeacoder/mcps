# Context Manifest: Hermes DB Agent Self Evolution Foundation

**Workspace**: `hermes-db-agent-self-evolution-foundation`
**Created**: 2026-06-11
**Status**: active

---

## Implement Context

| File / Source | Reason | Phase | Required |
|---|---|---|---|
| `specs/hermes-db-agent-self-evolution-foundation/spec.md` | Defines feature scope, requirements and non-goals. | implement | yes |
| `specs/hermes-db-agent-self-evolution-foundation/plan.md` | Defines module boundaries and ADRs. | implement | yes |
| `specs/hermes-db-agent-self-evolution-foundation/data-model.md` | Defines tables, state transitions and MCP contract. | implement | yes |
| `specs/hermes-db-agent-self-evolution-foundation/tasks.md` | Defines execution order and verification points. | implement | yes |
| `specs/hermes-db-wechat-retrospective-topic-optimizer/data-model.md` | Defines existing `learning_candidates` compatibility layer. | implement | yes |
| `packages/hermes-db/src/hermes_db_mcp/tools/wechat_retrospective.py` | Existing MCP tool style for retrospective persistence. | implement | yes |
| `packages/hermes-db/src/hermes_db_mcp/repositories/wechat_retrospective_repo.py` | Existing repository SQL/serialization style. | implement | yes |

---

## Check Context

| File / Source | Reason | Phase | Required |
|---|---|---|---|
| `specs/hermes-db-agent-self-evolution-foundation/spec.md` | Verify requirements and non-goals. | verify | yes |
| `specs/hermes-db-agent-self-evolution-foundation/plan.md` | Check architecture drift and ADR compliance. | verify | yes |
| `specs/hermes-db-agent-self-evolution-foundation/data-model.md` | Check schema, status and MCP contract compatibility. | verify | yes |
| `specs/hermes-db-agent-self-evolution-foundation/tasks.md` | Check task completion and evidence gate. | verify | yes |
| `specs/hermes-db-wechat-retrospective-topic-optimizer/acceptance.md` | Confirms retrospective learning candidate producer exists. | verify | yes |

---

## Research Context

| File / Source | Reason | Phase | Verified |
|---|---|---|---|
| `/Users/yqg/personal/AI/agents/specs/agent-self-evolution-foundation/plan.md` | Downstream agents contract this feature must satisfy. | plan / implement / verify | yes |
| `/Users/yqg/personal/AI/agents/specs/agent-self-evolution-foundation/data-model.md` | Agents-side contract mirror for policy/application semantics. | plan / implement / verify | yes |

