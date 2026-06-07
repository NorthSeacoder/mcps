from __future__ import annotations

from datetime import date, datetime
import json
from uuid import UUID

import asyncpg
from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from hermes_db_mcp.contracts import (
    DEFAULT_WECHAT_RETROSPECTIVE_LIMIT,
    error,
    validate_approved_ranking_hint_query,
    validate_learning_candidate_query,
    validate_learning_candidate_review,
    validate_learning_candidates_payload,
    validate_optional_uuid,
    validate_retrospective_report_payload,
    validate_retrospective_report_query,
    validate_suggestion_review,
    validate_topic_optimization_suggestion_query,
    validate_topic_performance_payload,
    validate_topic_performance_query,
    validate_topic_suggestions_payload,
)
from hermes_db_mcp.repositories import wechat_retrospective_repo
from hermes_db_mcp.server import AppContext, mcp


def _parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    return date.fromisoformat(value)


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _serialize_value(value):
    if isinstance(value, (UUID, date, datetime)):
        return str(value)
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize_value(item) for key, item in value.items()}
    return value


def _json_value(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _serialize_row(row: dict | None) -> dict | None:
    if row is None:
        return None
    result = {}
    for key, value in dict(row).items():
        out_key = key[:-5] if key.endswith("_json") else key
        out_value = _json_value(value) if key.endswith("_json") else value
        result[out_key] = _serialize_value(out_value)
    return result


def _serialize_items(rows: list[dict]) -> list[dict]:
    return [_serialize_row(row) for row in rows]


def _map_db_error(exc: Exception) -> dict:
    if isinstance(exc, asyncpg.ForeignKeyViolationError):
        constraint = getattr(exc, "constraint_name", "") or ""
        if "article" in constraint:
            field = "article_id"
        elif "topic" in constraint:
            field = "topic_id"
        elif "source_report" in constraint:
            field = "source_report_id"
        elif "report" in constraint:
            field = "report_id"
        else:
            field = "reference"
        return error("not_found", field=field, details={"constraint": constraint})
    if isinstance(exc, asyncpg.UniqueViolationError):
        return error("conflict", details={"message": str(exc)})
    if isinstance(exc, (asyncpg.UndefinedTableError, asyncpg.UndefinedColumnError)):
        return error("schema_drift", details={"message": str(exc)})
    return error("database_error", details={"message": str(exc)})


def _page(result: dict, *, limit: int, offset: int) -> dict:
    return {
        "items": _serialize_items(result["items"]),
        "total": result["total"],
        "limit": limit,
        "offset": offset,
    }


def _topic_performance_repo_row(record: dict) -> dict:
    row = dict(record)
    row["article_id"] = UUID(str(record["article_id"]))
    if record.get("topic_id"):
        row["topic_id"] = UUID(str(record["topic_id"]))
    row["stat_date"] = _parse_date(record["stat_date"])
    return row


def _report_repo_row(record: dict) -> dict:
    row = dict(record)
    row["period_start"] = _parse_date(record["period_start"])
    row["period_end"] = _parse_date(record["period_end"])
    if record.get("article_id"):
        row["article_id"] = UUID(str(record["article_id"]))
    return row


def _suggestion_repo_items(items: list[dict], *, report_id: str) -> list[dict]:
    rows = []
    for item in items:
        row = dict(item)
        row["report_id"] = UUID(str(item.get("report_id") or report_id))
        if item.get("target_id"):
            row["target_id"] = UUID(str(item["target_id"]))
        if item.get("expires_at"):
            row["expires_at"] = _parse_datetime(item["expires_at"])
        rows.append(row)
    return rows


def _learning_repo_items(items: list[dict], *, source_report_id: str) -> list[dict]:
    rows = []
    for item in items:
        row = dict(item)
        row["source_report_id"] = UUID(str(item.get("source_report_id") or source_report_id))
        rows.append(row)
    return rows


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def upsert_topic_performance(input: dict, ctx: Context) -> dict:
    """保存或更新单篇文章 topic performance 评分。"""
    app: AppContext = ctx.request_context.lifespan_context
    validation_error = validate_topic_performance_payload(input)
    if validation_error:
        return validation_error
    try:
        row = await wechat_retrospective_repo.upsert_topic_performance(
            app.pool,
            _topic_performance_repo_row(input),
        )
    except Exception as exc:
        return _map_db_error(exc)
    return _serialize_row(row)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def list_topic_performance(
    ctx: Context,
    account: str | None = None,
    article_id: str | None = None,
    topic_id: str | None = None,
    window_label: str | None = None,
    scoring_version: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = DEFAULT_WECHAT_RETROSPECTIVE_LIMIT,
    offset: int = 0,
) -> dict:
    """按 account/article/topic/window/date 查询 topic performance。"""
    app: AppContext = ctx.request_context.lifespan_context
    explicit_limit = limit != DEFAULT_WECHAT_RETROSPECTIVE_LIMIT
    validation_error = validate_topic_performance_query(
        account=account,
        article_id=article_id,
        topic_id=topic_id,
        window_label=window_label,
        scoring_version=scoring_version,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
        explicit_limit=explicit_limit,
    )
    if validation_error:
        return validation_error
    parsed_article_id, article_error = validate_optional_uuid(article_id, "article_id")
    if article_error:
        return article_error
    parsed_topic_id, topic_error = validate_optional_uuid(topic_id, "topic_id")
    if topic_error:
        return topic_error
    try:
        result = await wechat_retrospective_repo.list_topic_performance(
            app.pool,
            account=account,
            article_id=parsed_article_id,
            topic_id=parsed_topic_id,
            window_label=window_label,
            scoring_version=scoring_version,
            date_from=_parse_date(date_from),
            date_to=_parse_date(date_to),
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        return _map_db_error(exc)
    return _page(result, limit=limit, offset=offset)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    )
)
async def create_wechat_retrospective_report(input: dict, ctx: Context) -> dict:
    """创建公众号复盘报告记录。"""
    app: AppContext = ctx.request_context.lifespan_context
    validation_error = validate_retrospective_report_payload(input)
    if validation_error:
        return validation_error
    try:
        row = await wechat_retrospective_repo.create_wechat_retrospective_report(
            app.pool,
            _report_repo_row(input),
        )
    except Exception as exc:
        return _map_db_error(exc)
    return _serialize_row(row)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_wechat_retrospective_report(report_id: str, ctx: Context) -> dict:
    """按 report_id 获取公众号复盘报告。"""
    app: AppContext = ctx.request_context.lifespan_context
    parsed_report_id, report_error = validate_optional_uuid(report_id, "report_id")
    if report_error:
        return report_error
    try:
        row = await wechat_retrospective_repo.get_wechat_retrospective_report(
            app.pool,
            parsed_report_id,
        )
    except Exception as exc:
        return _map_db_error(exc)
    if row is None:
        return error("not_found", field="report_id")
    return _serialize_row(row)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def list_wechat_retrospective_reports(
    ctx: Context,
    account: str | None = None,
    report_type: str | None = None,
    article_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = DEFAULT_WECHAT_RETROSPECTIVE_LIMIT,
    offset: int = 0,
) -> dict:
    """按 account/type/article/date 查询公众号复盘报告。"""
    app: AppContext = ctx.request_context.lifespan_context
    explicit_limit = limit != DEFAULT_WECHAT_RETROSPECTIVE_LIMIT
    validation_error = validate_retrospective_report_query(
        account=account,
        report_type=report_type,
        article_id=article_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
        explicit_limit=explicit_limit,
    )
    if validation_error:
        return validation_error
    parsed_article_id, article_error = validate_optional_uuid(article_id, "article_id")
    if article_error:
        return article_error
    try:
        result = await wechat_retrospective_repo.list_wechat_retrospective_reports(
            app.pool,
            account=account,
            report_type=report_type,
            article_id=parsed_article_id,
            date_from=_parse_date(date_from),
            date_to=_parse_date(date_to),
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        return _map_db_error(exc)
    return _page(result, limit=limit, offset=offset)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    )
)
async def create_topic_optimization_suggestions(input: dict, ctx: Context) -> dict:
    """批量创建选题优化建议。"""
    app: AppContext = ctx.request_context.lifespan_context
    validation_error = validate_topic_suggestions_payload(
        account=input.get("account"),
        report_id=input.get("report_id"),
        items=input.get("items"),
    )
    if validation_error:
        return validation_error
    limit = len(input["items"])
    offset = 0
    try:
        rows = await wechat_retrospective_repo.create_topic_optimization_suggestions(
            app.pool,
            account=input["account"],
            report_id=UUID(str(input["report_id"])),
            items=_suggestion_repo_items(input["items"], report_id=input["report_id"]),
        )
    except Exception as exc:
        return _map_db_error(exc)
    return {
        "items": _serialize_items(rows),
        "total": len(rows),
        "limit": limit,
        "offset": offset,
    }


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def list_topic_optimization_suggestions(
    ctx: Context,
    account: str | None = None,
    report_id: str | None = None,
    review_status: str | None = None,
    suggestion_type: str | None = None,
    target_kind: str | None = None,
    target_id: str | None = None,
    target_key: str | None = None,
    limit: int = DEFAULT_WECHAT_RETROSPECTIVE_LIMIT,
    offset: int = 0,
) -> dict:
    """按 account/report/status/target 查询选题优化建议。"""
    app: AppContext = ctx.request_context.lifespan_context
    explicit_limit = limit != DEFAULT_WECHAT_RETROSPECTIVE_LIMIT
    validation_error = validate_topic_optimization_suggestion_query(
        account=account,
        report_id=report_id,
        review_status=review_status,
        suggestion_type=suggestion_type,
        target_kind=target_kind,
        target_id=target_id,
        target_key=target_key,
        limit=limit,
        offset=offset,
        explicit_limit=explicit_limit,
    )
    if validation_error:
        return validation_error
    parsed_report_id, report_error = validate_optional_uuid(report_id, "report_id")
    if report_error:
        return report_error
    parsed_target_id, target_error = validate_optional_uuid(target_id, "target_id")
    if target_error:
        return target_error
    try:
        result = await wechat_retrospective_repo.list_topic_optimization_suggestions(
            app.pool,
            account=account,
            report_id=parsed_report_id,
            review_status=review_status,
            suggestion_type=suggestion_type,
            target_kind=target_kind,
            target_id=parsed_target_id,
            target_key=target_key,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        return _map_db_error(exc)
    return _page(result, limit=limit, offset=offset)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    )
)
async def review_topic_optimization_suggestion(
    input: dict,
    ctx: Context,
) -> dict:
    """审核选题优化建议。"""
    app: AppContext = ctx.request_context.lifespan_context
    validation_error = validate_suggestion_review(
        suggestion_id=input.get("suggestion_id"),
        review_status=input.get("review_status"),
        reviewed_by=input.get("reviewed_by"),
        review_note=input.get("review_note"),
        application_trace_id=input.get("application_trace_id"),
    )
    if validation_error:
        return validation_error
    try:
        row = await wechat_retrospective_repo.review_topic_optimization_suggestion(
            app.pool,
            suggestion_id=UUID(str(input["suggestion_id"])),
            review_status=input["review_status"],
            reviewed_by=input.get("reviewed_by"),
            review_note=input.get("review_note"),
            application_trace_id=input.get("application_trace_id"),
        )
    except Exception as exc:
        return _map_db_error(exc)
    if row is None:
        return error("not_found", field="suggestion_id")
    return _serialize_row(row)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def list_approved_topic_ranking_hints(
    ctx: Context,
    account: str,
    target_kind: str | None = None,
    target_id: str | None = None,
    target_key: str | None = None,
    limit: int = DEFAULT_WECHAT_RETROSPECTIVE_LIMIT,
    offset: int = 0,
) -> dict:
    """查询 approved/applied 且未过期的选题排序 hints。"""
    app: AppContext = ctx.request_context.lifespan_context
    validation_error = validate_approved_ranking_hint_query(
        account=account,
        target_kind=target_kind,
        target_id=target_id,
        target_key=target_key,
        limit=limit,
        offset=offset,
    )
    if validation_error:
        return validation_error
    parsed_target_id, target_error = validate_optional_uuid(target_id, "target_id")
    if target_error:
        return target_error
    try:
        result = await wechat_retrospective_repo.list_approved_topic_ranking_hints(
            app.pool,
            account=account,
            target_kind=target_kind,
            target_id=parsed_target_id,
            target_key=target_key,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        return _map_db_error(exc)
    return _page(result, limit=limit, offset=offset)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    )
)
async def create_learning_candidates(input: dict, ctx: Context) -> dict:
    """批量创建复盘 learning candidates。"""
    app: AppContext = ctx.request_context.lifespan_context
    validation_error = validate_learning_candidates_payload(
        account=input.get("account"),
        source_report_id=input.get("source_report_id"),
        items=input.get("items"),
    )
    if validation_error:
        return validation_error
    limit = len(input["items"])
    offset = 0
    try:
        rows = await wechat_retrospective_repo.create_learning_candidates(
            app.pool,
            account=input["account"],
            source_report_id=UUID(str(input["source_report_id"])),
            items=_learning_repo_items(input["items"], source_report_id=input["source_report_id"]),
        )
    except Exception as exc:
        return _map_db_error(exc)
    return {
        "items": _serialize_items(rows),
        "total": len(rows),
        "limit": limit,
        "offset": offset,
    }


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def list_learning_candidates(
    ctx: Context,
    account: str | None = None,
    domain: str | None = None,
    source_report_id: str | None = None,
    status: str | None = None,
    candidate_type: str | None = None,
    limit: int = DEFAULT_WECHAT_RETROSPECTIVE_LIMIT,
    offset: int = 0,
) -> dict:
    """按 account/domain/report/status/type 查询 learning candidates。"""
    app: AppContext = ctx.request_context.lifespan_context
    explicit_limit = limit != DEFAULT_WECHAT_RETROSPECTIVE_LIMIT
    validation_error = validate_learning_candidate_query(
        account=account,
        domain=domain,
        source_report_id=source_report_id,
        status=status,
        candidate_type=candidate_type,
        limit=limit,
        offset=offset,
        explicit_limit=explicit_limit,
    )
    if validation_error:
        return validation_error
    parsed_report_id, report_error = validate_optional_uuid(
        source_report_id,
        "source_report_id",
    )
    if report_error:
        return report_error
    try:
        result = await wechat_retrospective_repo.list_learning_candidates(
            app.pool,
            account=account,
            domain=domain,
            source_report_id=parsed_report_id,
            status=status,
            candidate_type=candidate_type,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        return _map_db_error(exc)
    return _page(result, limit=limit, offset=offset)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    )
)
async def review_learning_candidate(input: dict, ctx: Context) -> dict:
    """审核 learning candidate。"""
    app: AppContext = ctx.request_context.lifespan_context
    validation_error = validate_learning_candidate_review(
        candidate_id=input.get("candidate_id"),
        status=input.get("status"),
        reviewed_by=input.get("reviewed_by"),
        review_note=input.get("review_note"),
        policy_id=input.get("policy_id"),
    )
    if validation_error:
        return validation_error
    try:
        row = await wechat_retrospective_repo.review_learning_candidate(
            app.pool,
            candidate_id=UUID(str(input["candidate_id"])),
            status=input["status"],
            reviewed_by=input.get("reviewed_by"),
            review_note=input.get("review_note"),
            policy_id=input.get("policy_id"),
        )
    except Exception as exc:
        return _map_db_error(exc)
    if row is None:
        return error("not_found", field="candidate_id")
    return _serialize_row(row)
