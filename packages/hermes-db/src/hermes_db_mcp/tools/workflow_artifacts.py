from datetime import datetime

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from hermes_db_mcp.server import mcp, AppContext
from hermes_db_mcp.repositories import workflow_repo
from hermes_db_mcp.contracts import (
    DEFAULT_WORKFLOW_ARTIFACT_LIMIT,
    error,
    validate_optional_uuid,
    validate_workflow_artifact_payload,
    validate_workflow_artifact_query,
)


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _serialize_artifact(row: dict, *, include_content: bool = False) -> dict:
    result = dict(row)
    for key in ("topic_id",):
        if result.get(key) is not None:
            result[key] = str(result[key])
    for key in ("created_at", "updated_at"):
        if result.get(key) is not None:
            result[key] = str(result[key])
    if not include_content:
        result.pop("content_text", None)
    else:
        result["content_inline"] = result.get("content_text") is not None
    return result


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def upsert_workflow_artifact(
    run_id: str,
    stage: str,
    type: str,
    name: str,
    content_hash: str,
    content_size_bytes: int,
    ctx: Context,
    artifact_id: str | None = None,
    task_id: str | None = None,
    topic_id: str | None = None,
    account: str | None = None,
    parent_artifact_id: str | None = None,
    content_preview: str | None = None,
    content_text: str | None = None,
    content_ref: str | None = None,
    metadata: dict | None = None,
) -> dict:
    """保存 workflow artifact 摘要、hash、metadata 和正文或引用。"""
    app: AppContext = ctx.request_context.lifespan_context

    validation_error = validate_workflow_artifact_payload(
        run_id=run_id,
        stage=stage,
        type=type,
        name=name,
        content_hash=content_hash,
        content_size_bytes=content_size_bytes,
        content_text=content_text,
        content_ref=content_ref,
        topic_id=topic_id,
        parent_artifact_id=parent_artifact_id,
    )
    if validation_error:
        return validation_error
    parsed_topic_id, topic_error = validate_optional_uuid(topic_id, "topic_id")
    if topic_error:
        return topic_error

    try:
        row, created = await workflow_repo.upsert_artifact(
            app.pool,
            artifact_id=artifact_id,
            run_id=run_id,
            task_id=task_id,
            topic_id=parsed_topic_id,
            account=account,
            stage=stage,
            type=type,
            name=name,
            parent_artifact_id=parent_artifact_id,
            content_hash=content_hash,
            content_size_bytes=content_size_bytes,
            content_preview=content_preview,
            content_text=content_text,
            content_ref=content_ref,
            metadata=metadata,
        )
    except ValueError as exc:
        if str(exc) == "artifact_id_conflict":
            return error("artifact_id_conflict", field="artifact_id")
        return error("invalid_field", details={"message": str(exc)})
    except Exception as exc:
        return error("database_error", details={"message": str(exc)})

    return {**_serialize_artifact(row), "created": created}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def list_workflow_artifacts(
    ctx: Context,
    run_id: str | None = None,
    topic_id: str | None = None,
    account: str | None = None,
    type: str | None = None,
    stage: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = DEFAULT_WORKFLOW_ARTIFACT_LIMIT,
    offset: int = 0,
) -> dict:
    """按 run/topic/account/date/type 查询 workflow artifact 摘要。"""
    app: AppContext = ctx.request_context.lifespan_context
    explicit_limit = limit != DEFAULT_WORKFLOW_ARTIFACT_LIMIT
    validation_error = validate_workflow_artifact_query(
        run_id=run_id,
        topic_id=topic_id,
        account=account,
        type=type,
        stage=stage,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
        explicit_limit=explicit_limit,
    )
    if validation_error:
        return validation_error
    parsed_topic_id, topic_error = validate_optional_uuid(topic_id, "topic_id")
    if topic_error:
        return topic_error

    try:
        rows = await workflow_repo.list_artifacts(
            app.pool,
            run_id=run_id,
            topic_id=parsed_topic_id,
            account=account,
            type=type,
            stage=stage,
            date_from=_parse_datetime(date_from),
            date_to=_parse_datetime(date_to),
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        return error("database_error", details={"message": str(exc)})
    return {"items": [_serialize_artifact(row) for row in rows], "limit": limit, "offset": offset}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_workflow_artifact_content(artifact_id: str, ctx: Context) -> dict:
    """读取 workflow artifact 的 inline 正文或 content_ref metadata。"""
    app: AppContext = ctx.request_context.lifespan_context
    if not artifact_id or not artifact_id.strip():
        return error("missing_required_field", field="artifact_id")

    try:
        row = await workflow_repo.get_artifact(app.pool, artifact_id=artifact_id)
    except Exception as exc:
        return error("database_error", details={"message": str(exc)})
    if row is None:
        return error("not_found", field="artifact_id", details={"artifact_id": artifact_id})
    return _serialize_artifact(row, include_content=True)
