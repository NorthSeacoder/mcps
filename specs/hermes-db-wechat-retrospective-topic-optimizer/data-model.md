# Data Model: Hermes DB WeChat Retrospective Topic Optimizer

**Workspace**: `hermes-db-wechat-retrospective-topic-optimizer` | **Date**: 2026-06-07

---

## Entities

### Topic Performance (表名: `hermes.topic_performance`)

**描述**: One idempotent performance score row for a published WeChat article under a scoring window/version. This is the durable fact source used by retrospective reports.

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| performance_id | UUID | PK | Server-generated row id |
| account | TEXT | NOT NULL | WeChat account namespace |
| article_id | UUID | NOT NULL, FK -> `hermes.wechat_articles(article_id)` ON DELETE CASCADE | Published article being scored |
| topic_id | UUID | NULL, FK -> `hermes.topics(id)` ON DELETE SET NULL | Source topic if available |
| stat_date | DATE | NOT NULL | Metric/statistic date |
| window_label | TEXT | NOT NULL | Score window, such as `D+1`, `D+3`, `D+7` |
| scoring_version | TEXT | NOT NULL | Scoring algorithm version, e.g. `wechat-retro-v1` |
| baseline_version | TEXT | NOT NULL | Baseline algorithm/version |
| normalized_score | DOUBLE PRECISION | NULL, CHECK 0..100 | Overall normalized score |
| read_score | DOUBLE PRECISION | NULL, CHECK 0..100 | Read performance component |
| engagement_score | DOUBLE PRECISION | NULL, CHECK 0..100 | Engagement component |
| share_score | DOUBLE PRECISION | NULL, CHECK 0..100 | Share component |
| conversion_score | DOUBLE PRECISION | NULL, CHECK 0..100 | Conversion/follow component |
| confidence | DOUBLE PRECISION | NOT NULL, CHECK 0..1 | Confidence in score quality |
| provisional | BOOLEAN | NOT NULL DEFAULT false | True for provisional D+1/D+3 style scores |
| low_sample_size | BOOLEAN | NOT NULL DEFAULT false | True when baseline/sample is low confidence |
| metric_snapshot_ids_json | JSONB | NOT NULL DEFAULT `[]` | Array of `wechat_article_metric_snapshots.snapshot_id` refs |
| baseline_snapshot_json | JSONB | NOT NULL DEFAULT `{}` | Baseline summary used for score |
| diagnosis_json | JSONB | NOT NULL DEFAULT `{}` | Structured diagnostic output |
| evidence_refs_json | JSONB | NOT NULL DEFAULT `{}` | Compact evidence refs |
| warnings_json | JSONB | NOT NULL DEFAULT `[]` | Explicit warnings, missing evidence, or provisional notes |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | Creation timestamp |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | Last update timestamp |

**唯一约束**:

- `uq_topic_performance_identity` on `(account, article_id, window_label, scoring_version)`

**检查约束**:

- `chk_topic_performance_scores_range`: every non-null score is between 0 and 100.
- `chk_topic_performance_confidence_range`: `confidence` is between 0 and 1.
- `chk_topic_performance_json_shapes`: JSON fields are object/array where semantically required if PostgreSQL check expressions are practical; otherwise enforce in contracts tests.

**索引**:

- `idx_topic_performance_account_stat` on `(account, stat_date DESC)`
- `idx_topic_performance_article_stat` on `(article_id, stat_date DESC)`
- `idx_topic_performance_topic_stat` on `(topic_id, stat_date DESC)` where `topic_id IS NOT NULL`
- `idx_topic_performance_window_stat` on `(window_label, stat_date DESC)`
- `idx_topic_performance_scoring_version` on `(scoring_version)`

### WeChat Retrospective Report (表名: `hermes.wechat_retrospective_reports`)

**描述**: Durable account/article/period retrospective report. Reports are queryable audit records and inputs to suggestions and learning candidates.

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| report_id | UUID | PK | Server-generated report id |
| account | TEXT | NOT NULL | WeChat account namespace |
| report_type | TEXT | NOT NULL, CHECK | `article`, `weekly`, `monthly`, `custom_period` |
| period_start | DATE | NOT NULL | Inclusive report period start |
| period_end | DATE | NOT NULL | Inclusive report period end |
| article_id | UUID | NULL, FK -> `hermes.wechat_articles(article_id)` ON DELETE SET NULL | Present for article reports |
| scoring_version | TEXT | NOT NULL | Scoring version used by report |
| generation_mode | TEXT | NOT NULL, CHECK | `structured_only`, `structured_plus_llm` |
| status | TEXT | NOT NULL, CHECK | `draft`, `completed`, `completed_with_warnings`, `failed` |
| sample_size | INTEGER | NOT NULL DEFAULT 0, CHECK >= 0 | Number of performances summarized |
| low_sample_size | BOOLEAN | NOT NULL DEFAULT false | True when report evidence is low-confidence |
| performance_ids_json | JSONB | NOT NULL DEFAULT `[]` | Array of `topic_performance.performance_id` refs |
| summary_json | JSONB | NOT NULL DEFAULT `{}` | Structured report summary |
| narrative_markdown | TEXT | NULL | Optional human-readable report body |
| high_performing_themes_json | JSONB | NOT NULL DEFAULT `[]` | Structured high-performing theme findings |
| low_performing_themes_json | JSONB | NOT NULL DEFAULT `[]` | Structured low-performing theme findings |
| title_patterns_json | JSONB | NOT NULL DEFAULT `[]` | Structured title pattern findings |
| recommendations_json | JSONB | NOT NULL DEFAULT `[]` | Structured recommendations |
| evidence_refs_json | JSONB | NOT NULL DEFAULT `{}` | Compact evidence refs |
| warnings_json | JSONB | NOT NULL DEFAULT `[]` | Report warnings |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | Creation timestamp |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | Last update timestamp |

**检查约束**:

- `chk_wechat_retrospective_reports_type`
- `chk_wechat_retrospective_reports_generation_mode`
- `chk_wechat_retrospective_reports_status`
- `chk_wechat_retrospective_reports_period`: `period_end >= period_start`
- `chk_wechat_retrospective_reports_sample_size`: `sample_size >= 0`

**索引**:

- `idx_wechat_retrospective_reports_account_period` on `(account, period_start DESC, period_end DESC)`
- `idx_wechat_retrospective_reports_account_type_created` on `(account, report_type, created_at DESC)`
- `idx_wechat_retrospective_reports_article` on `(article_id)` where `article_id IS NOT NULL`
- `idx_wechat_retrospective_reports_status_created` on `(status, created_at DESC)`

### Topic Optimization Suggestion (表名: `hermes.topic_optimization_suggestions`)

**描述**: Human-reviewable topic optimization suggestion. Approved/applied ranking hints may be consumed by topic radar and `pickNext`; pending/rejected/expired suggestions are audit-only.

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| suggestion_id | UUID | PK | Server-generated suggestion id |
| account | TEXT | NOT NULL | WeChat account namespace |
| report_id | UUID | NOT NULL, FK -> `hermes.wechat_retrospective_reports(report_id)` ON DELETE CASCADE | Source report |
| suggestion_type | TEXT | NOT NULL, CHECK | `revisit`, `cooldown`, `priority_adjust`, `ranking_hint`, `seed_prompt_hint` |
| target_kind | TEXT | NOT NULL, CHECK | `topic`, `mother_theme`, `column`, `title_pattern`, `account` |
| target_id | UUID | NULL | Optional concrete topic id or future entity id |
| target_key | TEXT | NULL | Stable text target key when no UUID exists |
| current_value_json | JSONB | NOT NULL DEFAULT `{}` | Current value snapshot |
| proposed_value_json | JSONB | NOT NULL DEFAULT `{}` | Proposed value or ranking hint |
| rationale | TEXT | NOT NULL | Human-readable reason |
| confidence | DOUBLE PRECISION | NOT NULL, CHECK 0..1 | Confidence in suggestion |
| evidence_refs_json | JSONB | NOT NULL DEFAULT `{}` | Compact evidence refs |
| review_status | TEXT | NOT NULL, CHECK | `pending`, `approved`, `rejected`, `expired`, `applied` |
| reviewed_by | TEXT | NULL | Reviewer identity |
| reviewed_at | TIMESTAMPTZ | NULL | Review timestamp |
| review_note | TEXT | NULL | Review note |
| applied_at | TIMESTAMPTZ | NULL | Future application timestamp |
| application_trace_id | TEXT | NULL | Future trace id for applied status |
| expires_at | TIMESTAMPTZ | NULL | Ranking hint expiry |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | Creation timestamp |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | Last update timestamp |

**检查约束**:

- `chk_topic_optimization_suggestions_type`
- `chk_topic_optimization_suggestions_target_kind`
- `chk_topic_optimization_suggestions_review_status`
- `chk_topic_optimization_suggestions_confidence`: `confidence` is between 0 and 1.
- `chk_topic_optimization_suggestions_target_ref`: at least one of `target_id` or `target_key` is present unless `target_kind='account'`.

**索引**:

- `idx_topic_optimization_suggestions_account_status_target` on `(account, review_status, target_kind)`
- `idx_topic_optimization_suggestions_account_target_key` on `(account, target_kind, target_key)` where `target_key IS NOT NULL`
- `idx_topic_optimization_suggestions_account_target_id` on `(account, target_kind, target_id)` where `target_id IS NOT NULL`
- `idx_topic_optimization_suggestions_report` on `(report_id)`
- `idx_topic_optimization_suggestions_expires_at` on `(expires_at)` where `expires_at IS NOT NULL`
- `idx_topic_optimization_suggestions_approved_hints` on `(account, target_kind, review_status, expires_at)` where `review_status IN ('approved', 'applied')`

**状态转换**:

```text
pending -> approved
pending -> rejected
pending -> expired
approved -> expired
approved -> applied   (future explicit trace tool, not MVP review tool)
```

MVP `review_topic_optimization_suggestion` may set only `approved`, `rejected`, or `expired`.

### Learning Candidate (表名: `hermes.learning_candidates`)

**描述**: Reviewable candidate strategy/policy extracted from retrospective evidence. It is a compatibility layer for future policy export and must not apply policy automatically in MVP.

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| candidate_id | UUID | PK | Server-generated candidate id |
| account | TEXT | NOT NULL | WeChat account namespace |
| domain | TEXT | NOT NULL | Domain, e.g. `wechat` |
| source_report_id | UUID | NOT NULL, FK -> `hermes.wechat_retrospective_reports(report_id)` ON DELETE CASCADE | Source report |
| source_suggestion_ids_json | JSONB | NOT NULL DEFAULT `[]` | Array of source suggestion ids |
| candidate_type | TEXT | NOT NULL, CHECK | `topic_strategy`, `title_strategy`, `column_strategy`, `writing_constraint`, `review_gate` |
| scope_json | JSONB | NOT NULL DEFAULT `{}` | Candidate scope |
| trigger_conditions_json | JSONB | NOT NULL DEFAULT `{}` | Trigger conditions |
| proposed_policy_json | JSONB | NOT NULL DEFAULT `{}` | Proposed future policy |
| confidence | DOUBLE PRECISION | NOT NULL, CHECK 0..1 | Candidate confidence |
| evidence_refs_json | JSONB | NOT NULL DEFAULT `{}` | Compact evidence refs |
| status | TEXT | NOT NULL, CHECK | `pending_review`, `approved`, `rejected`, `exported_to_policy`, `disabled` |
| policy_id | TEXT | NULL | Future exported policy id |
| reviewed_by | TEXT | NULL | Reviewer identity |
| reviewed_at | TIMESTAMPTZ | NULL | Review timestamp |
| review_note | TEXT | NULL | Review note |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | Creation timestamp |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | Last update timestamp |

**检查约束**:

- `chk_learning_candidates_type`
- `chk_learning_candidates_status`
- `chk_learning_candidates_confidence`: `confidence` is between 0 and 1.

**索引**:

- `idx_learning_candidates_account_status_type` on `(account, status, candidate_type)`
- `idx_learning_candidates_source_report` on `(source_report_id)`
- `idx_learning_candidates_domain` on `(domain)`
- `idx_learning_candidates_policy_id` on `(policy_id)` where `policy_id IS NOT NULL`

**状态转换**:

```text
pending_review -> approved
pending_review -> rejected
pending_review -> disabled
approved       -> disabled
approved       -> exported_to_policy   (future export tool, not MVP review tool)
```

MVP `review_learning_candidate` may set only `approved`, `rejected`, or `disabled`.

---

## Relationships

```text
hermes.wechat_articles 1:N hermes.topic_performance
hermes.topics          1:N hermes.topic_performance (optional topic_id)

hermes.wechat_articles 1:N hermes.wechat_retrospective_reports (optional article_id)
hermes.topic_performance N:M hermes.wechat_retrospective_reports via performance_ids_json

hermes.wechat_retrospective_reports 1:N hermes.topic_optimization_suggestions
hermes.wechat_retrospective_reports 1:N hermes.learning_candidates
hermes.topic_optimization_suggestions N:M hermes.learning_candidates via source_suggestion_ids_json
```

Notes:

- `performance_ids_json` and `source_suggestion_ids_json` intentionally store compact id arrays; PostgreSQL array-FK enforcement is not required for MVP.
- `evidence_refs_json` stores replay ids only, never full artifact content.
- No table in this feature mutates `hermes.topics`.

---

## DDL Scripts

```sql
CREATE TABLE IF NOT EXISTS hermes.topic_performance (
    performance_id UUID PRIMARY KEY,
    account TEXT NOT NULL,
    article_id UUID NOT NULL REFERENCES hermes.wechat_articles(article_id) ON DELETE CASCADE,
    topic_id UUID REFERENCES hermes.topics(id) ON DELETE SET NULL,
    stat_date DATE NOT NULL,
    window_label TEXT NOT NULL,
    scoring_version TEXT NOT NULL,
    baseline_version TEXT NOT NULL,
    normalized_score DOUBLE PRECISION,
    read_score DOUBLE PRECISION,
    engagement_score DOUBLE PRECISION,
    share_score DOUBLE PRECISION,
    conversion_score DOUBLE PRECISION,
    confidence DOUBLE PRECISION NOT NULL,
    provisional BOOLEAN NOT NULL DEFAULT false,
    low_sample_size BOOLEAN NOT NULL DEFAULT false,
    metric_snapshot_ids_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    baseline_snapshot_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    diagnosis_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence_refs_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    warnings_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_topic_performance_identity
        UNIQUE (account, article_id, window_label, scoring_version),
    CONSTRAINT chk_topic_performance_scores_range
        CHECK (
            (normalized_score IS NULL OR normalized_score BETWEEN 0 AND 100)
            AND (read_score IS NULL OR read_score BETWEEN 0 AND 100)
            AND (engagement_score IS NULL OR engagement_score BETWEEN 0 AND 100)
            AND (share_score IS NULL OR share_score BETWEEN 0 AND 100)
            AND (conversion_score IS NULL OR conversion_score BETWEEN 0 AND 100)
        ),
    CONSTRAINT chk_topic_performance_confidence_range
        CHECK (confidence >= 0 AND confidence <= 1)
);

CREATE TABLE IF NOT EXISTS hermes.wechat_retrospective_reports (
    report_id UUID PRIMARY KEY,
    account TEXT NOT NULL,
    report_type TEXT NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    article_id UUID REFERENCES hermes.wechat_articles(article_id) ON DELETE SET NULL,
    scoring_version TEXT NOT NULL,
    generation_mode TEXT NOT NULL,
    status TEXT NOT NULL,
    sample_size INTEGER NOT NULL DEFAULT 0,
    low_sample_size BOOLEAN NOT NULL DEFAULT false,
    performance_ids_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    summary_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    narrative_markdown TEXT,
    high_performing_themes_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    low_performing_themes_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    title_patterns_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    recommendations_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence_refs_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    warnings_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_wechat_retrospective_reports_type
        CHECK (report_type IN ('article', 'weekly', 'monthly', 'custom_period')),
    CONSTRAINT chk_wechat_retrospective_reports_generation_mode
        CHECK (generation_mode IN ('structured_only', 'structured_plus_llm')),
    CONSTRAINT chk_wechat_retrospective_reports_status
        CHECK (status IN ('draft', 'completed', 'completed_with_warnings', 'failed')),
    CONSTRAINT chk_wechat_retrospective_reports_period
        CHECK (period_end >= period_start),
    CONSTRAINT chk_wechat_retrospective_reports_sample_size
        CHECK (sample_size >= 0)
);

CREATE TABLE IF NOT EXISTS hermes.topic_optimization_suggestions (
    suggestion_id UUID PRIMARY KEY,
    account TEXT NOT NULL,
    report_id UUID NOT NULL REFERENCES hermes.wechat_retrospective_reports(report_id) ON DELETE CASCADE,
    suggestion_type TEXT NOT NULL,
    target_kind TEXT NOT NULL,
    target_id UUID,
    target_key TEXT,
    current_value_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    proposed_value_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    rationale TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    evidence_refs_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    review_status TEXT NOT NULL,
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ,
    review_note TEXT,
    applied_at TIMESTAMPTZ,
    application_trace_id TEXT,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_topic_optimization_suggestions_type
        CHECK (suggestion_type IN ('revisit', 'cooldown', 'priority_adjust', 'ranking_hint', 'seed_prompt_hint')),
    CONSTRAINT chk_topic_optimization_suggestions_target_kind
        CHECK (target_kind IN ('topic', 'mother_theme', 'column', 'title_pattern', 'account')),
    CONSTRAINT chk_topic_optimization_suggestions_review_status
        CHECK (review_status IN ('pending', 'approved', 'rejected', 'expired', 'applied')),
    CONSTRAINT chk_topic_optimization_suggestions_confidence
        CHECK (confidence >= 0 AND confidence <= 1),
    CONSTRAINT chk_topic_optimization_suggestions_target_ref
        CHECK (target_kind = 'account' OR target_id IS NOT NULL OR target_key IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS hermes.learning_candidates (
    candidate_id UUID PRIMARY KEY,
    account TEXT NOT NULL,
    domain TEXT NOT NULL,
    source_report_id UUID NOT NULL REFERENCES hermes.wechat_retrospective_reports(report_id) ON DELETE CASCADE,
    source_suggestion_ids_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    candidate_type TEXT NOT NULL,
    scope_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    trigger_conditions_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    proposed_policy_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    confidence DOUBLE PRECISION NOT NULL,
    evidence_refs_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL,
    policy_id TEXT,
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ,
    review_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_learning_candidates_type
        CHECK (candidate_type IN ('topic_strategy', 'title_strategy', 'column_strategy', 'writing_constraint', 'review_gate')),
    CONSTRAINT chk_learning_candidates_status
        CHECK (status IN ('pending_review', 'approved', 'rejected', 'exported_to_policy', 'disabled')),
    CONSTRAINT chk_learning_candidates_confidence
        CHECK (confidence >= 0 AND confidence <= 1)
);
```

Indexes should be created with `CREATE INDEX IF NOT EXISTS` using the names listed above. Downgrade should drop indexes first where needed, then drop tables in dependency order.

---

## Migration Notes

- Alembic revision: `0005_wechat_retrospective_topic_optimizer`
- Down revision: `0004_wechat_analytics_ingestion`
- Rollback order:
  1. `learning_candidates`
  2. `topic_optimization_suggestions`
  3. `wechat_retrospective_reports`
  4. `topic_performance`
- Rollback must not drop or alter `topics`, `wechat_articles`, `wechat_article_metric_snapshots`, `wechat_article_channel_daily_metrics`, or any previous feature table.
- Repository code should generate UUIDs rather than relying on DB-side UUID defaults, matching current hermes-db style.
- `updated_at` should be touched explicitly in repository `UPDATE` / `ON CONFLICT DO UPDATE` statements.

---

## Health Inspector Contract

`inspect_wechat_retrospective_topic_optimizer_schema(pool)` should return:

```python
{"wechat_retrospective_topic_optimizer": True}
```

only when all of the following are present:

- Four required tables exist.
- Required columns exist.
- Primary key, unique, check, and FK constraints listed above exist.
- Required indexes exist.
- JSONB fields are present as columns; JSON shape enforcement may live in contracts if SQL checks are too noisy.

Any missing table, column, constraint, FK, or index returns false.
