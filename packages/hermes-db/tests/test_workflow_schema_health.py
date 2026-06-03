from unittest.mock import AsyncMock

import pytest

from hermes_db_mcp.services.schema import inspect_workflow_schema


class FakeRow(dict):
    def __getitem__(self, key):
        return self.get(key)


class FakeAcquire:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakePool:
    def __init__(self, fetch_results):
        self.conn = AsyncMock()
        self.conn.fetch = AsyncMock(side_effect=fetch_results)

    def acquire(self):
        return FakeAcquire(self.conn)


@pytest.mark.asyncio
async def test_inspect_workflow_schema_returns_true_for_complete_schema():
    pool = FakePool(
        [
            [FakeRow(column_name=name) for name in {
                "run_id", "task_id", "topic_id", "account", "phase",
                "current_stage", "status", "dry_run", "metadata", "started_at",
                "completed_at", "created_at", "updated_at",
            }],
            [FakeRow(column_name=name) for name in {
                "artifact_id", "run_id", "stage", "type", "name", "version",
                "parent_artifact_id", "content_hash", "content_size_bytes",
                "content_preview", "content_text", "content_ref", "metadata",
                "created_at", "updated_at",
            }],
            [FakeRow(conname=name) for name in {
                "workflow_artifacts_run_id_fkey",
                "workflow_artifacts_parent_artifact_id_fkey",
                "chk_workflow_artifacts_content_present",
                "chk_workflow_artifacts_version_positive",
                "chk_workflow_artifacts_content_size_nonnegative",
                "uq_workflow_artifact_logical_version",
                "uq_workflow_artifact_logical_hash",
            }],
            [FakeRow(indexname=name) for name in {
                "idx_wechat_workflow_runs_topic_created",
                "idx_wechat_workflow_runs_account_created",
                "idx_workflow_artifacts_run_created",
                "idx_workflow_artifacts_topic_created",
                "idx_workflow_artifacts_account_created",
                "idx_workflow_artifacts_type_created",
                "idx_workflow_artifacts_stage_name",
            }],
        ]
    )

    assert await inspect_workflow_schema(pool) == {
        "workflow_runs": True,
        "workflow_artifacts": True,
    }


@pytest.mark.asyncio
async def test_inspect_workflow_schema_reflects_missing_tables():
    pool = FakePool([[], [], [], []])

    assert await inspect_workflow_schema(pool) == {
        "workflow_runs": False,
        "workflow_artifacts": False,
    }
