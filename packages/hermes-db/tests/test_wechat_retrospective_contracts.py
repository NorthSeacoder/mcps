from uuid import uuid4

from hermes_db_mcp.contracts import (
    DEFAULT_WECHAT_RETROSPECTIVE_LIMIT,
    MAX_WECHAT_RETROSPECTIVE_LIMIT,
    error,
    validate_approved_ranking_hint_query,
    validate_learning_candidate_query,
    validate_learning_candidate_review,
    validate_learning_candidates_payload,
    validate_retrospective_pagination,
    validate_retrospective_report_payload,
    validate_retrospective_report_query,
    validate_suggestion_review,
    validate_topic_optimization_suggestion_query,
    validate_topic_performance_payload,
    validate_topic_performance_query,
    validate_topic_suggestions_payload,
)


def performance_record(**overrides):
    record = {
        "account": "acct",
        "article_id": str(uuid4()),
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
        "evidence_refs": {},
        "warnings": [],
    }
    record.update(overrides)
    return record


def report_record(**overrides):
    record = {
        "account": "acct",
        "report_type": "article",
        "period_start": "2026-06-01",
        "period_end": "2026-06-07",
        "article_id": str(uuid4()),
        "scoring_version": "wechat-retro-v1",
        "generation_mode": "structured_only",
        "status": "completed",
        "sample_size": 3,
        "low_sample_size": False,
        "performance_ids": [str(uuid4())],
        "summary": {},
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


def learning_candidate_item(**overrides):
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


def test_validate_retrospective_pagination_accepts_default_bounds():
    assert validate_retrospective_pagination(DEFAULT_WECHAT_RETROSPECTIVE_LIMIT, 0) is None


def test_validate_retrospective_pagination_rejects_oversized_limit():
    err = validate_retrospective_pagination(MAX_WECHAT_RETROSPECTIVE_LIMIT + 1, 0)

    assert err["error"] == "invalid_field"
    assert err["field"] == "limit"


def test_validate_retrospective_pagination_rejects_negative_offset():
    err = validate_retrospective_pagination(DEFAULT_WECHAT_RETROSPECTIVE_LIMIT, -1)

    assert err["error"] == "invalid_field"
    assert err["field"] == "offset"


def test_validate_topic_performance_payload_accepts_valid_record():
    assert validate_topic_performance_payload(performance_record()) is None


def test_validate_topic_performance_payload_rejects_invalid_uuid():
    err = validate_topic_performance_payload(performance_record(article_id="bad"))

    assert err["error"] == "invalid_uuid"
    assert err["field"] == "article_id"


def test_validate_topic_performance_payload_rejects_score_outside_zero_hundred():
    err = validate_topic_performance_payload(performance_record(normalized_score=101))

    assert err["error"] == "invalid_field"
    assert err["field"] == "normalized_score"


def test_validate_topic_performance_payload_rejects_bad_confidence():
    err = validate_topic_performance_payload(performance_record(confidence=1.2))

    assert err["error"] == "invalid_field"
    assert err["field"] == "confidence"


def test_validate_topic_performance_payload_rejects_bad_json_shape():
    err = validate_topic_performance_payload(performance_record(evidence_refs=[]))

    assert err["error"] == "invalid_field"
    assert err["field"] == "evidence_refs"


def test_validate_topic_performance_query_accepts_bounded_filters():
    err = validate_topic_performance_query(
        account="acct",
        article_id=str(uuid4()),
        topic_id=str(uuid4()),
        window_label="D+7",
        scoring_version="wechat-retro-v1",
        date_from="2026-06-01",
        date_to="2026-06-07",
    )

    assert err is None


def test_validate_topic_performance_query_rejects_invalid_date_range():
    err = validate_topic_performance_query(
        account="acct",
        date_from="2026-06-08",
        date_to="2026-06-07",
    )

    assert err["error"] == "invalid_filter"
    assert err["field"] == "date_from"


def test_validate_retrospective_report_payload_accepts_valid_record():
    assert validate_retrospective_report_payload(report_record()) is None


def test_validate_retrospective_report_payload_rejects_invalid_type():
    err = validate_retrospective_report_payload(report_record(report_type="daily"))

    assert err["error"] == "invalid_field"
    assert err["field"] == "report_type"


def test_validate_retrospective_report_payload_rejects_invalid_period():
    err = validate_retrospective_report_payload(
        report_record(period_start="2026-06-08", period_end="2026-06-07")
    )

    assert err["error"] == "invalid_filter"
    assert err["field"] == "period_start"


def test_validate_retrospective_report_payload_rejects_negative_sample_size():
    err = validate_retrospective_report_payload(report_record(sample_size=-1))

    assert err["error"] == "invalid_field"
    assert err["field"] == "sample_size"


def test_validate_retrospective_report_payload_rejects_bad_json_sections():
    err = validate_retrospective_report_payload(report_record(recommendations={}))

    assert err["error"] == "invalid_field"
    assert err["field"] == "recommendations"


def test_validate_retrospective_report_query_accepts_filters():
    err = validate_retrospective_report_query(
        account="acct",
        report_type="article",
        article_id=str(uuid4()),
        date_from="2026-06-01",
        date_to="2026-06-07",
    )

    assert err is None


def test_validate_topic_suggestions_payload_accepts_pending_item():
    err = validate_topic_suggestions_payload(
        account="acct",
        report_id=str(uuid4()),
        items=[suggestion_item()],
    )

    assert err is None


def test_validate_topic_suggestions_payload_rejects_missing_target_ref():
    err = validate_topic_suggestions_payload(
        account="acct",
        report_id=str(uuid4()),
        items=[suggestion_item(target_key=None)],
    )

    assert err["error"] == "missing_required_field"
    assert err["field"] == "items[0].target_id"


def test_validate_topic_suggestions_payload_rejects_non_pending_create_status():
    err = validate_topic_suggestions_payload(
        account="acct",
        report_id=str(uuid4()),
        items=[suggestion_item(review_status="approved")],
    )

    assert err["error"] == "invalid_transition"
    assert err["field"] == "items[0].review_status"


def test_validate_topic_suggestions_payload_rejects_bad_expires_at():
    err = validate_topic_suggestions_payload(
        account="acct",
        report_id=str(uuid4()),
        items=[suggestion_item(expires_at="not-a-date")],
    )

    assert err["error"] == "invalid_field"
    assert err["field"] == "items[0].expires_at"


def test_validate_topic_optimization_suggestion_query_accepts_filters():
    err = validate_topic_optimization_suggestion_query(
        account="acct",
        report_id=str(uuid4()),
        review_status="pending",
        suggestion_type="cooldown",
        target_kind="mother_theme",
        target_key="food",
    )

    assert err is None


def test_validate_suggestion_review_accepts_review_targets():
    err = validate_suggestion_review(
        suggestion_id=str(uuid4()),
        review_status="approved",
        reviewed_by="operator",
    )

    assert err is None


def test_validate_suggestion_review_rejects_applied_status():
    err = validate_suggestion_review(
        suggestion_id=str(uuid4()),
        review_status="applied",
        reviewed_by="operator",
    )

    assert err["error"] == "invalid_transition"
    assert err["field"] == "review_status"


def test_validate_suggestion_review_rejects_application_trace_id():
    err = validate_suggestion_review(
        suggestion_id=str(uuid4()),
        review_status="approved",
        application_trace_id="trace-1",
    )

    assert err["error"] == "invalid_transition"
    assert err["field"] == "application_trace_id"


def test_validate_approved_ranking_hint_query_requires_account():
    err = validate_approved_ranking_hint_query(account=None)

    assert err["error"] == "missing_required_field"
    assert err["field"] == "account"


def test_validate_approved_ranking_hint_query_accepts_target_filters():
    err = validate_approved_ranking_hint_query(
        account="acct",
        target_kind="topic",
        target_id=str(uuid4()),
    )

    assert err is None


def test_validate_learning_candidates_payload_accepts_pending_item():
    err = validate_learning_candidates_payload(
        account="acct",
        source_report_id=str(uuid4()),
        items=[learning_candidate_item()],
    )

    assert err is None


def test_validate_learning_candidates_payload_rejects_bad_source_suggestion_id():
    err = validate_learning_candidates_payload(
        account="acct",
        source_report_id=str(uuid4()),
        items=[learning_candidate_item(source_suggestion_ids=["bad"])],
    )

    assert err["error"] == "invalid_uuid"
    assert err["field"] == "items[0].source_suggestion_ids[0]"


def test_validate_learning_candidates_payload_rejects_non_pending_status():
    err = validate_learning_candidates_payload(
        account="acct",
        source_report_id=str(uuid4()),
        items=[learning_candidate_item(status="exported_to_policy")],
    )

    assert err["error"] == "invalid_transition"
    assert err["field"] == "items[0].status"


def test_validate_learning_candidates_payload_rejects_bad_policy_shape():
    err = validate_learning_candidates_payload(
        account="acct",
        source_report_id=str(uuid4()),
        items=[learning_candidate_item(proposed_policy=[])],
    )

    assert err["error"] == "invalid_field"
    assert err["field"] == "items[0].proposed_policy"


def test_validate_learning_candidate_query_accepts_filters():
    err = validate_learning_candidate_query(
        account="acct",
        domain="wechat",
        source_report_id=str(uuid4()),
        status="pending_review",
        candidate_type="topic_strategy",
    )

    assert err is None


def test_validate_learning_candidate_review_accepts_review_targets():
    err = validate_learning_candidate_review(
        candidate_id=str(uuid4()),
        status="disabled",
        reviewed_by="operator",
        policy_id="policy-1",
    )

    assert err is None


def test_validate_learning_candidate_review_rejects_exported_status():
    err = validate_learning_candidate_review(
        candidate_id=str(uuid4()),
        status="exported_to_policy",
        reviewed_by="operator",
    )

    assert err["error"] == "invalid_transition"
    assert err["field"] == "status"


def test_structured_error_payload_preserves_code_field_and_details():
    err = error("schema_drift", field="topic_performance", details={"missing": "table"})

    assert err == {
        "error": "schema_drift",
        "message": "数据库 schema 未满足工具要求",
        "field": "topic_performance",
        "details": {"missing": "table"},
    }
