# Tasks: hermes-db topic bucket & revisit_of

**Feature**: `hermes-db-topic-bucket-revisit`  
**Spec**: [spec.md](spec.md)  
**Plan**: [plan.md](plan.md)  
**Status**: Ready for implement

---

## 执行原则

- 先完成 schema / dependency / image 资产，再改 tool 契约，最后做集成验证。
- `alembic upgrade head` 是发布步骤，不写入普通服务 `ENTRYPOINT`。
- `revisit_of` 的数据完整性同时靠工具层校验与 DB `CHECK` 兜底。
- bucket 阈值只从 server config 读取，客户端不再重复维护阈值。

---

## Phase 1: Migration 与发布资产

- [x] T001 [FR-001, FR-011, NFR-001] 在 `packages/hermes-db` 新增 Alembic 资产：`alembic.ini`、`migrations/env.py`、`migrations/script.py.mako`、`migrations/versions/0001_add_revisit_of_mother_theme.py`。
  - 验证：`alembic upgrade head` 能读取 `PG_DSN` 并连接目标 PG。

- [x] T002 [FR-001, US2-4] 在 migration 中为 `hermes.topics` 新增 `revisit_of`、`mother_theme`、`idx_topics_revisit_of`、`chk_topics_revisit_of_not_self`。
  - 验证：`revisit_of`/`mother_theme` 列存在，索引存在，`UPDATE hermes.topics SET revisit_of = id` 被拒绝。

- [x] T003 [FR-011] 更新 `pyproject.toml`：版本升到 `0.2.5`，新增 `alembic>=1.13` 与 `psycopg2-binary>=2.9`。
  - 验证：`uv sync` 后 `uv run alembic --version` 可用。

- [x] T004 [FR-011, NFR-001] 更新 `Dockerfile`：runtime 镜像复制 `alembic.ini` 与 `migrations/`，保持 `ENTRYPOINT ["hermes-db-mcp"]`。
  - 验证：构建镜像后可用同一镜像通过 `--entrypoint alembic ... upgrade head` 执行 migration；普通服务启动不自动迁移。

---

## Phase 2: 契约与数据字段传播

- [x] T005 [FR-004, US1] 在 `config.py` 增加 `bucket_hard_threshold=0.95`、`bucket_soft_threshold=0.80`、`bucket_revisit_days=90`、`version="0.2.5"`。
  - 验证：环境变量可覆盖阈值，默认值与 spec 一致。

- [x] T006 [FR-006, FR-010, US2-3, US2-4, US2-5] 更新 `contracts.py`：`EDITABLE_TOPIC_FIELDS` 和 `CLEARABLE_TOPIC_FIELDS` 增加 `revisit_of`、`mother_theme`；错误码增加 `invalid_revisit_of_self`、`revisit_target_not_found`；新增 revisit chain TypedDict。
  - 验证：非法字段仍被拒绝，新字段可更新/清空。

- [x] T007 [FR-005, FR-006, US2-1, US2-3] 更新 `topic_repo.insert_topic`、`get_by_id`、`update_topic_fields RETURNING`，保证 `revisit_of` 与 `mother_theme` 写入后能被读取和缓存。
  - 验证：`create_topic`/`update_topic` 后 `get_topic` 返回两个新字段。

- [x] T008 [US2-1, US2-3] 补充缓存序列化测试，确认 `serialize_topic_row()` 不丢失 `revisit_of` 与 `mother_theme`。
  - 验证：缓存字典包含新字段，UUID/datetime 序列化保持兼容。

---

## Phase 3: bucket 分档

- [x] T009 [FR-002, FR-003, FR-004, US1-1~US1-7, NFR-002] 在 `topic_repo.py` 增加可单测纯函数 `_compute_bucket(similarity, created_at, now, settings)`，返回 `bucket` 与 `age_days`。
  - 验证：覆盖 hard、soft、revisit、weak、`created_at=None`、90 天边界、阈值等于 0.80/0.95。

- [x] T010 [FR-002, US1] 更新 `topic_repo.find_similar`，对现有 SQL 返回行追加 `bucket` 与 `age_days`，不增加 DB 往返。
  - 验证：`threshold > 0.80` 时 weak 不出现但不报错；published 超过 3 个月仍按现有 SQL 排除。

- [x] T011 [FR-002, NFR-003] 更新 `tools/topics.py::find_similar_topics` 序列化逻辑，保留旧字段 `similarity`，新增字段以向后兼容方式返回。
  - 验证：旧客户端只读取 `similarity` 不受影响。

---

## Phase 4: revisit_of 写入与链路查询

- [x] T012 [FR-005, FR-010, US2-1, US2-5] 更新 `create_topic`：新增可选参数 `revisit_of`、`mother_theme`；写入前校验 `revisit_of` 目标存在。
  - 验证：不存在目标返回 `revisit_target_not_found`，不会写库。

- [x] T013 [FR-006, FR-010, US2-3, US2-4, US2-5] 更新 `update_topic`：当 `revisit_of` 不为 None 时校验 `revisit_of != id` 且目标存在。
  - 验证：自引用返回 `invalid_revisit_of_self`；不存在目标返回 `revisit_target_not_found`；合法更新返回 `updated_fields=["revisit_of"]`。

- [x] T014 [FR-007, FR-008, US2-2, US2-7, US2-8] 在 `topic_repo.py` 新增 `get_revisit_chain(pool, topic_id, max_depth=20)`，按 `revisit_of` 追溯祖先链并用 visited set 防环。
  - 验证：U0 ← U1 ← U2 从 U2 查询返回 `[U2, U1, U0]`；环路和 max_depth 截断返回 `truncated=true`。

- [x] T015 [FR-007, FR-008, US2-2] 在 `tools/topics.py` 注册 `list_revisit_chain(topic_id, max_depth=20)`。
  - 验证：工具列表包含 `list_revisit_chain`；返回项包含 id/title/status/created_at/published_url。

---

## Phase 5: health capabilities 与发布验证

- [x] T016 [FR-009, US3-1, US3-2] 更新 `tools/health.py`，返回 `version="0.2.5"`、`schema_revision` 与 schema-aware `capabilities.topic_bucket/topic_revisit_of/list_revisit_chain`。
  - 验证：旧版本缺失 capabilities 时，下游可等同全部 false；代码已升级但 DB 未迁移时 schema-dependent capabilities 返回 false。

- [x] T017 [Producer-Consumer Matrix, artifact-handoff] 在 hermes-db README 或部署文档补充本 feature 的 release migration 命令与下游探活契约。
  - 验证：文档包含 `docker compose run --rm --entrypoint alembic hermes-db-mcp upgrade head` 和 capabilities 键名。

- [x] T018 [Verification] 扩展/新增测试覆盖 migration、bucket、revisit_of 校验、list_revisit_chain、health capabilities。
  - 验证：`uv run pytest -q` 通过。

- [x] T019a [Release Gate, FR-012] 更新平台部署清单、resolver、workflow 与 NAS deploy 脚本：声明 migration entrypoint/command，启动后执行 MCP `health` smoke，校验必要 capabilities。
  - 验证：release 脚本从 `deploy/mcp-services.json` 读取 migration/smoke 配置；deploy 不再只以 container-running 作为健康标准。

- [x] T019b [MCP Hardening] 为 HTTP 401 补 `WWW-Authenticate`，补齐 inspiration 工具 annotations，收敛常用错误到 `ToolError` helper。
  - 验证：middleware、inspiration、contract 单测覆盖新增行为。

- [ ] T019 [Release Evidence, FR-011] 在目标环境执行 release migration 并启动 0.2.5 服务。
  - 验证：migration 成功；`health().version >= "0.2.5"`；三个 capabilities 为 true；schema 与 CHECK 约束存在。

---

## 依赖与顺序

1. T001-T004 是基础设施前置；未完成前不要启动业务字段实现。
2. T005-T008 建立 server config、字段白名单与读写传播。
3. T009-T011 可在 T005 后实现，但最终依赖 T007 的字段返回测试一起收口。
4. T012-T015 依赖 T006-T007 和 T002 的 DB 约束。
5. T016-T019 最后执行，用于 handoff 与发布证据闭环。

---

## 覆盖检查

| 场景 / 需求 | 对应任务 |
|-------------|----------|
| US1-1 ~ US1-4 bucket 四档 | T005, T009, T010, T011, T018 |
| US1-5 threshold > 0.80 | T009, T010, T018 |
| US1-6 published 3 个月过滤 | T010, T018 |
| US1-7 created_at null | T009, T018 |
| US2-1 create_topic 写 revisit_of | T007, T012, T018 |
| US2-2 list_revisit_chain | T014, T015, T018 |
| US2-3 update_topic 补 revisit_of | T006, T007, T013, T018 |
| US2-4 自引用拒绝 | T002, T013, T018, T019 |
| US2-5 目标不存在 | T012, T013, T018 |
| US2-7 环路截断 | T014, T018 |
| US3 health capabilities | T016, T019a, T019 |
| FR-011 release migration | T001, T003, T004, T017, T019a, T019 |
| FR-012 deploy smoke gate | T019a, T019 |

| 架构决策 / 质量属性 | 对应任务 | 验证任务 |
|----------------------|----------|----------|
| ADR-001/002 Alembic + psycopg2，同一镜像显式迁移 | T001, T003, T004, T017 | T019 |
| ADR-003 Python 层 bucket 计算 | T009, T010 | T018 |
| ADR-004 mother_theme 暂不建索引 | T002 | T019 |
| ADR-005 capabilities 平铺下划线且 schema-aware | T016 | T019a, T019 |
| ADR-006 list_revisit_chain 仅反向 | T014, T015 | T018 |
| 一致性：bucket 阈值唯一来源 server config | T005, T009, T010 | T018 |
| 数据完整性：FK + CHECK + 工具层校验 + 深度上限 | T002, T013, T014 | T018, T019 |
| 向后兼容：旧客户端不读新字段仍可用 | T011 | T018 |

---

## Stage Readiness

- 下一步建议：进入 `execute-plan`，按 Phase 1 → Phase 5 顺序实现。
- 任务边界：已具备文件范围、依赖顺序和验证方式。
- 阻塞项：无。
