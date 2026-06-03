# Feature Specification: hermes-db WeChat Artifact Persistence

**Workspace**: `hermes-db-wechat-artifact-persistence`  
**Created**: 2026-06-03  
**Status**: Ready for Tasks  
**Input**: 用户描述: "agents 仓的 wechat-artifact-persistence 需要 hermes-db 提供 workflow run 和 artifact 持久化能力；在 mcps 仓新建 feature spec，后续在 mcps 目录用 SDD 实现。"

> 本 feature 是 `agents/specs/wechat-artifact-persistence` 的上游能力。完成并部署后，agents 仓的 wechat-agent 才能把 `draft`、`transformed-draft`、`review`、`validation`、`image-prep`、`publish-result` 等产物写入 hermes-db 并按 run/topic/account 查询。

---

## Feature Traits

| Trait | 是否命中 | 依据 |
|---|:---:|---|
| `multi-stage-workflow` | ❌ | hermes-db 本身只提供存储与 MCP tools，不编排公众号 workflow |
| `external-side-effects` | ✅ | 需要新增 PG schema migration、MCP 写入工具和查询工具 |
| `artifact-handoff` | ✅ | 本 feature 交付的 run/artifact tools 会被 agents 仓 wechat-agent 消费 |
| `user-visible-output` | ❌ | 不交付 UI；只交付 MCP 工具结构化结果 |
| `prior-closure-failure` | ✅ | 当前 wechat-agent artifacts 只随响应返回，不持久化，复盘链路无法追溯生成时的正文版本 |

**结论**: 命中 `external-side-effects` + `artifact-handoff` + `prior-closure-failure`。plan 阶段必须明确 schema migration、MCP tool contract、幂等写入、查询默认不返回全文、以及 agents 仓联调 Evidence Gate。

---

## User Scenarios & Testing

### User Story 1 - 持久化 workflow run 主记录 (Priority: P1)

作为 wechat-agent，我希望 hermes-db 能记录每次公众号 workflow run 的生命周期，以便后续按 run/topic/account 串联草稿、发布稿、指标和复盘结果。

**Why this priority**: 没有 run 主记录，artifact、publication ledger、analytics snapshots 无法稳定关联。

**Acceptance Scenarios**:

1. **[US1-1] 创建或更新 run**
   **Given** wechat-agent 调用 `upsert_workflow_run`，传入 `run_id`、`task_id`、`topic_id?`、`account?`、`input_text`、`intent`、`phase`、`current_stage`、`status`、`dry_run`、`metadata`、`started_at`  
   **When** hermes-db 收到请求  
   **Then** 数据库存在一条 `wechat_workflow_runs` 记录，返回 `{ run_id, created, updated_at }`

2. **[US1-2] 完成 run**
   **Given** 已存在 run 记录  
   **When** wechat-agent 调用 `finish_workflow_run`，传入最终 `phase`、`current_stage`、`status`、`summary`、`failure_reason?`、`missing_inputs`、`next_action`、`completed_at`  
   **Then** 原 run 记录被更新，不创建不可关联的新主记录

**Edge Cases**:

- **[US1-3]** 同一个 `run_id` 重试调用 `upsert_workflow_run` 必须幂等，不重复插入。
- **[US1-4]** `dry_run=true` 的 run 也必须保存。
- **[US1-5]** blocked-before-start 的 run 可保存 `phase=blocked`、`current_stage=topic-status`、`failure_reason`。
- **[US1-6]** `topic_id` 为空的临时写作任务仍可按 `run_id` 查询。

### User Story 2 - 持久化关键 workflow artifacts (Priority: P1)

作为 wechat-agent，我希望 hermes-db 能保存每个关键 artifact 的摘要、hash、metadata 和可读取正文，以便后续复盘和人工编辑时找回当时生成的版本。

**Why this priority**: `draft` / `transformed-draft` 当前只在 `WorkflowResponse.artifacts` 中，调用方未保存时就丢失。

**Acceptance Scenarios**:

1. **[US2-1] 保存 draft 全文**
   **Given** wechat-agent 调用 `upsert_workflow_artifact`，传入 `type="draft"`、`name="draft"`、Markdown 正文、`content_hash`、`content_preview`、`metadata`  
   **When** hermes-db 写入成功  
   **Then** `workflow_artifacts` 中存在该 artifact，能通过 `get_workflow_artifact_content(artifact_id)` 读回正文

2. **[US2-2] 保存 transformed-draft 与父子关系**
   **Given** 已保存原始 `draft` artifact  
   **When** 保存 `name="transformed-draft"`，传入 `parent_artifact_id=<draft artifact_id>`  
   **Then** 查询 transformed-draft 时能追溯到原始 draft

3. **[US2-3] 同名 artifact 保留版本**
   **Given** 同一 `run_id`、`stage`、`name` 多次写入不同正文  
   **When** hermes-db upsert artifact  
   **Then** 不覆盖旧版本，按 `version` 保留版本顺序

**Edge Cases**:

- **[US2-4]** 图片二进制不得写入 `content_text`；只保存 manifest、URL 和 metadata。
- **[US2-5]** 超过大小阈值的正文必须支持 `content_ref`，DB 仍保存 preview/hash/size/metadata。
- **[US2-6]** `content_text` 和 `content_ref` 至少有一个存在；否则返回 validation error。
- **[US2-7]** 重复写入同一 artifact id/hash 必须幂等。

### User Story 3 - 查询 artifact 摘要和全文 (Priority: P1)

作为运营者或复盘 agent，我希望能按 `run_id`、`topic_id`、`account`、日期范围和 artifact 类型查询产物摘要，并在需要时读取全文，以便快速定位某篇文章的草稿和发布稿。

**Why this priority**: 后续 publication ledger、analytics ingestion、retrospective topic optimizer 都会从 topic/account/date 维度进入，而不是只知道 run id。

**Acceptance Scenarios**:

1. **[US3-1] 按 run 查询**
   **Given** 某 run 已保存多个 artifacts  
   **When** 调用 `list_workflow_artifacts(run_id=<id>)`  
   **Then** 返回该 run 下所有 artifact 摘要，包含 `artifact_id`、`stage`、`type`、`name`、`version`、`content_hash`、`content_size_bytes`、`content_preview`、`metadata`、`created_at`

2. **[US3-2] 按 topic 查询**
   **Given** 多个 run 绑定同一个 `topic_id`  
   **When** 调用 `list_workflow_artifacts(topic_id=<topic>)`  
   **Then** 返回该 topic 相关的 `draft`、`transformed-draft`、`review`、`validation`、`image-plan`、`publish-result` 摘要

3. **[US3-3] 按账号和日期查询**
   **Given** 多个账号产生 artifacts  
   **When** 调用 `list_workflow_artifacts(account=<alias>, date_from, date_to)`  
   **Then** 只返回对应账号和日期范围内的摘要

4. **[US3-4] 读取全文**
   **Given** 列表返回一个 artifact_id  
   **When** 调用 `get_workflow_artifact_content(artifact_id)`  
   **Then** 返回完整正文或解析后的 `content_ref` 内容

**Edge Cases**:

- **[US3-5]** `list_workflow_artifacts` 默认不得返回 `content_text` 全文。
- **[US3-6]** 查询不存在的 artifact id 返回结构化 `not_found`。
- **[US3-7]** 查询参数至少需要一个过滤条件或强制 limit，避免全表无界扫描。

### User Story 4 - 保持现有 topic tools 和 MCP transport 兼容 (Priority: P2)

作为现有 hermes-db MCP 调用方，我希望新增 workflow artifact tools 时不破坏 topic、inspiration、health 和 transport 行为。

**Why this priority**: wechat-agent 已依赖 `create_topic`、`list_topics`、`update_topic_status`、`publish_topic`；新增能力不能造成现有选题链路回退。

**Acceptance Scenarios**:

1. **[US4-1] 现有工具兼容**
   **Given** 新 migration 和 tools 已合入  
   **When** 调用现有 topic tools  
   **Then** 参数、返回结构和错误语义保持兼容

2. **[US4-2] health 暴露能力**
   **Given** 新表和 tools 可用  
   **When** 调用 `health`  
   **Then** `capabilities` 中能表达 workflow artifact persistence 可用，例如 `workflow_artifacts=true`

**Edge Cases**:

- **[US4-3]** migration 未执行时，新 tools 应返回可诊断 schema error，不应让 MCP server crash。
- **[US4-4]** Codex / Claude Code Streamable HTTP 连接行为不因新增 tools 改变。

---

## Requirements

### Functional Requirements

- **FR-001**: 系统必须新增 `wechat_workflow_runs` 表保存 workflow run 主记录。
- **FR-002**: 系统必须新增 `workflow_artifacts` 表保存 artifact 摘要、hash、metadata、正文或正文引用。
- **FR-003**: 系统必须提供 `upsert_workflow_run` MCP tool。
- **FR-004**: 系统必须提供 `finish_workflow_run` MCP tool。
- **FR-005**: 系统必须提供 `upsert_workflow_artifact` MCP tool。
- **FR-006**: 系统必须提供 `list_workflow_artifacts` MCP tool，默认只返回摘要，不返回全文。
- **FR-007**: 系统必须提供 `get_workflow_artifact_content` MCP tool。
- **FR-008**: artifact 写入必须支持 `run_id`、`task_id`、`topic_id?`、`account?`、`stage`、`type`、`name`、`version`、`parent_artifact_id?`、`content_hash`、`content_size_bytes`、`content_preview`、`metadata`。
- **FR-009**: `draft` 和 `transformed-draft` 必须支持完整 Markdown 读取。
- **FR-010**: `transformed-draft` 必须能通过 `parent_artifact_id` 追溯原始 `draft`。
- **FR-011**: 同一 run 下同名 artifact 多次生成必须保留版本顺序，不得无声覆盖。
- **FR-012**: `health` 必须暴露 workflow artifact persistence capability。
- **FR-013**: 新增 tools 不得删除、改名或破坏现有 topic/inspiration tools。

### Non-Functional Requirements

- **NFR-001**: 所有写入 tool 必须幂等，支持 wechat-agent 重试。
- **NFR-002**: 列表查询必须有索引支持，不得默认全表拉全文。
- **NFR-003**: MCP tool 错误必须结构化，包含 validation/not_found/schema_drift/transport 类别中的可诊断信息。
- **NFR-004**: migration 必须只新增表、索引、约束和 tools，不破坏现有 topic 表。
- **NFR-005**: 正文大小策略必须防止单次 MCP 响应失控。

### Quality Attributes

| 属性 | 目标 | 为什么重要 | 验收 / 证据 | 是否阻塞 plan |
|---|---|---|---|---|
| 持久性 | run/artifact 写入后可跨进程查询 | 复盘和 ledger 依赖历史版本 | migration + repository/tool tests | 是 |
| 幂等性 | 重试不产生不可关联重复记录 | wechat-agent 可能重试 run/stage | upsert 重复调用测试 | 是 |
| 兼容性 | 现有 topic tools 不回退 | 当前 wechat-agent topic 链路依赖 hermes-db | 现有测试套件通过 | 是 |
| 性能 | 列表查摘要，全文按需读 | 草稿可能较大 | list tool 测试不含 content_text | 是 |
| 可诊断性 | schema/tool 错误结构化 | 跨仓联调需要快速定位问题 | schema missing / not_found tests | 否 |

### Key Entities

- **wechat_workflow_runs**: workflow run 主记录，包含 run/task/topic/account/phase/current_stage/status/dry_run/summary/failure。
- **workflow_artifacts**: artifact 记录，包含 run/task/topic/account/stage/type/name/version/hash/content/metadata。
- **artifact parent relation**: `workflow_artifacts.parent_artifact_id`，用于 transformed-draft 追溯 draft。

---

## Out of Scope

- 不实现 wechat-agent 侧调用逻辑；该部分由 `agents/specs/wechat-artifact-persistence` 负责。
- 不采集微信公众平台阅读/分享/收藏指标；该部分属于 `wechat-analytics-ingestion`。
- 不创建 publication ledger；该部分属于 `wechat-publication-ledger`。
- 不实现复盘报告生成或 topic optimizer。
- 不引入通用文件对象存储服务；MVP 只需支持 `content_text` 和可扩展的 `content_ref` 字段。
- 不改变现有 topic 状态机。

---

## Upstream / Downstream Contract

- **上游实现仓**: `/Users/yqg/personal/AI/mcps/packages/hermes-db`
- **下游消费仓**: `/Users/yqg/personal/AI/agents`
- **下游 feature**: `agents/specs/wechat-artifact-persistence`
- **联调顺序**:
  1. hermes-db 完成 migration + MCP tools + health capability。
  2. agents 仓实现 `HermesWorkflowTools` adapter 和 `WorkflowPersistenceService`。
  3. 使用本地或 NAS hermes-db endpoint 做 run/artifact 写入与查询联调。

---

## Unclear Questions

- artifact 正文大小阈值由 hermes-db 统一限制，还是由 wechat-agent 调用前裁决；建议 plan 阶段定一个 MVP 默认值，例如 256KB。
- `content_ref` 的存储后端首期是否只接受外部路径字符串，还是 hermes-db 需要负责读取路径内容；建议首期只存引用，读取失败返回明确错误。
- `artifact_id` 由客户端传入还是服务端生成；建议允许客户端传入稳定 id，服务端缺省生成。

---

## Stage Readiness

- 下一步建议：`plan`
- 阻塞项：无阻塞；上述 unclear questions 属于 plan 阶段设计决策，不阻塞进入 plan。
