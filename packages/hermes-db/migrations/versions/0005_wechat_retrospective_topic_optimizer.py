"""add wechat retrospective topic optimizer

Revision ID: 0005_wechat_retrospective_topic_optimizer
Revises: 0004_wechat_analytics_ingestion
Create Date: 2026-06-07
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0005_wechat_retrospective_topic_optimizer"
down_revision: Union[str, None] = "0004_wechat_analytics_ingestion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
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
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_topic_performance_account_stat
        ON hermes.topic_performance(account, stat_date DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_topic_performance_article_stat
        ON hermes.topic_performance(article_id, stat_date DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_topic_performance_topic_stat
        ON hermes.topic_performance(topic_id, stat_date DESC)
        WHERE topic_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_topic_performance_window_stat
        ON hermes.topic_performance(window_label, stat_date DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_topic_performance_scoring_version
        ON hermes.topic_performance(scoring_version)
        """
    )

    op.execute(
        """
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
                CHECK (report_type IN (
                    'article',
                    'weekly',
                    'monthly',
                    'custom_period'
                )),
            CONSTRAINT chk_wechat_retrospective_reports_generation_mode
                CHECK (generation_mode IN (
                    'structured_only',
                    'structured_plus_llm'
                )),
            CONSTRAINT chk_wechat_retrospective_reports_status
                CHECK (status IN (
                    'draft',
                    'completed',
                    'completed_with_warnings',
                    'failed'
                )),
            CONSTRAINT chk_wechat_retrospective_reports_period
                CHECK (period_end >= period_start),
            CONSTRAINT chk_wechat_retrospective_reports_sample_size
                CHECK (sample_size >= 0)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_wechat_retrospective_reports_account_period
        ON hermes.wechat_retrospective_reports(account, period_start DESC, period_end DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_wechat_retrospective_reports_account_type_created
        ON hermes.wechat_retrospective_reports(account, report_type, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_wechat_retrospective_reports_article
        ON hermes.wechat_retrospective_reports(article_id)
        WHERE article_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_wechat_retrospective_reports_status_created
        ON hermes.wechat_retrospective_reports(status, created_at DESC)
        """
    )

    op.execute(
        """
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
                CHECK (suggestion_type IN (
                    'revisit',
                    'cooldown',
                    'priority_adjust',
                    'ranking_hint',
                    'seed_prompt_hint'
                )),
            CONSTRAINT chk_topic_optimization_suggestions_target_kind
                CHECK (target_kind IN (
                    'topic',
                    'mother_theme',
                    'column',
                    'title_pattern',
                    'account'
                )),
            CONSTRAINT chk_topic_optimization_suggestions_review_status
                CHECK (review_status IN (
                    'pending',
                    'approved',
                    'rejected',
                    'expired',
                    'applied'
                )),
            CONSTRAINT chk_topic_optimization_suggestions_confidence
                CHECK (confidence >= 0 AND confidence <= 1),
            CONSTRAINT chk_topic_optimization_suggestions_target_ref
                CHECK (
                    target_kind = 'account'
                    OR target_id IS NOT NULL
                    OR target_key IS NOT NULL
                )
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_topic_optimization_suggestions_account_status_target
        ON hermes.topic_optimization_suggestions(account, review_status, target_kind)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_topic_optimization_suggestions_account_target_key
        ON hermes.topic_optimization_suggestions(account, target_kind, target_key)
        WHERE target_key IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_topic_optimization_suggestions_account_target_id
        ON hermes.topic_optimization_suggestions(account, target_kind, target_id)
        WHERE target_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_topic_optimization_suggestions_report
        ON hermes.topic_optimization_suggestions(report_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_topic_optimization_suggestions_expires_at
        ON hermes.topic_optimization_suggestions(expires_at)
        WHERE expires_at IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_topic_optimization_suggestions_approved_hints
        ON hermes.topic_optimization_suggestions(
            account,
            target_kind,
            review_status,
            expires_at
        )
        WHERE review_status IN ('approved', 'applied')
        """
    )

    op.execute(
        """
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
                CHECK (candidate_type IN (
                    'topic_strategy',
                    'title_strategy',
                    'column_strategy',
                    'writing_constraint',
                    'review_gate'
                )),
            CONSTRAINT chk_learning_candidates_status
                CHECK (status IN (
                    'pending_review',
                    'approved',
                    'rejected',
                    'exported_to_policy',
                    'disabled'
                )),
            CONSTRAINT chk_learning_candidates_confidence
                CHECK (confidence >= 0 AND confidence <= 1)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_learning_candidates_account_status_type
        ON hermes.learning_candidates(account, status, candidate_type)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_learning_candidates_source_report
        ON hermes.learning_candidates(source_report_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_learning_candidates_domain
        ON hermes.learning_candidates(domain)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_learning_candidates_policy_id
        ON hermes.learning_candidates(policy_id)
        WHERE policy_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS hermes.idx_learning_candidates_policy_id")
    op.execute("DROP INDEX IF EXISTS hermes.idx_learning_candidates_domain")
    op.execute("DROP INDEX IF EXISTS hermes.idx_learning_candidates_source_report")
    op.execute("DROP INDEX IF EXISTS hermes.idx_learning_candidates_account_status_type")
    op.execute("DROP TABLE IF EXISTS hermes.learning_candidates")
    op.execute("DROP INDEX IF EXISTS hermes.idx_topic_optimization_suggestions_approved_hints")
    op.execute("DROP INDEX IF EXISTS hermes.idx_topic_optimization_suggestions_expires_at")
    op.execute("DROP INDEX IF EXISTS hermes.idx_topic_optimization_suggestions_report")
    op.execute("DROP INDEX IF EXISTS hermes.idx_topic_optimization_suggestions_account_target_id")
    op.execute("DROP INDEX IF EXISTS hermes.idx_topic_optimization_suggestions_account_target_key")
    op.execute("DROP INDEX IF EXISTS hermes.idx_topic_optimization_suggestions_account_status_target")
    op.execute("DROP TABLE IF EXISTS hermes.topic_optimization_suggestions")
    op.execute("DROP INDEX IF EXISTS hermes.idx_wechat_retrospective_reports_status_created")
    op.execute("DROP INDEX IF EXISTS hermes.idx_wechat_retrospective_reports_article")
    op.execute("DROP INDEX IF EXISTS hermes.idx_wechat_retrospective_reports_account_type_created")
    op.execute("DROP INDEX IF EXISTS hermes.idx_wechat_retrospective_reports_account_period")
    op.execute("DROP TABLE IF EXISTS hermes.wechat_retrospective_reports")
    op.execute("DROP INDEX IF EXISTS hermes.idx_topic_performance_scoring_version")
    op.execute("DROP INDEX IF EXISTS hermes.idx_topic_performance_window_stat")
    op.execute("DROP INDEX IF EXISTS hermes.idx_topic_performance_topic_stat")
    op.execute("DROP INDEX IF EXISTS hermes.idx_topic_performance_article_stat")
    op.execute("DROP INDEX IF EXISTS hermes.idx_topic_performance_account_stat")
    op.execute("DROP TABLE IF EXISTS hermes.topic_performance")
