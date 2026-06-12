from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
import json
from uuid import UUID, uuid4

import asyncpg


AGENT_POLICY_COLUMNS = """
    policy_version_id, policy_id, version, domain, policy_type, status,
    scope_json, task_types_json, decision_points_json, trigger_conditions_json,
    policy_body_json, priority, precedence, source_candidate_id,
    source_policy_version_id, evidence_refs_json, approved_by, approved_at,
    effective_from, effective_until, disable_reason, metadata_json,
    created_at, updated_at
"""

POLICY_APPLICATION_COLUMNS = """
    application_id, run_id, domain, agent_name, task_type, decision_point,
    policy_id, policy_version_id, policy_version, scope_json,
    matched_conditions_json, application_status, applied_action_json,
    outcome_summary_json, warning, error_summary_json, created_at
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


async def promote_learning_candidate_to_policy(
    pool: asyncpg.Pool,
    *,
    candidate_id: UUID,
    approved_by: str,
    review_note: str | None = None,
    policy_type: str | None = None,
    task_types: list[str] | None = None,
    decision_points: list[str] | None = None,
    effective_from: datetime | None = None,
    effective_until: datetime | None = None,
    priority: int = 0,
    metadata: dict | None = None,
) -> dict | None:
    async with pool.acquire() as conn:
        async with conn.transaction():
            candidate = await conn.fetchrow(
                f"""
                SELECT {LEARNING_CANDIDATE_COLUMNS}
                FROM hermes.learning_candidates
                WHERE candidate_id = $1
                FOR UPDATE
                """,
                candidate_id,
            )
            if candidate is None:
                return None
            if candidate["status"] == "exported_to_policy" and candidate["policy_id"]:
                return await conn.fetchrow(
                    f"""
                    SELECT {AGENT_POLICY_COLUMNS}
                    FROM hermes.agent_policies
                    WHERE policy_id = $1::uuid
                    ORDER BY version DESC
                    LIMIT 1
                    """,
                    str(candidate["policy_id"]),
                )
            if candidate["status"] != "approved":
                raise ValueError("invalid_state: learning candidate must be approved")
            existing = await conn.fetchrow(
                f"""
                SELECT {AGENT_POLICY_COLUMNS}
                FROM hermes.agent_policies
                WHERE source_candidate_id = $1
                ORDER BY version DESC
                LIMIT 1
                """,
                candidate_id,
            )
            if existing is not None:
                await conn.fetchrow(
                    """
                    UPDATE hermes.learning_candidates
                    SET status = 'exported_to_policy',
                        reviewed_by = $2,
                        reviewed_at = now(),
                        review_note = COALESCE($3, review_note),
                        policy_id = $4,
                        updated_at = now()
                    WHERE candidate_id = $1
                    RETURNING candidate_id
                    """,
                    candidate_id,
                    approved_by,
                    review_note,
                    str(existing["policy_id"]),
                )
                return _row(existing)

            policy_id = uuid4()
            policy_version_id = uuid4()
            row = await conn.fetchrow(
                f"""
                INSERT INTO hermes.agent_policies (
                    policy_version_id, policy_id, version, domain, policy_type,
                    status, scope_json, task_types_json, decision_points_json,
                    trigger_conditions_json, policy_body_json, priority,
                    source_candidate_id, evidence_refs_json, approved_by,
                    effective_from, effective_until, metadata_json
                )
                VALUES (
                    $1, $2, 1, $3, $4, 'active', $5, $6, $7, $8, $9, $10,
                    $11, $12, $13, $14, $15, $16
                )
                RETURNING {AGENT_POLICY_COLUMNS}
                """,
                policy_version_id,
                policy_id,
                candidate["domain"],
                policy_type or candidate["candidate_type"],
                _jsonb(candidate["scope_json"] or {}),
                _jsonb(task_types or []),
                _jsonb(decision_points or []),
                _jsonb(candidate["trigger_conditions_json"] or {}),
                _jsonb(candidate["proposed_policy_json"] or {}),
                priority,
                candidate_id,
                _jsonb(candidate["evidence_refs_json"] or {}),
                approved_by,
                effective_from,
                effective_until,
                _jsonb(metadata or {}),
            )
            await conn.fetchrow(
                """
                UPDATE hermes.learning_candidates
                SET status = 'exported_to_policy',
                    reviewed_by = $2,
                    reviewed_at = now(),
                    review_note = COALESCE($3, review_note),
                    policy_id = $4,
                    updated_at = now()
                WHERE candidate_id = $1
                RETURNING candidate_id
                """,
                candidate_id,
                approved_by,
                review_note,
                str(row["policy_id"]),
            )
            return _row(row)


async def list_agent_policies(
    pool: asyncpg.Pool,
    *,
    domain: str | None = None,
    policy_type: str | None = None,
    status: str | None = None,
    source_candidate_id: UUID | None = None,
    policy_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    conditions = []
    params: list = []
    idx = 1
    for column, value in (
        ("domain", domain),
        ("policy_type", policy_type),
        ("status", status),
        ("source_candidate_id", source_candidate_id),
        ("policy_id", policy_id),
    ):
        idx = _add_eq_filter(conditions, params, column=column, value=value, idx=idx)
    return await _list_with_total(
        pool,
        columns=AGENT_POLICY_COLUMNS,
        table="hermes.agent_policies",
        conditions=conditions,
        params=params,
        order_by="ORDER BY priority DESC, created_at DESC",
        limit=limit,
        offset=offset,
    )


async def get_applicable_agent_policies(
    pool: asyncpg.Pool,
    *,
    domain: str,
    scope: dict,
    task_type: str,
    decision_point: str | None = None,
    now: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    conditions = [
        "domain = $1",
        "status = 'active'",
        "(effective_from IS NULL OR effective_from <= COALESCE($4, now()))",
        "(effective_until IS NULL OR effective_until > COALESCE($4, now()))",
        "(task_types_json = '[]'::jsonb OR task_types_json ? $2)",
        "(scope_json = '{}'::jsonb OR scope_json <@ $3::jsonb)",
    ]
    params: list = [domain, task_type, _jsonb(scope), now]
    if decision_point is not None:
        conditions.append("(decision_points_json = '[]'::jsonb OR decision_points_json ? $5)")
        params.append(decision_point)
    result = await _list_with_total(
        pool,
        columns=AGENT_POLICY_COLUMNS,
        table="hermes.agent_policies",
        conditions=conditions,
        params=params,
        order_by="ORDER BY priority DESC, created_at DESC",
        limit=limit,
        offset=offset,
    )
    result["warnings"] = []
    return result


async def disable_agent_policy(
    pool_or_conn,
    *,
    policy_id: UUID,
    disabled_by: str,
    disable_reason: str,
) -> dict | None:
    async with _connection(pool_or_conn) as conn:
        row = await conn.fetchrow(
            f"""
            UPDATE hermes.agent_policies
            SET status = 'disabled',
                disable_reason = $3,
                metadata_json = metadata_json || jsonb_build_object('disabled_by', $2),
                updated_at = now()
            WHERE policy_id = $1 AND status = 'active'
            RETURNING {AGENT_POLICY_COLUMNS}
            """,
            policy_id,
            disabled_by,
            disable_reason,
        )
    return _row(row)


async def rollback_agent_policy(
    pool: asyncpg.Pool,
    *,
    policy_id: UUID,
    to_policy_version_id: UUID,
    reviewed_by: str,
    review_note: str | None = None,
) -> dict | None:
    async with pool.acquire() as conn:
        async with conn.transaction():
            target = await conn.fetchrow(
                f"""
                SELECT {AGENT_POLICY_COLUMNS}
                FROM hermes.agent_policies
                WHERE policy_id = $1 AND policy_version_id = $2
                FOR UPDATE
                """,
                policy_id,
                to_policy_version_id,
            )
            if target is None:
                return None
            current = await conn.fetchrow(
                f"""
                UPDATE hermes.agent_policies
                SET status = 'rolled_back',
                    disable_reason = COALESCE($2, disable_reason),
                    updated_at = now()
                WHERE policy_id = $1 AND status = 'active'
                RETURNING {AGENT_POLICY_COLUMNS}
                """,
                policy_id,
                review_note,
            )
            next_version_row = await conn.fetchrow(
                """
                SELECT COALESCE(MAX(version), 0) + 1 AS next_version
                FROM hermes.agent_policies
                WHERE policy_id = $1
                """,
                policy_id,
            )
            row = await conn.fetchrow(
                f"""
                INSERT INTO hermes.agent_policies (
                    policy_version_id, policy_id, version, domain, policy_type,
                    status, scope_json, task_types_json, decision_points_json,
                    trigger_conditions_json, policy_body_json, priority, precedence,
                    source_candidate_id, source_policy_version_id, evidence_refs_json,
                    approved_by, effective_from, effective_until, disable_reason,
                    metadata_json
                )
                VALUES (
                    $1, $2, $3, $4, $5, 'active', $6, $7, $8, $9, $10, $11, $12,
                    $13, $14, $15, $16, $17, $18, NULL, $19
                )
                RETURNING {AGENT_POLICY_COLUMNS}
                """,
                uuid4(),
                policy_id,
                int(next_version_row["next_version"]),
                target["domain"],
                target["policy_type"],
                _jsonb(target["scope_json"] or {}),
                _jsonb(target["task_types_json"] or []),
                _jsonb(target["decision_points_json"] or []),
                _jsonb(target["trigger_conditions_json"] or {}),
                _jsonb(target["policy_body_json"] or {}),
                target["priority"],
                target["precedence"],
                target["source_candidate_id"],
                current["policy_version_id"] if current else None,
                _jsonb(target["evidence_refs_json"] or {}),
                reviewed_by,
                target["effective_from"],
                target["effective_until"],
                _jsonb({"rollback_to": str(to_policy_version_id), "review_note": review_note}),
            )
            return _row(row)


async def record_policy_application(pool_or_conn, record: dict) -> dict:
    async with _connection(pool_or_conn) as conn:
        row = await conn.fetchrow(
            f"""
            INSERT INTO hermes.policy_applications (
                application_id, run_id, domain, agent_name, task_type,
                decision_point, policy_id, policy_version_id, policy_version,
                scope_json, matched_conditions_json, application_status,
                applied_action_json, outcome_summary_json, warning,
                error_summary_json
            )
            VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                $11, $12, $13, $14, $15, $16
            )
            RETURNING {POLICY_APPLICATION_COLUMNS}
            """,
            record.get("application_id") or uuid4(),
            record.get("run_id"),
            record["domain"],
            record["agent_name"],
            record["task_type"],
            record["decision_point"],
            record["policy_id"],
            record["policy_version_id"],
            record["policy_version"],
            _jsonb(record.get("scope") or record.get("scope_json") or {}),
            _jsonb(record.get("matched_conditions") or record.get("matched_conditions_json") or {}),
            record["application_status"],
            _jsonb(record.get("applied_action") or record.get("applied_action_json") or {}),
            _jsonb(record.get("outcome_summary") or record.get("outcome_summary_json") or {}),
            record.get("warning"),
            _jsonb(record["error_summary"]) if record.get("error_summary") is not None else None,
        )
    return dict(row)


async def list_policy_applications(
    pool: asyncpg.Pool,
    *,
    policy_id: UUID | None = None,
    policy_version_id: UUID | None = None,
    run_id: str | None = None,
    domain: str | None = None,
    task_type: str | None = None,
    decision_point: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    conditions = []
    params: list = []
    idx = 1
    for column, value in (
        ("policy_id", policy_id),
        ("policy_version_id", policy_version_id),
        ("run_id", run_id),
        ("domain", domain),
        ("task_type", task_type),
        ("decision_point", decision_point),
    ):
        idx = _add_eq_filter(conditions, params, column=column, value=value, idx=idx)
    return await _list_with_total(
        pool,
        columns=POLICY_APPLICATION_COLUMNS,
        table="hermes.policy_applications",
        conditions=conditions,
        params=params,
        order_by="ORDER BY created_at DESC",
        limit=limit,
        offset=offset,
    )
