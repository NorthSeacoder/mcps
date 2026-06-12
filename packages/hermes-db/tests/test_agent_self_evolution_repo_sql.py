from uuid import uuid4

import pytest

from hermes_db_mcp.repositories import agent_self_evolution_repo


class FakeTransaction:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        self.conn.transaction_entries += 1
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def __init__(self, *, candidate_status="approved"):
        self.candidate_status = candidate_status
        self.fetchrow_calls = []
        self.fetch_calls = []
        self.transaction_entries = 0
        self.policy_id = uuid4()
        self.policy_version_id = uuid4()

    def transaction(self):
        return FakeTransaction(self)

    async def fetchrow(self, sql, *params):
        self.fetchrow_calls.append((sql, params))
        if "SELECT count(*) AS total" in sql:
            return {"total": 0}
        if "FROM hermes.learning_candidates" in sql and "FOR UPDATE" in sql:
            return {
                "candidate_id": params[0],
                "domain": "wechat",
                "candidate_type": "topic_strategy",
                "scope_json": {"account": "acct"},
                "trigger_conditions_json": {},
                "proposed_policy_json": {"rule": "prefer high confidence"},
                "evidence_refs_json": {},
                "status": self.candidate_status,
                "policy_id": str(self.policy_id) if self.candidate_status == "exported_to_policy" else None,
            }
        if "FROM hermes.agent_policies" in sql and "source_candidate_id = $1" in sql:
            return None
        if "INSERT INTO hermes.agent_policies" in sql:
            return {
                "policy_version_id": params[0],
                "policy_id": params[1],
                "version": params[2] if isinstance(params[2], int) else 1,
                "domain": params[3],
                "policy_type": params[4],
                "status": "active",
            }
        if "UPDATE hermes.learning_candidates" in sql:
            return {"candidate_id": params[0]}
        if "UPDATE hermes.agent_policies" in sql and "status = 'disabled'" in sql:
            return {"policy_id": params[0], "status": "disabled"}
        if "SELECT" in sql and "policy_version_id = $2" in sql:
            return {
                "policy_version_id": params[1],
                "policy_id": params[0],
                "version": 1,
                "domain": "wechat",
                "policy_type": "topic_strategy",
                "scope_json": {},
                "task_types_json": [],
                "decision_points_json": [],
                "trigger_conditions_json": {},
                "policy_body_json": {},
                "priority": 0,
                "precedence": "scope_specific_over_global",
                "source_candidate_id": None,
                "evidence_refs_json": {},
                "effective_from": None,
                "effective_until": None,
            }
        if "UPDATE hermes.agent_policies" in sql and "status = 'rolled_back'" in sql:
            return {"policy_version_id": self.policy_version_id}
        if "SELECT COALESCE(MAX(version), 0) + 1" in sql:
            return {"next_version": 3}
        if "INSERT INTO hermes.policy_applications" in sql:
            return {"application_id": params[0], "policy_id": params[6]}
        return None

    async def fetch(self, sql, *params):
        self.fetch_calls.append((sql, params))
        return []


class FakeAcquire:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakePool:
    def __init__(self, *, candidate_status="approved"):
        self.conn = FakeConnection(candidate_status=candidate_status)

    def acquire(self):
        return FakeAcquire(self.conn)


@pytest.mark.asyncio
async def test_promote_learning_candidate_creates_policy_and_updates_candidate():
    pool = FakePool()
    candidate_id = uuid4()

    row = await agent_self_evolution_repo.promote_learning_candidate_to_policy(
        pool,
        candidate_id=candidate_id,
        approved_by="operator",
        task_types=["topic_selection"],
        decision_points=["before_ranking"],
    )

    assert row["status"] == "active"
    assert pool.conn.transaction_entries == 1
    insert_sql, insert_params = next(
        call for call in pool.conn.fetchrow_calls if "INSERT INTO hermes.agent_policies" in call[0]
    )
    assert "source_candidate_id" in insert_sql
    assert insert_params[10] == candidate_id
    update_sql, update_params = next(
        call for call in pool.conn.fetchrow_calls if "UPDATE hermes.learning_candidates" in call[0]
    )
    assert "status = 'exported_to_policy'" in update_sql
    assert update_params[3] == str(row["policy_id"])


@pytest.mark.asyncio
async def test_promote_learning_candidate_rejects_non_approved_candidate():
    pool = FakePool(candidate_status="pending_review")

    with pytest.raises(ValueError, match="invalid_state"):
        await agent_self_evolution_repo.promote_learning_candidate_to_policy(
            pool,
            candidate_id=uuid4(),
            approved_by="operator",
        )


@pytest.mark.asyncio
async def test_list_agent_policies_builds_filters_count_and_ordering():
    pool = FakePool()
    policy_id = uuid4()
    source_candidate_id = uuid4()

    result = await agent_self_evolution_repo.list_agent_policies(
        pool,
        domain="wechat",
        policy_type="topic_strategy",
        status="active",
        source_candidate_id=source_candidate_id,
        policy_id=policy_id,
        limit=10,
        offset=5,
    )

    sql, params = pool.conn.fetch_calls[0]
    assert result == {"items": [], "total": 0}
    assert "FROM hermes.agent_policies" in sql
    assert "domain = $1" in sql
    assert "policy_type = $2" in sql
    assert "status = $3" in sql
    assert "source_candidate_id = $4" in sql
    assert "policy_id = $5" in sql
    assert "ORDER BY priority DESC, created_at DESC" in sql
    assert params == (
        "wechat",
        "topic_strategy",
        "active",
        source_candidate_id,
        policy_id,
        10,
        5,
    )


@pytest.mark.asyncio
async def test_get_applicable_agent_policies_filters_active_scope_task_and_time():
    pool = FakePool()

    result = await agent_self_evolution_repo.get_applicable_agent_policies(
        pool,
        domain="wechat",
        scope={"account": "acct"},
        task_type="topic_selection",
        decision_point="before_ranking",
    )

    sql, params = pool.conn.fetch_calls[0]
    assert result == {"items": [], "total": 0, "warnings": []}
    assert "status = 'active'" in sql
    assert "task_types_json ? $2" in sql
    assert "scope_json <@ $3::jsonb" in sql
    assert "decision_points_json ? $5" in sql
    assert params[0] == "wechat"
    assert params[1] == "topic_selection"
    assert params[2] == '{"account": "acct"}'


@pytest.mark.asyncio
async def test_disable_agent_policy_updates_active_version_only():
    conn = FakeConnection()
    policy_id = uuid4()

    row = await agent_self_evolution_repo.disable_agent_policy(
        conn,
        policy_id=policy_id,
        disabled_by="operator",
        disable_reason="bad outcome",
    )

    sql, params = conn.fetchrow_calls[0]
    assert row["status"] == "disabled"
    assert "WHERE policy_id = $1 AND status = 'active'" in sql
    assert params == (policy_id, "operator", "bad outcome")


@pytest.mark.asyncio
async def test_rollback_agent_policy_copies_target_into_new_active_version():
    pool = FakePool()
    policy_id = uuid4()
    target_version_id = uuid4()

    row = await agent_self_evolution_repo.rollback_agent_policy(
        pool,
        policy_id=policy_id,
        to_policy_version_id=target_version_id,
        reviewed_by="operator",
        review_note="rollback",
    )

    insert_sql, insert_params = pool.conn.fetchrow_calls[-1]
    assert row["status"] == "active"
    assert "INSERT INTO hermes.agent_policies" in insert_sql
    assert insert_params[1] == policy_id
    assert insert_params[2] == 3
    assert insert_params[13] == pool.conn.policy_version_id


@pytest.mark.asyncio
async def test_record_policy_application_inserts_append_only_trace():
    conn = FakeConnection()
    policy_id = uuid4()
    policy_version_id = uuid4()

    row = await agent_self_evolution_repo.record_policy_application(
        conn,
        {
            "domain": "wechat",
            "agent_name": "topic-agent",
            "task_type": "topic_selection",
            "decision_point": "before_ranking",
            "policy_id": policy_id,
            "policy_version_id": policy_version_id,
            "policy_version": 1,
            "application_status": "applied",
            "scope": {"account": "acct"},
        },
    )

    sql, params = conn.fetchrow_calls[0]
    assert row["policy_id"] == policy_id
    assert "INSERT INTO hermes.policy_applications" in sql
    assert params[6] == policy_id
    assert params[7] == policy_version_id
    assert params[9] == '{"account": "acct"}'


@pytest.mark.asyncio
async def test_list_policy_applications_builds_filters_count_and_ordering():
    pool = FakePool()
    policy_id = uuid4()
    policy_version_id = uuid4()

    result = await agent_self_evolution_repo.list_policy_applications(
        pool,
        policy_id=policy_id,
        policy_version_id=policy_version_id,
        run_id="run-1",
        domain="wechat",
        task_type="topic_selection",
        decision_point="before_ranking",
        limit=10,
        offset=5,
    )

    sql, params = pool.conn.fetch_calls[0]
    assert result == {"items": [], "total": 0}
    assert "FROM hermes.policy_applications" in sql
    assert "policy_id = $1" in sql
    assert "policy_version_id = $2" in sql
    assert "run_id = $3" in sql
    assert "domain = $4" in sql
    assert "task_type = $5" in sql
    assert "decision_point = $6" in sql
    assert "ORDER BY created_at DESC" in sql
    assert params == (
        policy_id,
        policy_version_id,
        "run-1",
        "wechat",
        "topic_selection",
        "before_ranking",
        10,
        5,
    )
