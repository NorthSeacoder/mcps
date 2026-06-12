"""add agent self evolution foundation

Revision ID: 0006_agent_self_evolution_foundation
Revises: 0005_wechat_retro_opt
Create Date: 2026-06-11
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0006_agent_self_evolution_foundation"
down_revision: Union[str, None] = "0005_wechat_retro_opt"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS hermes.agent_policies (
            policy_version_id UUID PRIMARY KEY,
            policy_id UUID NOT NULL,
            version INTEGER NOT NULL,
            domain TEXT NOT NULL,
            policy_type TEXT NOT NULL,
            status TEXT NOT NULL,
            scope_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            task_types_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            decision_points_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            trigger_conditions_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            policy_body_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            priority INTEGER NOT NULL DEFAULT 0,
            precedence TEXT NOT NULL DEFAULT 'scope_specific_over_global',
            source_candidate_id UUID REFERENCES hermes.learning_candidates(candidate_id) ON DELETE SET NULL,
            source_policy_version_id UUID REFERENCES hermes.agent_policies(policy_version_id) ON DELETE SET NULL,
            evidence_refs_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            approved_by TEXT NOT NULL,
            approved_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            effective_from TIMESTAMPTZ,
            effective_until TIMESTAMPTZ,
            disable_reason TEXT,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_agent_policies_policy_version UNIQUE (policy_id, version),
            CONSTRAINT chk_agent_policies_version_positive CHECK (version >= 1),
            CONSTRAINT chk_agent_policies_status
                CHECK (status IN (
                    'draft',
                    'active',
                    'superseded',
                    'disabled',
                    'rolled_back',
                    'expired'
                )),
            CONSTRAINT chk_agent_policies_policy_type
                CHECK (policy_type IN (
                    'topic_strategy',
                    'title_strategy',
                    'column_strategy',
                    'writing_constraint',
                    'review_gate',
                    'sop'
                )),
            CONSTRAINT chk_agent_policies_effective_range
                CHECK (
                    effective_until IS NULL
                    OR effective_from IS NULL
                    OR effective_until > effective_from
                ),
            CONSTRAINT chk_agent_policies_scope_json_object
                CHECK (jsonb_typeof(scope_json) = 'object'),
            CONSTRAINT chk_agent_policies_task_types_json_array
                CHECK (jsonb_typeof(task_types_json) = 'array'),
            CONSTRAINT chk_agent_policies_decision_points_json_array
                CHECK (jsonb_typeof(decision_points_json) = 'array'),
            CONSTRAINT chk_agent_policies_trigger_conditions_json_object
                CHECK (jsonb_typeof(trigger_conditions_json) = 'object'),
            CONSTRAINT chk_agent_policies_policy_body_json_object
                CHECK (jsonb_typeof(policy_body_json) = 'object'),
            CONSTRAINT chk_agent_policies_evidence_refs_json_object
                CHECK (jsonb_typeof(evidence_refs_json) = 'object'),
            CONSTRAINT chk_agent_policies_metadata_json_object
                CHECK (jsonb_typeof(metadata_json) = 'object')
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_policies_source_candidate
        ON hermes.agent_policies(source_candidate_id)
        WHERE source_candidate_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_agent_policies_active_lookup
        ON hermes.agent_policies(domain, policy_type, status, priority DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_agent_policies_source_candidate
        ON hermes.agent_policies(source_candidate_id)
        WHERE source_candidate_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_agent_policies_policy_id
        ON hermes.agent_policies(policy_id, version DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_agent_policies_scope_gin
        ON hermes.agent_policies USING GIN (scope_json)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_agent_policies_trigger_conditions_gin
        ON hermes.agent_policies USING GIN (trigger_conditions_json)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS hermes.policy_applications (
            application_id UUID PRIMARY KEY,
            run_id TEXT,
            domain TEXT NOT NULL,
            agent_name TEXT NOT NULL,
            task_type TEXT NOT NULL,
            decision_point TEXT NOT NULL,
            policy_id UUID NOT NULL,
            policy_version_id UUID NOT NULL REFERENCES hermes.agent_policies(policy_version_id) ON DELETE RESTRICT,
            policy_version INTEGER NOT NULL,
            scope_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            matched_conditions_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            application_status TEXT NOT NULL,
            applied_action_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            outcome_summary_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            warning TEXT,
            error_summary_json JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_policy_applications_version_positive CHECK (policy_version >= 1),
            CONSTRAINT chk_policy_applications_status
                CHECK (application_status IN (
                    'applied',
                    'skipped',
                    'blocked',
                    'failed'
                )),
            CONSTRAINT chk_policy_applications_scope_json_object
                CHECK (jsonb_typeof(scope_json) = 'object'),
            CONSTRAINT chk_policy_applications_matched_conditions_json_object
                CHECK (jsonb_typeof(matched_conditions_json) = 'object'),
            CONSTRAINT chk_policy_applications_applied_action_json_object
                CHECK (jsonb_typeof(applied_action_json) = 'object'),
            CONSTRAINT chk_policy_applications_outcome_summary_json_object
                CHECK (jsonb_typeof(outcome_summary_json) = 'object'),
            CONSTRAINT chk_policy_applications_error_summary_json_object
                CHECK (error_summary_json IS NULL OR jsonb_typeof(error_summary_json) = 'object')
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_policy_applications_run
        ON hermes.policy_applications(run_id)
        WHERE run_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_policy_applications_policy
        ON hermes.policy_applications(policy_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_policy_applications_policy_version
        ON hermes.policy_applications(policy_version_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_policy_applications_domain_task
        ON hermes.policy_applications(domain, task_type, created_at DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS hermes.idx_policy_applications_domain_task")
    op.execute("DROP INDEX IF EXISTS hermes.idx_policy_applications_policy_version")
    op.execute("DROP INDEX IF EXISTS hermes.idx_policy_applications_policy")
    op.execute("DROP INDEX IF EXISTS hermes.idx_policy_applications_run")
    op.execute("DROP TABLE IF EXISTS hermes.policy_applications")
    op.execute("DROP INDEX IF EXISTS hermes.idx_agent_policies_trigger_conditions_gin")
    op.execute("DROP INDEX IF EXISTS hermes.idx_agent_policies_scope_gin")
    op.execute("DROP INDEX IF EXISTS hermes.idx_agent_policies_policy_id")
    op.execute("DROP INDEX IF EXISTS hermes.idx_agent_policies_source_candidate")
    op.execute("DROP INDEX IF EXISTS hermes.idx_agent_policies_active_lookup")
    op.execute("DROP INDEX IF EXISTS hermes.uq_agent_policies_source_candidate")
    op.execute("DROP TABLE IF EXISTS hermes.agent_policies")
