from uuid import UUID

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from hermes_db_mcp.server import mcp, AppContext
from hermes_db_mcp.services.embedding import generate_embedding
from hermes_db_mcp.services.state_machine import validate_transition
from hermes_db_mcp.services.cache import (
    cache_record,
    get_cached,
    update_recent_set,
    delete_cached,
    serialize_topic_row,
)
from hermes_db_mcp.repositories import topic_repo
from hermes_db_mcp.contracts import (
    validate_priority,
    validate_resonance,
    validate_title,
    validate_clear_fields,
    validate_batch_ids,
    validate_pagination,
    error,
    TopicUpdateResult,
    BatchTopicUpdateResult,
    TopicListResult,
    ToolError,
)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    )
)
async def create_topic(
    title: str,
    account: str,
    ctx: Context,
    angle: str | None = None,
    priority: str = "B",
    column_name: str | None = None,
    resonance: str | None = None,
    content: str | None = None,
    source: str = "topic-inbox",
) -> dict:
    """创建选题。自动生成 embedding 并写入 PG + Redis。"""
    app: AppContext = ctx.request_context.lifespan_context

    if not title:
        return {"error": "missing_required_field", "field": "title"}
    if not account:
        return {"error": "missing_required_field", "field": "account"}
    if len(title) > 200:
        return {"error": "field_too_long", "field": "title", "max_length": 200}

    embed_text = f"{title} {angle}" if angle else title
    embedding = await generate_embedding(app.http, embed_text)

    row = await topic_repo.insert_topic(
        app.pool,
        title=title,
        account=account,
        angle=angle,
        priority=priority,
        column_name=column_name,
        resonance=resonance,
        content=content,
        source=source,
        embedding=embedding,
    )

    topic_id = str(row["id"])
    await update_recent_set(app.redis, f"hermes:topics:recent:{account}", topic_id)

    return {
        "id": topic_id,
        "status": row["status"],
        "embedding_pending": embedding is None,
        "created_at": str(row["created_at"]),
    }


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def find_similar_topics(
    text: str,
    ctx: Context,
    account: str | None = None,
    threshold: float = 0.5,
    limit: int = 5,
) -> list[dict] | dict:
    """根据文本语义检索相似选题。"""
    app: AppContext = ctx.request_context.lifespan_context

    embedding = await generate_embedding(app.http, text)
    if embedding is None:
        return {"error": "embedding_unavailable", "message": "无法生成查询向量"}

    rows = await topic_repo.find_similar(
        app.pool,
        embedding=embedding,
        account=account,
        threshold=threshold,
        limit=limit,
    )
    for r in rows:
        r["id"] = str(r["id"])
        r["similarity"] = round(r["similarity"], 4)
        r["created_at"] = str(r["created_at"])
    return rows


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def update_topic_status(id: str, new_status: str, ctx: Context) -> dict:
    """更新选题状态，内置状态机校验。"""
    app: AppContext = ctx.request_context.lifespan_context

    topic_id = UUID(id)
    current = await topic_repo.get_by_id(app.pool, topic_id=topic_id)
    if not current:
        return {"error": "not_found", "id": id}

    err = validate_transition("topic", current["status"], new_status)
    if err:
        return err

    row = await topic_repo.update_status(
        app.pool, topic_id=topic_id, new_status=new_status
    )
    await cache_record(
        app.redis, f"hermes:topic:{id}", {**current, "status": new_status}
    )

    return {
        "id": id,
        "status": row["status"],
        "previous_status": current["status"],
    }


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def publish_topic(id: str, published_url: str, ctx: Context) -> dict:
    """将选题标记为已发布，同时记录文章链接。仅 writing 状态可发布。"""
    app: AppContext = ctx.request_context.lifespan_context

    topic_id = UUID(id)
    current = await topic_repo.get_by_id(app.pool, topic_id=topic_id)
    if not current:
        return {"error": "not_found", "id": id}

    err = validate_transition("topic", current["status"], "published")
    if err:
        return err

    row = await topic_repo.publish(
        app.pool, topic_id=topic_id, published_url=published_url
    )
    await cache_record(
        app.redis,
        f"hermes:topic:{id}",
        {**current, "status": "published", "published_url": published_url},
    )

    return {
        "id": id,
        "status": row["status"],
        "published_url": row["published_url"],
        "previous_status": current["status"],
    }


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def list_topics(
    ctx: Context,
    account: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    exclude_published: bool = False,
    limit: int = 20,
    offset: int = 0,
) -> TopicListResult | ToolError:
    """
    T013: 列出选题，支持按账号、状态、优先级过滤，可排除已发布

    Args:
        account: 账号过滤(可选)
        status: 状态过滤(可选)
        priority: 优先级过滤 A/B/C(可选)
        exclude_published: 是否排除 published 状态(默认 False)
        limit: 每页数量(1-100, 默认 20)
        offset: 偏移量(默认 0)

    Returns:
        成功: TopicListResult 包含 items/total，items 包含运营字段
        失败: ToolError
    """
    app: AppContext = ctx.request_context.lifespan_context

    # 校验输入
    if err := validate_priority(priority):
        return err
    if err := validate_pagination(limit, offset):
        return err

    items, total = await topic_repo.list_by_filter(
        app.pool,
        account=account,
        status=status,
        priority=priority,
        exclude_published=exclude_published,
        limit=limit,
        offset=offset,
    )
    for item in items:
        item["id"] = str(item["id"])
        item["created_at"] = str(item["created_at"])

    result: TopicListResult = {"items": items, "total": total}
    return result


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_topic(id: str, ctx: Context) -> dict:
    """获取单条选题详情，优先读 Redis 缓存。"""
    app: AppContext = ctx.request_context.lifespan_context

    cache_key = f"hermes:topic:{id}"
    cached = await get_cached(app.redis, cache_key)
    if cached:
        return cached

    topic_id = UUID(id)
    row = await topic_repo.get_by_id(app.pool, topic_id=topic_id)
    if not row:
        return {"error": "not_found", "id": id}

    result = {
        k: str(v) if k in ("id", "created_at", "updated_at") else v
        for k, v in row.items()
    }
    await cache_record(app.redis, cache_key, result)
    return result


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def update_topic(
    id: str,
    ctx: Context,
    title: str | None = None,
    angle: str | None = None,
    priority: str | None = None,
    column_name: str | None = None,
    resonance: str | None = None,
    content: str | None = None,
    clear_fields: list[str] | None = None,
) -> TopicUpdateResult | ToolError:
    """
    T011: 更新单条 topic 的可编辑字段

    Args:
        id: topic UUID
        title: 新标题(可选)
        angle: 新角度(可选)
        priority: 新优先级 A/B/C(可选)
        column_name: 新专栏名(可选)
        resonance: 新共鸣度 高/中/低(可选)
        content: 新内容(可选)
        clear_fields: 要清空的字段列表,只允许 angle/column_name/resonance/content

    Returns:
        成功: TopicUpdateResult 包含 id/updated_fields/embedding_regenerated/updated_at
        失败: ToolError 包含 error/message/field/details
    """
    app: AppContext = ctx.request_context.lifespan_context

    # 校验输入
    if err := validate_priority(priority):
        return err
    if err := validate_resonance(resonance):
        return err
    if err := validate_title(title):
        return err
    if err := validate_clear_fields(clear_fields):
        return err

    # 解析 UUID
    try:
        topic_id = UUID(id)
    except (ValueError, AttributeError):
        return error("invalid_uuid", field="id", details={"value": id})

    # 读取旧值
    current = await topic_repo.get_by_id(app.pool, topic_id=topic_id)
    if not current:
        return error("not_found", details={"id": id})

    # 构造更新字段
    fields = {}
    if title is not None:
        fields["title"] = title
    if angle is not None:
        fields["angle"] = angle
    if priority is not None:
        fields["priority"] = priority
    if column_name is not None:
        fields["column_name"] = column_name
    if resonance is not None:
        fields["resonance"] = resonance
    if content is not None:
        fields["content"] = content

    # 处理 clear_fields
    if clear_fields:
        for field in clear_fields:
            fields[field] = None

    if not fields:
        return error("no_fields_to_update")

    # 判断是否需要重算 embedding
    embedding_regenerated = False
    embedding_pending = False
    new_embedding = ...  # Ellipsis 表示不更新

    if "title" in fields or "angle" in fields:
        # 合并后的完整语义文本
        merged_title = fields.get("title", current["title"])
        merged_angle = fields.get("angle", current.get("angle"))
        embed_text = f"{merged_title} {merged_angle}" if merged_angle else merged_title

        new_embedding = await generate_embedding(app.http, embed_text)
        embedding_regenerated = True
        if new_embedding is None:
            embedding_pending = True

    # 执行更新
    try:
        updated_row = await topic_repo.update_topic_fields(
            app.pool,
            topic_id=topic_id,
            fields=fields,
            embedding=new_embedding,
        )
    except Exception as e:
        return error("database_error", details={"message": str(e)})

    if not updated_row:
        return error("not_found", details={"id": id})

    # 重写缓存
    cache_key = f"hermes:topic:{id}"
    serialized = serialize_topic_row(updated_row)
    await cache_record(app.redis, cache_key, serialized)

    # 构造结果
    result: TopicUpdateResult = {
        "id": id,
        "updated_fields": list(fields.keys()),
        "embedding_regenerated": embedding_regenerated,
        "updated_at": str(updated_row["updated_at"]),
    }
    if embedding_pending:
        result["embedding_pending"] = True

    return result


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def batch_update_topics(
    ids: list[str],
    ctx: Context,
    priority: str | None = None,
    resonance: str | None = None,
    column_name: str | None = None,
) -> BatchTopicUpdateResult | ToolError:
    """
    T012: 批量更新 topic 运营字段

    Args:
        ids: topic UUID 列表
        priority: 新优先级 A/B/C(可选)
        resonance: 新共鸣度 高/中/低(可选)
        column_name: 新专栏名(可选)

    Returns:
        成功: BatchTopicUpdateResult 包含 requested_count/unique_count/matched/updated/not_found_ids
        失败: ToolError
    """
    app: AppContext = ctx.request_context.lifespan_context

    # 校验输入
    if err := validate_priority(priority):
        return err
    if err := validate_resonance(resonance):
        return err

    # 解析并去重 UUIDs
    requested_count = len(ids)
    parsed_ids, err = validate_batch_ids(ids)
    if err:
        return err

    unique_count = len(parsed_ids)

    # 构造更新字段
    fields = {}
    if priority is not None:
        fields["priority"] = priority
    if resonance is not None:
        fields["resonance"] = resonance
    if column_name is not None:
        fields["column_name"] = column_name

    if not fields:
        return error("no_fields_to_update")

    # 执行批量更新
    try:
        updated_ids = await topic_repo.batch_update_fields(
            app.pool,
            topic_ids=parsed_ids,
            fields=fields,
        )
    except Exception as e:
        return error("database_error", details={"message": str(e)})

    # 计算 not_found
    updated_id_set = set(updated_ids)
    not_found_ids = [str(uid) for uid in parsed_ids if uid not in updated_id_set]

    # 删除相关缓存
    cache_keys = [f"hermes:topic:{uid}" for uid in updated_ids]
    await delete_cached(app.redis, *cache_keys)

    # 构造结果
    result: BatchTopicUpdateResult = {
        "requested_count": requested_count,
        "unique_count": unique_count,
        "matched": len(updated_ids),
        "updated": len(updated_ids),
        "updated_fields": list(fields.keys()),
        "not_found_ids": not_found_ids,
    }

    return result
