from pathlib import Path


def test_topic_revisit_migration_contains_required_schema_changes():
    migration = Path(
        "migrations/versions/0001_add_revisit_of_mother_theme.py"
    ).read_text()

    assert "ADD COLUMN IF NOT EXISTS revisit_of UUID" in migration
    assert "pg_constraint" in migration
    assert "ADD CONSTRAINT fk_topics_revisit_of" in migration
    assert "REFERENCES hermes.topics(id)" in migration
    assert "ON DELETE SET NULL" in migration
    assert "ADD COLUMN IF NOT EXISTS mother_theme TEXT" in migration
    assert "chk_topics_revisit_of_not_self" in migration
    assert "CHECK (revisit_of IS NULL OR revisit_of <> id)" in migration
    assert "CREATE INDEX IF NOT EXISTS idx_topics_revisit_of" in migration


def test_workflow_artifact_migration_contains_required_schema_changes():
    migration = Path(
        "migrations/versions/0002_wechat_workflow_artifacts.py"
    ).read_text()

    assert 'down_revision: Union[str, None] = "0001_topic_revisit"' in migration
    assert "CREATE TABLE IF NOT EXISTS hermes.wechat_workflow_runs" in migration
    assert "CREATE TABLE IF NOT EXISTS hermes.workflow_artifacts" in migration
    assert "REFERENCES hermes.wechat_workflow_runs(run_id)" in migration
    assert "REFERENCES hermes.topics(id) ON DELETE SET NULL" in migration
    assert "chk_workflow_artifacts_content_present" in migration
    assert "uq_workflow_artifact_logical_version" in migration
    assert "uq_workflow_artifact_logical_hash" in migration
    assert "idx_workflow_artifacts_run_created" in migration
    assert "idx_workflow_artifacts_stage_name" in migration
