# Data Model: Hermes DB Agent Self Evolution Foundation

**Workspace**: `hermes-db-agent-self-evolution-foundation` | **Date**: 2026-06-11

---

## Entities

### Agent Policy (table: `hermes.agent_policies`)

**描述**: Versioned, scoped runtime policy that can influence future agent planning or execution after review.

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| policy_version_id | UUID | PK | Exact policy version id used by application trace |
| policy_id | UUID | NOT NULL | Stable policy family id |
| version | INTEGER | NOT NULL, CHECK >= 1 | Monotonic version within policy_id |
| domain | TEXT | NOT NULL | `wechat`, `novel`, `xhs`, `global`, etc. |
| policy_type | TEXT | NOT NULL, CHECK | `topic_strategy`, `title_strategy`, `column_strategy`, `writing_constraint`, `review_gate`, `sop` |
| status | TEXT | NOT NULL, CHECK | `draft`, `active`, `superseded`, `disabled`, `rolled_back`, `expired` |
| scope_json | JSONB | NOT NULL DEFAULT `{}` | Domain/account/project scope selector |
| task_types_json | JSONB | NOT NULL DEFAULT `[]` | Applicable task types |
| decision_points_json | JSONB | NOT NULL DEFAULT `[]` | Applicable decision points |
| trigger_conditions_json | JSONB | NOT NULL DEFAULT `{}` | Match conditions |
| policy_body_json | JSONB | NOT NULL DEFAULT `{}` | Domain-specific policy payload |
| priority | INTEGER | NOT NULL DEFAULT 0 | Higher priority wins when otherwise compatible |
| precedence | TEXT | NOT NULL DEFAULT `scope_specific_over_global` | Conflict/precedence hint |
| source_candidate_id | UUID | NULL, FK -> `hermes.learning_candidates(candidate_id)` ON DELETE SET NULL | Source learning candidate |
| source_policy_version_id | UUID | NULL | Previous version when superseding/rollback |
| evidence_refs_json | JSONB | NOT NULL DEFAULT `{}` | Compact evidence refs |
| approved_by | TEXT | NOT NULL | Reviewer/operator |
| approved_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | Approval time |
| effective_from | TIMESTAMPTZ | NULL | Start time; null means immediate |
| effective_until | TIMESTAMPTZ | NULL | End time |
| disable_reason | TEXT | NULL | Disable/rollback reason |
| metadata_json | JSONB | NOT NULL DEFAULT `{}` | Extra metadata |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | Created time |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | Updated time |

**唯一约束**:

- `uq_agent_policies_policy_version` on `(policy_id, version)`
- `uq_agent_policies_source_candidate` on `(source_candidate_id)` where `source_candidate_id IS NOT NULL` for default idempotent promote.

**检查约束**:

- `chk_agent_policies_version_positive`
- `chk_agent_policies_status`
- `chk_agent_policies_policy_type`
- `chk_agent_policies_effective_range`: `effective_until IS NULL OR effective_from IS NULL OR effective_until > effective_from`
- JSON shape checks for object/array fields where practical.

**索引**:

- `idx_agent_policies_active_lookup` on `(domain, policy_type, status, priority DESC)`
- `idx_agent_policies_source_candidate` on `(source_candidate_id)` where `source_candidate_id IS NOT NULL`
- `idx_agent_policies_policy_id` on `(policy_id, version DESC)`
- GIN indexes on `scope_json` and `trigger_conditions_json` if supported.

**状态转换**:

```text
draft -> active
active -> superseded
active -> disabled
active -> expired
active -> rolled_back
superseded -> rolled_back
disabled -> active   (explicit restore only)
```

---

### Policy Application (table: `hermes.policy_applications`)

**描述**: Append-only trace that a specific policy version was considered or applied during an agent run.

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| application_id | UUID | PK | Server-generated application trace id |
| run_id | TEXT | NULL | Existing workflow/agent run id; full agent_runs table is not required in MVP |
| domain | TEXT | NOT NULL | Domain |
| agent_name | TEXT | NOT NULL | Consumer agent |
| task_type | TEXT | NOT NULL | Task type |
| decision_point | TEXT | NOT NULL | Where policy was used |
| policy_id | UUID | NOT NULL | Policy family id |
| policy_version_id | UUID | NOT NULL, FK -> `hermes.agent_policies(policy_version_id)` ON DELETE RESTRICT | Exact policy version |
| policy_version | INTEGER | NOT NULL | Version number copied for convenience |
| scope_json | JSONB | NOT NULL DEFAULT `{}` | Scope at application time |
| matched_conditions_json | JSONB | NOT NULL DEFAULT `{}` | Conditions that matched |
| application_status | TEXT | NOT NULL, CHECK | `applied`, `skipped`, `blocked`, `failed` |
| applied_action_json | JSONB | NOT NULL DEFAULT `{}` | Applied action/result payload |
| outcome_summary_json | JSONB | NOT NULL DEFAULT `{}` | Immediate outcome summary |
| warning | TEXT | NULL | Non-fatal warning |
| error_summary_json | JSONB | NULL | Failure details |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | Created time |

**索引**:

- `idx_policy_applications_run` on `(run_id)` where `run_id IS NOT NULL`
- `idx_policy_applications_policy` on `(policy_id, created_at DESC)`
- `idx_policy_applications_policy_version` on `(policy_version_id, created_at DESC)`
- `idx_policy_applications_domain_task` on `(domain, task_type, created_at DESC)`

**说明**:

- Application records are append-only.
- Do not update application rows except for administrative repair; corrective action should disable/rollback policy or add a new trace.

---

## Learning Candidate Compatibility

Existing table `hermes.learning_candidates` remains the producer.

This feature depends on:

- `candidate_id`
- `domain`
- `candidate_type`
- `scope_json`
- `trigger_conditions_json`
- `proposed_policy_json`
- `evidence_refs_json`
- `status`
- `policy_id`

Compatibility notes:

- Existing `learning_candidates.policy_id` is `TEXT`; this feature must keep it compatible and write `str(agent_policies.policy_id)` back during promotion.
- This feature must not rewrite existing candidate rows or change `learning_candidates.policy_id` to UUID in-place.

Promotion rules:

```text
status = approved -> exported_to_policy
status in pending_review/rejected/disabled -> cannot promote
status = exported_to_policy -> return existing policy for idempotent promote
```

---

## MCP Tool Contracts

### `promote_learning_candidate_to_policy(input) -> AgentPolicy`

Required:

- `candidate_id`
- `approved_by`

Optional:

- `review_note`
- `policy_type`
- `task_types`
- `decision_points`
- `effective_from`
- `effective_until`
- `priority`
- `metadata`

Behavior:

- Candidate must be approved.
- Policy body defaults from `learning_candidates.proposed_policy_json`.
- Scope defaults from `learning_candidates.scope_json`.
- Trigger conditions default from `learning_candidates.trigger_conditions_json`.
- Evidence refs default from `learning_candidates.evidence_refs_json`.
- Candidate receives `status=exported_to_policy` and `policy_id=str(agent_policies.policy_id)`.

### `list_agent_policies(input) -> { items, total, limit, offset }`

Filters:

- `domain`
- `policy_type`
- `status`
- `source_candidate_id`
- `policy_id`
- `limit`
- `offset`

### `get_applicable_agent_policies(input) -> { items, warnings, total, limit, offset }`

Required:

- `domain`
- `scope`
- `task_type`

Optional:

- `decision_point`
- `now`
- `limit`
- `offset`

Returns only active, in-scope, time-valid policies.

### `disable_agent_policy(input) -> AgentPolicy`

Required:

- `policy_id`
- `disabled_by`
- `disable_reason`

Disables current active version and keeps history.

### `rollback_agent_policy(input) -> AgentPolicy`

Required:

- `policy_id`
- `to_policy_version_id`
- `reviewed_by`

Creates a new active version from the target version and marks current active version rolled back.

Rollback semantics:

- Do not mutate the historical target version into active in-place.
- Copy the target policy payload into a new monotonically increasing version.
- Mark the current active version as `rolled_back`.
- Preserve the target historical version status for audit.

### `record_policy_application(input) -> PolicyApplication`

Required:

- `domain`
- `agent_name`
- `task_type`
- `decision_point`
- `policy_id`
- `policy_version_id`
- `policy_version`
- `application_status`

Optional:

- `run_id`
- `scope`
- `matched_conditions`
- `applied_action`
- `outcome_summary`
- `warning`
- `error_summary`

### `list_policy_applications(input) -> { items, total, limit, offset }`

Filters:

- `policy_id`
- `policy_version_id`
- `run_id`
- `domain`
- `task_type`
- `decision_point`
- `limit`
- `offset`

---

## Health Capability

`health` should expose:

```json
{
  "capabilities": {
    "agent_self_evolution_foundation": true
  }
}
```

Capability is true only when:

- `hermes.agent_policies` exists with required columns, checks and indexes.
- `hermes.policy_applications` exists with required columns and indexes.
- Existing `hermes.learning_candidates` compatibility columns exist.

Tool registration is verified by import/registration tests, not by the runtime health schema inspector.

---

## Migration Notes

- Preferred Alembic revision id: `0006_agent_self_evolution` (file `0006_agent_self_evolution_foundation.py`; revision id stays <= 32 chars for `alembic_version.version_num`).
- Expected `down_revision`: `0005_wechat_retro_opt`.
- Migration is additive.
- Downgrade order: drop `policy_applications` before `agent_policies`.
- Do not delete or rewrite existing `learning_candidates` rows on upgrade/downgrade.
