from datetime import datetime

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from hermes_db_mcp.server import mcp, AppContext
from hermes_db_mcp.repositories import workflow_repo
from hermes_db_mcp.contracts import (
    error,
    validate_finish_workflow_run_payload,
    validate_optional_uuid,
    validate_workflow_run_payload,
)


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _serialize_run(row: dict) -> dict:
    result = dict(row)
    for key in ("topic_id",):
        if result.get(key) is not None:
            result[key] = str(result[key])
    for key in ("started_at", "completed_at", "created_at", "updated_at"):
        if result.get(key) is not None:
            result[key] = str(result[key])
    return result


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def upsert_workflow_run(
    run_id: str,
    phase: str,
    status: str,
    ctx: Context,
    task_id: str | None = None,
    topic_id: str | None = None,
    account: str | None = None,
    input_text: str | None = None,
    intent: str | None = None,
    current_stage: str | None = None,
    dry_run: bool = False,
    metadata: dict | None = None,
    started_at: str | None = None,
) -> dict:
    """创建或更新公众号 workflow run 主记录。"""
    app: AppContext = ctx.request_context.lifespan_context

    validation_error = validate_workflow_run_payload(
        run_id=run_id,
        phase=phase,
        status=status,
    )
    if validation_error:
        return validation_error
    parsed_topic_id, topic_error = validate_optional_uuid(topic_id, "topic_id")
    if topic_error:
        return topic_error

    try:
        row = await workflow_repo.upsert_run(
            app.pool,
            run_id=run_id,
            task_id=task_id,
            topic_id=parsed_topic_id,
            account=account,
            input_text=input_text,
            intent=intent,
            phase=phase,
            current_stage=current_stage,
            status=status,
            dry_run=dry_run,
            metadata=metadata,
            started_at=_parse_datetime(started_at),
        )
    except Exception as exc:
        return error("database_error", details={"message": str(exc)})

    return _serialize_run(row)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def finish_workflow_run(
    run_id: str,
    phase: str,
    status: str,
    ctx: Context,
    current_stage: str | None = None,
    summary: str | None = None,
    failure_reason: str | None = None,
    missing_inputs: list | None = None,
    next_action: str | None = None,
    completed_at: str | None = None,
) -> dict:
    """完成、失败或阻塞一个公众号 workflow run。"""
    app: AppContext = ctx.request_context.lifespan_context

    validation_error = validate_finish_workflow_run_payload(
        run_id=run_id,
        phase=phase,
        status=status,
    )
    if validation_error:
        return validation_error

    try:
        row = await workflow_repo.finish_run(
            app.pool,
            run_id=run_id,
            phase=phase,
            status=status,
            current_stage=current_stage,
            summary=summary,
            failure_reason=failure_reason,
            missing_inputs=missing_inputs,
            next_action=next_action,
            completed_at=_parse_datetime(completed_at),
        )
    except Exception as exc:
        return error("database_error", details={"message": str(exc)})

    if row is None:
        return error("not_found", field="run_id", details={"run_id": run_id})
    return _serialize_run(row)
