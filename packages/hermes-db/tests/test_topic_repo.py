import pytest

from hermes_db_mcp.repositories import topic_repo


class FakeConnection:
    def __init__(self):
        self.sql = None
        self.params = None

    async def fetch(self, sql, *params):
        self.sql = sql
        self.params = params
        return []


class FakeAcquire:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return None


class FakePool:
    def __init__(self):
        self.conn = FakeConnection()

    def acquire(self):
        return FakeAcquire(self.conn)


@pytest.mark.asyncio
async def test_find_similar_excludes_old_published_topics(monkeypatch):
    async def noop_register_vector(conn):
        return None

    monkeypatch.setattr(topic_repo, "register_vector", noop_register_vector)
    pool = FakePool()

    await topic_repo.find_similar(
        pool,
        embedding=[0.1, 0.2],
        account="moon",
        threshold=0.7,
        limit=3,
    )

    assert "(status != 'published' OR updated_at >= now() - interval '3 months')" in pool.conn.sql
    assert "account = $4" in pool.conn.sql
    assert pool.conn.params == ([0.1, 0.2], 0.7, 3, "moon")
