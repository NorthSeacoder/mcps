# Feature Specification: MCP Transport Compatibility

**Workspace**: `mcp-transport-compatibility`  
**Created**: 2026-05-28  
**Status**: Draft  
**Input**: 用户描述: "如果能接受 mcp 这边进行优化,是否可以保证 codex 和claude 都能连上呢? 先评估迁移到 mcps monorepo 后功能是否有变化，然后在该项目下继续填写这个 feature"

---

## Migration Assessment

`hermes-db-mcp` 已迁入 `mcps` monorepo，当前目标工作区应以 `mcps/packages/hermes-db` 为准。

只读对比结论：

- `packages/hermes-db/src` 与独立仓 `src` 功能源码一致，仅存在 `__pycache__` 差异。
- `packages/hermes-db/tests` 与独立仓 `tests` 一致，仅存在 `__pycache__` 差异。
- `pyproject.toml`、`Dockerfile`、服务目录内 `docker-compose.yml` 与独立仓一致。
- `packages/hermes-db/README.md` 只比独立仓多了迁入 `mcps` 平台仓的说明。
- `deploy/services/hermes-db.yml` 是 monorepo 新增的平台层 NAS compose 描述，不改变 MCP tool 业务能力。

因此：迁移后 hermes-db 的工具契约、源码入口、transport 现状没有实质变化；Codex/Claude Code 连接兼容问题也原样存在，应在 `mcps/packages/hermes-db` 内继续推进。

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Codex can connect via Streamable HTTP (Priority: P1)

作为 Codex 用户，我希望 `packages/hermes-db` 暴露的 `/mcp` endpoint 能被 Codex 的 Streamable HTTP MCP client 成功初始化，以便在 Codex 中直接使用 `health`、topic、inspiration 等工具。

**Why this priority**: 当前阻塞点是 Codex 启动时报 `Unexpected content type: missing-content-type; body:`，导致整个 `hermes-db` MCP 不可用。

**Acceptance Scenarios**:

1. **[US1-1] Codex initialize succeeds**  
   **Given** hermes-db-mcp 已通过 `mcps` 构建/部署且网络可达，Codex 配置 `type = "streamable-http"`、`url = "http://<host>:<port>/mcp"`、携带有效 bearer token  
   **When** Codex 启动并向 `/mcp` 发送 MCP initialize 请求  
   **Then** initialize 必须成功，Codex 不应报告 `MCP startup incomplete` 或 `Unexpected content type`

2. **[US1-2] Codex can list and call tools**  
   **Given** Codex 已完成 MCP initialize  
   **When** Codex 请求工具列表并调用 `health`  
   **Then** 工具列表必须包含现有 hermes-db tools，`health` 必须返回结构化状态

**Edge Cases**:

- **[US1-3]** 当 Codex 发送的 `Accept` header 与 Python MCP SDK 默认期望不完全一致时，server 必须仍能返回符合 MCP Streamable HTTP 语义的响应，或返回带 `Content-Type` 的明确 JSON 错误。
- **[US1-4]** 当 token 缺失或错误时，server 必须返回 `401`，并带 `Content-Type: application/json` 与可读 JSON body，不得返回空 body 或缺失 content type。

### User Story 2 - Claude Code remains compatible (Priority: P1)

作为 Claude Code 用户，我希望现有可用的 hermes-db-mcp 配置在优化后继续可用，以便服务端修复 Codex 兼容性时不破坏已有 Claude Code workflow。

**Why this priority**: 当前 Claude Code 连接正常，任何服务端改动都必须避免回归。

**Acceptance Scenarios**:

1. **[US2-1] Claude Code Streamable HTTP still works**  
   **Given** Claude Code 配置 `type: "streamable-http"`、`url: "http://<host>:<port>/mcp"`、携带有效 Authorization header  
   **When** Claude Code 启动 MCP client  
   **Then** initialize、tools/list、`health` 调用必须保持成功

2. **[US2-2] Existing tool contracts remain unchanged**  
   **Given** Claude Code 或其他客户端已依赖现有 tool 名称与参数  
   **When** 调用 `create_topic`、`find_similar_topics`、`update_topic_status`、`list_topics`、`get_topic`、inspiration tools  
   **Then** tool 名称、入参、返回结构不得因 transport 兼容改动而改变

**Edge Cases**:

- **[US2-3]** 如果 Claude Code 发送 `headers.Authorization` 或 ccswitch 生成的等价 header，server 必须按标准 HTTP header 处理，不依赖客户端配置字段名。
- **[US2-4]** 如果客户端使用 SSE 旧配置，server 应有明确支持或明确不支持的行为，不得静默返回难以诊断的空响应。

### User Story 3 - ccswitch can manage client-specific config without service hacks (Priority: P2)

作为维护者，我希望 ccswitch 只负责按客户端 schema 生成配置，而 hermes-db-mcp 自己负责 HTTP transport 兼容，以便后续 MCP 服务可以复用同一配置管理方式。

**Why this priority**: `mcps` 的目标是统一管理多个 MCP 服务，不能为单个服务在 ccswitch 层堆过多特殊逻辑。

**Acceptance Scenarios**:

1. **[US3-1] Codex config is documented**  
   **Given** 维护者需要通过 ccswitch 输出 Codex 配置  
   **When** 查看 `packages/hermes-db` 或平台文档  
   **Then** 文档必须说明 Codex 使用 `http_headers` 或 `bearer_token_env_var`

2. **[US3-2] Claude Code config is documented**  
   **Given** 维护者需要通过 ccswitch 输出 Claude Code 配置  
   **When** 查看 `packages/hermes-db` 或平台文档  
   **Then** 文档必须说明 Claude Code 使用 `headers`，并可同时保留 `http_headers` 作为兼容字段

**Edge Cases**:

- **[US3-3]** 如果 ccswitch 暂不支持 env token 模板，文档必须给出静态 bearer header 配置方式，但标记 env token 为推荐方向。

### User Story 4 - Operators can diagnose transport failures (Priority: P2)

作为维护者，我希望 hermes-db-mcp 在认证、路由、content negotiation 或 MCP 初始化失败时返回可诊断结果，以便快速判断是配置、网络、token 还是协议协商问题。

**Why this priority**: 当前 Codex 错误信息指向 `missing-content-type`，无法直接定位真实失败原因。

**Acceptance Scenarios**:

1. **[US4-1] HTTP errors are structured**  
   **Given** 请求命中 `/mcp`、`/sse` 或不存在路径  
   **When** 请求失败  
   **Then** response 必须包含明确 status code、`Content-Type`、短 JSON 或文本 body

2. **[US4-2] README documents client-specific config**  
   **Given** 维护者需要通过 ccswitch 管理 Claude Code 与 Codex 配置  
   **When** 查看项目文档  
   **Then** 文档必须说明 Claude Code 与 Codex 的配置字段差异，以及推荐的 token/env 管理方式

**Edge Cases**:

- **[US4-3]** 对没有 body 的错误响应，必须通过 middleware 或路由层补齐可读错误，避免客户端报错偏离真实原因。

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系统必须支持 Codex 通过 Streamable HTTP `/mcp` endpoint 完成 MCP initialize。
- **FR-002**: 系统必须保持 Claude Code 通过 Streamable HTTP `/mcp` endpoint 的现有连接能力。
- **FR-003**: 系统必须确保所有认证失败响应带有明确 `Content-Type` 与 body。
- **FR-004**: 系统必须确保 `/mcp` 上 content negotiation 失败时返回可诊断响应，不得出现空 body 或缺失 content type。
- **FR-005**: 系统必须保持现有 MCP tools 的名称、参数和返回结构兼容。
- **FR-006**: 系统必须在 `mcps` 文档中区分 Claude Code 与 Codex 的 MCP 配置 schema，尤其是 `headers` 与 `http_headers` / `bearer_token_env_var` 差异。
- **FR-007**: 系统必须提供本地或集成验证方式，覆盖 Codex 风格请求、Claude Code 风格请求、无 token、错误 token、错误 path。
- **FR-008**: 如果继续支持 SSE，系统必须明确 `/sse` 与 `/messages/` 的 endpoint 行为；如果不支持 SSE，则必须在文档中明确退役或非目标。
- **FR-009**: 本 feature 的代码修改范围必须以 `packages/hermes-db` 为主；平台文档修改范围为 `packages/hermes-db/README.md`、`docs/hermes-db-deployment.md` 或相关 `deploy` 文档。

### Non-Functional Requirements

- **NFR-001**: 兼容层不得引入额外数据库、Redis 或 embedding 调用。
- **NFR-002**: transport 兼容改动不得降低认证要求；无有效 token 时不得暴露工具调用能力。
- **NFR-003**: 错误响应应保持短小，避免泄露 token、数据库连接串或内部堆栈。
- **NFR-004**: 线上部署仍应仅暴露在既有网络边界内，不因兼容 Codex 而扩大公网访问面。
- **NFR-005**: `mcps` monorepo 的平台层部署约定不得被单服务特殊配置破坏。

### Quality Attributes

| 属性 | 目标 | 为什么重要 | 验收 / 证据 | 是否阻塞 plan |
|------|------|------------|-------------|----------------|
| 兼容性 | Codex 与 Claude Code 均可连接 `/mcp` | 本 feature 的核心目标 | 两类客户端 initialize + `health` 成功 | 是 |
| 可诊断性 | 401/404/406/500 都有明确 content type 与 body | 避免 `missing-content-type` 类误导错误 | HTTP 探测用例覆盖错误响应 | 是 |
| 安全性 | 保持 bearer token 认证 | MCP 持有 DB 写入能力 | 无 token / 错 token 均失败 | 是 |
| 平台一致性 | ccswitch 只做配置 schema 映射，server 负责协议兼容 | 符合 `mcps` monorepo 的长期管理目标 | 文档记录推荐配置与边界 | 否 |

### Key Entities *(if applicable)*

- **MCP HTTP Endpoint**: hermes-db-mcp 对外暴露的 HTTP transport endpoint，包括 `/mcp` 以及可能保留的 `/sse`、`/messages/`。
- **Client Profile**: 不同 MCP 客户端的配置和请求特征，例如 Codex、Claude Code、curl/诊断脚本。
- **Auth Failure Response**: bearer token 缺失或错误时的标准化错误响应。
- **ccswitch Render Target**: ccswitch 输出给 Codex 或 Claude Code 的客户端配置格式。

---

## Out of Scope *(if applicable)*

- 不新增、删除或改名现有 hermes-db MCP tools。
- 不修改 topic、inspiration、embedding、PG、Redis 的业务逻辑。
- 不把 hermes-db-mcp 改造成通用 SQL MCP。
- 不要求 ccswitch 实现复杂的 hermes-db 专用协议适配；ccswitch 只需按客户端 schema 输出配置。
- 不在本 feature 中迁移数据库 schema。
- 不在本 feature 中完成 NAS 运行态从独立仓到 `mcps` 的最终切换，除非后续用户明确要求。

---

## Unclear Questions *(if applicable)*

- **Q1**: 线上是否必须继续支持 SSE `/sse`，还是只需 Streamable HTTP `/mcp`？建议 plan 阶段根据现有调用方确认。
- **Q2**: Codex 的失败是否完全由 `Accept` negotiation 触发，还是还存在 rmcp 对 response content type 的额外限制？需要在 plan 阶段用最小复现验证。
- **Q3**: ccswitch 是否支持 per-client env token 模板？如果支持，文档应推荐 env；如果不支持，先记录静态 header 配置。
- **Q4**: NAS 当前运行态是否仍来自独立仓镜像/compose？这不阻塞 spec，但会影响实现后验证环境选择。

---

## Stage Readiness

- 下一步建议：`plan`
- 阻塞项（如有）：Q1 会影响是否设计“同时暴露 `/mcp` + `/sse`”还是“只修 `/mcp`”；Q4 会影响最终在独立运行态还是 `mcps` 运行态验证，但不阻塞进入 plan。
