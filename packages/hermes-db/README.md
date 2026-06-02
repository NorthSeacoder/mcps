# hermes-db-mcp

Hermes 领域级 DB MCP Server — 语义化数据访问工具。

对外暴露领域工具（create_topic / find_similar_topics 等），内部封装 embedding 生成、PG 读写、Redis 缓存、状态机校验。

> 本服务已迁入 `mcps` 平台仓。源码位于 `packages/hermes-db/`，公共部署描述位于 `deploy/services/hermes-db.yml`。本目录内的 `docker-compose.yml` 是服务自带的本地开发样例，NAS 部署沿用平台层 compose。详见 [`docs/hermes-db-deployment.md`](../../docs/hermes-db-deployment.md)。

## 工具列表

| Tool | 说明 |
|------|------|
| `health` | PG/Redis/Embedding 三项探活 |
| `create_topic` | 创建选题（自动 embedding + 缓存；支持 `revisit_of` / `mother_theme`） |
| `find_similar_topics` | 语义相似选题检索（返回 `similarity`、`bucket`、`age_days`） |
| `update_topic_status` | 状态流转（内置状态机） |
| `list_topics` | 列表查询（分页 + 过滤） |
| `get_topic` | 单条详情（缓存优先） |
| `list_revisit_chain` | 按 `revisit_of` 追溯母题迭代链 |
| `create_novel_inspiration` | 创建灵感 |
| `find_similar_inspirations` | 语义相似灵感检索 |
| `list_inspirations` | 灵感列表 |
| `get_inspiration` | 灵感详情 |

## 本地开发（stdio 模式）

```bash
cp .env.example .env
# 编辑 .env 填入真实连接信息
uv sync
uv run hermes-db-mcp
```

## 部署（docker compose + Streamable HTTP 模式）

```bash
cp .env.example .env
# 编辑 .env: TRANSPORT=streamable-http, API_TOKEN, PG_DSN, REDIS_URL, EMBEDDING_*
docker compose up -d
```

Server 在 proxy 网络内监听 `8080` 端口，不映射宿主机端口。

### 数据库迁移

schema 变更使用 Alembic。迁移是发布步骤，不绑定普通服务 `ENTRYPOINT`：

```bash
docker compose run --rm --entrypoint alembic hermes-db-mcp upgrade head
docker compose up -d hermes-db-mcp
```

`alembic upgrade head` 会根据数据库内的 `alembic_version` 判断待执行 revision；数据库已在最新版本时不会重复执行 DDL。镜像内包含 `alembic.ini` 和 `migrations/`，可用同一镜像执行迁移和启动服务。

### topic bucket / revisit capabilities

`health()` 返回以下能力键，供下游 agent 判断是否可以消费 server 端去重分档和母题链路：

```json
{
  "version": "0.2.5",
  "schema_revision": "0001_topic_revisit",
  "capabilities": {
    "topic_bucket": true,
    "topic_revisit_of": true,
    "list_revisit_chain": true
  }
}
```

`capabilities` 由当前数据库 schema 检测得出；如果 release migration 未执行，相关键会返回 `false`，下游应按未部署新能力处理。

## MCP Client 配置

推荐使用 Streamable HTTP `/mcp` endpoint。服务端使用标准 HTTP `Authorization: Bearer <token>` 认证；不同客户端只是配置字段名不同。

### Codex

Codex 可以直接写静态 header：

```toml
[mcp_servers.hermes-db]
type = "streamable-http"
url = "http://hermes-db-mcp:8080/mcp"
http_headers = { Authorization = "Bearer <token>" }
```

也可以用环境变量承载 token：

```toml
[mcp_servers.hermes-db]
type = "streamable-http"
url = "http://hermes-db-mcp:8080/mcp"
bearer_token_env_var = "HERMES_DB_MCP_TOKEN"
```

### Claude Code

Claude Code 使用 `headers` 字段：

```json
{
  "mcpServers": {
    "hermes-db": {
      "type": "streamable-http",
      "url": "http://hermes-db-mcp:8080/mcp",
      "headers": {
        "Authorization": "Bearer <token>"
      }
    }
  }
}
```

### SSE legacy

如果仍需要旧 SSE transport，需要显式设置 `TRANSPORT=sse`，并使用 `/sse` endpoint：

```json
{
  "mcpServers": {
    "hermes-db": {
      "url": "http://hermes-db-mcp:8080/sse"
    }
  }
}
```

除非现有客户端只能使用 SSE，否则新配置应优先使用 Streamable HTTP。

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `PG_DSN` | - | PostgreSQL 连接串 |
| `REDIS_URL` | - | Redis 连接 URL |
| `EMBEDDING_BASE_URL` | - | OpenAI 兼容 embedding API |
| `EMBEDDING_API_KEY` | - | API Key |
| `EMBEDDING_MODEL` | text-embedding-v3 | 模型名 |
| `EMBEDDING_DIMENSION` | 1024 | 向量维度 |
| `TRANSPORT` | stdio | stdio、sse 或 streamable-http |
| `API_TOKEN` | - | HTTP/SSE bearer token；为空时不启用认证，生产环境必须配置 |
| `BUCKET_HARD_THRESHOLD` | `0.95` | `find_similar_topics` hard bucket 阈值 |
| `BUCKET_SOFT_THRESHOLD` | `0.80` | `find_similar_topics` soft/revisit bucket 阈值 |
| `BUCKET_REVISIT_DAYS` | `90` | 超过该天数的中等相似选题返回 revisit bucket |
