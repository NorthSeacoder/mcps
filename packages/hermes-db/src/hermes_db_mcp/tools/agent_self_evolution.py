from __future__ import annotations

from datetime import datetime
import json
from uuid import UUID

import asyncpg
from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from hermes_db_mcp.contracts import (
    DEFAULT_AGENT_POLICY_LIMIT,
    error,
    validate_agent_policy_query,
    validate_applicable_agent_policy_query,
    validate_disable_agent_policy_payload,
    validate_optional_uuid,
    validate_policy_application_query,
    validate_promote_learning_candidate_to_policy_payload,
    validate_record_policy_application_payload,
    validate_rollback_agent_policy_payload,
)
from hermes_db_mcp.repositories import agent_self_evolution_repo
from hermes_db_mcp.server import AppContext, mcp


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _serialize_value(value):
    if isinstance(value, (UUID, datetime)):
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
    if isinstance(exc, ValueError) and str(exc).startswith("invalid_state"):
        return error("invalid_transition", details={"message": str(exc)})
    if isinstance(exc, asyncpg.ForeignKeyViolationError):
        return error("not_found", field="reference")
    if isinstance(exc, asyncpg.UniqueViolationError):
        return error("conflict", details={"message": str(exc)})
    if isinstance(exc, (asyncpg.UndefinedTableError, asyncpg.UndefinedColumnError)):
        return error("schema_drift", details={"message": str(exc)})
    return error("database_error", details={"message": str(exc)})


def _page(result: dict, *, limit: int, offset: int) -> dict:
    payload = {
        "items": _serialize_items(result["items"]),
        "total": result["total"],
        "limit": limit,
        "offset": offset,
    }
    if "warnings" in result:
        payload["warnings"] = result["warnings"]
    return payload


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def promote_learning_candidate_to_policy(input: dict, ctx: Context) -> dict:
    """Promote an approved learning candidate into an active agent policy."""
    app: AppContext = ctx.request_context.lifespan_context
    validation_error = validate_promote_learning_candidate_to_policy_payload(input)
    if validation_error:
        return validation_error
    try:
        row = await agent_self_evolution_repo.promote_learning_candidate_to_policy(
            app.pool,
            candidate_id=UUID(str(input["candidate_id"])),
            approved_by=input["approved_by"],
            review_note=input.get("review_note"),
            policy_type=input.get("policy_type"),
            task_types=input.get("task_types"),
            decision_points=input.get("decision_points"),
            effective_from=_parse_datetime(input.get("effective_from")),
            effective_until=_parse_datetime(input.get("effective_until")),
            priority=input.get("priority", 0),
            metadata=input.get("metadata"),
        )
    except Exception as exc:
        return _map_db_error(exc)
    if row is None:
        return error("not_found", field="candidate_id")
    return _serialize_row(row)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def list_agent_policies(
    ctx: Context,
    domain: str | None = None,
    policy_type: str | None = None,
    status: str | None = None,
    source_candidate_id: str | None = None,
    policy_id: str | None = None,
    limit: int = DEFAULT_AGENT_POLICY_LIMIT,
    offset: int = 0,
) -> dict:
    """List agent policies with bounded filters."""
    app: AppContext = ctx.request_context.lifespan_context
    explicit_limit = limit != DEFAULT_AGENT_POLICY_LIMIT
    validation_error = validate_agent_policy_query(
        domain=domain,
        policy_type=policy_type,
        status=status,
        source_candidate_id=source_candidate_id,
        policy_id=policy_id,
        limit=limit,
        offset=offset,
        explicit_limit=explicit_limit,
    )
    if validation_error:
        return validation_error
    parsed_source_candidate_id, candidate_err = validate_optional_uuid(
        source_candidate_id, "source_candidate_id"
    )
    if candidate_err:
        return candidate_err
    parsed_policy_id, policy_err = validate_optional_uuid(policy_id, "policy_id")
    if policy_err:
        return policy_err
    try:
        result = await agent_self_evolution_repo.list_agent_policies(
            app.pool,
            domain=domain,
            policy_type=policy_type,
            status=status,
            source_candidate_id=parsed_source_candidate_id,
            policy_id=parsed_policy_id,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        return _map_db_error(exc)
    return _page(result, limit=limit, offset=offset)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_applicable_agent_policies(input: dict, ctx: Context) -> dict:
    """Return active policies matching domain, scope, task and optional decision point."""
    app: AppContext = ctx.request_context.lifespan_context
    validation_error = validate_applicable_agent_policy_query(input)
    if validation_error:
        return validation_error
    limit = input.get("limit", DEFAULT_AGENT_POLICY_LIMIT)
    offset = input.get("offset", 0)
    try:
        result = await agent_self_evolution_repo.get_applicable_agent_policies(
            app.pool,
            domain=input["domain"],
            scope=input["scope"],
            task_type=input["task_type"],
            decision_point=input.get("decision_point"),
            now=_parse_datetime(input.get("now")),
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        return _map_db_error(exc)
    return _page(result, limit=limit, offset=offset)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def disable_agent_policy(input: dict, ctx: Context) -> dict:
    """Disable the current active version of a policy family."""
    app: AppContext = ctx.request_context.lifespan_context
    validation_error = validate_disable_agent_policy_payload(input)
    if validation_error:
        return validation_error
    try:
        row = await agent_self_evolution_repo.disable_agent_policy(
            app.pool,
            policy_id=UUID(str(input["policy_id"])),
            disabled_by=input["disabled_by"],
            disable_reason=input["disable_reason"],
        )
    except Exception as exc:
        return _map_db_error(exc)
    if row is None:
        return error("not_found", field="policy_id")
    return _serialize_row(row)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    )
)
async def rollback_agent_policy(input: dict, ctx: Context) -> dict:
    """Create a new active rollback version from a historical policy version."""
    app: AppContext = ctx.request_context.lifespan_context
    validation_error = validate_rollback_agent_policy_payload(input)
    if validation_error:
        return validation_error
    try:
        row = await agent_self_evolution_repo.rollback_agent_policy(
            app.pool,
            policy_id=UUID(str(input["policy_id"])),
            to_policy_version_id=UUID(str(input["to_policy_version_id"])),
            reviewed_by=input["reviewed_by"],
            review_note=input.get("review_note"),
        )
    except Exception as exc:
        return _map_db_error(exc)
    if row is None:
        return error("not_found", field="policy_id")
    return _serialize_row(row)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    )
)
async def record_policy_application(input: dict, ctx: Context) -> dict:
    """Record an append-only policy application trace."""
    app: AppContext = ctx.request_context.lifespan_context
    validation_error = validate_record_policy_application_payload(input)
    if validation_error:
        return validation_error
    record = dict(input)
    record["policy_id"] = UUID(str(input["policy_id"]))
    record["policy_version_id"] = UUID(str(input["policy_version_id"]))
    try:
        row = await agent_self_evolution_repo.record_policy_application(app.pool, record)
    except Exception as exc:
        return _map_db_error(exc)
    return _serialize_row(row)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def list_policy_applications(
    ctx: Context,
    policy_id: str | None = None,
    policy_version_id: str | None = None,
    run_id: str | None = None,
    domain: str | None = None,
    task_type: str | None = None,
    decision_point: str | None = None,
    limit: int = DEFAULT_AGENT_POLICY_LIMIT,
    offset: int = 0,
) -> dict:
    """List policy application traces."""
    app: AppContext = ctx.request_context.lifespan_context
    explicit_limit = limit != DEFAULT_AGENT_POLICY_LIMIT
    validation_error = validate_policy_application_query(
        policy_id=policy_id,
        policy_version_id=policy_version_id,
        run_id=run_id,
        domain=domain,
        task_type=task_type,
        decision_point=decision_point,
        limit=limit,
        offset=offset,
        explicit_limit=explicit_limit,
    )
    if validation_error:
        return validation_error
    parsed_policy_id, policy_err = validate_optional_uuid(policy_id, "policy_id")
    if policy_err:
        return policy_err
    parsed_policy_version_id, version_err = validate_optional_uuid(
        policy_version_id, "policy_version_id"
    )
    if version_err:
        return version_err
    try:
        result = await agent_self_evolution_repo.list_policy_applications(
            app.pool,
            policy_id=parsed_policy_id,
            policy_version_id=parsed_policy_version_id,
            run_id=run_id,
            domain=domain,
            task_type=task_type,
            decision_point=decision_point,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        return _map_db_error(exc)
    return _page(result, limit=limit, offset=offset)
