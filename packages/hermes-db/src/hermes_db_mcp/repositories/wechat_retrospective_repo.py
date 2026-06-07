from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date
import json
from uuid import UUID, uuid4

import asyncpg


TOPIC_PERFORMANCE_COLUMNS = """
    performance_id, account, article_id, topic_id, stat_date, window_label,
    scoring_version, baseline_version, normalized_score, read_score,
    engagement_score, share_score, conversion_score, confidence, provisional,
    low_sample_size, metric_snapshot_ids_json, baseline_snapshot_json,
    diagnosis_json, evidence_refs_json, warnings_json, created_at, updated_at
"""

RETROSPECTIVE_REPORT_COLUMNS = """
    report_id, account, report_type, period_start, period_end, article_id,
    scoring_version, generation_mode, status, sample_size, low_sample_size,
    performance_ids_json, summary_json, narrative_markdown,
    high_performing_themes_json, low_performing_themes_json,
    title_patterns_json, recommendations_json, evidence_refs_json,
    warnings_json, created_at, updated_at
"""

TOPIC_SUGGESTION_COLUMNS = """
    suggestion_id, account, report_id, suggestion_type, target_kind, target_id,
    target_key, current_value_json, proposed_value_json, rationale, confidence,
    evidence_refs_json, review_status, reviewed_by, reviewed_at, review_note,
    applied_at, application_trace_id, expires_at, created_at, updated_at
"""

LEARNING_CANDIDATE_COLUMNS = """
    candidate_id, account, domain, source_report_id, source_suggestion_ids_json,
    candidate_type, scope_json, trigger_conditions_json, proposed_policy_json,
    confidence, evidence_refs_json, status, policy_id, reviewed_by, reviewed_at,
    review_note, created_at, updated_at
"""


def _jsonb(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def _row(row: asyncpg.Record | dict | None) -> dict | None:
    return dict(row) if row else None


@asynccontextmanager
async def _connection(pool_or_conn):
    if hasattr(pool_or_conn, "acquire"):
        async with pool_or_conn.acquire() as conn:
            yield conn
    else:
        yield pool_or_conn


async def _fetchrow(pool_or_conn, sql: str, *params):
    async with _connection(pool_or_conn) as conn:
        return await conn.fetchrow(sql, *params)


async def _fetch(pool_or_conn, sql: str, *params):
    async with _connection(pool_or_conn) as conn:
        return await conn.fetch(sql, *params)


def _add_eq_filter(
    conditions: list[str],
    params: list,
    *,
    column: str,
    value,
    idx: int,
) -> int:
    if value is not None:
        conditions.append(f"{column} = ${idx}")
        params.append(value)
        return idx + 1
    return idx


def _where(conditions: list[str]) -> str:
    return "WHERE " + " AND ".join(conditions) if conditions else ""


async def _list_with_total(
    pool: asyncpg.Pool,
    *,
    columns: str,
    table: str,
    conditions: list[str],
    params: list,
    order_by: str,
    limit: int,
    offset: int,
) -> dict:
    where = _where(conditions)
    item_params = params + [limit, offset]
    limit_idx = len(params) + 1
    sql = f"""
        SELECT {columns}
        FROM {table}
        {where}
        {order_by}
        LIMIT ${limit_idx} OFFSET ${limit_idx + 1}
    """
    count_sql = f"""
        SELECT count(*) AS total
        FROM {table}
        {where}
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *item_params)
        total_row = await conn.fetchrow(count_sql, *params)
    return {
        "items": [dict(row) for row in rows],
        "total": int(total_row["total"]) if total_row else 0,
    }


def _topic_performance_params(record: dict) -> list:
    return [
        record.get("performance_id") or uuid4(),
        record["account"],
        record["article_id"],
        record.get("topic_id"),
        record["stat_date"],
        record["window_label"],
        record["scoring_version"],
        record["baseline_version"],
        record.get("normalized_score"),
        record.get("read_score"),
        record.get("engagement_score"),
        record.get("share_score"),
        record.get("conversion_score"),
        record["confidence"],
        record.get("provisional", False),
        record.get("low_sample_size", False),
        _jsonb(record.get("metric_snapshot_ids") or record.get("metric_snapshot_ids_json") or []),
        _jsonb(record.get("baseline_snapshot") or record.get("baseline_snapshot_json") or {}),
        _jsonb(record.get("diagnosis") or record.get("diagnosis_json") or {}),
        _jsonb(record.get("evidence_refs") or record.get("evidence_refs_json") or {}),
        _jsonb(record.get("warnings") or record.get("warnings_json") or []),
    ]


async def upsert_topic_performance(pool_or_conn, record: dict) -> dict:
    row = await _fetchrow(
        pool_or_conn,
        f"""
        INSERT INTO hermes.topic_performance (
            performance_id, account, article_id, topic_id, stat_date,
            window_label, scoring_version, baseline_version, normalized_score,
            read_score, engagement_score, share_score, conversion_score,
            confidence, provisional, low_sample_size, metric_snapshot_ids_json,
            baseline_snapshot_json, diagnosis_json, evidence_refs_json, warnings_json
        )
        VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
            $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21
        )
        ON CONFLICT (account, article_id, window_label, scoring_version) DO UPDATE SET
            topic_id = EXCLUDED.topic_id,
            stat_date = EXCLUDED.stat_date,
            baseline_version = EXCLUDED.baseline_version,
            normalized_score = EXCLUDED.normalized_score,
            read_score = EXCLUDED.read_score,
            engagement_score = EXCLUDED.engagement_score,
            share_score = EXCLUDED.share_score,
            conversion_score = EXCLUDED.conversion_score,
            confidence = EXCLUDED.confidence,
            provisional = EXCLUDED.provisional,
            low_sample_size = EXCLUDED.low_sample_size,
            metric_snapshot_ids_json = EXCLUDED.metric_snapshot_ids_json,
            baseline_snapshot_json = EXCLUDED.baseline_snapshot_json,
            diagnosis_json = EXCLUDED.diagnosis_json,
            evidence_refs_json = EXCLUDED.evidence_refs_json,
            warnings_json = EXCLUDED.warnings_json,
            updated_at = now()
        RETURNING {TOPIC_PERFORMANCE_COLUMNS}
        """,
        *_topic_performance_params(record),
    )
    return dict(row)


async def list_topic_performance(
    pool: asyncpg.Pool,
    *,
    account: str | None = None,
    article_id: UUID | None = None,
    topic_id: UUID | None = None,
    window_label: str | None = None,
    scoring_version: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    conditions = []
    params: list = []
    idx = 1
    for column, value in (
        ("account", account),
        ("article_id", article_id),
        ("topic_id", topic_id),
        ("window_label", window_label),
        ("scoring_version", scoring_version),
    ):
        idx = _add_eq_filter(conditions, params, column=column, value=value, idx=idx)
    if date_from is not None:
        conditions.append(f"stat_date >= ${idx}")
        params.append(date_from)
        idx += 1
    if date_to is not None:
        conditions.append(f"stat_date <= ${idx}")
        params.append(date_to)

    return await _list_with_total(
        pool,
        columns=TOPIC_PERFORMANCE_COLUMNS,
        table="hermes.topic_performance",
        conditions=conditions,
        params=params,
        order_by="ORDER BY stat_date DESC, updated_at DESC",
        limit=limit,
        offset=offset,
    )


def _report_params(record: dict) -> list:
    return [
        record.get("report_id") or uuid4(),
        record["account"],
        record["report_type"],
        record["period_start"],
        record["period_end"],
        record.get("article_id"),
        record["scoring_version"],
        record["generation_mode"],
        record["status"],
        record.get("sample_size", 0),
        record.get("low_sample_size", False),
        _jsonb(record.get("performance_ids") or record.get("performance_ids_json") or []),
        _jsonb(record.get("summary") or record.get("summary_json") or {}),
        record.get("narrative_markdown"),
        _jsonb(
            record.get("high_performing_themes")
            or record.get("high_performing_themes_json")
            or []
        ),
        _jsonb(
            record.get("low_performing_themes")
            or record.get("low_performing_themes_json")
            or []
        ),
        _jsonb(record.get("title_patterns") or record.get("title_patterns_json") or []),
        _jsonb(record.get("recommendations") or record.get("recommendations_json") or []),
        _jsonb(record.get("evidence_refs") or record.get("evidence_refs_json") or {}),
        _jsonb(record.get("warnings") or record.get("warnings_json") or []),
    ]


async def create_wechat_retrospective_report(pool_or_conn, record: dict) -> dict:
    row = await _fetchrow(
        pool_or_conn,
        f"""
        INSERT INTO hermes.wechat_retrospective_reports (
            report_id, account, report_type, period_start, period_end,
            article_id, scoring_version, generation_mode, status, sample_size,
            low_sample_size, performance_ids_json, summary_json,
            narrative_markdown, high_performing_themes_json,
            low_performing_themes_json, title_patterns_json,
            recommendations_json, evidence_refs_json, warnings_json
        )
        VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
            $11, $12, $13, $14, $15, $16, $17, $18, $19, $20
        )
        RETURNING {RETROSPECTIVE_REPORT_COLUMNS}
        """,
        *_report_params(record),
    )
    return dict(row)


async def get_wechat_retrospective_report(pool_or_conn, report_id: UUID) -> dict | None:
    row = await _fetchrow(
        pool_or_conn,
        f"""
        SELECT {RETROSPECTIVE_REPORT_COLUMNS}
        FROM hermes.wechat_retrospective_reports
        WHERE report_id = $1
        """,
        report_id,
    )
    return _row(row)


async def list_wechat_retrospective_reports(
    pool: asyncpg.Pool,
    *,
    account: str | None = None,
    report_type: str | None = None,
    article_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    conditions = []
    params: list = []
    idx = 1
    for column, value in (
        ("account", account),
        ("report_type", report_type),
        ("article_id", article_id),
    ):
        idx = _add_eq_filter(conditions, params, column=column, value=value, idx=idx)
    if date_from is not None:
        conditions.append(f"period_start >= ${idx}")
        params.append(date_from)
        idx += 1
    if date_to is not None:
        conditions.append(f"period_end <= ${idx}")
        params.append(date_to)

    return await _list_with_total(
        pool,
        columns=RETROSPECTIVE_REPORT_COLUMNS,
        table="hermes.wechat_retrospective_reports",
        conditions=conditions,
        params=params,
        order_by="ORDER BY period_start DESC, created_at DESC",
        limit=limit,
        offset=offset,
    )


def _suggestion_params(account: str, report_id: UUID, item: dict) -> list:
    return [
        item.get("suggestion_id") or uuid4(),
        item.get("account") or account,
        item.get("report_id") or report_id,
        item["suggestion_type"],
        item["target_kind"],
        item.get("target_id"),
        item.get("target_key"),
        _jsonb(item.get("current_value") or item.get("current_value_json") or {}),
        _jsonb(item.get("proposed_value") or item.get("proposed_value_json") or {}),
        item["rationale"],
        item["confidence"],
        _jsonb(item.get("evidence_refs") or item.get("evidence_refs_json") or {}),
        item.get("review_status", "pending"),
        item.get("expires_at"),
    ]


async def _insert_topic_suggestion(conn, account: str, report_id: UUID, item: dict) -> dict:
    row = await conn.fetchrow(
        f"""
        INSERT INTO hermes.topic_optimization_suggestions (
            suggestion_id, account, report_id, suggestion_type, target_kind,
            target_id, target_key, current_value_json, proposed_value_json,
            rationale, confidence, evidence_refs_json, review_status, expires_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
        RETURNING {TOPIC_SUGGESTION_COLUMNS}
        """,
        *_suggestion_params(account, report_id, item),
    )
    return dict(row)


async def create_topic_optimization_suggestions(
    pool_or_conn,
    *,
    account: str,
    report_id: UUID,
    items: list[dict],
) -> list[dict]:
    async with _connection(pool_or_conn) as conn:
        async with conn.transaction():
            return [
                await _insert_topic_suggestion(conn, account, report_id, item)
                for item in items
            ]


async def list_topic_optimization_suggestions(
    pool: asyncpg.Pool,
    *,
    account: str | None = None,
    report_id: UUID | None = None,
    review_status: str | None = None,
    suggestion_type: str | None = None,
    target_kind: str | None = None,
    target_id: UUID | None = None,
    target_key: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    conditions = []
    params: list = []
    idx = 1
    for column, value in (
        ("account", account),
        ("report_id", report_id),
        ("review_status", review_status),
        ("suggestion_type", suggestion_type),
        ("target_kind", target_kind),
        ("target_id", target_id),
        ("target_key", target_key),
    ):
        idx = _add_eq_filter(conditions, params, column=column, value=value, idx=idx)

    return await _list_with_total(
        pool,
        columns=TOPIC_SUGGESTION_COLUMNS,
        table="hermes.topic_optimization_suggestions",
        conditions=conditions,
        params=params,
        order_by="ORDER BY created_at DESC",
        limit=limit,
        offset=offset,
    )


async def review_topic_optimization_suggestion(
    pool_or_conn,
    *,
    suggestion_id: UUID,
    review_status: str,
    reviewed_by: str | None = None,
    review_note: str | None = None,
    application_trace_id: str | None = None,
) -> dict | None:
    row = await _fetchrow(
        pool_or_conn,
        f"""
        UPDATE hermes.topic_optimization_suggestions
        SET review_status = $2,
            reviewed_by = $3,
            reviewed_at = now(),
            review_note = $4,
            application_trace_id = COALESCE($5, application_trace_id),
            updated_at = now()
        WHERE suggestion_id = $1
        RETURNING {TOPIC_SUGGESTION_COLUMNS}
        """,
        suggestion_id,
        review_status,
        reviewed_by,
        review_note,
        application_trace_id,
    )
    return _row(row)


async def list_approved_topic_ranking_hints(
    pool: asyncpg.Pool,
    *,
    account: str,
    target_kind: str | None = None,
    target_id: UUID | None = None,
    target_key: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    conditions = [
        "account = $1",
        "review_status IN ('approved', 'applied')",
        "(expires_at IS NULL OR expires_at > now())",
    ]
    params: list = [account]
    idx = 2
    for column, value in (
        ("target_kind", target_kind),
        ("target_id", target_id),
        ("target_key", target_key),
    ):
        idx = _add_eq_filter(conditions, params, column=column, value=value, idx=idx)

    return await _list_with_total(
        pool,
        columns=TOPIC_SUGGESTION_COLUMNS,
        table="hermes.topic_optimization_suggestions",
        conditions=conditions,
        params=params,
        order_by="ORDER BY created_at DESC",
        limit=limit,
        offset=offset,
    )


def _learning_candidate_params(account: str, source_report_id: UUID, item: dict) -> list:
    return [
        item.get("candidate_id") or uuid4(),
        item.get("account") or account,
        item["domain"],
        item.get("source_report_id") or source_report_id,
        _jsonb(item.get("source_suggestion_ids") or item.get("source_suggestion_ids_json") or []),
        item["candidate_type"],
        _jsonb(item.get("scope") or item.get("scope_json") or {}),
        _jsonb(item.get("trigger_conditions") or item.get("trigger_conditions_json") or {}),
        _jsonb(item.get("proposed_policy") or item.get("proposed_policy_json") or {}),
        item["confidence"],
        _jsonb(item.get("evidence_refs") or item.get("evidence_refs_json") or {}),
        item.get("status", "pending_review"),
    ]


async def _insert_learning_candidate(
    conn,
    account: str,
    source_report_id: UUID,
    item: dict,
) -> dict:
    row = await conn.fetchrow(
        f"""
        INSERT INTO hermes.learning_candidates (
            candidate_id, account, domain, source_report_id,
            source_suggestion_ids_json, candidate_type, scope_json,
            trigger_conditions_json, proposed_policy_json, confidence,
            evidence_refs_json, status
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        RETURNING {LEARNING_CANDIDATE_COLUMNS}
        """,
        *_learning_candidate_params(account, source_report_id, item),
    )
    return dict(row)


async def create_learning_candidates(
    pool_or_conn,
    *,
    account: str,
    source_report_id: UUID,
    items: list[dict],
) -> list[dict]:
    async with _connection(pool_or_conn) as conn:
        async with conn.transaction():
            return [
                await _insert_learning_candidate(conn, account, source_report_id, item)
                for item in items
            ]


async def list_learning_candidates(
    pool: asyncpg.Pool,
    *,
    account: str | None = None,
    domain: str | None = None,
    source_report_id: UUID | None = None,
    status: str | None = None,
    candidate_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    conditions = []
    params: list = []
    idx = 1
    for column, value in (
        ("account", account),
        ("domain", domain),
        ("source_report_id", source_report_id),
        ("status", status),
        ("candidate_type", candidate_type),
    ):
        idx = _add_eq_filter(conditions, params, column=column, value=value, idx=idx)

    return await _list_with_total(
        pool,
        columns=LEARNING_CANDIDATE_COLUMNS,
        table="hermes.learning_candidates",
        conditions=conditions,
        params=params,
        order_by="ORDER BY created_at DESC",
        limit=limit,
        offset=offset,
    )


async def review_learning_candidate(
    pool_or_conn,
    *,
    candidate_id: UUID,
    status: str,
    reviewed_by: str | None = None,
    review_note: str | None = None,
    policy_id: str | None = None,
) -> dict | None:
    row = await _fetchrow(
        pool_or_conn,
        f"""
        UPDATE hermes.learning_candidates
        SET status = $2,
            reviewed_by = $3,
            reviewed_at = now(),
            review_note = $4,
            policy_id = COALESCE($5, policy_id),
            updated_at = now()
        WHERE candidate_id = $1
        RETURNING {LEARNING_CANDIDATE_COLUMNS}
        """,
        candidate_id,
        status,
        reviewed_by,
        review_note,
        policy_id,
    )
    return _row(row)
