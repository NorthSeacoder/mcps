# Implementation Plan: hermes-db topic bucket & revisit_of

**Workspace**: `hermes-db-topic-bucket-revisit` | **Date**: 2026-06-01 | **Spec**: [spec.md](spec.md)
**Target version**: 0.2.6 | **Current version**: 0.1.13

---

## Summary

在 hermes-db 0.2.6 中完成三件事：① 用 alembic 给 `hermes.topics` 加两个 NULL 字段（`revisit_of` + `mother_theme`）并禁止 `revisit_of` 自引用；② 在 `find_similar_topics` 返回值里加 `bucket`/`age_days` 注解，阈值从 `config.py` 读取；③ 新增 `list_revisit_chain` 工具和 `health.capabilities`。部署链路采用显式 release migration：镜像包含 alembic 资产，发布时先运行一次 `alembic upgrade head`，成功后再启动新版 server；普通容器重启不默认执行 migration。

---

## Architecture Overview

```text
Deploy flow:
  git tag hermes-db-v0.2.6
  → CI build image
  → NAS pull image
  → release step: docker compose run --rm --entrypoint alembic hermes-db-mcp upgrade head
                                                   ↑ psycopg2 连接，执行 DDL，幂等
  → docker compose up -d hermes-db-mcp
                         ↑ asyncpg pool，业务流量

Request flow (find_similar_topics):
  tool call
  → generate_embedding()
  → topic_repo.find_similar()     # SQL 返回 id/title/similarity/created_at
  → _compute_bucket(row, thresholds)  # 纯 CPU，按 similarity + age_days 判定
  → 返回含 bucket/age_days 的列表

Request flow (list_revisit_chain):
  tool call(topic_id, max_depth=20)
  → topic_repo.get_revisit_chain()   # while 循环 + visited set，防环
  → 返回数组（含起点本身）
```

---

## Producer-Consumer Matrix

> spec 命中 `artifact-handoff`，下游 feature `wechat-topic-radar-online` 消费本 feature 产物。

| Producer | Artifact | Consumer | Consumption Proof |
|---|---|---|---|
| hermes-db 0.2.6 | `find_similar_topics` 返回的 `bucket` 字段 | wechat-topic-radar-online | 启动时调用 `health().capabilities.topic_bucket == true`；实际调用能读到 `bucket` 字段 |
| hermes-db 0.2.6 | `create_topic` / `update_topic` 的 `revisit_of` 参数 | wechat-topic-radar-online | `health().capabilities.topic_revisit_of == true`；写入后 `get_topic` 能读到该字段 |
| hermes-db 0.2.6 | `list_revisit_chain` 工具 | wechat-topic-radar-online | `health().capabilities.list_revisit_chain == true`；工具存在于 MCP 工具列表 |
| hermes-db 0.2.6 | `health().version >= "0.2.6"` | wechat-topic-radar-online 启动 gate | 启动日志中能看到 version 检查通过，否则降级到本地常量 |

**孤儿 artifact 处理**：无孤儿；`mother_theme` 字段是 `revisit_of` 链路的补充上下文，由同一 consumer 读取，不单独作为 artifact。

---

## Lightweight ADR

| 决策 | 背景 | 候选 | 结论 | 代价 | 来源 |
|---|---|---|---|---|---|
| ADR-001: 改库方式 | 项目历史无 migration 工具，手工改库无追溯 | A: alembic + psycopg2 / B: 启动幂等 DDL / C: 手工 SQL | **alembic + psycopg2**（用户选择） | 引入 psycopg2-binary + alembic 依赖；env.py 需做 URL 转换 | UNVERIFIED |
| ADR-002: alembic 驱动 | asyncpg 是运行时驱动，alembic 需要同步驱动 | A: psycopg2-binary（同步）/ B: asyncpg async alembic（需 SQLAlchemy）| **psycopg2-binary**，仅 migration 时使用，运行时仍用 asyncpg | 镜像多一个 driver；URL 需替换 `postgresql://` → `postgresql+psycopg2://` | UNVERIFIED |
| ADR-003: bucket 计算位置 | 可在 SQL 层或 Python 层做 | A: SQL CASE WHEN / B: Python 层（repo 返回后计算）| **Python 层**，在 `_compute_bucket()` 纯函数中算，方便单测且不增 SQL 复杂度 | 无额外 DB 往返，符合 NFR-002 | UNVERIFIED |
| ADR-004: UQ-1 mother_theme 索引 | 短期手工标注，查询需求不明确 | 建 / 不建 | **不建**，DDL 里加 COMMENT 预留 | 未来有 by-theme 查询时需补 ALTER | UNVERIFIED |
| ADR-005: UQ-2 capabilities 键名 | health 现有结构是 pg/redis/embedding 平铺 | 平铺下划线 `topic_bucket` vs 嵌套 `topic.bucket` | **平铺下划线**，与现有 health 风格一致 | 若 capabilities 增多，未来可能需要重构为嵌套 | UNVERIFIED |
| ADR-006: UQ-3 list_revisit_chain 方向 | 反向（祖先链）vs 正向（子代） | 反向 / 双向 | **仅反向**（本 spec 范围），正向单开 feature | — | UNVERIFIED |

---

## Module Design

### Module 1: `packages/hermes-db/migrations/` *(新建)*

**职责**：alembic schema 版本管理

**改动**：
- `alembic.ini`：`script_location = migrations`；`sqlalchemy.url` 留空（由 env.py 运行时从 `PG_DSN` 读取）
- `migrations/env.py`：读 `PG_DSN` 环境变量，替换前缀为 `postgresql+psycopg2://`，offline/online 模式均支持
- `migrations/versions/0001_add_revisit_of_mother_theme.py`：
  ```text
  upgrade():
    ALTER TABLE hermes.topics
      ADD COLUMN IF NOT EXISTS revisit_of UUID
        REFERENCES hermes.topics(id) ON DELETE SET NULL;
    ALTER TABLE hermes.topics
      ADD COLUMN IF NOT EXISTS mother_theme TEXT;
    ALTER TABLE hermes.topics
      ADD CONSTRAINT chk_topics_revisit_of_not_self
      CHECK (revisit_of IS NULL OR revisit_of <> id);
    CREATE INDEX IF NOT EXISTS idx_topics_revisit_of
      ON hermes.topics(revisit_of);
  downgrade():
    DROP INDEX IF EXISTS idx_topics_revisit_of;
    ALTER TABLE hermes.topics
      DROP CONSTRAINT IF EXISTS chk_topics_revisit_of_not_self;
    ALTER TABLE hermes.topics DROP COLUMN IF EXISTS mother_theme;
    ALTER TABLE hermes.topics DROP COLUMN IF EXISTS revisit_of;
  ```

**注意**：`ADD COLUMN NULL` 在 PG 中是在线操作，无需停机（NFR-001 满足）。

---

### Module 2: `config.py`

**改动**：在 `Settings` 中新增三个可覆盖的 bucket 阈值字段：

```text
bucket_hard_threshold: float = 0.95
bucket_soft_threshold: float = 0.80
bucket_revisit_days: int = 90
version: str = "0.2.6"  # 硬编码，作为 health 探活依据
```

**注意**：阈值与 `find_similar` 的 `threshold` 参数相互独立——`threshold` 是调用方的最低相似度过滤，`bucket_*` 是返回行的分档标注。二者不冲突；bucket 只注解已返回的行。

---

### Module 3: `contracts.py`

**改动**：
- `EDITABLE_TOPIC_FIELDS` 新增 `"revisit_of"` 和 `"mother_theme"`
- `CLEARABLE_TOPIC_FIELDS` 新增 `"revisit_of"` 和 `"mother_theme"`
- 新增错误码：`"invalid_revisit_of_self"` / `"revisit_target_not_found"`
- 新增 `RevisitChainItem(TypedDict)`：`id / title / status / created_at / published_url`
- 新增 `RevisitChainResult(TypedDict)`：`items: list[RevisitChainItem] / truncated: bool`

---

### Module 4: `repositories/topic_repo.py`

**4a. `find_similar` 改动**：

SQL 新增 `created_at` 已在查询中（现有），新增 bucket 计算在 Python 层：

```text
返回行后，对每行调用 _compute_bucket(similarity, created_at, thresholds)：
  age_days = (now - created_at).days  # created_at 为 None → age_days = None
  hard:   similarity >= hard_threshold
  soft:   soft_threshold <= similarity < hard_threshold AND age_days <= revisit_days
  revisit: soft_threshold <= similarity < hard_threshold AND age_days > revisit_days
  weak:   similarity < soft_threshold
  特例：age_days is None → 按 similarity 单独判（hard/soft/weak，不出 revisit）
```

`_compute_bucket` 为模块内纯函数，接受 `(similarity, age_days, cfg)` → `str`。

**4b. `insert_topic` 改动**：SQL 新增 `revisit_of`, `mother_theme` 两列，参数透传。

**4c. `update_topic_fields` 改动**：白名单扩展后自然生效（`EDITABLE_TOPIC_FIELDS` 改动已覆盖）。

**4d. 新增 `get_revisit_chain(pool, topic_id, max_depth=20) → dict`**：

```text
visited = set()
chain = []
current_id = topic_id
while current_id and len(chain) < max_depth:
    if current_id in visited:          # 环路保护
        return {"items": chain, "truncated": True}
    visited.add(current_id)
    row = SELECT id, title, status, created_at, published_url, revisit_of
          FROM hermes.topics WHERE id = current_id
    if not row: break
    chain.append(row without revisit_of)
    current_id = row["revisit_of"]     # 向上追溯
return {"items": chain, "truncated": len(chain) == max_depth and current_id is not None}
```

---

### Module 5: `tools/topics.py`

**5a. `create_topic` 改动**：
- 新增可选参数 `revisit_of: str | None = None` 和 `mother_theme: str | None = None`
- 在调用 `insert_topic` 前做校验（返回结构化错误，不写库）：
  - `revisit_of` 不为 None 时，查 `get_by_id(revisit_of)` 确认存在，否则返回 `revisit_target_not_found`

**5b. `update_topic` 改动**：
- `revisit_of` 和 `mother_theme` 进入可编辑字段白名单
- 当 `revisit_of` 不为 None 时：
  - 若 `revisit_of == id`，返回 `invalid_revisit_of_self`
  - 若目标不存在，返回 `revisit_target_not_found`
  - DB 层 `chk_topics_revisit_of_not_self` 作为最终保护，避免绕过工具层写入自引用

**5c. `find_similar_topics` 改动**：bucket 计算已在 repo 层完成，tool 层只需将 `age_days` 一并暴露（`None` 保留为 null）。

**5d. 新增 `list_revisit_chain` 工具**：
```text
@mcp.tool(annotations=readOnlyHint=True)
async def list_revisit_chain(topic_id: str, ctx, max_depth: int = 20):
  validate UUID
  result = await topic_repo.get_revisit_chain(pool, UUID(topic_id), max_depth)
  serialize ids/created_at
  return result
```

---

### Module 6: `tools/health.py`

**改动**：在返回 dict 末尾追加：
```text
result["version"] = settings.version   # "0.2.6"
result["schema_revision"] = SELECT version_num FROM alembic_version LIMIT 1
result["capabilities"] = inspect_topic_schema(pool)
```
`capabilities` 必须由当前数据库 schema 推导，不能无条件返回 True。旧版本没有这两个键，或代码已升级但 DB migration 未执行时，下游都应等同于全 False。

---

### Module 7: `pyproject.toml` + `Dockerfile`

**pyproject.toml**：
- `version = "0.2.6"`
- `dependencies` 新增 `"alembic>=1.13"` 和 `"psycopg2-binary>=2.9"`

**Dockerfile**：
- 保持服务入口职责单一，不把 migration 绑定进普通 `ENTRYPOINT`
- runtime 镜像必须复制 `alembic.ini`、`migrations/` 与 `alembic` console script，保证发布步骤可用同一镜像覆盖 entrypoint 执行 migration

**Release command（NAS / compose）**：
```bash
docker compose run --rm --entrypoint alembic hermes-db-mcp upgrade head
docker compose up -d hermes-db-mcp
```
`alembic upgrade head` 会根据 `alembic_version` 判断当前 revision；已是最新时不会重复执行 DDL。但它仍应作为发布步骤显式运行，避免普通容器重启、健康检查或未来多副本场景触发迁移。

平台发布脚本会从 `deploy/mcp-services.json` 读取 migration 与 MCP health smoke 配置：先覆盖 entrypoint 执行 Alembic，再启动容器，最后调用 `health` 工具校验 PG 与必要 capabilities。

---

## Data Model

详见 spec.md FR-001；此处记录关键决策：

| 字段 | 类型 | 约束 | 索引 | 说明 |
|---|---|---|---|---|
| `revisit_of` | UUID | NULL, FK self-ref ON DELETE SET NULL, CHECK 不允许自引用 | 有（`idx_topics_revisit_of`） | 祖先链追溯的核心字段 |
| `mother_theme` | TEXT | NULL | 无（ADR-004） | 手工标注，暂不查询 |

`get_by_id` 和 `update_topic_fields` 的 `RETURNING` 子句需补入这两个字段，以免序列化后字段缺失。

---

## Project Structure

```text
packages/hermes-db/
  alembic.ini                                    ← 新建
  migrations/
    env.py                                       ← 新建
    script.py.mako                               ← 新建（alembic 默认模板）
    versions/
      0001_add_revisit_of_mother_theme.py        ← 新建
  src/hermes_db_mcp/
    config.py                                    ← 加 4 个字段
    contracts.py                                 ← 扩展白名单 + 新 TypedDict + 新错误码
    repositories/
      topic_repo.py                              ← 改 find_similar + insert_topic；新增 get_revisit_chain
    tools/
      topics.py                                  ← 改 create_topic + find_similar_topics；新增 list_revisit_chain
      health.py                                  ← 加 version + capabilities
  pyproject.toml                                 ← version + 2 deps
  Dockerfile                                     ← 复制 alembic 资产，保持服务 ENTRYPOINT
```

---

## Risks and Tradeoffs

- **psycopg2 URL 转换**：`PG_DSN` 格式可能带参数（`?sslmode=...`），env.py 需用 URL 解析而非字符串替换。
- **self-referencing FK 不阻止自引用**：`revisit_of = id` 会满足 FK，因此必须增加 `CHECK (revisit_of IS NULL OR revisit_of <> id)`，并在 `update_topic` 工具层提前返回 `invalid_revisit_of_self`。
- **alembic 首次运行**：如果目标 PG 已有旧表但无 `alembic_version` 表，alembic 会直接执行 0001 migration；`ADD COLUMN IF NOT EXISTS` 保证幂等。
- **migration 执行时机**：`alembic upgrade head` 幂等但不是普通服务启动职责。本 feature 采用 release step 运行，避免迁移失败导致旧服务无意下线，也避免未来多副本同时迁移。
- **`get_by_id` / `update_topic_fields` RETURNING 漏字段**：若忘记补 `revisit_of` / `mother_theme`，字段写入成功但读出缺失。tasks 阶段需明确列为验收点。
- **threshold vs bucket 边界**：文档需明确说明两者独立，避免下游误以为 threshold=0.85 时 weak/soft 不存在是 bug。

---

## Verification Strategy

1. **Migration**：`alembic upgrade head` 后，`SELECT column_name FROM information_schema.columns WHERE table_schema='hermes' AND table_name='topics'` 能看到 `revisit_of` 和 `mother_theme`；索引通过 `\d hermes.topics` 确认；`UPDATE hermes.topics SET revisit_of = id` 被 `chk_topics_revisit_of_not_self` 拒绝。
2. **bucket 分档**：在 PG 写入覆盖四档的测试数据，调用 `find_similar_topics(threshold=0.5)`，验证每条的 `bucket` 与预期一致（对应 spec US1-1 ~ US1-4）。
3. **revisit_of 链路**：写入 U0→U1→U2 链，调用 `list_revisit_chain(U2)` 返回三条倒序结果；写入环路 A↔B，验证 `truncated=true`。
4. **health capabilities**：调用 `health()` 验证 `version="0.2.6"` 且三个 capabilities 均为 true。
5. **向后兼容**：旧客户端只读 `similarity` 字段，新响应新增字段不影响其解析（NFR-003）。

---

## Stage Readiness

- 是否需要 `data-model.md`：**不需要**；新增两个 NULL 字段，无状态机/关系图，plan.md 已覆盖完整。
- 下一步建议：`tasks`（方案稳定，无架构歧义，可拆任务）
- 阻塞项：无

---

## Design Artifacts

| 产物 | 是否需要 | 说明 |
|---|---|---|
| plan.md | 必须 | 当前文档 |
| data-model.md | 不需要 | 变更简单，plan.md 已覆盖 |
| tasks.md | 后续阶段生成 | 由 `tasks` 阶段产出 |
| acceptance.md | 后续阶段生成 | verify 阶段产出 |

---

## Sources

| 决策 | 来源 | 备注 |
|---|---|---|
| alembic async 支持 | UNVERIFIED | alembic 1.12+ 支持 async，但本方案用 psycopg2 同步驱动规避依赖 |
| PG ADD COLUMN NULL 在线性 | UNVERIFIED | PG 官方文档确认 NULL 列无需 table rewrite |
| Alembic `upgrade head` 幂等语义 | VERIFIED | 官方文档说明会基于当前 revision 应用待执行 migration |
