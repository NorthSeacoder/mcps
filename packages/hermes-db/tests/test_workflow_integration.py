import pytest

from hermes_db_mcp.repositories import workflow_repo


@pytest.mark.asyncio
async def test_workflow_run_and_artifact_roundtrip(db_pool):
    run_id = "pytest-wechat-artifact-run"
    artifact_id = "pytest-wechat-artifact-draft"

    async with db_pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM hermes.workflow_artifacts WHERE artifact_id = $1",
            artifact_id,
        )
        await conn.execute(
            "DELETE FROM hermes.wechat_workflow_runs WHERE run_id = $1",
            run_id,
        )

    try:
        run = await workflow_repo.upsert_run(
            db_pool,
            run_id=run_id,
            phase="draft",
            current_stage="draft",
            status="running",
            dry_run=True,
            metadata={"source": "pytest"},
        )

        assert run["run_id"] == run_id
        assert run["created"] is True

        artifact, created = await workflow_repo.upsert_artifact(
            db_pool,
            artifact_id=artifact_id,
            run_id=run_id,
            stage="draft",
            type="draft",
            name="draft",
            content_hash="sha256:pytest-draft",
            content_size_bytes=7,
            content_preview="# Draft",
            content_text="# Draft",
            metadata={"source": "pytest"},
        )

        assert created is True
        assert artifact["version"] == 1

        listed = await workflow_repo.list_artifacts(db_pool, run_id=run_id)

        assert len(listed) == 1
        assert listed[0]["artifact_id"] == artifact_id
        assert "content_text" not in listed[0]

        content = await workflow_repo.get_artifact(db_pool, artifact_id=artifact_id)

        assert content["content_text"] == "# Draft"

        finished = await workflow_repo.finish_run(
            db_pool,
            run_id=run_id,
            phase="done",
            status="completed",
            summary="pytest complete",
        )

        assert finished["status"] == "completed"
    finally:
        async with db_pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM hermes.workflow_artifacts WHERE artifact_id = $1",
                artifact_id,
            )
            await conn.execute(
                "DELETE FROM hermes.wechat_workflow_runs WHERE run_id = $1",
                run_id,
            )
