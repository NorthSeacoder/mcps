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
| `upsert_workflow_run` | 创建或更新公众号 workflow run 主记录 |
| `finish_workflow_run` | 完成、失败或阻塞公众号 workflow run |
| `upsert_workflow_artifact` | 保存 workflow artifact 摘要、hash、metadata 和正文或引用 |
| `list_workflow_artifacts` | 按 run/topic/account/date/type 查询 workflow artifact 摘要 |
| `get_workflow_artifact_content` | 读取 workflow artifact 的 inline 正文或 `content_ref` metadata |
| `upsert_wechat_article` | 创建或更新公众号 article ledger 主记录 |
| `list_wechat_articles` | 按 account/topic/run/status/date 查询 article 摘要 |
| `get_wechat_article` | 读取 article ledger 详情和外部引用列表 |
| `update_wechat_article_external_refs` | 补写或修复 article 外部引用 |
| `upsert_topic_performance` | 写入或更新公众号文章选题表现评分 |
| `list_topic_performance` | 查询选题表现评分和诊断摘要 |
| `create_wechat_retrospective_report` | 保存文章/周期复盘报告结构化结果 |
| `get_wechat_retrospective_report` | 读取单份复盘报告 |
| `list_wechat_retrospective_reports` | 按 account/type/article/date 查询复盘报告 |
| `create_topic_optimization_suggestions` | 批量保存选题优化建议 |
| `list_topic_optimization_suggestions` | 查询优化建议和审核状态 |
| `review_topic_optimization_suggestion` | 审核优化建议，不直接修改 topics |
| `list_approved_topic_ranking_hints` | 查询已审核通过且未过期的 ranking hints |
| `create_learning_candidates` | 批量保存策略学习候选项 |
| `list_learning_candidates` | 查询学习候选项 |
| `review_learning_candidate` | 审核学习候选项，不直接导出策略 |
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

### topic bucket / revisit / workflow / publication ledger / analytics / retrospective capabilities

`health()` 返回以下能力键，供下游 agent 判断是否可以消费 server 端去重分档、母题链路、workflow artifact 持久化、公众号发布台账、微信文章数据导入和复盘选题优化持久化：

```json
{
  "version": "0.2.16",
  "schema_revision": "0006_agent_self_evolution",
  "capabilities": {
    "topic_bucket": true,
    "topic_revisit_of": true,
    "list_revisit_chain": true,
    "workflow_runs": true,
    "workflow_artifacts": true,
    "wechat_publication_ledger": true,
    "wechat_analytics_ingestion": true,
    "wechat_retrospective_topic_optimizer": true,
    "agent_self_evolution_foundation": true
  }
}
```

`capabilities` 由当前数据库 schema 检测得出；如果 release migration 未执行，相关键会返回 `false`，下游应按未部署新能力处理。

### workflow artifact persistence

Workflow artifact tools 只负责持久化和查询，不编排公众号 workflow。正文小于 256 KiB 时可写入 `content_text`；更大的产物应写入 `content_ref`，hermes-db 只保存并返回引用，不读取外部文件或 URL。`list_workflow_artifacts` 默认只返回摘要，不返回 `content_text`；需要正文时调用 `get_workflow_artifact_content`。

### wechat publication ledger

Article ledger tools 负责保存公众号文章发布台账，不调用微信发布 API，也不复制 artifact 正文。`upsert_wechat_article` 以 `(account, publication_idempotency_key)` 保证幂等；`article_id` 由服务端生成。`wechat_articles` 通过 FK 关联 workflow run 和已存在的 draft/final/publish artifacts；外部 URL、微信平台标识、YouMind 引用和人工修复引用写入 `wechat_article_external_refs`。`list_wechat_articles` 和 `get_wechat_article` 只返回 article 元数据、artifact id 和 external refs，不返回 artifact content。

### wechat analytics ingestion

Analytics ingestion tools 负责保存已由 agents 侧 normalizer 转换好的微信文章指标，不解析 Excel/CSV/JSON 文件。`bulk_upsert_wechat_article_metric_snapshots` 以 `(article_id, stat_date, window_label, source)` 幂等写入文章指标快照，并以 `(article_id, metric_date, channel, source)` 幂等写入渠道日明细。`list_wechat_article_metric_snapshots` 支持按 account、article、date window 和 `window_label` 查询；默认不返回 `raw_json`，需要调试原始行时传 `include_raw=true`。

### wechat retrospective topic optimizer

Retrospective topic optimizer tools 负责保存 agents 侧计算好的文章表现评分、复盘报告、选题优化建议和学习候选项，不负责评分算法、LLM 叙述生成或自动修改 `topics`。`upsert_topic_performance` 以 `(account, article_id, window_label, scoring_version)` 幂等写入；reports、suggestions、learning candidates 保持 append-only。下游调用前应检查 `health().capabilities.wechat_retrospective_topic_optimizer == true`；未执行 `0005_wechat_retro_opt` migration 时该 capability 会返回 `false`。

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
| `EMBEDDING_DIMENSION` | 0 | 向量维度参数；`0` 表示请求 embedding 时不发送 `dimensions` |
| `TRANSPORT` | stdio | stdio、sse 或 streamable-http |
| `API_TOKEN` | - | HTTP/SSE bearer token；为空时不启用认证，生产环境必须配置 |
| `BUCKET_HARD_THRESHOLD` | `0.95` | `find_similar_topics` hard bucket 阈值 |
| `BUCKET_SOFT_THRESHOLD` | `0.80` | `find_similar_topics` soft/revisit bucket 阈值 |
| `BUCKET_REVISIT_DAYS` | `90` | 超过该天数的中等相似选题返回 revisit bucket |
