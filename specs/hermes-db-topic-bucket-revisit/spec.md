# Feature Specification: hermes-db topic bucket & revisit_of

**Workspace**: `hermes-db-topic-bucket-revisit`
**Created**: 2026-06-01
**Status**: Released
**Input**: 用户描述: "把公众号选题 skill 里的『三档去重 + revisit_of 同母题换角度』口径从 skill 文档层固化到 hermes-db；当前 find_similar_topics 只返回 similarity，没有 bucket 分档，也没有 revisit_of 字段记录同母题换角度的迭代链路。"

> 本 feature 是上游能力建设：完成后供同仓 wechat-agent feature `wechat-topic-radar-online` 消费。下游 feature 启动前会通过 health/能力探活判断本 feature 是否已部署生效。

---

## Feature Traits *(LM 自动检测，用户可 override)*

| Trait | 是否命中 | 依据 |
|---|:---:|---|
| `multi-stage-workflow` | ❌ | 本 feature 仅升级 DB schema 与 MCP tool 契约，不涉及多阶段编排 |
| `external-side-effects` | ✅ | 会写 PG schema migration、影响 Redis 缓存 key 结构、改变 MCP tool 响应字段 |
| `artifact-handoff` | ✅ | bucket 字段与 revisit_of 是给下游 wechat-agent 的契约产物，被另一个 feature 消费 |
| `user-visible-output` | ❌ | 不交付 UI/文档/通知；仅交付 MCP 工具结构化结果 |
| `prior-closure-failure` | ✅ | 三档去重口径以前散落在 `.hermes/skills/.../shared-topic-rules.md` 和 `_shared/dedupe-rules.md`，从未落地到 server 端，导致多个 agent 各自实现一份阈值常量，存在不一致风险 |

**结论**: 命中 `external-side-effects` + `artifact-handoff` + `prior-closure-failure`，下游需启用 Producer-Consumer Matrix（plan 阶段明确 bucket 字段契约）、Evidence Gate（verify 阶段必须证明 schema 已迁移且 tool 返回新字段）、三维 Verdict（closeout 检查 wechat-agent 是否实际开始消费 bucket，避免 schema 改完但调用方还在用本地常量）。

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 三档去重 bucket 由 server 返回 (Priority: P1)

作为使用 hermes-db MCP 的下游 agent（wechat-agent / skill / 第三方），我希望 `find_similar_topics` 直接告诉我每条相似项落在哪一档（hard / soft / revisit / weak），以便我不需要在客户端重复实现"similarity 阈值 + 时间窗口"判定。

**Why this priority**: 当前 wechat-agent 的 `topic-service.ts:19-20` 和 `topic-radar-service.ts:32-33` 硬编码了 0.85/0.95 阈值，与 skill 层 `_shared/dedupe-rules.md` 的 0.80/0.95+90 天口径不一致；任何调用方独立维护阈值都会偏离真相源。

**Acceptance Scenarios**:

1. **[US1-1] 高相似命中返回 hard bucket**
   **Given** 账号 `micro-rain-spring` 已存在选题 `T_OLD`（30 天前创建，draft 状态）
   **When** 调用 `find_similar_topics(text=与 T_OLD 标题几乎一致, account=micro-rain-spring, threshold=0.5, limit=5)`
   **Then** 返回数组中包含 T_OLD，其 `bucket="hard"`、`similarity≥0.95`、`age_days≈30`

2. **[US1-2] 90 天内中等相似返回 soft bucket**
   **Given** 账号 `micro-rain-spring` 存在 60 天前创建的选题 T_MID，相似度落在 [0.80, 0.95)
   **When** 同上调用
   **Then** 返回项 `bucket="soft"`，调用方据此应警告但不立即拒绝

3. **[US1-3] 90 天前同母题返回 revisit bucket**
   **Given** 账号 `micro-rain-spring` 存在 120 天前创建的选题 T_OLDER，相似度落在 [0.80, 0.95)
   **When** 同上调用
   **Then** 返回项 `bucket="revisit"`，调用方据此可以新建一条 `revisit_of=T_OLDER.id` 的新选题

4. **[US1-4] 低相似返回 weak bucket（仍在数组内供调用方决策）**
   **Given** 账号存在 similarity 在 [threshold, 0.80) 的选题
   **When** 同上调用
   **Then** 返回项 `bucket="weak"`

**Edge Cases**:

- **[US1-5]** `threshold` 大于 0.80 时，weak bucket 自然不会出现，不视为错误
- **[US1-6]** `published` 状态选题超过 3 个月仍按现有 SQL 过滤逻辑排除，不进入 bucket 判定
- **[US1-7]** 没有 `created_at`（极端异常数据）→ `age_days=null`、bucket 退化为按 similarity 单独判定（hard / soft / weak，无 revisit）

---

### User Story 2 - 同母题换角度的迭代链路 (Priority: P1)

作为运营/agent，我希望同母题（90 天前命中过）的新选题能在 server 上明确标记为 `revisit_of=<旧 topic id>`，并能反向查询一条母题的全部迭代版本，以便复盘"这个母题我们换过几次角度，每次发布表现如何"。

**Why this priority**: 没有持久化的链路，"换角度复用旧母题"就等同于"复制粘贴标题"，无法回答"上一次写这个母题时切口是什么、读者反馈如何"。

**Acceptance Scenarios**:

1. **[US2-1] 创建时显式带 revisit_of**
   **Given** 已存在选题 T_OLDER（id=U1，120 天前）
   **When** 调用 `create_topic(title=新角度标题, account=..., revisit_of=U1, mother_theme="拖延-早晨场景")`
   **Then** 新建选题 T_NEW 返回 id=U2，且后续 `get_topic(U2)` 可读到 `revisit_of=U1`、`mother_theme="拖延-早晨场景"`

2. **[US2-2] 追溯母题迭代链**
   **Given** 存在链 U0 ← U1 ← U2（U1.revisit_of=U0，U2.revisit_of=U1）
   **When** 调用 `list_revisit_chain(topic_id=U2)`
   **Then** 返回按时间倒序的数组 `[{id:U2,...},{id:U1,...},{id:U0,...}]`，每项含 id/title/status/created_at/published_url

3. **[US2-3] 更新已有选题补充 revisit_of**
   **Given** 已存在选题 T_NEW，当时未填 revisit_of
   **When** 调用 `update_topic(id=T_NEW, revisit_of=U1)`
   **Then** 返回 `updated_fields=["revisit_of"]`，再次读取能看到 revisit_of=U1

**Edge Cases**:

- **[US2-4] 自引用**：`revisit_of` 不允许指向自己 → 返回 `error: invalid_revisit_of_self`
- **[US2-5] 不存在的 revisit_of**：指向不存在的 topic id → 返回 `error: revisit_target_not_found`
- **[US2-6] 跨账号 revisit**：当前不限制跨账号引用（同一个母题可能被多个账号写过），但 `list_revisit_chain` 不做跨账号过滤
- **[US2-7] 链路成环**：A.revisit_of=B、B.revisit_of=A → `list_revisit_chain` 必须有循环保护，最多遍历 max_depth=20 后截断并在响应中标记 `truncated=true`
- **[US2-8] 删除被引用的旧选题**：`ON DELETE SET NULL` 保证链断开但新选题不丢失，`list_revisit_chain` 遇到 null 自然终止

---

### User Story 3 - 调用方能探活本 feature 是否已部署 (Priority: P1)

作为下游 wechat-agent 启动逻辑，我希望在开始消费 bucket 之前能用一个轻量调用确认 hermes-db 已部署本 feature，否则降级到本地阈值兜底（沿用旧 0.85/0.95 常量），不要让上游因 server 版本不一致而崩溃。

**Why this priority**: 用户明确要求"本项目 feature 开始实施前检测下 hermes-db 这个 mcp 的功能是否已经完备"。如果没有探活信号，下游只能靠 try/catch 字段缺失，体验差。

**Acceptance Scenarios**:

1. **[US3-1] health 返回能力清单**
   **Given** hermes-db 已部署本 feature
   **When** 调用 `health()`
   **Then** 响应包含 `capabilities: { topic_bucket: true, topic_revisit_of: true, list_revisit_chain: true }`（或同等结构），版本号 `version` 字段 ≥ 本 feature 发布版本，且 `schema_revision` 能反映 Alembic 当前 revision

2. **[US3-2] 未升级时 capabilities 缺失对应键**
   **Given** hermes-db 仍为旧版本
   **When** 调用 `health()`
   **Then** `capabilities` 中相应键为 `false` 或缺失，下游据此降级；如果代码已升级但数据库 migration 未执行，相关 schema-dependent capability 必须返回 `false`

**Edge Cases**:

- **[US3-3]** capabilities 字段为本次新增，旧版本响应中可能整体缺失 `capabilities` 字段 → 下游应将"缺失"等同于"全部 false"

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `hermes.topics` 表必须新增字段 `revisit_of UUID NULL REFERENCES hermes.topics(id) ON DELETE SET NULL` 和 `mother_theme TEXT NULL`，并对 `revisit_of` 建索引；`revisit_of` 必须通过 DB 约束或等效校验禁止指向自身
- **FR-002**: `find_similar_topics` 工具响应中每项必须新增 `bucket: "hard" | "soft" | "revisit" | "weak"` 字段和 `age_days: int | null`
- **FR-003**: bucket 判定规则必须为：`hard` if `similarity ≥ 0.95`；`soft` if `0.80 ≤ similarity < 0.95 AND age_days ≤ 90`；`revisit` if `0.80 ≤ similarity < 0.95 AND age_days > 90`；`weak` if `similarity < 0.80`
- **FR-004**: bucket 阈值（0.95 / 0.80 / 90 天）必须可通过 server 配置项覆盖（环境变量或 config 文件），默认值与本 spec 一致
- **FR-005**: `create_topic` 工具必须新增可选参数 `revisit_of: UUID | None` 和 `mother_theme: str | None`，写入对应字段
- **FR-006**: `update_topic` 的可编辑字段白名单（`EDITABLE_TOPIC_FIELDS`）必须包含 `revisit_of` 和 `mother_theme`
- **FR-007**: 必须新增 MCP 工具 `list_revisit_chain(topic_id: UUID, max_depth: int = 20)`，沿 `revisit_of` 反向遍历，返回数组（包含起点本身）
- **FR-008**: `list_revisit_chain` 必须有循环保护，遇到环路时截断并返回 `truncated: true`
- **FR-009**: `health` 工具响应必须新增 `capabilities` 对象，至少包含 `topic_bucket`、`topic_revisit_of`、`list_revisit_chain` 三个布尔键；这些 capability 必须反映当前 DB schema，而不是只反映代码版本
- **FR-010**: `create_topic` 和 `update_topic` 当 `revisit_of` 指向不存在 / 等于自身时必须返回结构化错误，不允许写入异常数据
- **FR-011**: DB migration 必须作为发布步骤显式执行（例如 `alembic upgrade head`），不默认绑定到普通服务 `ENTRYPOINT`；镜像必须包含执行 migration 所需的 `alembic.ini` 与 `migrations/`
- **FR-012**: 发布流程必须在启动新版服务前执行声明式 migration，并在启动后通过 MCP `health` smoke 校验 PG 可用、schema revision 与必要 capabilities

### Non-Functional Requirements

- **NFR-001**: schema migration 必须可在线执行（`ADD COLUMN NULL` 无需停机）；现有数据 revisit_of/mother_theme 默认 null；migration 失败不得让旧版本运行态被无意替换
- **NFR-002**: `find_similar_topics` 新增 bucket 计算不得使单次查询延迟 P95 增加超过 10ms（bucket 是纯 CPU 字段计算，不增 SQL 往返）
- **NFR-003**: 向后兼容：未升级的旧客户端（不读 bucket 字段）必须仍能正常解析响应；bucket 是新增字段，不替换 similarity

### Quality Attributes

| 属性 | 目标 | 为什么重要 | 验收 / 证据 | 是否阻塞 plan |
|---|---|---|---|---|
| 一致性 | bucket 阈值唯一来源是 server config | 多客户端阈值各自维护是当前 closure failure 的根因 | wechat-agent + 任意第二个客户端拉到相同 bucket 结果 | 是 |
| 可演进性 | bucket 算法可在不破坏 API 的前提下调整 | 阈值是经验值，未来可能要调到 0.82/85/120d | 调整 server config 后 tool 响应自动反映新结果，无需客户端发版 | 是 |
| 可观测性 | health.capabilities 是 schema-aware 能力信号 | 下游 gate 决定是否走新流程，不能被未迁移 DB 误导 | wechat-agent 启动时调用 health，能从响应中读取 capabilities；旧版本缺失或未迁移视为 false | 否 |
| 数据完整性 | revisit_of 引用链不能产生环路或无效引用 | 环路会让 list_revisit_chain 死循环 | FK 约束 + 自引用检查 + 遍历深度上限 | 是 |

### Key Entities

- **Topic（扩展）**: 新增 `revisit_of: UUID | null`（FK 自引用）和 `mother_theme: str | null`
- **SimilarTopic（响应）**: 新增 `bucket: enum`、`age_days: int | null`
- **Capabilities（响应）**: `{ topic_bucket: bool, topic_revisit_of: bool, list_revisit_chain: bool, ... }`

---

## Out of Scope

- 不做"母题自动聚类"：`mother_theme` 是手动 / 调用方传入的字符串，server 不做语义聚类
- 不做选题家族的复合查询（如"按 mother_theme 统计发布率"），下游有需要时再开 feature
- 不做 bucket 触发的自动写盘动作（拒绝 / 警告 / 入库都是调用方决策，server 只给信号）
- 不调整 `published` 状态的 3 个月窗口逻辑（沿用现有 SQL）

---

## Unclear Questions

- **UQ-1**：`mother_theme` 是否需要建索引？短期看用于人工标注 + revisit 链上下文，未必查询频繁。建议 plan 阶段决定（默认不建，DDL 里预留 comment）
- **UQ-2**：health.capabilities 的键名是否要带 namespace（如 `topic.bucket` vs `topic_bucket`）？参考现有 health 结构在 plan 阶段对齐
- **UQ-3**：`list_revisit_chain` 是否同时支持正向遍历（找子代）？当前 spec 只要求反向。如未来需要可单开

---

## Stage Readiness

- 下一步建议：`plan`（无重大歧义，UQ 都是局部决策可在 plan 阶段解决）
- 阻塞项：无
- 下游依赖：完成后通知 `wechat-topic-radar-online`（agents 仓）feature owner，其 implement 阶段开始前需调用 `health()` 确认 capabilities 全部为 true
