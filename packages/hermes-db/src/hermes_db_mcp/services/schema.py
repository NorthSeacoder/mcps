from __future__ import annotations

from collections.abc import Iterable

import asyncpg


async def _fetch_column_names(pool: asyncpg.Pool, table_schema: str, table_name: str) -> set[str]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = $1 AND table_name = $2
            """,
            table_schema,
            table_name,
        )
    return {row["column_name"] for row in rows}


async def _fetch_constraint_names(
    pool: asyncpg.Pool,
    constraint_names: Iterable[str],
    table_schema: str = "hermes",
    table_name: str = "topics",
) -> set[str]:
    wanted = list(constraint_names)
    if not wanted:
        return set()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT conname
            FROM pg_constraint
            WHERE connamespace = $1::regnamespace
              AND conrelid = $2::regclass
              AND conname = ANY($3::text[])
            """,
            table_schema,
            f"{table_schema}.{table_name}",
            wanted,
        )
    return {row["conname"] for row in rows}


async def inspect_topic_schema(pool: asyncpg.Pool) -> dict[str, bool]:
    columns = await _fetch_column_names(pool, "hermes", "topics")
    constraints = await _fetch_constraint_names(
        pool,
        (
            "fk_topics_revisit_of",
            "chk_topics_revisit_of_not_self",
        ),
    )

    return {
        "topic_bucket": "embedding" in columns,
        "topic_revisit_of": {"revisit_of", "mother_theme"}.issubset(columns)
        and "fk_topics_revisit_of" in constraints
        and "chk_topics_revisit_of_not_self" in constraints,
        "list_revisit_chain": "revisit_of" in columns,
    }


async def _fetch_index_names(
    pool: asyncpg.Pool,
    table_schema: str,
    index_names: Iterable[str],
) -> set[str]:
    wanted = list(index_names)
    if not wanted:
        return set()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT indexname
            FROM pg_indexes
            WHERE schemaname = $1
              AND indexname = ANY($2::text[])
            """,
            table_schema,
            wanted,
        )
    return {row["indexname"] for row in rows}


async def inspect_workflow_schema(pool: asyncpg.Pool) -> dict[str, bool]:
    run_columns = await _fetch_column_names(pool, "hermes", "wechat_workflow_runs")
    artifact_columns = await _fetch_column_names(pool, "hermes", "workflow_artifacts")
    artifact_constraints = await _fetch_constraint_names(
        pool,
        (
            "workflow_artifacts_pkey",
            "workflow_artifacts_run_id_fkey",
            "workflow_artifacts_parent_artifact_id_fkey",
            "chk_workflow_artifacts_content_present",
            "chk_workflow_artifacts_version_positive",
            "chk_workflow_artifacts_content_size_nonnegative",
            "uq_workflow_artifact_logical_version",
            "uq_workflow_artifact_logical_hash",
        ),
        table_name="workflow_artifacts",
    )
    indexes = await _fetch_index_names(
        pool,
        "hermes",
        (
            "idx_wechat_workflow_runs_topic_created",
            "idx_wechat_workflow_runs_account_created",
            "idx_workflow_artifacts_run_created",
            "idx_workflow_artifacts_topic_created",
            "idx_workflow_artifacts_account_created",
            "idx_workflow_artifacts_type_created",
            "idx_workflow_artifacts_stage_name",
        ),
    )

    run_required = {
        "run_id",
        "task_id",
        "topic_id",
        "account",
        "phase",
        "current_stage",
        "status",
        "dry_run",
        "metadata",
        "started_at",
        "completed_at",
        "created_at",
        "updated_at",
    }
    artifact_required = {
        "artifact_id",
        "run_id",
        "stage",
        "type",
        "name",
        "version",
        "parent_artifact_id",
        "content_hash",
        "content_size_bytes",
        "content_preview",
        "content_text",
        "content_ref",
        "metadata",
        "created_at",
        "updated_at",
    }

    return {
        "workflow_runs": run_required.issubset(run_columns),
        "workflow_artifacts": artifact_required.issubset(artifact_columns)
        and {
            "workflow_artifacts_run_id_fkey",
            "workflow_artifacts_parent_artifact_id_fkey",
            "chk_workflow_artifacts_content_present",
            "chk_workflow_artifacts_version_positive",
            "chk_workflow_artifacts_content_size_nonnegative",
            "uq_workflow_artifact_logical_version",
            "uq_workflow_artifact_logical_hash",
        }.issubset(artifact_constraints)
        and {
            "idx_workflow_artifacts_run_created",
            "idx_workflow_artifacts_topic_created",
            "idx_workflow_artifacts_account_created",
            "idx_workflow_artifacts_type_created",
            "idx_workflow_artifacts_stage_name",
        }.issubset(indexes),
    }


async def inspect_wechat_publication_ledger_schema(pool: asyncpg.Pool) -> dict[str, bool]:
    article_columns = await _fetch_column_names(pool, "hermes", "wechat_articles")
    ref_columns = await _fetch_column_names(pool, "hermes", "wechat_article_external_refs")
    article_constraints = await _fetch_constraint_names(
        pool,
        (
            "wechat_articles_pkey",
            "uq_wechat_articles_account_idempotency",
            "chk_wechat_articles_status",
            "chk_wechat_articles_reference_for_published",
        ),
        table_name="wechat_articles",
    )
    ref_constraints = await _fetch_constraint_names(
        pool,
        (
            "wechat_article_external_refs_pkey",
            "chk_wechat_article_external_refs_type",
            "chk_wechat_article_external_refs_value_nonempty",
        ),
        table_name="wechat_article_external_refs",
    )
    indexes = await _fetch_index_names(
        pool,
        "hermes",
        (
            "idx_wechat_articles_account_created",
            "idx_wechat_articles_account_status_created",
            "idx_wechat_articles_topic_created",
            "idx_wechat_articles_run_id",
            "idx_wechat_articles_published_url",
            "idx_wechat_articles_canonical_url",
            "idx_wechat_articles_publish_target_created",
            "uq_wechat_article_external_ref_active",
            "uq_wechat_article_external_ref_article_active",
            "idx_wechat_article_refs_article_created",
            "idx_wechat_article_refs_type_value_active",
        ),
    )

    article_required = {
        "article_id",
        "publication_idempotency_key",
        "account",
        "topic_id",
        "run_id",
        "task_id",
        "draft_artifact_id",
        "published_artifact_id",
        "publish_artifact_id",
        "status",
        "dry_run",
        "title",
        "published_url",
        "canonical_url",
        "publish_target",
        "external_reference",
        "metadata",
        "published_at",
        "created_at",
        "updated_at",
    }
    ref_required = {
        "ref_id",
        "article_id",
        "ref_type",
        "ref_value",
        "ref_source",
        "is_primary",
        "metadata",
        "superseded_at",
        "created_at",
        "updated_at",
    }

    return {
        "wechat_publication_ledger": article_required.issubset(article_columns)
        and ref_required.issubset(ref_columns)
        and {
            "uq_wechat_articles_account_idempotency",
            "chk_wechat_articles_status",
            "chk_wechat_articles_reference_for_published",
        }.issubset(article_constraints)
        and {
            "chk_wechat_article_external_refs_type",
            "chk_wechat_article_external_refs_value_nonempty",
        }.issubset(ref_constraints)
        and {
            "idx_wechat_articles_account_created",
            "idx_wechat_articles_account_status_created",
            "idx_wechat_articles_topic_created",
            "idx_wechat_articles_run_id",
            "idx_wechat_articles_published_url",
            "idx_wechat_articles_canonical_url",
            "idx_wechat_articles_publish_target_created",
            "uq_wechat_article_external_ref_active",
            "uq_wechat_article_external_ref_article_active",
            "idx_wechat_article_refs_article_created",
            "idx_wechat_article_refs_type_value_active",
        }.issubset(indexes),
    }


async def inspect_wechat_analytics_ingestion_schema(pool: asyncpg.Pool) -> dict[str, bool]:
    import_columns = await _fetch_column_names(pool, "hermes", "analytics_import_runs")
    snapshot_columns = await _fetch_column_names(pool, "hermes", "wechat_article_metric_snapshots")
    channel_columns = await _fetch_column_names(
        pool,
        "hermes",
        "wechat_article_channel_daily_metrics",
    )
    import_constraints = await _fetch_constraint_names(
        pool,
        (
            "analytics_import_runs_pkey",
            "chk_analytics_import_runs_status",
            "chk_analytics_import_runs_counts_nonnegative",
        ),
        table_name="analytics_import_runs",
    )
    snapshot_constraints = await _fetch_constraint_names(
        pool,
        (
            "wechat_article_metric_snapshots_pkey",
            "wechat_article_metric_snapshots_article_id_fkey",
            "wechat_article_metric_snapshots_import_run_id_fkey",
            "uq_wechat_article_metric_snapshot_identity",
            "chk_wechat_article_metric_snapshot_counts_nonnegative",
            "chk_wechat_article_metric_snapshot_completion_rate",
        ),
        table_name="wechat_article_metric_snapshots",
    )
    channel_constraints = await _fetch_constraint_names(
        pool,
        (
            "wechat_article_channel_daily_metrics_pkey",
            "wechat_article_channel_daily_metrics_article_id_fkey",
            "wechat_article_channel_daily_metrics_import_run_id_fkey",
            "uq_wechat_article_channel_daily_identity",
            "chk_wechat_article_channel_daily_counts_nonnegative",
        ),
        table_name="wechat_article_channel_daily_metrics",
    )
    indexes = await _fetch_index_names(
        pool,
        "hermes",
        (
            "idx_analytics_import_runs_account_created",
            "idx_analytics_import_runs_source_created",
            "idx_analytics_import_runs_status_created",
            "idx_wechat_article_metric_snapshots_account_stat",
            "idx_wechat_article_metric_snapshots_article_stat",
            "idx_wechat_article_metric_snapshots_window_stat",
            "idx_wechat_article_metric_snapshots_source_stat",
            "idx_wechat_article_metric_snapshots_import_run",
            "idx_wechat_article_channel_daily_account_date",
            "idx_wechat_article_channel_daily_article_date",
            "idx_wechat_article_channel_daily_channel_date",
            "idx_wechat_article_channel_daily_import_run",
        ),
    )

    import_required = {
        "import_run_id",
        "account",
        "source",
        "status",
        "total_rows",
        "created",
        "updated",
        "skipped",
        "unmatched",
        "errors",
        "metadata",
        "created_at",
        "updated_at",
    }
    snapshot_required = {
        "snapshot_id",
        "article_id",
        "account",
        "stat_date",
        "window_label",
        "source",
        "read_user_count",
        "average_stay_seconds",
        "completion_rate",
        "new_follow_user_count",
        "share_user_count",
        "wow_user_count",
        "like_user_count",
        "favorite_user_count",
        "reward_cents",
        "comment_count",
        "delivered_user_count",
        "account_message_read_user_count",
        "first_share_user_count",
        "total_share_user_count",
        "share_generated_read_user_count",
        "missing_fields",
        "raw_json",
        "import_run_id",
        "collected_at",
        "created_at",
        "updated_at",
    }
    channel_required = {
        "metric_id",
        "article_id",
        "account",
        "metric_date",
        "channel",
        "source",
        "read_user_count",
        "share_user_count",
        "raw_json",
        "import_run_id",
        "created_at",
        "updated_at",
    }

    return {
        "wechat_analytics_ingestion": import_required.issubset(import_columns)
        and snapshot_required.issubset(snapshot_columns)
        and channel_required.issubset(channel_columns)
        and {
            "chk_analytics_import_runs_status",
            "chk_analytics_import_runs_counts_nonnegative",
        }.issubset(import_constraints)
        and {
            "wechat_article_metric_snapshots_article_id_fkey",
            "wechat_article_metric_snapshots_import_run_id_fkey",
            "uq_wechat_article_metric_snapshot_identity",
            "chk_wechat_article_metric_snapshot_counts_nonnegative",
            "chk_wechat_article_metric_snapshot_completion_rate",
        }.issubset(snapshot_constraints)
        and {
            "wechat_article_channel_daily_metrics_article_id_fkey",
            "wechat_article_channel_daily_metrics_import_run_id_fkey",
            "uq_wechat_article_channel_daily_identity",
            "chk_wechat_article_channel_daily_counts_nonnegative",
        }.issubset(channel_constraints)
        and {
            "idx_analytics_import_runs_account_created",
            "idx_analytics_import_runs_source_created",
            "idx_analytics_import_runs_status_created",
            "idx_wechat_article_metric_snapshots_account_stat",
            "idx_wechat_article_metric_snapshots_article_stat",
            "idx_wechat_article_metric_snapshots_window_stat",
            "idx_wechat_article_metric_snapshots_source_stat",
            "idx_wechat_article_metric_snapshots_import_run",
            "idx_wechat_article_channel_daily_account_date",
            "idx_wechat_article_channel_daily_article_date",
            "idx_wechat_article_channel_daily_channel_date",
            "idx_wechat_article_channel_daily_import_run",
        }.issubset(indexes),
    }


async def inspect_wechat_retrospective_topic_optimizer_schema(
    pool: asyncpg.Pool,
) -> dict[str, bool]:
    performance_columns = await _fetch_column_names(pool, "hermes", "topic_performance")
    report_columns = await _fetch_column_names(pool, "hermes", "wechat_retrospective_reports")
    suggestion_columns = await _fetch_column_names(
        pool,
        "hermes",
        "topic_optimization_suggestions",
    )
    candidate_columns = await _fetch_column_names(pool, "hermes", "learning_candidates")
    performance_constraints = await _fetch_constraint_names(
        pool,
        (
            "topic_performance_pkey",
            "topic_performance_article_id_fkey",
            "topic_performance_topic_id_fkey",
            "uq_topic_performance_identity",
            "chk_topic_performance_scores_range",
            "chk_topic_performance_confidence_range",
        ),
        table_name="topic_performance",
    )
    report_constraints = await _fetch_constraint_names(
        pool,
        (
            "wechat_retrospective_reports_pkey",
            "wechat_retrospective_reports_article_id_fkey",
            "chk_wechat_retrospective_reports_type",
            "chk_wechat_retrospective_reports_generation_mode",
            "chk_wechat_retrospective_reports_status",
            "chk_wechat_retrospective_reports_period",
            "chk_wechat_retrospective_reports_sample_size",
        ),
        table_name="wechat_retrospective_reports",
    )
    suggestion_constraints = await _fetch_constraint_names(
        pool,
        (
            "topic_optimization_suggestions_pkey",
            "topic_optimization_suggestions_report_id_fkey",
            "chk_topic_optimization_suggestions_type",
            "chk_topic_optimization_suggestions_target_kind",
            "chk_topic_optimization_suggestions_review_status",
            "chk_topic_optimization_suggestions_confidence",
            "chk_topic_optimization_suggestions_target_ref",
        ),
        table_name="topic_optimization_suggestions",
    )
    candidate_constraints = await _fetch_constraint_names(
        pool,
        (
            "learning_candidates_pkey",
            "learning_candidates_source_report_id_fkey",
            "chk_learning_candidates_type",
            "chk_learning_candidates_status",
            "chk_learning_candidates_confidence",
        ),
        table_name="learning_candidates",
    )
    indexes = await _fetch_index_names(
        pool,
        "hermes",
        (
            "idx_topic_performance_account_stat",
            "idx_topic_performance_article_stat",
            "idx_topic_performance_topic_stat",
            "idx_topic_performance_window_stat",
            "idx_topic_performance_scoring_version",
            "idx_wechat_retrospective_reports_account_period",
            "idx_wechat_retrospective_reports_account_type_created",
            "idx_wechat_retrospective_reports_article",
            "idx_wechat_retrospective_reports_status_created",
            "idx_topic_optimization_suggestions_account_status_target",
            "idx_topic_optimization_suggestions_account_target_key",
            "idx_topic_optimization_suggestions_account_target_id",
            "idx_topic_optimization_suggestions_report",
            "idx_topic_optimization_suggestions_expires_at",
            "idx_topic_optimization_suggestions_approved_hints",
            "idx_learning_candidates_account_status_type",
            "idx_learning_candidates_source_report",
            "idx_learning_candidates_domain",
            "idx_learning_candidates_policy_id",
        ),
    )

    performance_required = {
        "performance_id",
        "account",
        "article_id",
        "topic_id",
        "stat_date",
        "window_label",
        "scoring_version",
        "baseline_version",
        "normalized_score",
        "read_score",
        "engagement_score",
        "share_score",
        "conversion_score",
        "confidence",
        "provisional",
        "low_sample_size",
        "metric_snapshot_ids_json",
        "baseline_snapshot_json",
        "diagnosis_json",
        "evidence_refs_json",
        "warnings_json",
        "created_at",
        "updated_at",
    }

    report_required = {
        "report_id",
        "account",
        "report_type",
        "period_start",
        "period_end",
        "article_id",
        "scoring_version",
        "generation_mode",
        "status",
        "sample_size",
        "low_sample_size",
        "performance_ids_json",
        "summary_json",
        "narrative_markdown",
        "high_performing_themes_json",
        "low_performing_themes_json",
        "title_patterns_json",
        "recommendations_json",
        "evidence_refs_json",
        "warnings_json",
        "created_at",
        "updated_at",
    }
    suggestion_required = {
        "suggestion_id",
        "account",
        "report_id",
        "suggestion_type",
        "target_kind",
        "target_id",
        "target_key",
        "current_value_json",
        "proposed_value_json",
        "rationale",
        "confidence",
        "evidence_refs_json",
        "review_status",
        "reviewed_by",
        "reviewed_at",
        "review_note",
        "applied_at",
        "application_trace_id",
        "expires_at",
        "created_at",
        "updated_at",
    }
    candidate_required = {
        "candidate_id",
        "account",
        "domain",
        "source_report_id",
        "source_suggestion_ids_json",
        "candidate_type",
        "scope_json",
        "trigger_conditions_json",
        "proposed_policy_json",
        "confidence",
        "evidence_refs_json",
        "status",
        "policy_id",
        "reviewed_by",
        "reviewed_at",
        "review_note",
        "created_at",
        "updated_at",
    }

    return {
        "wechat_retrospective_topic_optimizer": performance_required.issubset(
            performance_columns
        )
        and report_required.issubset(report_columns)
        and suggestion_required.issubset(suggestion_columns)
        and candidate_required.issubset(candidate_columns)
        and {
            "topic_performance_pkey",
            "topic_performance_article_id_fkey",
            "topic_performance_topic_id_fkey",
            "uq_topic_performance_identity",
            "chk_topic_performance_scores_range",
            "chk_topic_performance_confidence_range",
        }.issubset(performance_constraints)
        and {
            "wechat_retrospective_reports_pkey",
            "wechat_retrospective_reports_article_id_fkey",
            "chk_wechat_retrospective_reports_type",
            "chk_wechat_retrospective_reports_generation_mode",
            "chk_wechat_retrospective_reports_status",
            "chk_wechat_retrospective_reports_period",
            "chk_wechat_retrospective_reports_sample_size",
        }.issubset(report_constraints)
        and {
            "topic_optimization_suggestions_pkey",
            "topic_optimization_suggestions_report_id_fkey",
            "chk_topic_optimization_suggestions_type",
            "chk_topic_optimization_suggestions_target_kind",
            "chk_topic_optimization_suggestions_review_status",
            "chk_topic_optimization_suggestions_confidence",
            "chk_topic_optimization_suggestions_target_ref",
        }.issubset(suggestion_constraints)
        and {
            "learning_candidates_pkey",
            "learning_candidates_source_report_id_fkey",
            "chk_learning_candidates_type",
            "chk_learning_candidates_status",
            "chk_learning_candidates_confidence",
        }.issubset(candidate_constraints)
        and {
            "idx_topic_performance_account_stat",
            "idx_topic_performance_article_stat",
            "idx_topic_performance_topic_stat",
            "idx_topic_performance_window_stat",
            "idx_topic_performance_scoring_version",
            "idx_wechat_retrospective_reports_account_period",
            "idx_wechat_retrospective_reports_account_type_created",
            "idx_wechat_retrospective_reports_article",
            "idx_wechat_retrospective_reports_status_created",
            "idx_topic_optimization_suggestions_account_status_target",
            "idx_topic_optimization_suggestions_account_target_key",
            "idx_topic_optimization_suggestions_account_target_id",
            "idx_topic_optimization_suggestions_report",
            "idx_topic_optimization_suggestions_expires_at",
            "idx_topic_optimization_suggestions_approved_hints",
            "idx_learning_candidates_account_status_type",
            "idx_learning_candidates_source_report",
            "idx_learning_candidates_domain",
            "idx_learning_candidates_policy_id",
        }.issubset(indexes),
    }


async def inspect_agent_self_evolution_foundation_schema(
    pool: asyncpg.Pool,
) -> dict[str, bool]:
    policy_columns = await _fetch_column_names(pool, "hermes", "agent_policies")
    application_columns = await _fetch_column_names(pool, "hermes", "policy_applications")
    candidate_columns = await _fetch_column_names(pool, "hermes", "learning_candidates")
    policy_constraints = await _fetch_constraint_names(
        pool,
        (
            "agent_policies_pkey",
            "agent_policies_source_candidate_id_fkey",
            "agent_policies_source_policy_version_id_fkey",
            "uq_agent_policies_policy_version",
            "chk_agent_policies_version_positive",
            "chk_agent_policies_status",
            "chk_agent_policies_policy_type",
            "chk_agent_policies_effective_range",
            "chk_agent_policies_scope_json_object",
            "chk_agent_policies_task_types_json_array",
            "chk_agent_policies_decision_points_json_array",
            "chk_agent_policies_trigger_conditions_json_object",
            "chk_agent_policies_policy_body_json_object",
            "chk_agent_policies_evidence_refs_json_object",
            "chk_agent_policies_metadata_json_object",
        ),
        table_name="agent_policies",
    )
    application_constraints = await _fetch_constraint_names(
        pool,
        (
            "policy_applications_pkey",
            "policy_applications_policy_version_id_fkey",
            "chk_policy_applications_version_positive",
            "chk_policy_applications_status",
            "chk_policy_applications_scope_json_object",
            "chk_policy_applications_matched_conditions_json_object",
            "chk_policy_applications_applied_action_json_object",
            "chk_policy_applications_outcome_summary_json_object",
            "chk_policy_applications_error_summary_json_object",
        ),
        table_name="policy_applications",
    )
    indexes = await _fetch_index_names(
        pool,
        "hermes",
        (
            "uq_agent_policies_source_candidate",
            "idx_agent_policies_active_lookup",
            "idx_agent_policies_source_candidate",
            "idx_agent_policies_policy_id",
            "idx_agent_policies_scope_gin",
            "idx_agent_policies_trigger_conditions_gin",
            "idx_policy_applications_run",
            "idx_policy_applications_policy",
            "idx_policy_applications_policy_version",
            "idx_policy_applications_domain_task",
        ),
    )

    policy_required = {
        "policy_version_id",
        "policy_id",
        "version",
        "domain",
        "policy_type",
        "status",
        "scope_json",
        "task_types_json",
        "decision_points_json",
        "trigger_conditions_json",
        "policy_body_json",
        "priority",
        "precedence",
        "source_candidate_id",
        "source_policy_version_id",
        "evidence_refs_json",
        "approved_by",
        "approved_at",
        "effective_from",
        "effective_until",
        "disable_reason",
        "metadata_json",
        "created_at",
        "updated_at",
    }
    application_required = {
        "application_id",
        "run_id",
        "domain",
        "agent_name",
        "task_type",
        "decision_point",
        "policy_id",
        "policy_version_id",
        "policy_version",
        "scope_json",
        "matched_conditions_json",
        "application_status",
        "applied_action_json",
        "outcome_summary_json",
        "warning",
        "error_summary_json",
        "created_at",
    }
    candidate_compat_required = {
        "candidate_id",
        "domain",
        "candidate_type",
        "scope_json",
        "trigger_conditions_json",
        "proposed_policy_json",
        "evidence_refs_json",
        "status",
        "policy_id",
    }

    return {
        "agent_self_evolution_foundation": policy_required.issubset(policy_columns)
        and application_required.issubset(application_columns)
        and candidate_compat_required.issubset(candidate_columns)
        and {
            "agent_policies_pkey",
            "agent_policies_source_candidate_id_fkey",
            "agent_policies_source_policy_version_id_fkey",
            "uq_agent_policies_policy_version",
            "chk_agent_policies_version_positive",
            "chk_agent_policies_status",
            "chk_agent_policies_policy_type",
            "chk_agent_policies_effective_range",
            "chk_agent_policies_scope_json_object",
            "chk_agent_policies_task_types_json_array",
            "chk_agent_policies_decision_points_json_array",
            "chk_agent_policies_trigger_conditions_json_object",
            "chk_agent_policies_policy_body_json_object",
            "chk_agent_policies_evidence_refs_json_object",
            "chk_agent_policies_metadata_json_object",
        }.issubset(policy_constraints)
        and {
            "policy_applications_pkey",
            "policy_applications_policy_version_id_fkey",
            "chk_policy_applications_version_positive",
            "chk_policy_applications_status",
            "chk_policy_applications_scope_json_object",
            "chk_policy_applications_matched_conditions_json_object",
            "chk_policy_applications_applied_action_json_object",
            "chk_policy_applications_outcome_summary_json_object",
            "chk_policy_applications_error_summary_json_object",
        }.issubset(application_constraints)
        and {
            "uq_agent_policies_source_candidate",
            "idx_agent_policies_active_lookup",
            "idx_agent_policies_source_candidate",
            "idx_agent_policies_policy_id",
            "idx_agent_policies_scope_gin",
            "idx_agent_policies_trigger_conditions_gin",
            "idx_policy_applications_run",
            "idx_policy_applications_policy",
            "idx_policy_applications_policy_version",
            "idx_policy_applications_domain_task",
        }.issubset(indexes),
    }
