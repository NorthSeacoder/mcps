from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from hermes_db_mcp.server import mcp, AppContext
from hermes_db_mcp.config import settings
from hermes_db_mcp.services.embedding import build_embedding_payload
from hermes_db_mcp.services.schema import (
    inspect_agent_self_evolution_foundation_schema,
    inspect_topic_schema,
    inspect_wechat_analytics_ingestion_schema,
    inspect_wechat_publication_ledger_schema,
    inspect_wechat_retrospective_topic_optimizer_schema,
    inspect_workflow_schema,
)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def health(ctx: Context) -> dict:
    """检查 PG、Redis、Embedding 三项服务的连接状态。"""
    app: AppContext = ctx.request_context.lifespan_context
    result = {}
    pg_ok = False

    # PG
    try:
        await app.pool.fetchval("SELECT 1")
        result["pg"] = "ok"
        pg_ok = True
    except Exception as e:
        result["pg"] = f"error: {e}"

    # Redis
    try:
        await app.redis.ping()
        result["redis"] = "ok"
    except Exception as e:
        result["redis"] = f"error: {e}"

    # Embedding
    try:
        resp = await app.http.post(
            "/embeddings",
            json=build_embedding_payload("ping"),
            headers={"Authorization": f"Bearer {settings.embedding_api_key}"},
            timeout=3.0,
        )
        resp.raise_for_status()
        result["embedding"] = "ok"
    except Exception as e:
        result["embedding"] = f"error: {e}"

    result["version"] = settings.version
    result["schema_revision"] = None
    result["capabilities"] = {
        "topic_bucket": False,
        "topic_revisit_of": False,
        "list_revisit_chain": False,
        "workflow_runs": False,
        "workflow_artifacts": False,
        "wechat_publication_ledger": False,
        "wechat_analytics_ingestion": False,
        "wechat_retrospective_topic_optimizer": False,
        "agent_self_evolution_foundation": False,
    }

    if pg_ok:
        try:
            result["schema_revision"] = await app.pool.fetchval(
                "SELECT version_num FROM alembic_version LIMIT 1"
            )
        except Exception:
            result["schema_revision"] = None

        try:
            result["capabilities"] = {
                **await inspect_topic_schema(app.pool),
                **await inspect_workflow_schema(app.pool),
                **await inspect_wechat_publication_ledger_schema(app.pool),
                **await inspect_wechat_analytics_ingestion_schema(app.pool),
                **await inspect_wechat_retrospective_topic_optimizer_schema(app.pool),
                **await inspect_agent_self_evolution_foundation_schema(app.pool),
            }
        except Exception as e:
            result["schema_error"] = str(e)

    return result
