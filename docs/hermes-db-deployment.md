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
8. 确认无误后归档原仓。

在切换完成前，原仓的运行态保持可用，两者可并存。
