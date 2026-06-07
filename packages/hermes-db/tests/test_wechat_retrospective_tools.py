from datetime import date, datetime
import inspect
from unittest.mock import MagicMock
from uuid import uuid4

import asyncpg
import pytest

from hermes_db_mcp import server
from hermes_db_mcp.tools.wechat_retrospective import (
    create_learning_candidates,
    create_topic_optimization_suggestions,
    create_wechat_retrospective_report,
    get_wechat_retrospective_report,
    list_approved_topic_ranking_hints,
    list_learning_candidates,
    list_topic_optimization_suggestions,
    list_topic_performance,
    list_wechat_retrospective_reports,
    review_learning_candidate,
    review_topic_optimization_suggestion,
    upsert_topic_performance,
)


class FakeAppContext:
    def __init__(self):
        self.pool = MagicMock()


class FakeContext:
    def __init__(self, app_context):
        self.request_context = MagicMock()
        self.request_context.lifespan_context = app_context


def performance_input(article_id=None, **overrides):
    record = {
        "account": "acct",
        "article_id": str(article_id or uuid4()),
        "topic_id": str(uuid4()),
        "stat_date": "2026-06-07",
        "window_label": "D+7",
        "scoring_version": "wechat-retro-v1",
        "baseline_version": "account-rolling-v1",
        "normalized_score": 86.4,
        "read_score": 90,
        "engagement_score": 80,
        "share_score": 88,
        "conversion_score": 70,
        "confidence": 0.82,
        "provisional": False,
        "low_sample_size": False,
        "metric_snapshot_ids": [str(uuid4())],
        "baseline_snapshot": {},
        "diagnosis": {},
        "evidence_refs": {"articles": []},
        "warnings": [],
    }
    record.update(overrides)
    return record


def report_input(article_id=None, **overrides):
    record = {
        "account": "acct",
        "report_type": "article",
        "period_start": "2026-06-01",
        "period_end": "2026-06-07",
        "article_id": str(article_id or uuid4()),
        "scoring_version": "wechat-retro-v1",
        "generation_mode": "structured_only",
        "status": "completed",
        "sample_size": 2,
        "low_sample_size": False,
        "performance_ids": [str(uuid4())],
        "summary": {},
        "narrative_markdown": "summary",
        "high_performing_themes": [],
        "low_performing_themes": [],
        "title_patterns": [],
        "recommendations": [],
        "evidence_refs": {},
        "warnings": [],
    }
    record.update(overrides)
    return record


def suggestion_item(**overrides):
    item = {
        "suggestion_type": "cooldown",
        "target_kind": "mother_theme",
        "target_key": "food",
        "current_value": {},
        "proposed_value": {"action": "cooldown"},
        "rationale": "Underperformed baseline.",
        "confidence": 0.76,
        "evidence_refs": {},
        "review_status": "pending",
    }
    item.update(overrides)
    return item


def learning_item(**overrides):
    item = {
        "domain": "wechat",
        "source_suggestion_ids": [str(uuid4())],
        "candidate_type": "topic_strategy",
        "scope": {},
        "trigger_conditions": {},
        "proposed_policy": {},
        "confidence": 0.78,
        "evidence_refs": {},
        "status": "pending_review",
    }
    item.update(overrides)
    return item


@pytest.mark.asyncio
async def test_upsert_topic_performance_success_serializes_json_fields(monkeypatch):
    article_id = uuid4()
    performance_id = uuid4()

    async def mock_upsert_topic_performance(pool, record):
        assert record["article_id"] == article_id
        assert record["stat_date"] == date(2026, 6, 7)
        return {
            "performance_id": performance_id,
            "article_id": article_id,
            "stat_date": date(2026, 6, 7),
            "metric_snapshot_ids_json": '["snapshot-1"]',
            "evidence_refs_json": '{"articles": []}',
            "warnings_json": "[]",
            "updated_at": datetime(2026, 6, 7),
        }

    monkeypatch.setattr(
        "hermes_db_mcp.tools.wechat_retrospective.wechat_retrospective_repo.upsert_topic_performance",
        mock_upsert_topic_performance,
    )

    result = await upsert_topic_performance(
        performance_input(article_id=article_id),
        FakeContext(FakeAppContext()),
    )

    assert result["performance_id"] == str(performance_id)
    assert result["article_id"] == str(article_id)
    assert result["stat_date"] == "2026-06-07"
    assert result["metric_snapshot_ids"] == ["snapshot-1"]
    assert result["evidence_refs"] == {"articles": []}
    assert "metric_snapshot_ids_json" not in result


@pytest.mark.asyncio
async def test_upsert_topic_performance_validation_error_does_not_write(monkeypatch):
    wrote = False

    async def mock_upsert_topic_performance(pool, record):
        nonlocal wrote
        wrote = True

    monkeypatch.setattr(
        "hermes_db_mcp.tools.wechat_retrospective.wechat_retrospective_repo.upsert_topic_performance",
        mock_upsert_topic_performance,
    )

    result = await upsert_topic_performance(
        performance_input(normalized_score=101),
        FakeContext(FakeAppContext()),
    )

    assert wrote is False
    assert result["error"] == "invalid_field"
    assert result["field"] == "normalized_score"


@pytest.mark.asyncio
async def test_upsert_topic_performance_maps_schema_drift(monkeypatch):
    async def mock_upsert_topic_performance(pool, record):
        raise asyncpg.UndefinedTableError("missing")

    monkeypatch.setattr(
        "hermes_db_mcp.tools.wechat_retrospective.wechat_retrospective_repo.upsert_topic_performance",
        mock_upsert_topic_performance,
    )

    result = await upsert_topic_performance(
        performance_input(),
        FakeContext(FakeAppContext()),
    )

    assert result["error"] == "schema_drift"


@pytest.mark.asyncio
async def test_list_topic_performance_returns_pagination_shape(monkeypatch):
    performance_id = uuid4()

    async def mock_list_topic_performance(pool, **kwargs):
        assert kwargs["limit"] == 10
        assert kwargs["offset"] == 2
        return {
            "items": [
                {
                    "performance_id": performance_id,
                    "metric_snapshot_ids_json": "[]",
                    "updated_at": datetime(2026, 6, 7),
                }
            ],
            "total": 1,
        }

    monkeypatch.setattr(
        "hermes_db_mcp.tools.wechat_retrospective.wechat_retrospective_repo.list_topic_performance",
        mock_list_topic_performance,
    )

    result = await list_topic_performance(
        FakeContext(FakeAppContext()),
        account="acct",
        limit=10,
        offset=2,
    )

    assert result == {
        "items": [
                {
                    "performance_id": str(performance_id),
                    "metric_snapshot_ids": [],
                    "updated_at": "2026-06-07 00:00:00",
                }
            ],
        "total": 1,
        "limit": 10,
        "offset": 2,
    }


@pytest.mark.asyncio
async def test_create_get_and_list_reports(monkeypatch):
    report_id = uuid4()

    async def mock_create_report(pool, record):
        assert record["period_start"] == date(2026, 6, 1)
        return {"report_id": report_id, "summary_json": "{}", "performance_ids_json": "[]"}

    async def mock_get_report(pool, requested_report_id):
        assert requested_report_id == report_id
        return {"report_id": report_id, "recommendations_json": "[]"}

    async def mock_list_reports(pool, **kwargs):
        assert kwargs["date_from"] == date(2026, 6, 1)
        return {"items": [{"report_id": report_id, "warnings_json": "[]"}], "total": 1}

    monkeypatch.setattr(
        "hermes_db_mcp.tools.wechat_retrospective.wechat_retrospective_repo.create_wechat_retrospective_report",
        mock_create_report,
    )
    monkeypatch.setattr(
        "hermes_db_mcp.tools.wechat_retrospective.wechat_retrospective_repo.get_wechat_retrospective_report",
        mock_get_report,
    )
    monkeypatch.setattr(
        "hermes_db_mcp.tools.wechat_retrospective.wechat_retrospective_repo.list_wechat_retrospective_reports",
        mock_list_reports,
    )

    created = await create_wechat_retrospective_report(
        report_input(),
        FakeContext(FakeAppContext()),
    )
    fetched = await get_wechat_retrospective_report(
        str(report_id),
        FakeContext(FakeAppContext()),
    )
    listed = await list_wechat_retrospective_reports(
        FakeContext(FakeAppContext()),
        account="acct",
        report_type="article",
        date_from="2026-06-01",
    )

    assert created["report_id"] == str(report_id)
    assert created["summary"] == {}
    assert fetched["recommendations"] == []
    assert listed["items"][0]["warnings"] == []
    assert listed["total"] == 1


@pytest.mark.asyncio
async def test_get_wechat_retrospective_report_returns_not_found(monkeypatch):
    async def mock_get_report(pool, report_id):
        return None

    monkeypatch.setattr(
        "hermes_db_mcp.tools.wechat_retrospective.wechat_retrospective_repo.get_wechat_retrospective_report",
        mock_get_report,
    )

    result = await get_wechat_retrospective_report(
        str(uuid4()),
        FakeContext(FakeAppContext()),
    )

    assert result["error"] == "not_found"
    assert result["field"] == "report_id"


@pytest.mark.asyncio
async def test_create_list_and_review_topic_suggestions(monkeypatch):
    report_id = uuid4()
    suggestion_id = uuid4()

    async def mock_create_suggestions(pool, **kwargs):
        assert kwargs["report_id"] == report_id
        assert kwargs["items"][0]["target_key"] == "food"
        return [
            {
                "suggestion_id": suggestion_id,
                "proposed_value_json": '{"action": "cooldown"}',
                "review_status": "pending",
            }
        ]

    async def mock_list_suggestions(pool, **kwargs):
        assert kwargs["review_status"] == "pending"
        return {"items": [{"suggestion_id": suggestion_id, "current_value_json": "{}"}], "total": 1}

    async def mock_review_suggestion(pool, **kwargs):
        assert kwargs["suggestion_id"] == suggestion_id
        assert kwargs["review_status"] == "approved"
        return {"suggestion_id": suggestion_id, "review_status": "approved"}

    monkeypatch.setattr(
        "hermes_db_mcp.tools.wechat_retrospective.wechat_retrospective_repo.create_topic_optimization_suggestions",
        mock_create_suggestions,
    )
    monkeypatch.setattr(
        "hermes_db_mcp.tools.wechat_retrospective.wechat_retrospective_repo.list_topic_optimization_suggestions",
        mock_list_suggestions,
    )
    monkeypatch.setattr(
        "hermes_db_mcp.tools.wechat_retrospective.wechat_retrospective_repo.review_topic_optimization_suggestion",
        mock_review_suggestion,
    )

    created = await create_topic_optimization_suggestions(
        {"account": "acct", "report_id": str(report_id), "items": [suggestion_item()]},
        FakeContext(FakeAppContext()),
    )
    listed = await list_topic_optimization_suggestions(
        FakeContext(FakeAppContext()),
        account="acct",
        review_status="pending",
    )
    reviewed = await review_topic_optimization_suggestion(
        {
            "suggestion_id": str(suggestion_id),
            "review_status": "approved",
            "reviewed_by": "operator",
        },
        FakeContext(FakeAppContext()),
    )

    assert created["items"][0]["proposed_value"] == {"action": "cooldown"}
    assert created["total"] == 1
    assert listed["items"][0]["current_value"] == {}
    assert reviewed["review_status"] == "approved"


@pytest.mark.asyncio
async def test_review_topic_suggestion_rejects_applied_without_write(monkeypatch):
    wrote = False

    async def mock_review_suggestion(pool, **kwargs):
        nonlocal wrote
        wrote = True

    monkeypatch.setattr(
        "hermes_db_mcp.tools.wechat_retrospective.wechat_retrospective_repo.review_topic_optimization_suggestion",
        mock_review_suggestion,
    )

    result = await review_topic_optimization_suggestion(
        {"suggestion_id": str(uuid4()), "review_status": "applied"},
        FakeContext(FakeAppContext()),
    )

    assert wrote is False
    assert result["error"] == "invalid_transition"
    assert result["field"] == "review_status"


@pytest.mark.asyncio
async def test_list_approved_topic_ranking_hints_requires_account():
    result = await list_approved_topic_ranking_hints(
        FakeContext(FakeAppContext()),
        account=None,
    )

    assert result["error"] == "missing_required_field"
    assert result["field"] == "account"


@pytest.mark.asyncio
async def test_list_approved_topic_ranking_hints_success(monkeypatch):
    suggestion_id = uuid4()

    async def mock_list_hints(pool, **kwargs):
        assert kwargs["account"] == "acct"
        assert kwargs["target_kind"] == "topic"
        return {
            "items": [
                {
                    "suggestion_id": suggestion_id,
                    "review_status": "approved",
                    "expires_at": None,
                    "proposed_value_json": '{"ranking_weight_delta": 0.2}',
                }
            ],
            "total": 1,
        }

    monkeypatch.setattr(
        "hermes_db_mcp.tools.wechat_retrospective.wechat_retrospective_repo.list_approved_topic_ranking_hints",
        mock_list_hints,
    )

    result = await list_approved_topic_ranking_hints(
        FakeContext(FakeAppContext()),
        account="acct",
        target_kind="topic",
    )

    assert result["items"][0]["suggestion_id"] == str(suggestion_id)
    assert result["items"][0]["proposed_value"] == {"ranking_weight_delta": 0.2}
    assert result["total"] == 1


@pytest.mark.asyncio
async def test_create_list_and_review_learning_candidates(monkeypatch):
    report_id = uuid4()
    candidate_id = uuid4()

    async def mock_create_candidates(pool, **kwargs):
        assert kwargs["source_report_id"] == report_id
        return [
            {
                "candidate_id": candidate_id,
                "source_suggestion_ids_json": "[]",
                "proposed_policy_json": "{}",
                "status": "pending_review",
            }
        ]

    async def mock_list_candidates(pool, **kwargs):
        assert kwargs["status"] == "pending_review"
        return {"items": [{"candidate_id": candidate_id, "scope_json": "{}"}], "total": 1}

    async def mock_review_candidate(pool, **kwargs):
        assert kwargs["candidate_id"] == candidate_id
        assert kwargs["policy_id"] == "policy-1"
        return {"candidate_id": candidate_id, "status": "approved", "policy_id": "policy-1"}

    monkeypatch.setattr(
        "hermes_db_mcp.tools.wechat_retrospective.wechat_retrospective_repo.create_learning_candidates",
        mock_create_candidates,
    )
    monkeypatch.setattr(
        "hermes_db_mcp.tools.wechat_retrospective.wechat_retrospective_repo.list_learning_candidates",
        mock_list_candidates,
    )
    monkeypatch.setattr(
        "hermes_db_mcp.tools.wechat_retrospective.wechat_retrospective_repo.review_learning_candidate",
        mock_review_candidate,
    )

    created = await create_learning_candidates(
        {"account": "acct", "source_report_id": str(report_id), "items": [learning_item()]},
        FakeContext(FakeAppContext()),
    )
    listed = await list_learning_candidates(
        FakeContext(FakeAppContext()),
        account="acct",
        status="pending_review",
    )
    reviewed = await review_learning_candidate(
        {
            "candidate_id": str(candidate_id),
            "status": "approved",
            "reviewed_by": "operator",
            "policy_id": "policy-1",
        },
        FakeContext(FakeAppContext()),
    )

    assert created["items"][0]["source_suggestion_ids"] == []
    assert created["items"][0]["proposed_policy"] == {}
    assert listed["items"][0]["scope"] == {}
    assert reviewed["policy_id"] == "policy-1"


@pytest.mark.asyncio
async def test_review_learning_candidate_rejects_exported_status_without_write(monkeypatch):
    wrote = False

    async def mock_review_candidate(pool, **kwargs):
        nonlocal wrote
        wrote = True

    monkeypatch.setattr(
        "hermes_db_mcp.tools.wechat_retrospective.wechat_retrospective_repo.review_learning_candidate",
        mock_review_candidate,
    )

    result = await review_learning_candidate(
        {"candidate_id": str(uuid4()), "status": "exported_to_policy"},
        FakeContext(FakeAppContext()),
    )

    assert wrote is False
    assert result["error"] == "invalid_transition"
    assert result["field"] == "status"


@pytest.mark.asyncio
async def test_review_learning_candidate_returns_not_found(monkeypatch):
    async def mock_review_candidate(pool, **kwargs):
        return None

    monkeypatch.setattr(
        "hermes_db_mcp.tools.wechat_retrospective.wechat_retrospective_repo.review_learning_candidate",
        mock_review_candidate,
    )

    result = await review_learning_candidate(
        {"candidate_id": str(uuid4()), "status": "approved"},
        FakeContext(FakeAppContext()),
    )

    assert result["error"] == "not_found"
    assert result["field"] == "candidate_id"


@pytest.mark.asyncio
async def test_list_learning_candidates_maps_schema_drift(monkeypatch):
    async def mock_list_candidates(pool, **kwargs):
        raise asyncpg.UndefinedColumnError("missing")

    monkeypatch.setattr(
        "hermes_db_mcp.tools.wechat_retrospective.wechat_retrospective_repo.list_learning_candidates",
        mock_list_candidates,
    )

    result = await list_learning_candidates(
        FakeContext(FakeAppContext()),
        account="acct",
    )

    assert result["error"] == "schema_drift"


def test_register_tools_imports_wechat_retrospective_module():
    source = inspect.getsource(server.register_tools)

    assert "wechat_retrospective" in source
