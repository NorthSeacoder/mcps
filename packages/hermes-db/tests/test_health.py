from unittest.mock import AsyncMock, MagicMock

import pytest

from hermes_db_mcp.config import settings
from hermes_db_mcp.tools.health import health


class FakeAppContext:
    def __init__(self):
        self.pool = MagicMock()
        self.pool.fetchval = AsyncMock(side_effect=[1, "0001_topic_revisit"])
        self.redis = MagicMock()
        self.redis.ping = AsyncMock(return_value=True)
        self.http = MagicMock()
        self.http.post = AsyncMock(return_value=MagicMock(raise_for_status=MagicMock()))


class FakeContext:
    def __init__(self, app_context):
        self.request_context = MagicMock()
        self.request_context.lifespan_context = app_context


@pytest.mark.asyncio
async def test_health_returns_version_and_capabilities():
    ctx = FakeContext(FakeAppContext())

    result = await health(ctx)

    assert result["version"] == "0.2.15"
    assert result["capabilities"] == {
        "topic_bucket": True,
        "topic_revisit_of": True,
        "list_revisit_chain": True,
        "workflow_runs": True,
        "workflow_artifacts": True,
        "wechat_publication_ledger": True,
        "wechat_analytics_ingestion": True,
        "wechat_retrospective_topic_optimizer": True,
        "agent_self_evolution_foundation": True,
    }
    assert result["schema_revision"] == "0001_topic_revisit"


@pytest.mark.asyncio
async def test_health_embedding_probe_omits_dimensions_when_not_configured(
    monkeypatch,
):
    monkeypatch.setattr(settings, "embedding_dimension", 0)
    app = FakeAppContext()
    ctx = FakeContext(app)

    await health(ctx)

    assert app.http.post.call_args.kwargs["json"] == {
        "model": settings.embedding_model,
        "input": "ping",
    }


@pytest.mark.asyncio
async def test_health_embedding_probe_includes_positive_dimensions(monkeypatch):
    monkeypatch.setattr(settings, "embedding_dimension", 1024)
    app = FakeAppContext()
    ctx = FakeContext(app)

    await health(ctx)

    assert app.http.post.call_args.kwargs["json"] == {
        "model": settings.embedding_model,
        "input": "ping",
        "dimensions": 1024,
    }


@pytest.mark.asyncio
async def test_health_disables_capabilities_when_pg_is_unavailable(monkeypatch):
    app = FakeAppContext()
    app.pool.fetchval = AsyncMock(side_effect=RuntimeError("pg down"))
    ctx = FakeContext(app)

    result = await health(ctx)

    assert result["pg"].startswith("error:")
    assert result["schema_revision"] is None
    assert result["capabilities"] == {
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


@pytest.fixture(autouse=True)
def schema_inspector(monkeypatch):
    async def inspect_topic_schema(pool):
        return {
            "topic_bucket": True,
            "topic_revisit_of": True,
            "list_revisit_chain": True,
        }

    monkeypatch.setattr(
        "hermes_db_mcp.tools.health.inspect_topic_schema",
        inspect_topic_schema,
    )

    async def inspect_workflow_schema(pool):
        return {
            "workflow_runs": True,
            "workflow_artifacts": True,
        }

    monkeypatch.setattr(
        "hermes_db_mcp.tools.health.inspect_workflow_schema",
        inspect_workflow_schema,
    )

    async def inspect_wechat_publication_ledger_schema(pool):
        return {
            "wechat_publication_ledger": True,
        }

    monkeypatch.setattr(
        "hermes_db_mcp.tools.health.inspect_wechat_publication_ledger_schema",
        inspect_wechat_publication_ledger_schema,
    )

    async def inspect_wechat_analytics_ingestion_schema(pool):
        return {
            "wechat_analytics_ingestion": True,
        }

    monkeypatch.setattr(
        "hermes_db_mcp.tools.health.inspect_wechat_analytics_ingestion_schema",
        inspect_wechat_analytics_ingestion_schema,
    )

    async def inspect_wechat_retrospective_topic_optimizer_schema(pool):
        return {
            "wechat_retrospective_topic_optimizer": True,
        }

    monkeypatch.setattr(
        "hermes_db_mcp.tools.health.inspect_wechat_retrospective_topic_optimizer_schema",
        inspect_wechat_retrospective_topic_optimizer_schema,
    )

    async def inspect_agent_self_evolution_foundation_schema(pool):
        return {
            "agent_self_evolution_foundation": True,
        }

    monkeypatch.setattr(
        "hermes_db_mcp.tools.health.inspect_agent_self_evolution_foundation_schema",
        inspect_agent_self_evolution_foundation_schema,
    )
