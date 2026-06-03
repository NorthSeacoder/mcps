"""add wechat workflow runs and artifacts

Revision ID: 0002_wechat_workflow_artifacts
Revises: 0001_topic_revisit
Create Date: 2026-06-03
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0002_wechat_workflow_artifacts"
down_revision: Union[str, None] = "0001_topic_revisit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
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
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_wechat_workflow_runs_topic_created
        ON hermes.wechat_workflow_runs(topic_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_wechat_workflow_runs_account_created
        ON hermes.wechat_workflow_runs(account, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_wechat_workflow_runs_task_id
        ON hermes.wechat_workflow_runs(task_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_wechat_workflow_runs_status_created
        ON hermes.wechat_workflow_runs(status, created_at DESC)
        """
    )

    op.execute(
        """
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
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_workflow_artifacts_run_created
        ON hermes.workflow_artifacts(run_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_workflow_artifacts_topic_created
        ON hermes.workflow_artifacts(topic_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_workflow_artifacts_account_created
        ON hermes.workflow_artifacts(account, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_workflow_artifacts_type_created
        ON hermes.workflow_artifacts(type, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_workflow_artifacts_stage_name
        ON hermes.workflow_artifacts(run_id, stage, name)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_workflow_artifacts_parent
        ON hermes.workflow_artifacts(parent_artifact_id)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS hermes.idx_workflow_artifacts_parent")
    op.execute("DROP INDEX IF EXISTS hermes.idx_workflow_artifacts_stage_name")
    op.execute("DROP INDEX IF EXISTS hermes.idx_workflow_artifacts_type_created")
    op.execute("DROP INDEX IF EXISTS hermes.idx_workflow_artifacts_account_created")
    op.execute("DROP INDEX IF EXISTS hermes.idx_workflow_artifacts_topic_created")
    op.execute("DROP INDEX IF EXISTS hermes.idx_workflow_artifacts_run_created")
    op.execute("DROP TABLE IF EXISTS hermes.workflow_artifacts")
    op.execute("DROP INDEX IF EXISTS hermes.idx_wechat_workflow_runs_status_created")
    op.execute("DROP INDEX IF EXISTS hermes.idx_wechat_workflow_runs_task_id")
    op.execute("DROP INDEX IF EXISTS hermes.idx_wechat_workflow_runs_account_created")
    op.execute("DROP INDEX IF EXISTS hermes.idx_wechat_workflow_runs_topic_created")
    op.execute("DROP TABLE IF EXISTS hermes.wechat_workflow_runs")
