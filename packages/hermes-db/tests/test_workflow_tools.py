from datetime import datetime
from unittest.mock import MagicMock

import pytest

from hermes_db_mcp.tools.workflow_artifacts import (
    get_workflow_artifact_content,
    list_workflow_artifacts,
    upsert_workflow_artifact,
)
from hermes_db_mcp.tools.workflow_runs import finish_workflow_run, upsert_workflow_run


class FakeAppContext:
    def __init__(self):
        self.pool = MagicMock()


class FakeContext:
    def __init__(self, app_context):
        self.request_context = MagicMock()
        self.request_context.lifespan_context = app_context


@pytest.mark.asyncio
async def test_upsert_workflow_run_success(monkeypatch):
    async def mock_upsert_run(pool, **kwargs):
        return {
            **kwargs,
            "summary": None,
            "failure_reason": None,
            "missing_inputs": [],
            "next_action": None,
            "completed_at": None,
            "created_at": datetime(2026, 6, 3),
            "updated_at": datetime(2026, 6, 3),
            "created": True,
        }

    monkeypatch.setattr(
        "hermes_db_mcp.tools.workflow_runs.workflow_repo.upsert_run",
        mock_upsert_run,
    )

    result = await upsert_workflow_run("run-1", "draft", "running", FakeContext(FakeAppContext()))

    assert result["run_id"] == "run-1"
    assert result["created"] is True


@pytest.mark.asyncio
async def test_finish_workflow_run_not_found(monkeypatch):
    async def mock_finish_run(pool, **kwargs):
        return None

    monkeypatch.setattr(
        "hermes_db_mcp.tools.workflow_runs.workflow_repo.finish_run",
        mock_finish_run,
    )

    result = await finish_workflow_run("run-404", "done", "completed", FakeContext(FakeAppContext()))

    assert result["error"] == "not_found"
    assert result["field"] == "run_id"


@pytest.mark.asyncio
async def test_upsert_workflow_artifact_success(monkeypatch):
    async def mock_upsert_artifact(pool, **kwargs):
        return {
            **kwargs,
            "artifact_id": kwargs["artifact_id"] or "artifact-1",
            "version": 1,
            "created_at": datetime(2026, 6, 3),
            "updated_at": datetime(2026, 6, 3),
        }, True

    monkeypatch.setattr(
        "hermes_db_mcp.tools.workflow_artifacts.workflow_repo.upsert_artifact",
        mock_upsert_artifact,
    )

    result = await upsert_workflow_artifact(
        "run-1",
        "draft",
        "draft",
        "draft",
        "sha256:abc",
        7,
        FakeContext(FakeAppContext()),
        content_text="# Draft",
    )

    assert result["artifact_id"] == "artifact-1"
    assert result["version"] == 1
    assert result["created"] is True
    assert "content_text" not in result


@pytest.mark.asyncio
async def test_list_workflow_artifacts_omits_content_text(monkeypatch):
    async def mock_list_artifacts(pool, **kwargs):
        return [
            {
                "artifact_id": "artifact-1",
                "run_id": kwargs["run_id"],
                "task_id": None,
                "topic_id": None,
                "account": None,
                "stage": "draft",
                "type": "draft",
                "name": "draft",
                "version": 1,
                "parent_artifact_id": None,
                "content_hash": "sha256:abc",
                "content_size_bytes": 7,
                "content_preview": "# Draft",
                "content_ref": None,
                "content_text": "# Draft",
                "metadata": {},
                "created_at": datetime(2026, 6, 3),
                "updated_at": datetime(2026, 6, 3),
            }
        ]

    monkeypatch.setattr(
        "hermes_db_mcp.tools.workflow_artifacts.workflow_repo.list_artifacts",
        mock_list_artifacts,
    )

    result = await list_workflow_artifacts(FakeContext(FakeAppContext()), run_id="run-1")

    assert result["items"][0]["artifact_id"] == "artifact-1"
    assert "content_text" not in result["items"][0]


@pytest.mark.asyncio
async def test_get_workflow_artifact_content_returns_inline(monkeypatch):
    async def mock_get_artifact(pool, artifact_id):
        return {
            "artifact_id": artifact_id,
            "run_id": "run-1",
            "task_id": None,
            "topic_id": None,
            "account": None,
            "stage": "draft",
            "type": "draft",
            "name": "draft",
            "version": 1,
            "parent_artifact_id": None,
            "content_hash": "sha256:abc",
            "content_size_bytes": 7,
            "content_preview": "# Draft",
            "content_ref": None,
            "content_text": "# Draft",
            "metadata": {},
            "created_at": datetime(2026, 6, 3),
            "updated_at": datetime(2026, 6, 3),
        }

    monkeypatch.setattr(
        "hermes_db_mcp.tools.workflow_artifacts.workflow_repo.get_artifact",
        mock_get_artifact,
    )

    result = await get_workflow_artifact_content("artifact-1", FakeContext(FakeAppContext()))

    assert result["content_text"] == "# Draft"
    assert result["content_inline"] is True
