from unittest.mock import AsyncMock

import pytest

from hermes_db_mcp.services.schema import (
    inspect_agent_self_evolution_foundation_schema,
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


POLICY_COLUMNS = {
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

APPLICATION_COLUMNS = {
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

CANDIDATE_COLUMNS = {
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

POLICY_CONSTRAINTS = {
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
}

APPLICATION_CONSTRAINTS = {
    "policy_applications_pkey",
    "policy_applications_policy_version_id_fkey",
    "chk_policy_applications_version_positive",
    "chk_policy_applications_status",
    "chk_policy_applications_scope_json_object",
    "chk_policy_applications_matched_conditions_json_object",
    "chk_policy_applications_applied_action_json_object",
    "chk_policy_applications_outcome_summary_json_object",
    "chk_policy_applications_error_summary_json_object",
}

INDEXES = {
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
}


def column_rows(names):
    return [FakeRow(column_name=name) for name in names]


def constraint_rows(names):
    return [FakeRow(conname=name) for name in names]


def index_rows(names):
    return [FakeRow(indexname=name) for name in names]


def complete_fetch_results(
    *,
    policy_columns=POLICY_COLUMNS,
    application_columns=APPLICATION_COLUMNS,
    candidate_columns=CANDIDATE_COLUMNS,
    policy_constraints=POLICY_CONSTRAINTS,
    application_constraints=APPLICATION_CONSTRAINTS,
    indexes=INDEXES,
):
    return [
        column_rows(policy_columns),
        column_rows(application_columns),
        column_rows(candidate_columns),
        constraint_rows(policy_constraints),
        constraint_rows(application_constraints),
        index_rows(indexes),
    ]


@pytest.mark.asyncio
async def test_inspect_agent_self_evolution_schema_returns_true_for_complete_schema():
    pool = FakePool(complete_fetch_results())

    assert await inspect_agent_self_evolution_foundation_schema(pool) == {
        "agent_self_evolution_foundation": True,
    }


@pytest.mark.asyncio
async def test_inspect_agent_self_evolution_schema_reflects_missing_table():
    pool = FakePool([[], [], [], [], [], []])

    assert await inspect_agent_self_evolution_foundation_schema(pool) == {
        "agent_self_evolution_foundation": False,
    }


@pytest.mark.asyncio
async def test_inspect_agent_self_evolution_schema_reflects_missing_column():
    pool = FakePool(
        complete_fetch_results(policy_columns=POLICY_COLUMNS - {"policy_body_json"})
    )

    assert await inspect_agent_self_evolution_foundation_schema(pool) == {
        "agent_self_evolution_foundation": False,
    }


@pytest.mark.asyncio
async def test_inspect_agent_self_evolution_schema_reflects_missing_constraint():
    pool = FakePool(
        complete_fetch_results(
            policy_constraints=POLICY_CONSTRAINTS - {"chk_agent_policies_policy_type"}
        )
    )

    assert await inspect_agent_self_evolution_foundation_schema(pool) == {
        "agent_self_evolution_foundation": False,
    }


@pytest.mark.asyncio
async def test_inspect_agent_self_evolution_schema_reflects_missing_index():
    pool = FakePool(
        complete_fetch_results(indexes=INDEXES - {"idx_policy_applications_domain_task"})
    )

    assert await inspect_agent_self_evolution_foundation_schema(pool) == {
        "agent_self_evolution_foundation": False,
    }
