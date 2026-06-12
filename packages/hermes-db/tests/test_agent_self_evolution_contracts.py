from uuid import uuid4

from hermes_db_mcp.contracts import (
    DEFAULT_AGENT_POLICY_LIMIT,
    MAX_AGENT_POLICY_LIMIT,
    validate_agent_policy_pagination,
    validate_agent_policy_query,
    validate_applicable_agent_policy_query,
    validate_disable_agent_policy_payload,
    validate_policy_application_query,
    validate_promote_learning_candidate_to_policy_payload,
    validate_record_policy_application_payload,
    validate_rollback_agent_policy_payload,
)


def promote_payload(**overrides):
    payload = {
        "candidate_id": str(uuid4()),
        "approved_by": "operator",
        "policy_type": "topic_strategy",
        "task_types": ["topic_selection"],
        "decision_points": ["before_ranking"],
        "metadata": {},
    }
    payload.update(overrides)
    return payload


def applicable_query(**overrides):
    query = {
        "domain": "wechat",
        "scope": {"account": "acct"},
        "task_type": "topic_selection",
        "decision_point": "before_ranking",
    }
    query.update(overrides)
    return query


def application_payload(**overrides):
    payload = {
        "domain": "wechat",
        "agent_name": "topic-agent",
        "task_type": "topic_selection",
        "decision_point": "before_ranking",
        "policy_id": str(uuid4()),
        "policy_version_id": str(uuid4()),
        "policy_version": 1,
        "application_status": "applied",
        "scope": {"account": "acct"},
        "matched_conditions": {},
        "applied_action": {},
        "outcome_summary": {},
    }
    payload.update(overrides)
    return payload


def test_validate_agent_policy_pagination_accepts_bounds():
    assert validate_agent_policy_pagination(DEFAULT_AGENT_POLICY_LIMIT, 0) is None


def test_validate_agent_policy_pagination_rejects_oversized_limit():
    err = validate_agent_policy_pagination(MAX_AGENT_POLICY_LIMIT + 1, 0)

    assert err["error"] == "invalid_field"
    assert err["field"] == "limit"


def test_validate_promote_learning_candidate_to_policy_payload_accepts_valid_input():
    assert validate_promote_learning_candidate_to_policy_payload(promote_payload()) is None


def test_validate_promote_learning_candidate_to_policy_payload_rejects_invalid_candidate_id():
    err = validate_promote_learning_candidate_to_policy_payload(
        promote_payload(candidate_id="bad")
    )

    assert err["error"] == "invalid_uuid"
    assert err["field"] == "candidate_id"


def test_validate_promote_learning_candidate_to_policy_payload_rejects_bad_array_shape():
    err = validate_promote_learning_candidate_to_policy_payload(
        promote_payload(task_types="topic_selection")
    )

    assert err["error"] == "invalid_field"
    assert err["field"] == "task_types"


def test_validate_agent_policy_query_requires_filter_or_explicit_limit():
    err = validate_agent_policy_query()

    assert err["error"] == "invalid_filter"


def test_validate_agent_policy_query_accepts_filters():
    err = validate_agent_policy_query(
        domain="wechat",
        policy_type="topic_strategy",
        status="active",
        source_candidate_id=str(uuid4()),
        policy_id=str(uuid4()),
        explicit_limit=True,
    )

    assert err is None


def test_validate_agent_policy_query_rejects_invalid_status():
    err = validate_agent_policy_query(status="pending", explicit_limit=True)

    assert err["error"] == "invalid_field"
    assert err["field"] == "status"


def test_validate_applicable_agent_policy_query_accepts_valid_input():
    assert validate_applicable_agent_policy_query(applicable_query()) is None


def test_validate_applicable_agent_policy_query_requires_scope_object():
    err = validate_applicable_agent_policy_query(applicable_query(scope=[]))

    assert err["error"] == "invalid_field"
    assert err["field"] == "scope"


def test_validate_disable_agent_policy_payload_accepts_valid_input():
    err = validate_disable_agent_policy_payload(
        {
            "policy_id": str(uuid4()),
            "disabled_by": "operator",
            "disable_reason": "bad outcome",
        }
    )

    assert err is None


def test_validate_rollback_agent_policy_payload_accepts_valid_input():
    err = validate_rollback_agent_policy_payload(
        {
            "policy_id": str(uuid4()),
            "to_policy_version_id": str(uuid4()),
            "reviewed_by": "operator",
        }
    )

    assert err is None


def test_validate_record_policy_application_payload_accepts_valid_input():
    assert validate_record_policy_application_payload(application_payload()) is None


def test_validate_record_policy_application_payload_rejects_invalid_status():
    err = validate_record_policy_application_payload(
        application_payload(application_status="unknown")
    )

    assert err["error"] == "invalid_field"
    assert err["field"] == "application_status"


def test_validate_record_policy_application_payload_rejects_invalid_version():
    err = validate_record_policy_application_payload(application_payload(policy_version=0))

    assert err["error"] == "invalid_field"
    assert err["field"] == "policy_version"


def test_validate_record_policy_application_payload_rejects_bool_version():
    err = validate_record_policy_application_payload(application_payload(policy_version=True))

    assert err["error"] == "invalid_field"
    assert err["field"] == "policy_version"


def test_validate_policy_application_query_accepts_filters():
    err = validate_policy_application_query(
        policy_id=str(uuid4()),
        policy_version_id=str(uuid4()),
        run_id="run-1",
        domain="wechat",
        task_type="topic_selection",
        decision_point="before_ranking",
    )

    assert err is None


def test_validate_policy_application_query_requires_filter_or_explicit_limit():
    err = validate_policy_application_query()

    assert err["error"] == "invalid_filter"
