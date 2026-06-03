from __future__ import annotations

from collections.abc import Iterable

import asyncpg


async def _fetch_column_names(pool: asyncpg.Pool, table_schema: str, table_name: str) -> set[str]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = $1 AND table_name = $2
            """,
            table_schema,
            table_name,
        )
    return {row["column_name"] for row in rows}


async def _fetch_constraint_names(
    pool: asyncpg.Pool,
    constraint_names: Iterable[str],
    table_schema: str = "hermes",
    table_name: str = "topics",
) -> set[str]:
    wanted = list(constraint_names)
    if not wanted:
        return set()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT conname
            FROM pg_constraint
            WHERE connamespace = $1::regnamespace
              AND conrelid = $2::regclass
              AND conname = ANY($3::text[])
            """,
            table_schema,
            f"{table_schema}.{table_name}",
            wanted,
        )
    return {row["conname"] for row in rows}


async def inspect_topic_schema(pool: asyncpg.Pool) -> dict[str, bool]:
    columns = await _fetch_column_names(pool, "hermes", "topics")
    constraints = await _fetch_constraint_names(
        pool,
        (
            "fk_topics_revisit_of",
            "chk_topics_revisit_of_not_self",
        ),
    )

    return {
        "topic_bucket": "embedding" in columns,
        "topic_revisit_of": {"revisit_of", "mother_theme"}.issubset(columns)
        and "fk_topics_revisit_of" in constraints
        and "chk_topics_revisit_of_not_self" in constraints,
        "list_revisit_chain": "revisit_of" in columns,
    }


async def _fetch_index_names(
    pool: asyncpg.Pool,
    table_schema: str,
    index_names: Iterable[str],
) -> set[str]:
    wanted = list(index_names)
    if not wanted:
        return set()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT indexname
            FROM pg_indexes
            WHERE schemaname = $1
              AND indexname = ANY($2::text[])
            """,
            table_schema,
            wanted,
        )
    return {row["indexname"] for row in rows}


async def inspect_workflow_schema(pool: asyncpg.Pool) -> dict[str, bool]:
    run_columns = await _fetch_column_names(pool, "hermes", "wechat_workflow_runs")
    artifact_columns = await _fetch_column_names(pool, "hermes", "workflow_artifacts")
    artifact_constraints = await _fetch_constraint_names(
        pool,
        (
            "workflow_artifacts_pkey",
            "workflow_artifacts_run_id_fkey",
            "workflow_artifacts_parent_artifact_id_fkey",
            "chk_workflow_artifacts_content_present",
            "chk_workflow_artifacts_version_positive",
            "chk_workflow_artifacts_content_size_nonnegative",
            "uq_workflow_artifact_logical_version",
            "uq_workflow_artifact_logical_hash",
        ),
        table_name="workflow_artifacts",
    )
    indexes = await _fetch_index_names(
        pool,
        "hermes",
        (
            "idx_wechat_workflow_runs_topic_created",
            "idx_wechat_workflow_runs_account_created",
            "idx_workflow_artifacts_run_created",
            "idx_workflow_artifacts_topic_created",
            "idx_workflow_artifacts_account_created",
            "idx_workflow_artifacts_type_created",
            "idx_workflow_artifacts_stage_name",
        ),
    )

    run_required = {
        "run_id",
        "task_id",
        "topic_id",
        "account",
        "phase",
        "current_stage",
        "status",
        "dry_run",
        "metadata",
        "started_at",
        "completed_at",
        "created_at",
        "updated_at",
    }
    artifact_required = {
        "artifact_id",
        "run_id",
        "stage",
        "type",
        "name",
        "version",
        "parent_artifact_id",
        "content_hash",
        "content_size_bytes",
        "content_preview",
        "content_text",
        "content_ref",
        "metadata",
        "created_at",
        "updated_at",
    }

    return {
        "workflow_runs": run_required.issubset(run_columns),
        "workflow_artifacts": artifact_required.issubset(artifact_columns)
        and {
            "workflow_artifacts_run_id_fkey",
            "workflow_artifacts_parent_artifact_id_fkey",
            "chk_workflow_artifacts_content_present",
            "chk_workflow_artifacts_version_positive",
            "chk_workflow_artifacts_content_size_nonnegative",
            "uq_workflow_artifact_logical_version",
            "uq_workflow_artifact_logical_hash",
        }.issubset(artifact_constraints)
        and {
            "idx_workflow_artifacts_run_created",
            "idx_workflow_artifacts_topic_created",
            "idx_workflow_artifacts_account_created",
            "idx_workflow_artifacts_type_created",
            "idx_workflow_artifacts_stage_name",
        }.issubset(indexes),
    }
