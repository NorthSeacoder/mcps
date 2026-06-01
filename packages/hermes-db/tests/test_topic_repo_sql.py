"""
测试 topic_repo 的更新能力 - SQL 逻辑验证 (Phase 2)
"""

import pytest
from uuid import uuid4

from hermes_db_mcp.repositories import topic_repo


class FakeConnection:
    """模拟数据库连接,捕获 SQL 和参数"""

    def __init__(self, return_value=None):
        self.sql = None
        self.params = None
        self.return_value = return_value

    async def fetchrow(self, sql, *params):
        self.sql = sql
        self.params = params
        return self.return_value

    async def fetch(self, sql, *params):
        self.sql = sql
        self.params = params
        return self.return_value or []

    async def fetchval(self, sql, *params):
        self.sql = sql
        self.params = params
        return 0


class FakeAcquire:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return None


class FakePool:
    def __init__(self, return_value=None):
        self.conn = FakeConnection(return_value)

    def acquire(self):
        return FakeAcquire(self.conn)


@pytest.mark.asyncio
class TestUpdateTopicFieldsSQL:
    """T005: 测试 update_topic_fields SQL 构造"""

    async def test_update_single_field_sql(self, monkeypatch):
        """单字段更新 SQL 正确"""

        async def noop_register(conn):
            pass

        monkeypatch.setattr(topic_repo, "register_vector", noop_register)

        mock_row = {"id": uuid4(), "title": "test", "priority": "A"}
        pool = FakePool(return_value=mock_row)
        topic_id = uuid4()

        await topic_repo.update_topic_fields(
            pool,
            topic_id=topic_id,
            fields={"priority": "A"},
        )

        assert "UPDATE hermes.topics" in pool.conn.sql
        assert "SET priority = $1" in pool.conn.sql
        assert "WHERE id = $2" in pool.conn.sql
        assert pool.conn.params == ("A", topic_id)

    async def test_update_multiple_fields_sql(self, monkeypatch):
        """多字段更新 SQL 正确"""

        async def noop_register(conn):
            pass

        monkeypatch.setattr(topic_repo, "register_vector", noop_register)

        mock_row = {"id": uuid4()}
        pool = FakePool(return_value=mock_row)
        topic_id = uuid4()

        await topic_repo.update_topic_fields(
            pool,
            topic_id=topic_id,
            fields={
                "priority": "C",
                "resonance": "高",
                "column_name": "技术专栏",
            },
        )

        sql = pool.conn.sql
        assert "UPDATE hermes.topics" in sql
        assert "priority = $1" in sql
        assert "resonance = $2" in sql
        assert "column_name = $3" in sql
        assert "WHERE id = $4" in sql
        assert pool.conn.params == ("C", "高", "技术专栏", topic_id)

    async def test_update_with_embedding_sql(self, monkeypatch):
        """embedding 更新 SQL 正确"""

        async def noop_register(conn):
            pass

        monkeypatch.setattr(topic_repo, "register_vector", noop_register)

        mock_row = {"id": uuid4()}
        pool = FakePool(return_value=mock_row)
        topic_id = uuid4()
        new_embedding = [0.1] * 1024

        await topic_repo.update_topic_fields(
            pool,
            topic_id=topic_id,
            fields={"title": "新标题"},
            embedding=new_embedding,
        )

        sql = pool.conn.sql
        assert "title = $1" in sql
        assert "embedding = $2" in sql
        assert "WHERE id = $3" in sql
        assert pool.conn.params == ("新标题", new_embedding, topic_id)

    async def test_update_returns_full_columns(self, monkeypatch):
        """RETURNING 包含完整字段集"""

        async def noop_register(conn):
            pass

        monkeypatch.setattr(topic_repo, "register_vector", noop_register)

        mock_row = {"id": uuid4()}
        pool = FakePool(return_value=mock_row)

        await topic_repo.update_topic_fields(
            pool,
            topic_id=uuid4(),
            fields={"priority": "A"},
        )

        sql = pool.conn.sql
        assert "RETURNING" in sql
        assert "id" in sql
        assert "title" in sql
        assert "angle" in sql
        assert "account" in sql
        assert "status" in sql
        assert "priority" in sql
        assert "column_name" in sql
        assert "resonance" in sql
        assert "content" in sql
        assert "source" in sql
        assert "published_url" in sql
        assert "created_at" in sql
        assert "updated_at" in sql

    async def test_update_invalid_field_raises(self):
        """不可编辑字段抛出异常"""
        pool = FakePool()

        with pytest.raises(ValueError, match="不可编辑字段"):
            await topic_repo.update_topic_fields(
                pool,
                topic_id=uuid4(),
                fields={"status": "published"},
            )

    async def test_update_no_fields_raises(self):
        """未提供任何字段抛出异常"""
        pool = FakePool()

        with pytest.raises(ValueError, match="未提供任何可更新字段"):
            await topic_repo.update_topic_fields(
                pool,
                topic_id=uuid4(),
                fields={},
            )


@pytest.mark.asyncio
class TestBatchUpdateFieldsSQL:
    """T006: 测试 batch_update_fields SQL 构造"""

    async def test_batch_update_sql(self):
        """批量更新 SQL 正确"""
        pool = FakePool(return_value=[{"id": uuid4()}, {"id": uuid4()}])
        ids = [uuid4(), uuid4()]

        await topic_repo.batch_update_fields(
            pool,
            topic_ids=ids,
            fields={"priority": "A"},
        )

        sql = pool.conn.sql
        assert "UPDATE hermes.topics" in sql
        assert "SET priority = $1" in sql
        assert "WHERE id = ANY($2)" in sql
        assert "RETURNING id" in sql
        assert pool.conn.params == ("A", ids)

    async def test_batch_update_multiple_fields_sql(self):
        """批量更新多字段 SQL 正确"""
        pool = FakePool(return_value=[])
        ids = [uuid4(), uuid4()]

        await topic_repo.batch_update_fields(
            pool,
            topic_ids=ids,
            fields={
                "priority": "B",
                "resonance": "中",
                "column_name": "运营专栏",
            },
        )

        sql = pool.conn.sql
        assert "priority = $1" in sql
        assert "resonance = $2" in sql
        assert "column_name = $3" in sql
        assert "WHERE id = ANY($4)" in sql
        assert pool.conn.params == ("B", "中", "运营专栏", ids)

    async def test_batch_update_invalid_field_raises(self):
        """批量更新不支持的字段抛出异常"""
        pool = FakePool()
        ids = [uuid4(), uuid4()]

        with pytest.raises(ValueError, match="批量更新不支持字段"):
            await topic_repo.batch_update_fields(
                pool,
                topic_ids=ids,
                fields={"title": "新标题"},
            )

    async def test_batch_update_no_fields_raises(self):
        """未提供任何字段抛出异常"""
        pool = FakePool()
        ids = [uuid4(), uuid4()]

        with pytest.raises(ValueError, match="未提供任何可更新字段"):
            await topic_repo.batch_update_fields(
                pool,
                topic_ids=ids,
                fields={},
            )

    async def test_batch_update_empty_ids_returns_empty(self):
        """空 ids 列表返回空结果"""
        pool = FakePool()

        result = await topic_repo.batch_update_fields(
            pool,
            topic_ids=[],
            fields={"priority": "A"},
        )

        assert result == []


@pytest.mark.asyncio
class TestListByFilterEnhancedSQL:
    """T007: 测试增强的 list_by_filter SQL 构造"""

    async def test_list_with_priority_filter_sql(self):
        """priority 过滤 SQL 正确"""
        pool = FakePool(return_value=[])

        await topic_repo.list_by_filter(
            pool,
            priority="A",
            limit=20,
            offset=0,
        )

        sql = pool.conn.sql
        assert "priority = $1" in sql
        assert "LIMIT $2 OFFSET $3" in sql

    async def test_list_exclude_published_sql(self):
        """exclude_published SQL 正确"""
        pool = FakePool(return_value=[])

        await topic_repo.list_by_filter(
            pool,
            exclude_published=True,
            limit=20,
            offset=0,
        )

        sql = pool.conn.sql
        assert "status != 'published'" in sql

    async def test_list_returns_operational_fields_sql(self):
        """SELECT 包含运营字段"""
        pool = FakePool(return_value=[])

        await topic_repo.list_by_filter(
            pool,
            limit=20,
            offset=0,
        )

        sql = pool.conn.sql
        assert "resonance" in sql
        assert "column_name" in sql
        assert "priority" in sql

    async def test_list_combined_filters_sql(self):
        """组合过滤条件 SQL 正确"""
        pool = FakePool(return_value=[])

        await topic_repo.list_by_filter(
            pool,
            account="test_account",
            priority="B",
            exclude_published=True,
            limit=10,
            offset=0,
        )

        sql = pool.conn.sql
        assert "account = $1" in sql
        assert "priority = $2" in sql
        assert "status != 'published'" in sql
        assert "LIMIT $3 OFFSET $4" in sql
