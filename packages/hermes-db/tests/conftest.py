"""
测试 fixtures
"""

import pytest
import asyncpg
import os


@pytest.fixture
async def db_pool():
    """
    提供真实数据库连接池用于集成测试
    需要环境变量: DATABASE_URL
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL not set, skipping integration tests")

    pool = await asyncpg.create_pool(database_url, min_size=1, max_size=2)
    try:
        yield pool
    finally:
        await pool.close()


@pytest.fixture
async def sample_topic(db_pool):
    """创建一个测试 topic"""
    from hermes_db_mcp.repositories import topic_repo

    row = await topic_repo.insert_topic(
        db_pool,
        title="测试选题",
        account="test_account",
        priority="B",
    )

    yield row

    # 清理
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM hermes.topics WHERE id = $1", row["id"])


@pytest.fixture
async def sample_topics(db_pool):
    """创建多个测试 topics"""
    from hermes_db_mcp.repositories import topic_repo

    topics = []
    for i in range(5):
        row = await topic_repo.insert_topic(
            db_pool,
            title=f"测试选题 {i}",
            account="test_account",
            priority="B",
        )
        topics.append(row)

    yield topics

    # 清理
    async with db_pool.acquire() as conn:
        ids = [t["id"] for t in topics]
        await conn.execute("DELETE FROM hermes.topics WHERE id = ANY($1)", ids)


@pytest.fixture
async def sample_topics_mixed_priority(db_pool):
    """创建不同 priority 的测试 topics"""
    from hermes_db_mcp.repositories import topic_repo

    topics = []
    priorities = ["A", "A", "B", "B", "C"]
    for i, priority in enumerate(priorities):
        row = await topic_repo.insert_topic(
            db_pool,
            title=f"测试选题 {i}",
            account="test_account",
            priority=priority,
        )
        topics.append(row)

    yield topics

    # 清理
    async with db_pool.acquire() as conn:
        ids = [t["id"] for t in topics]
        await conn.execute("DELETE FROM hermes.topics WHERE id = ANY($1)", ids)


@pytest.fixture
async def sample_topics_mixed_status(db_pool):
    """创建不同 status 的测试 topics"""
    from hermes_db_mcp.repositories import topic_repo

    topics = []
    statuses = ["draft", "writing", "published"]
    for i, status in enumerate(statuses):
        row = await topic_repo.insert_topic(
            db_pool,
            title=f"测试选题 {i}",
            account="test_account",
        )
        # 更新 status
        async with db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE hermes.topics SET status = $1 WHERE id = $2",
                status,
                row["id"],
            )
        row["status"] = status
        topics.append(row)

    yield topics

    # 清理
    async with db_pool.acquire() as conn:
        ids = [t["id"] for t in topics]
        await conn.execute("DELETE FROM hermes.topics WHERE id = ANY($1)", ids)


@pytest.fixture
async def sample_topics_mixed(db_pool):
    """创建混合条件的测试 topics"""
    from hermes_db_mcp.repositories import topic_repo

    topics = []
    configs = [
        {"account": "test_account", "priority": "A", "status": "draft"},
        {"account": "test_account", "priority": "B", "status": "draft"},
        {"account": "test_account", "priority": "B", "status": "writing"},
        {"account": "other_account", "priority": "B", "status": "draft"},
        {"account": "test_account", "priority": "A", "status": "published"},
    ]

    for i, config in enumerate(configs):
        row = await topic_repo.insert_topic(
            db_pool,
            title=f"测试选题 {i}",
            account=config["account"],
            priority=config["priority"],
        )
        # 更新 status
        async with db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE hermes.topics SET status = $1 WHERE id = $2",
                config["status"],
                row["id"],
            )
        row["status"] = config["status"]
        topics.append(row)

    yield topics

    # 清理
    async with db_pool.acquire() as conn:
        ids = [t["id"] for t in topics]
        await conn.execute("DELETE FROM hermes.topics WHERE id = ANY($1)", ids)
