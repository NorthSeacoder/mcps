# Data Model: hermes-db WeChat Artifact Persistence

**Workspace**: `hermes-db-wechat-artifact-persistence` | **Date**: 2026-06-03

---

## Entities

### Workflow Run (表名: `hermes.wechat_workflow_runs`)

**描述**: One durable record for a downstream WeChat content workflow execution. It anchors artifacts, retries, completion state, and retrospective queries.

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| run_id | TEXT | PRIMARY KEY, NOT NULL | Downstream workflow stable id |
| task_id | TEXT | INDEX, NULL | Optional downstream task id |
| topic_id | UUID | FK -> `hermes.topics(id)`, NULL, INDEX | Related topic when available |
| account | TEXT | NULL, INDEX | WeChat account alias |
| input_text | TEXT | NULL | Original user or workflow input |
| intent | TEXT | NULL | Workflow intent |
| phase | TEXT | NOT NULL | Current high-level phase |
| current_stage | TEXT | NULL | Current stage name |
| status | TEXT | NOT NULL | `running`, `completed`, `failed`, `blocked`, or downstream-compatible value |
| dry_run | BOOLEAN | NOT NULL, DEFAULT false | Whether this run was a dry run |
| summary | TEXT | NULL | Final or latest summary |
| failure_reason | TEXT | NULL | Failure or blocked reason |
| missing_inputs | JSONB | NOT NULL, DEFAULT `'[]'::jsonb` | Missing input descriptors |
| next_action | TEXT | NULL | Suggested next action |
| metadata | JSONB | NOT NULL, DEFAULT `'{}'::jsonb` | Caller-supplied structured metadata |
| started_at | TIMESTAMPTZ | NULL | Workflow start timestamp |
| completed_at | TIMESTAMPTZ | NULL | Workflow completion timestamp |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Row creation time |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Row update time |

**索引**:

- `idx_wechat_workflow_runs_topic_created` on `(topic_id, created_at DESC)`
- `idx_wechat_workflow_runs_account_created` on `(account, created_at DESC)`
- `idx_wechat_workflow_runs_task_id` on `(task_id)`
- `idx_wechat_workflow_runs_status_created` on `(status, created_at DESC)`

**状态语义**:

```text
running -> completed
running -> failed
running -> blocked
blocked -> running
blocked -> failed
```

The database should not over-constrain status values in MVP. Tool validation may recognize common values, but downstream-compatible status strings should remain possible unless they break query semantics.

### Workflow Artifact (表名: `hermes.workflow_artifacts`)

**描述**: Versioned generated artifact linked to a workflow run. It stores summary fields for list queries and either inline text content or an external content reference.

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| artifact_id | TEXT | PRIMARY KEY, NOT NULL | Client-provided stable id or server-generated UUID string |
| run_id | TEXT | FK -> `hermes.wechat_workflow_runs(run_id)`, NOT NULL, INDEX | Owning workflow run |
| task_id | TEXT | NULL, INDEX | Copied from payload/run for query convenience |
| topic_id | UUID | FK -> `hermes.topics(id)`, NULL, INDEX | Copied from payload/run for query convenience |
| account | TEXT | NULL, INDEX | Copied from payload/run for query convenience |
| stage | TEXT | NOT NULL | Producing workflow stage |
| type | TEXT | NOT NULL, INDEX | Artifact type, e.g. `draft`, `review`, `publish-result` |
| name | TEXT | NOT NULL | Logical artifact name, e.g. `draft`, `transformed-draft` |
| version | INTEGER | NOT NULL | Monotonic per `(run_id, stage, name)` |
| parent_artifact_id | TEXT | FK -> `hermes.workflow_artifacts(artifact_id)`, NULL | Parent artifact for transformed outputs |
| content_hash | TEXT | NOT NULL | Stable hash of content or referenced payload |
| content_size_bytes | INTEGER | NOT NULL, CHECK `>= 0` | Original content size |
| content_preview | TEXT | NULL | Short preview safe for list output |
| content_text | TEXT | NULL | Inline body, max 256 KiB by tool validation |
| content_ref | TEXT | NULL | External content reference when not stored inline |
| metadata | JSONB | NOT NULL, DEFAULT `'{}'::jsonb` | Caller-supplied structured metadata |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Row creation time |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Row update time |

**约束**:

- `chk_workflow_artifacts_content_present`: `content_text IS NOT NULL OR content_ref IS NOT NULL`
- `chk_workflow_artifacts_version_positive`: `version >= 1`
- `chk_workflow_artifacts_content_size_nonnegative`: `content_size_bytes >= 0`
- `uq_workflow_artifact_logical_version`: unique `(run_id, stage, name, version)`
- `uq_workflow_artifact_logical_hash`: unique `(run_id, stage, name, content_hash)`

**索引**:

- `idx_workflow_artifacts_run_created` on `(run_id, created_at DESC)`
- `idx_workflow_artifacts_topic_created` on `(topic_id, created_at DESC)`
- `idx_workflow_artifacts_account_created` on `(account, created_at DESC)`
- `idx_workflow_artifacts_type_created` on `(type, created_at DESC)`
- `idx_workflow_artifacts_stage_name` on `(run_id, stage, name)`
- `idx_workflow_artifacts_parent` on `(parent_artifact_id)`

**版本语义**:

```text
same artifact_id                         -> retry; return existing row if hash matches
same run_id + stage + name + content_hash -> retry; return existing row
same run_id + stage + name + new hash      -> insert version = max(version) + 1
```

If a client sends an existing `artifact_id` with a different `content_hash`, the tool should return structured validation error instead of mutating the old artifact.

---

## Relationships

```text
hermes.topics 1:N hermes.wechat_workflow_runs
hermes.wechat_workflow_runs 1:N hermes.workflow_artifacts
hermes.workflow_artifacts 1:N hermes.workflow_artifacts (parent -> children)
```

Relationship behavior:

- Deleting a topic should not delete historical workflow data. `topic_id` uses `ON DELETE SET NULL`.
- Deleting a workflow run is not part of MVP. If future retention deletes runs, artifacts should be deleted or archived by an explicit retention feature.
- Parent artifact deletion is not part of MVP. FK should use `ON DELETE SET NULL` to keep child artifacts queryable.

---

## DDL Scripts

```sql
CREATE TABLE IF NOT EXISTS hermes.wechat_workflow_runs (
    run_id TEXT PRIMARY KEY,
    task_id TEXT,
    topic_id UUID REFERENCES hermes.topics(id) ON DELETE SET NULL,
    account TEXT,
    input_text TEXT,
    intent TEXT,
    phase TEXT NOT NULL,
    current_stage TEXT,
    status TEXT NOT NULL,
    dry_run BOOLEAN NOT NULL DEFAULT false,
    summary TEXT,
    failure_reason TEXT,
    missing_inputs JSONB NOT NULL DEFAULT '[]'::jsonb,
    next_action TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_wechat_workflow_runs_topic_created
ON hermes.wechat_workflow_runs(topic_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_wechat_workflow_runs_account_created
ON hermes.wechat_workflow_runs(account, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_wechat_workflow_runs_task_id
ON hermes.wechat_workflow_runs(task_id);

CREATE INDEX IF NOT EXISTS idx_wechat_workflow_runs_status_created
ON hermes.wechat_workflow_runs(status, created_at DESC);

CREATE TABLE IF NOT EXISTS hermes.workflow_artifacts (
    artifact_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES hermes.wechat_workflow_runs(run_id) ON DELETE CASCADE,
    task_id TEXT,
    topic_id UUID REFERENCES hermes.topics(id) ON DELETE SET NULL,
    account TEXT,
    stage TEXT NOT NULL,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    version INTEGER NOT NULL,
    parent_artifact_id TEXT REFERENCES hermes.workflow_artifacts(artifact_id) ON DELETE SET NULL,
    content_hash TEXT NOT NULL,
    content_size_bytes INTEGER NOT NULL,
    content_preview TEXT,
    content_text TEXT,
    content_ref TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_workflow_artifacts_content_present
        CHECK (content_text IS NOT NULL OR content_ref IS NOT NULL),
    CONSTRAINT chk_workflow_artifacts_version_positive
        CHECK (version >= 1),
    CONSTRAINT chk_workflow_artifacts_content_size_nonnegative
        CHECK (content_size_bytes >= 0),
    CONSTRAINT uq_workflow_artifact_logical_version
        UNIQUE (run_id, stage, name, version),
    CONSTRAINT uq_workflow_artifact_logical_hash
        UNIQUE (run_id, stage, name, content_hash)
);

CREATE INDEX IF NOT EXISTS idx_workflow_artifacts_run_created
ON hermes.workflow_artifacts(run_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_workflow_artifacts_topic_created
ON hermes.workflow_artifacts(topic_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_workflow_artifacts_account_created
ON hermes.workflow_artifacts(account, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_workflow_artifacts_type_created
ON hermes.workflow_artifacts(type, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_workflow_artifacts_stage_name
ON hermes.workflow_artifacts(run_id, stage, name);

CREATE INDEX IF NOT EXISTS idx_workflow_artifacts_parent
ON hermes.workflow_artifacts(parent_artifact_id);
```

---

## Migration Notes

- Alembic revision: `0002_wechat_workflow_artifacts`
- Down revision: `0001_topic_revisit`
- Upgrade should use idempotent `CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, and guarded constraint creation where PostgreSQL requires it.
- Downgrade should drop artifact indexes/table before run indexes/table.
- Release deployment must run `alembic upgrade head` before using new tools.
- `health` should expose workflow capability as false or schema error if migration has not run.

---

## Query Contracts

### `list_workflow_artifacts`

Allowed filters:

- `run_id`
- `topic_id`
- `account`
- `type`
- `stage`
- `date_from`
- `date_to`

Rules:

- At least one filter is required unless `limit` is explicitly provided and bounded.
- Default `limit` should be 50; maximum should be 200.
- Response must not include `content_text`.

### `get_workflow_artifact_content`

Rules:

- If `content_text` is present, return the inline text body and summary fields.
- If only `content_ref` is present, return `content_ref`, `content_hash`, `content_size_bytes`, `content_preview`, and metadata with an explicit `content_inline=false`.
- Missing artifact returns structured `not_found`.

---

## Content Policy

- Inline `content_text` maximum: 256 KiB.
- `content_text` and `content_ref` cannot both be absent.
- Binary image data must not be stored in `content_text`.
- `content_preview` should be caller-provided or derived by tool logic, bounded to a small size suitable for list output.
