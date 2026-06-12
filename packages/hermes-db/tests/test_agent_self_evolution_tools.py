from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from hermes_db_mcp.server import register_tools
from hermes_db_mcp.tools.agent_self_evolution import (
    disable_agent_policy,
    get_applicable_agent_policies,
    list_agent_policies,
    list_policy_applications,
    promote_learning_candidate_to_policy,
    record_policy_application,
    rollback_agent_policy,
)


class FakeContext:
    def __init__(self):
        self.request_context = MagicMock()
        self.request_context.lifespan_context = MagicMock(pool=MagicMock())


@pytest.mark.asyncio
async def test_promote_learning_candidate_to_policy_returns_serialized_row(monkeypatch):
    policy_id = uuid4()
    policy_version_id = uuid4()
    mock_promote = AsyncMock(
        return_value={
            "policy_id": policy_id,
            "policy_version_id": policy_version_id,
            "scope_json": {"account": "acct"},
            "task_types_json": ["topic_selection"],
        }
    )
    monkeypatch.setattr(
        "hermes_db_mcp.tools.agent_self_evolution."
        "agent_self_evolution_repo.promote_learning_candidate_to_policy",
        mock_promote,
    )

    result = await promote_learning_candidate_to_policy(
        {"candidate_id": str(uuid4()), "approved_by": "operator"},
        FakeContext(),
    )

    assert result["policy_id"] == str(policy_id)
    assert result["policy_version_id"] == str(policy_version_id)
    assert result["scope"] == {"account": "acct"}
    assert result["task_types"] == ["topic_selection"]


@pytest.mark.asyncio
async def test_promote_learning_candidate_to_policy_maps_invalid_state(monkeypatch):
    mock_promote = AsyncMock(side_effect=ValueError("invalid_state: no"))
    monkeypatch.setattr(
        "hermes_db_mcp.tools.agent_self_evolution."
        "agent_self_evolution_repo.promote_learning_candidate_to_policy",
        mock_promote,
    )

    result = await promote_learning_candidate_to_policy(
        {"candidate_id": str(uuid4()), "approved_by": "operator"},
        FakeContext(),
    )

    assert result["error"] == "invalid_transition"


@pytest.mark.asyncio
async def test_list_agent_policies_returns_page(monkeypatch):
    mock_list = AsyncMock(return_value={"items": [], "total": 0})
    monkeypatch.setattr(
        "hermes_db_mcp.tools.agent_self_evolution.agent_self_evolution_repo.list_agent_policies",
        mock_list,
    )

    result = await list_agent_policies(FakeContext(), domain="wechat")

    assert result == {"items": [], "total": 0, "limit": 50, "offset": 0}


@pytest.mark.asyncio
async def test_get_applicable_agent_policies_returns_warnings(monkeypatch):
    mock_query = AsyncMock(return_value={"items": [], "total": 0, "warnings": ["conflict"]})
    monkeypatch.setattr(
        "hermes_db_mcp.tools.agent_self_evolution."
        "agent_self_evolution_repo.get_applicable_agent_policies",
        mock_query,
    )

    result = await get_applicable_agent_policies(
        {"domain": "wechat", "scope": {}, "task_type": "topic_selection"},
        FakeContext(),
    )

    assert result["warnings"] == ["conflict"]


@pytest.mark.asyncio
async def test_disable_agent_policy_returns_not_found(monkeypatch):
    mock_disable = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "hermes_db_mcp.tools.agent_self_evolution.agent_self_evolution_repo.disable_agent_policy",
        mock_disable,
    )

    result = await disable_agent_policy(
        {
            "policy_id": str(uuid4()),
            "disabled_by": "operator",
            "disable_reason": "bad outcome",
        },
        FakeContext(),
    )

    assert result["error"] == "not_found"
    assert result["field"] == "policy_id"


@pytest.mark.asyncio
async def test_rollback_agent_policy_returns_serialized_row(monkeypatch):
    mock_rollback = AsyncMock(return_value={"policy_id": uuid4(), "status": "active"})
    monkeypatch.setattr(
        "hermes_db_mcp.tools.agent_self_evolution.agent_self_evolution_repo.rollback_agent_policy",
        mock_rollback,
    )

    result = await rollback_agent_policy(
        {
            "policy_id": str(uuid4()),
            "to_policy_version_id": str(uuid4()),
            "reviewed_by": "operator",
        },
        FakeContext(),
    )

    assert result["status"] == "active"


@pytest.mark.asyncio
async def test_record_policy_application_passes_uuid_values(monkeypatch):
    policy_id = uuid4()
    policy_version_id = uuid4()
    mock_record = AsyncMock(return_value={"policy_id": policy_id})
    monkeypatch.setattr(
        "hermes_db_mcp.tools.agent_self_evolution."
        "agent_self_evolution_repo.record_policy_application",
        mock_record,
    )

    result = await record_policy_application(
        {
            "domain": "wechat",
            "agent_name": "topic-agent",
            "task_type": "topic_selection",
            "decision_point": "before_ranking",
            "policy_id": str(policy_id),
            "policy_version_id": str(policy_version_id),
            "policy_version": 1,
            "application_status": "applied",
        },
        FakeContext(),
    )

    record = mock_record.call_args.args[1]
    assert record["policy_id"] == policy_id
    assert record["policy_version_id"] == policy_version_id
    assert result["policy_id"] == str(policy_id)


@pytest.mark.asyncio
async def test_list_policy_applications_returns_page(monkeypatch):
    mock_list = AsyncMock(return_value={"items": [], "total": 0})
    monkeypatch.setattr(
        "hermes_db_mcp.tools.agent_self_evolution."
        "agent_self_evolution_repo.list_policy_applications",
        mock_list,
    )

    result = await list_policy_applications(FakeContext(), domain="wechat")

    assert result == {"items": [], "total": 0, "limit": 50, "offset": 0}


def test_register_tools_imports_agent_self_evolution_module():
    register_tools()
