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


def test_wechat_publication_ledger_migration_contains_required_schema_changes():
    migration = Path(
        "migrations/versions/0003_wechat_publication_ledger.py"
    ).read_text()

    assert 'down_revision: Union[str, None] = "0002_wechat_workflow_artifacts"' in migration
    assert "CREATE TABLE IF NOT EXISTS hermes.wechat_articles" in migration
    assert "CREATE TABLE IF NOT EXISTS hermes.wechat_article_external_refs" in migration
    assert "REFERENCES hermes.wechat_workflow_runs(run_id)" in migration
    assert "REFERENCES hermes.workflow_artifacts(artifact_id)" in migration
    assert "uq_wechat_articles_account_idempotency" in migration
    assert "chk_wechat_articles_status" in migration
    assert "chk_wechat_articles_reference_for_published" in migration
    assert "uq_wechat_article_external_ref_active" in migration
    assert "uq_wechat_article_external_ref_article_active" in migration
    assert "idx_wechat_articles_account_status_created" in migration
    assert "idx_wechat_article_refs_type_value_active" in migration


def test_wechat_analytics_ingestion_migration_contains_required_schema_changes():
    migration = Path(
        "migrations/versions/0004_wechat_analytics_ingestion.py"
    ).read_text()

    assert 'down_revision: Union[str, None] = "0003_wechat_publication_ledger"' in migration
    assert "CREATE TABLE IF NOT EXISTS hermes.analytics_import_runs" in migration
    assert "CREATE TABLE IF NOT EXISTS hermes.wechat_article_metric_snapshots" in migration
    assert "CREATE TABLE IF NOT EXISTS hermes.wechat_article_channel_daily_metrics" in migration
    assert "CREATE TABLE IF NOT EXISTS hermes.wechat_article_audience_profiles" not in migration
    assert "REFERENCES hermes.wechat_articles(article_id) ON DELETE CASCADE" in migration
    assert "REFERENCES hermes.analytics_import_runs(import_run_id) ON DELETE SET NULL" in migration
    assert "chk_analytics_import_runs_status" in migration
    assert "chk_analytics_import_runs_counts_nonnegative" in migration
    assert "uq_wechat_article_metric_snapshot_identity" in migration
    assert "chk_wechat_article_metric_snapshot_counts_nonnegative" in migration
    assert "chk_wechat_article_metric_snapshot_completion_rate" in migration
    assert "uq_wechat_article_channel_daily_identity" in migration
    assert "chk_wechat_article_channel_daily_counts_nonnegative" in migration
    assert "idx_analytics_import_runs_account_created" in migration
    assert "idx_wechat_article_metric_snapshots_account_stat" in migration
    assert "idx_wechat_article_metric_snapshots_article_stat" in migration
    assert "idx_wechat_article_metric_snapshots_source_stat" in migration
    assert "idx_wechat_article_channel_daily_account_date" in migration
    assert "idx_wechat_article_channel_daily_article_date" in migration
    assert "DROP TABLE IF EXISTS hermes.wechat_article_channel_daily_metrics" in migration
    assert "DROP TABLE IF EXISTS hermes.wechat_article_metric_snapshots" in migration
    assert "DROP TABLE IF EXISTS hermes.analytics_import_runs" in migration


def test_wechat_retrospective_topic_optimizer_migration_contains_required_schema_changes():
    migration = Path(
        "migrations/versions/0005_wechat_retrospective_topic_optimizer.py"
    ).read_text()

    assert 'revision: str = "0005_wechat_retro_opt"' in migration
    assert 'down_revision: Union[str, None] = "0004_wechat_analytics_ingestion"' in migration
    assert "CREATE TABLE IF NOT EXISTS hermes.topic_performance" in migration
    assert "CREATE TABLE IF NOT EXISTS hermes.wechat_retrospective_reports" in migration
    assert "CREATE TABLE IF NOT EXISTS hermes.topic_optimization_suggestions" in migration
    assert "CREATE TABLE IF NOT EXISTS hermes.learning_candidates" in migration
    assert "REFERENCES hermes.wechat_articles(article_id) ON DELETE CASCADE" in migration
    assert "REFERENCES hermes.topics(id) ON DELETE SET NULL" in migration
    assert "REFERENCES hermes.wechat_articles(article_id) ON DELETE SET NULL" in migration
    assert (
        "REFERENCES hermes.wechat_retrospective_reports(report_id) ON DELETE CASCADE"
        in migration
    )
    assert "uq_topic_performance_identity" in migration
    assert "chk_topic_performance_scores_range" in migration
    assert "chk_topic_performance_confidence_range" in migration
    assert "chk_wechat_retrospective_reports_type" in migration
    assert "chk_wechat_retrospective_reports_generation_mode" in migration
    assert "chk_wechat_retrospective_reports_status" in migration
    assert "chk_wechat_retrospective_reports_period" in migration
    assert "chk_topic_optimization_suggestions_type" in migration
    assert "chk_topic_optimization_suggestions_target_kind" in migration
    assert "chk_topic_optimization_suggestions_review_status" in migration
    assert "chk_topic_optimization_suggestions_target_ref" in migration
    assert "chk_learning_candidates_type" in migration
    assert "chk_learning_candidates_status" in migration
    assert "idx_topic_performance_account_stat" in migration
    assert "idx_topic_performance_article_stat" in migration
    assert "idx_topic_performance_topic_stat" in migration
    assert "idx_wechat_retrospective_reports_account_period" in migration
    assert "idx_wechat_retrospective_reports_account_type_created" in migration
    assert "idx_topic_optimization_suggestions_account_status_target" in migration
    assert "idx_topic_optimization_suggestions_approved_hints" in migration
    assert "idx_learning_candidates_account_status_type" in migration
    assert "idx_learning_candidates_source_report" in migration
    assert "DROP TABLE IF EXISTS hermes.learning_candidates" in migration
    assert "DROP TABLE IF EXISTS hermes.topic_optimization_suggestions" in migration
    assert "DROP TABLE IF EXISTS hermes.wechat_retrospective_reports" in migration
    assert "DROP TABLE IF EXISTS hermes.topic_performance" in migration


def test_agent_self_evolution_foundation_migration_contains_required_schema_changes():
    migration = Path(
        "migrations/versions/0006_agent_self_evolution_foundation.py"
    ).read_text()

    assert 'revision: str = "0006_agent_self_evolution"' in migration
    assert 'down_revision: Union[str, None] = "0005_wechat_retro_opt"' in migration
    assert "CREATE TABLE IF NOT EXISTS hermes.agent_policies" in migration
    assert "CREATE TABLE IF NOT EXISTS hermes.policy_applications" in migration
    assert (
        "REFERENCES hermes.learning_candidates(candidate_id) ON DELETE SET NULL"
        in migration
    )
    assert (
        "REFERENCES hermes.agent_policies(policy_version_id) ON DELETE RESTRICT"
        in migration
    )
    assert "uq_agent_policies_policy_version" in migration
    assert "uq_agent_policies_source_candidate" in migration
    assert "chk_agent_policies_version_positive" in migration
    assert "chk_agent_policies_status" in migration
    assert "chk_agent_policies_policy_type" in migration
    assert "chk_agent_policies_effective_range" in migration
    assert "chk_agent_policies_scope_json_object" in migration
    assert "chk_agent_policies_task_types_json_array" in migration
    assert "chk_policy_applications_version_positive" in migration
    assert "chk_policy_applications_status" in migration
    assert "chk_policy_applications_error_summary_json_object" in migration
    assert "idx_agent_policies_active_lookup" in migration
    assert "idx_agent_policies_source_candidate" in migration
    assert "idx_agent_policies_policy_id" in migration
    assert "idx_agent_policies_scope_gin" in migration
    assert "idx_agent_policies_trigger_conditions_gin" in migration
    assert "idx_policy_applications_run" in migration
    assert "idx_policy_applications_policy" in migration
    assert "idx_policy_applications_policy_version" in migration
    assert "idx_policy_applications_domain_task" in migration
    assert "DROP TABLE IF EXISTS hermes.policy_applications" in migration
    assert "DROP TABLE IF EXISTS hermes.agent_policies" in migration
    assert migration.index("DROP TABLE IF EXISTS hermes.policy_applications") < migration.index(
        "DROP TABLE IF EXISTS hermes.agent_policies"
    )
