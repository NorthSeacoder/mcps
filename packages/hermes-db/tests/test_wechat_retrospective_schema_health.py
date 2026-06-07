from unittest.mock import AsyncMock

import pytest

from hermes_db_mcp.services.schema import (
    inspect_wechat_retrospective_topic_optimizer_schema,
)


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


PERFORMANCE_COLUMNS = {
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

REPORT_COLUMNS = {
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

SUGGESTION_COLUMNS = {
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

CANDIDATE_COLUMNS = {
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

PERFORMANCE_CONSTRAINTS = {
    "topic_performance_pkey",
    "topic_performance_article_id_fkey",
    "topic_performance_topic_id_fkey",
    "uq_topic_performance_identity",
    "chk_topic_performance_scores_range",
    "chk_topic_performance_confidence_range",
}

REPORT_CONSTRAINTS = {
    "wechat_retrospective_reports_pkey",
    "wechat_retrospective_reports_article_id_fkey",
    "chk_wechat_retrospective_reports_type",
    "chk_wechat_retrospective_reports_generation_mode",
    "chk_wechat_retrospective_reports_status",
    "chk_wechat_retrospective_reports_period",
    "chk_wechat_retrospective_reports_sample_size",
}

SUGGESTION_CONSTRAINTS = {
    "topic_optimization_suggestions_pkey",
    "topic_optimization_suggestions_report_id_fkey",
    "chk_topic_optimization_suggestions_type",
    "chk_topic_optimization_suggestions_target_kind",
    "chk_topic_optimization_suggestions_review_status",
    "chk_topic_optimization_suggestions_confidence",
    "chk_topic_optimization_suggestions_target_ref",
}

CANDIDATE_CONSTRAINTS = {
    "learning_candidates_pkey",
    "learning_candidates_source_report_id_fkey",
    "chk_learning_candidates_type",
    "chk_learning_candidates_status",
    "chk_learning_candidates_confidence",
}

INDEXES = {
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
}


def column_rows(names):
    return [FakeRow(column_name=name) for name in names]


def constraint_rows(names):
    return [FakeRow(conname=name) for name in names]


def index_rows(names):
    return [FakeRow(indexname=name) for name in names]


def complete_fetch_results(
    *,
    performance_columns=PERFORMANCE_COLUMNS,
    report_columns=REPORT_COLUMNS,
    suggestion_columns=SUGGESTION_COLUMNS,
    candidate_columns=CANDIDATE_COLUMNS,
    performance_constraints=PERFORMANCE_CONSTRAINTS,
    report_constraints=REPORT_CONSTRAINTS,
    suggestion_constraints=SUGGESTION_CONSTRAINTS,
    candidate_constraints=CANDIDATE_CONSTRAINTS,
    indexes=INDEXES,
):
    return [
        column_rows(performance_columns),
        column_rows(report_columns),
        column_rows(suggestion_columns),
        column_rows(candidate_columns),
        constraint_rows(performance_constraints),
        constraint_rows(report_constraints),
        constraint_rows(suggestion_constraints),
        constraint_rows(candidate_constraints),
        index_rows(indexes),
    ]


@pytest.mark.asyncio
async def test_inspect_wechat_retrospective_schema_returns_true_for_complete_schema():
    pool = FakePool(complete_fetch_results())

    assert await inspect_wechat_retrospective_topic_optimizer_schema(pool) == {
        "wechat_retrospective_topic_optimizer": True,
    }


@pytest.mark.asyncio
async def test_inspect_wechat_retrospective_schema_reflects_missing_tables():
    pool = FakePool([[], [], [], [], [], [], [], [], []])

    assert await inspect_wechat_retrospective_topic_optimizer_schema(pool) == {
        "wechat_retrospective_topic_optimizer": False,
    }


@pytest.mark.asyncio
async def test_inspect_wechat_retrospective_schema_reflects_missing_column():
    pool = FakePool(
        complete_fetch_results(
            performance_columns=PERFORMANCE_COLUMNS - {"metric_snapshot_ids_json"}
        )
    )

    assert await inspect_wechat_retrospective_topic_optimizer_schema(pool) == {
        "wechat_retrospective_topic_optimizer": False,
    }


@pytest.mark.asyncio
async def test_inspect_wechat_retrospective_schema_reflects_missing_constraint():
    pool = FakePool(
        complete_fetch_results(
            suggestion_constraints=SUGGESTION_CONSTRAINTS
            - {"chk_topic_optimization_suggestions_target_ref"}
        )
    )

    assert await inspect_wechat_retrospective_topic_optimizer_schema(pool) == {
        "wechat_retrospective_topic_optimizer": False,
    }


@pytest.mark.asyncio
async def test_inspect_wechat_retrospective_schema_reflects_missing_fk():
    pool = FakePool(
        complete_fetch_results(
            candidate_constraints=CANDIDATE_CONSTRAINTS
            - {"learning_candidates_source_report_id_fkey"}
        )
    )

    assert await inspect_wechat_retrospective_topic_optimizer_schema(pool) == {
        "wechat_retrospective_topic_optimizer": False,
    }


@pytest.mark.asyncio
async def test_inspect_wechat_retrospective_schema_reflects_missing_index():
    pool = FakePool(
        complete_fetch_results(
            indexes=INDEXES - {"idx_topic_optimization_suggestions_approved_hints"}
        )
    )

    assert await inspect_wechat_retrospective_topic_optimizer_schema(pool) == {
        "wechat_retrospective_topic_optimizer": False,
    }
