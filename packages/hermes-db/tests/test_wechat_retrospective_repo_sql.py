from datetime import date
from uuid import uuid4

import pytest

from hermes_db_mcp.repositories import wechat_retrospective_repo


class FakeTransaction:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        self.conn.transaction_entries += 1
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def __init__(self):
        self.fetchrow_calls = []
        self.fetch_calls = []
        self.transaction_entries = 0

    def transaction(self):
        return FakeTransaction(self)

    async def fetchrow(self, sql, *params):
        self.fetchrow_calls.append((sql, params))
        if "SELECT count(*) AS total" in sql:
            return {"total": 0}
        if "INSERT INTO hermes.topic_performance" in sql:
            return {"performance_id": params[0], "account": params[1]}
        if "INSERT INTO hermes.wechat_retrospective_reports" in sql:
            return {"report_id": params[0], "account": params[1]}
        if "SELECT" in sql and "FROM hermes.wechat_retrospective_reports" in sql:
            return {"report_id": params[0]}
        if "INSERT INTO hermes.topic_optimization_suggestions" in sql:
            return {"suggestion_id": params[0], "account": params[1]}
        if "UPDATE hermes.topic_optimization_suggestions" in sql:
            return {"suggestion_id": params[0], "review_status": params[1]}
        if "INSERT INTO hermes.learning_candidates" in sql:
            return {"candidate_id": params[0], "account": params[1]}
        if "UPDATE hermes.learning_candidates" in sql:
            return {"candidate_id": params[0], "status": params[1]}
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
    def __init__(self):
        self.conn = FakeConnection()

    def acquire(self):
        return FakeAcquire(self.conn)


def performance_row(**overrides):
    row = {
        "account": "acct",
        "article_id": uuid4(),
        "topic_id": uuid4(),
        "stat_date": date(2026, 6, 7),
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
    row.update(overrides)
    return row


def report_row(**overrides):
    row = {
        "account": "acct",
        "report_type": "article",
        "period_start": date(2026, 6, 1),
        "period_end": date(2026, 6, 7),
        "article_id": uuid4(),
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
    row.update(overrides)
    return row


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


@pytest.mark.asyncio
async def test_upsert_topic_performance_uses_identity_conflict_and_jsonb():
    conn = FakeConnection()

    row = await wechat_retrospective_repo.upsert_topic_performance(
        conn,
        performance_row(),
    )

    sql, params = conn.fetchrow_calls[0]
    assert row["account"] == "acct"
    assert "INSERT INTO hermes.topic_performance" in sql
    assert "ON CONFLICT (account, article_id, window_label, scoring_version)" in sql
    assert "updated_at = now()" in sql
    assert params[1] == "acct"
    assert params[5] == "D+7"
    assert params[16].startswith("[")
    assert params[17] == "{}"
    assert params[20] == "[]"


@pytest.mark.asyncio
async def test_list_topic_performance_builds_filters_count_and_ordering():
    pool = FakePool()
    article_id = uuid4()
    topic_id = uuid4()

    result = await wechat_retrospective_repo.list_topic_performance(
        pool,
        account="acct",
        article_id=article_id,
        topic_id=topic_id,
        window_label="D+7",
        scoring_version="wechat-retro-v1",
        date_from=date(2026, 6, 1),
        date_to=date(2026, 6, 7),
        limit=10,
        offset=5,
    )

    sql, params = pool.conn.fetch_calls[0]
    count_sql, count_params = pool.conn.fetchrow_calls[0]
    assert result == {"items": [], "total": 0}
    assert "FROM hermes.topic_performance" in sql
    assert "account = $1" in sql
    assert "article_id = $2" in sql
    assert "topic_id = $3" in sql
    assert "window_label = $4" in sql
    assert "scoring_version = $5" in sql
    assert "stat_date >= $6" in sql
    assert "stat_date <= $7" in sql
    assert "ORDER BY stat_date DESC, updated_at DESC" in sql
    assert params == (
        "acct",
        article_id,
        topic_id,
        "D+7",
        "wechat-retro-v1",
        date(2026, 6, 1),
        date(2026, 6, 7),
        10,
        5,
    )
    assert "SELECT count(*) AS total" in count_sql
    assert count_params == params[:-2]


@pytest.mark.asyncio
async def test_create_get_and_list_retrospective_reports_use_report_contract():
    pool = FakePool()
    report_id = uuid4()
    article_id = uuid4()

    created = await wechat_retrospective_repo.create_wechat_retrospective_report(
        pool.conn,
        report_row(report_id=report_id, article_id=article_id),
    )
    fetched = await wechat_retrospective_repo.get_wechat_retrospective_report(
        pool.conn,
        report_id,
    )
    listed = await wechat_retrospective_repo.list_wechat_retrospective_reports(
        pool,
        account="acct",
        report_type="article",
        article_id=article_id,
        date_from=date(2026, 6, 1),
        date_to=date(2026, 6, 7),
        limit=20,
        offset=0,
    )

    insert_sql, insert_params = pool.conn.fetchrow_calls[0]
    get_sql, get_params = pool.conn.fetchrow_calls[1]
    list_sql, list_params = pool.conn.fetch_calls[0]
    count_sql, _count_params = pool.conn.fetchrow_calls[2]
    assert created["report_id"] == report_id
    assert fetched == {"report_id": report_id}
    assert listed == {"items": [], "total": 0}
    assert "INSERT INTO hermes.wechat_retrospective_reports" in insert_sql
    assert insert_params[11].startswith("[")
    assert "performance_ids_json" in insert_sql
    assert "FROM hermes.wechat_retrospective_reports" in get_sql
    assert get_params == (report_id,)
    assert "period_start >= $4" in list_sql
    assert "period_end <= $5" in list_sql
    assert list_params == (
        "acct",
        "article",
        article_id,
        date(2026, 6, 1),
        date(2026, 6, 7),
        20,
        0,
    )
    assert "SELECT count(*) AS total" in count_sql


@pytest.mark.asyncio
async def test_create_topic_optimization_suggestions_uses_transaction_and_jsonb():
    pool = FakePool()
    report_id = uuid4()

    rows = await wechat_retrospective_repo.create_topic_optimization_suggestions(
        pool,
        account="acct",
        report_id=report_id,
        items=[suggestion_item()],
    )

    sql, params = pool.conn.fetchrow_calls[0]
    assert pool.conn.transaction_entries == 1
    assert rows[0]["account"] == "acct"
    assert "INSERT INTO hermes.topic_optimization_suggestions" in sql
    assert "report_id" in sql
    assert params[1] == "acct"
    assert params[2] == report_id
    assert params[7] == "{}"
    assert params[8] == '{"action": "cooldown"}'
    assert params[12] == "pending"


@pytest.mark.asyncio
async def test_list_topic_optimization_suggestions_builds_filters_and_total():
    pool = FakePool()
    report_id = uuid4()
    target_id = uuid4()

    await wechat_retrospective_repo.list_topic_optimization_suggestions(
        pool,
        account="acct",
        report_id=report_id,
        review_status="pending",
        suggestion_type="cooldown",
        target_kind="topic",
        target_id=target_id,
        target_key="food",
        limit=25,
        offset=2,
    )

    sql, params = pool.conn.fetch_calls[0]
    count_sql, count_params = pool.conn.fetchrow_calls[0]
    assert "FROM hermes.topic_optimization_suggestions" in sql
    assert "review_status = $3" in sql
    assert "suggestion_type = $4" in sql
    assert "target_kind = $5" in sql
    assert "target_id = $6" in sql
    assert "target_key = $7" in sql
    assert params == (
        "acct",
        report_id,
        "pending",
        "cooldown",
        "topic",
        target_id,
        "food",
        25,
        2,
    )
    assert "SELECT count(*) AS total" in count_sql
    assert count_params == params[:-2]


@pytest.mark.asyncio
async def test_review_topic_optimization_suggestion_updates_only_suggestion_row():
    conn = FakeConnection()
    suggestion_id = uuid4()

    row = await wechat_retrospective_repo.review_topic_optimization_suggestion(
        conn,
        suggestion_id=suggestion_id,
        review_status="approved",
        reviewed_by="operator",
        review_note="looks good",
    )

    sql, params = conn.fetchrow_calls[0]
    assert row == {"suggestion_id": suggestion_id, "review_status": "approved"}
    assert "UPDATE hermes.topic_optimization_suggestions" in sql
    assert "UPDATE hermes.topics" not in sql
    assert "reviewed_at = now()" in sql
    assert "updated_at = now()" in sql
    assert params == (suggestion_id, "approved", "operator", "looks good", None)


@pytest.mark.asyncio
async def test_list_approved_topic_ranking_hints_filters_status_expiry_and_target():
    pool = FakePool()
    target_id = uuid4()

    await wechat_retrospective_repo.list_approved_topic_ranking_hints(
        pool,
        account="acct",
        target_kind="topic",
        target_id=target_id,
        limit=10,
        offset=0,
    )

    sql, params = pool.conn.fetch_calls[0]
    count_sql, count_params = pool.conn.fetchrow_calls[0]
    assert "review_status IN ('approved', 'applied')" in sql
    assert "(expires_at IS NULL OR expires_at > now())" in sql
    assert "account = $1" in sql
    assert "target_kind = $2" in sql
    assert "target_id = $3" in sql
    assert params == ("acct", "topic", target_id, 10, 0)
    assert "review_status IN ('approved', 'applied')" in count_sql
    assert count_params == params[:-2]


@pytest.mark.asyncio
async def test_create_learning_candidates_uses_transaction_and_source_refs_json():
    pool = FakePool()
    source_report_id = uuid4()

    rows = await wechat_retrospective_repo.create_learning_candidates(
        pool,
        account="acct",
        source_report_id=source_report_id,
        items=[learning_candidate_item()],
    )

    sql, params = pool.conn.fetchrow_calls[0]
    assert pool.conn.transaction_entries == 1
    assert rows[0]["account"] == "acct"
    assert "INSERT INTO hermes.learning_candidates" in sql
    assert params[1] == "acct"
    assert params[3] == source_report_id
    assert params[4].startswith("[")
    assert params[6] == "{}"
    assert params[11] == "pending_review"


@pytest.mark.asyncio
async def test_list_learning_candidates_builds_filters_and_total():
    pool = FakePool()
    source_report_id = uuid4()

    await wechat_retrospective_repo.list_learning_candidates(
        pool,
        account="acct",
        domain="wechat",
        source_report_id=source_report_id,
        status="pending_review",
        candidate_type="topic_strategy",
        limit=20,
        offset=3,
    )

    sql, params = pool.conn.fetch_calls[0]
    count_sql, count_params = pool.conn.fetchrow_calls[0]
    assert "FROM hermes.learning_candidates" in sql
    assert "account = $1" in sql
    assert "domain = $2" in sql
    assert "source_report_id = $3" in sql
    assert "status = $4" in sql
    assert "candidate_type = $5" in sql
    assert params == (
        "acct",
        "wechat",
        source_report_id,
        "pending_review",
        "topic_strategy",
        20,
        3,
    )
    assert "SELECT count(*) AS total" in count_sql
    assert count_params == params[:-2]


@pytest.mark.asyncio
async def test_review_learning_candidate_updates_review_fields_and_policy_id():
    conn = FakeConnection()
    candidate_id = uuid4()

    row = await wechat_retrospective_repo.review_learning_candidate(
        conn,
        candidate_id=candidate_id,
        status="approved",
        reviewed_by="operator",
        review_note="ship it",
        policy_id="policy-1",
    )

    sql, params = conn.fetchrow_calls[0]
    assert row == {"candidate_id": candidate_id, "status": "approved"}
    assert "UPDATE hermes.learning_candidates" in sql
    assert "reviewed_at = now()" in sql
    assert "policy_id = COALESCE($5, policy_id)" in sql
    assert params == (candidate_id, "approved", "operator", "ship it", "policy-1")
