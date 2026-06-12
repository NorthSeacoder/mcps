# hermes-db 部署说明

本文档描述 `hermes-db` 在 `mcps` 平台仓内的源码、构建与部署边界。

---

## 源码位置

```
packages/hermes-db/
├── src/hermes_db_mcp/     # 业务源码
├── tests/                 # 测试
├── pyproject.toml         # 依赖与入口定义
├── Dockerfile             # 镜像构建
├── docker-compose.yml     # 本地开发用 compose（非 NAS 部署）
└── .env.example           # 环境变量模板
```

---

## 构建镜像

```bash
cd packages/hermes-db
docker build -t ghcr.io/northseacoder/hermes-db-mcp:latest .
```

本地构建只用于调试。正式发布使用服务级 Git tag：

```bash
git tag hermes-db-v0.1.1
git push origin hermes-db-v0.1.1
```

GitHub Actions 会构建并推送：

```text
ghcr.io/northseacoder/hermes-db-mcp:v0.1.1
```

---

## 本地开发

```bash
cd packages/hermes-db
cp .env.example .env
# 编辑 .env 填入本地 PG/Redis/Embedding 连接信息
uv sync
uv run hermes-db-mcp          # stdio 模式
```

或使用本地 compose：

```bash
docker compose up -d           # 使用服务目录内的 docker-compose.yml
```

如本次发布包含 schema 变更，先用同一镜像显式执行 Alembic migration：

```bash
docker compose run --rm --entrypoint alembic hermes-db-mcp upgrade head
docker compose up -d hermes-db-mcp
```

迁移不绑定普通服务 `ENTRYPOINT`。这样迁移失败时旧运行态不会被无意替换，也避免未来多副本同时尝试迁移。

### `0005_wechat_retro_opt` 发布检查

包含 `0005_wechat_retro_opt` 的版本会新增 `topic_performance`、`wechat_retrospective_reports`、`topic_optimization_suggestions`、`learning_candidates` 四张表，用于公众号复盘选题优化的持久化、审核和学习候选项交接。

发布前后建议执行：

```bash
cd packages/hermes-db
DATABASE_URL=<postgres-url> uv run pytest tests/test_wechat_retrospective_integration.py -q
docker compose run --rm --entrypoint alembic hermes-db-mcp upgrade head
```

迁移后通过 MCP `health` 确认：

```json
{
  "schema_revision": "0005_wechat_retro_opt",
  "capabilities": {
    "wechat_retrospective_topic_optimizer": true
  }
}
```

同时确认 `tools/list` 包含 `upsert_topic_performance`、`list_topic_performance`、`create_wechat_retrospective_report`、`list_wechat_retrospective_reports`、`create_topic_optimization_suggestions`、`list_approved_topic_ranking_hints`、`create_learning_candidates`、`review_learning_candidate`。

如需回滚 schema，`alembic downgrade 0004_wechat_analytics_ingestion` 会删除上述四张 retrospective 表及其中数据，但不修改既有 topic、workflow、publication ledger 或 analytics 表。生产回滚前应先确认复盘产物是否需要备份或导出。

### `0006_agent_self_evolution` 发布检查

包含 `0006_agent_self_evolution` 的版本会新增 `agent_policies` 和 `policy_applications` 两张表，用于 agent 自演化的 runtime policy store 和 application trace：approved `learning_candidates` 可被提升为 versioned active policy，业务 agent 按 domain/scope/task_type/decision_point 查询 applicable policy，并写回 append-only application trace；disable/rollback 保留历史。

发布前后建议执行：

```bash
cd packages/hermes-db
DATABASE_URL=<postgres-url> uv run pytest tests/test_agent_self_evolution_repo_sql.py tests/test_agent_self_evolution_tools.py -q
docker compose run --rm --entrypoint alembic hermes-db-mcp upgrade head
```

迁移后通过 MCP `health` 确认：

```json
{
  "schema_revision": "0006_agent_self_evolution",
  "capabilities": {
    "agent_self_evolution_foundation": true
  }
}
```

同时确认 `tools/list` 包含 `promote_learning_candidate_to_policy`、`list_agent_policies`、`get_applicable_agent_policies`、`disable_agent_policy`、`rollback_agent_policy`、`record_policy_application`、`list_policy_applications`。

如需回滚 schema，`alembic downgrade 0005_wechat_retro_opt` 会先删除 `policy_applications` 再删除 `agent_policies`，但不修改 `learning_candidates` 及更早的表。生产回滚前应确认 policy 与 application trace 是否需要备份。

---

## NAS 部署

NAS 部署由 self-hosted runner 执行。runner 根据 `deploy/mcp-services.json` 找到 compose 项目目录，并调用：

```bash
scripts/nas-deploy-mcp.sh
```

NAS 私有配置（PG_DSN、REDIS_URL、密钥等）通过 `deploy/nas.local.env` 提供，不进入开源仓。

---

## 迁移状态

| 内容 | 状态 |
|------|------|
| 源码 | 已迁入 `packages/hermes-db/` |
| Dockerfile | 已迁入 |
| 构建约定 | 已对齐平台镜像命名 |
| 平台层 compose | 已创建 `deploy/services/hermes-db.yml` |
| NAS 运行态切换 | 待单独安排（不在首期范围） |

---

## 切换步骤（后续执行）

当准备好将 NAS 运行态从原仓切换到平台仓时：

1. 确认 `deploy/nas.local.env` 已在 NAS 上准备好。
2. 停止原仓的容器。
3. 使用平台层 compose 拉取并启动。
4. 如版本包含 migration，执行 `docker compose run --rm --entrypoint alembic hermes-db-mcp upgrade head`。
5. 启动服务后验证服务可用性（调用 `health` 工具）。
6. 对 `hermes-db-v0.2.0` 及之后版本，确认 `health().capabilities.topic_bucket`、`topic_revisit_of`、`list_revisit_chain` 均为 `true`。
7. 对 `hermes-db-v0.2.9` 及之后版本，确认 `health().schema_revision == "0002_wechat_workflow_artifacts"`，且 `health().capabilities.workflow_runs`、`workflow_artifacts` 均为 `true`。
8. 对包含 `0003_wechat_publication_ledger` 的版本，确认 `health().schema_revision == "0003_wechat_publication_ledger"`，且 `health().capabilities.wechat_publication_ledger == true`；`tools/list` 应包含 `upsert_wechat_article`、`list_wechat_articles`、`get_wechat_article`、`update_wechat_article_external_refs`。
9. 对包含 `0004_wechat_analytics_ingestion` 的版本，确认 `health().schema_revision == "0004_wechat_analytics_ingestion"`，且 `health().capabilities.wechat_analytics_ingestion == true`；`tools/list` 应包含 `bulk_upsert_wechat_article_metric_snapshots`、`list_wechat_article_metric_snapshots`。
10. 对包含 `0005_wechat_retro_opt` 的版本，确认 `health().schema_revision == "0005_wechat_retro_opt"`，且 `health().capabilities.wechat_retrospective_topic_optimizer == true`；`tools/list` 应包含 `upsert_topic_performance`、`list_topic_performance`、`create_wechat_retrospective_report`、`list_wechat_retrospective_reports`、`create_topic_optimization_suggestions`、`list_approved_topic_ranking_hints`、`create_learning_candidates`、`review_learning_candidate`。agents 侧 live smoke 需要在该 capability 为 true 后再执行。
11. 对包含 `0006_agent_self_evolution` 的版本，确认 `health().schema_revision == "0006_agent_self_evolution"`，且 `health().capabilities.agent_self_evolution_foundation == true`；`tools/list` 应包含 `promote_learning_candidate_to_policy`、`list_agent_policies`、`get_applicable_agent_policies`、`disable_agent_policy`、`rollback_agent_policy`、`record_policy_application`、`list_policy_applications`。agents 侧 policy live smoke 需要在该 capability 为 true 后再执行。
12. 确认无误后归档原仓。

在切换完成前，原仓的运行态保持可用，两者可并存。
