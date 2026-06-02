from unittest.mock import AsyncMock, MagicMock

import pytest

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

    assert result["version"] == "0.2.5"
    assert result["capabilities"] == {
        "topic_bucket": True,
        "topic_revisit_of": True,
        "list_revisit_chain": True,
    }
    assert result["schema_revision"] == "0001_topic_revisit"


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
