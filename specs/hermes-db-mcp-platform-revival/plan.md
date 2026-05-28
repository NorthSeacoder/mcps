# Implementation Plan: Hermes DB MCP Platform Revival

**Workspace**: `mcps` | **Date**: 2026-05-27 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/hermes-db-mcp-platform-revival/spec.md`

---

## Summary

把 `mcps` 从旧模板仓恢复为可持续维护的 MCP 平台仓，统一承载多个 MCP 服务的源码、部署脚本和文档，并将 `hermes-db` 的源码与部署流程迁入其中。首期只统一源码与发布/部署规范，不强制切换现有 NAS 运行态；NAS 私有配置与本地覆盖文件继续通过 `.gitignore` 隔离。

---

## Architecture Overview

本次改动的核心是把仓库拆成“平台层 + 服务层 + 本地私有覆盖层”三部分：

```text
mcps/
├── packages/
│   ├── tpl/                  # 统一服务模板
│   ├── weekly/               # 现有示例服务
│   └── hermes-db/            # 迁入的 Hermes DB MCP 服务
├── scripts/                  # 平台级脚手架与部署辅助脚本
├── deploy/                   # 公共部署约定、镜像构建约定
├── docs/                     # 平台文档、NAS 使用说明、服务接入说明
├── specs/                    # 需求、方案、任务、验收文档
└── .gitignore                # 排除 NAS 私有配置与本地覆盖文件
```

数据流和控制流保持简单：

1. 开发者在 `mcps` 中修改服务源码或部署描述。
2. CI / 本地脚本按统一约定构建服务镜像。
3. NAS 只拉取指定服务对应的镜像名。
4. NAS 私有值通过本地覆盖文件提供，不进入公共仓。

`hermes-db` 现有的服务能力不改业务语义，只调整它在平台仓中的组织方式和部署接入方式。

---

## Architecture Reference *(if applicable)*

| 参考模式 / 模板 | 来源 URL | 适配点 | 不适配点 | 当前阶段 |
|-----------------|----------|--------|----------|----------|
| Workspace Monorepo | UNVERIFIED | 统一管理多个 MCP 服务、共享脚本和模板 | 不适合把所有运行态强行合并为单进程 | MVP |
| Service-per-image Deployment | UNVERIFIED | 每个 MCP 独立构建镜像、独立拉取 | 仍需公共部署约定来避免碎片化 | MVP |

---

## Quality Attribute Targets *(if applicable)*

| 属性 | 目标 | 设计影响 | 验证方式 |
|------|------|----------|----------|
| 可演进性 | 后续新增 MCP 时只需替换服务目录和镜像名 | 需要统一模板、脚本和部署文档 | 新增一个最小服务时不改平台核心脚本 |
| 安全性 | NAS 私有信息不进入公共仓 | `.gitignore` + 本地覆盖文件约定 | 仓库审查不出现私有镜像名、密钥和内网地址 |
| 可回滚性 | 首期迁移不破坏既有 NAS 运行态 | 不把运行态切换与源码迁移绑定 | 迁移前后可分别构建与部署 |
| 可维护性 | 平台仓结构清晰，职责分层明确 | `packages/`、`deploy/`、`docs/` 分离 | 目录和 README 能独立说明每层职责 |

---

## Capacity / Scale Notes *(if applicable)*

- **规模假设**: 早期服务数量少，主要是 `hermes-db` + 少量后续 MCP。
- **读写特征**: 平台层读多写少，服务层按各自生命周期发布。
- **失败代价**: 最坏情况是某个服务镜像构建或 NAS 拉取失败；平台仓本身不应导致现有服务数据丢失。

---

## Lightweight ADR *(if applicable)*

| 决策 | 背景 | 候选 | 结论 | 代价 | 来源 |
|------|------|------|------|------|------|
| ADR-001 | 需要统一多个 MCP 的源码与部署规范 | A. 维持散仓；B. 复活 `mcps` 平台仓 | 选 B | 需要整理旧模板仓并补充平台级约定 | UNVERIFIED |
| ADR-002 | 需要隔离 NAS 私有配置 | A. 写进仓库；B. `.gitignore` + 本地覆盖 | 选 B | 本地首启需手工准备覆盖文件 | UNVERIFIED |
| ADR-003 | 需要平滑迁移 `hermes-db` | A. 一次性切 NAS 运行态；B. 先迁源码和流程 | 选 B | 短期会有过渡态，需要明确切换步骤 | UNVERIFIED |

---

## Key Design Decisions

### Decision 1: 复活 `mcps` 为平台仓而不是单服务仓

- **背景**: 现有 `mcps` 只是旧模板集合，不能承载后续多个 MCP 的长期维护。
- **选项**:
  - A: 保持模板仓用途，只新增少量服务
  - B: 升级为平台仓，统一模板、脚本和部署约定
- **结论**: 选 B。后续会持续增加 MCP，统一平台层能显著降低重复成本。
- **影响**: 需要重整目录和文档，但能换来长期一致的工程约定。
- **来源**: UNVERIFIED

### Decision 2: `hermes-db` 首期只迁源码与部署流程

- **背景**: 现有 NAS 运行态已可用，强切会放大风险。
- **选项**:
  - A: 立即连同 NAS 容器、卷、域名一起切换
  - B: 先迁源码、构建和发布，再单独安排运行态切换
- **结论**: 选 B。
- **影响**: 迁移分两步走，短期多一层过渡，但回滚简单。
- **来源**: UNVERIFIED

### Decision 3: NAS 私有配置一律不进公共仓

- **背景**: 后续所有 MCP 都会有本地差异，尤其是 NAS 镜像名、地址和 secret。
- **选项**:
  - A: 在仓库里直接写死
  - B: 用 `.gitignore` 排除本地覆盖文件
- **结论**: 选 B。
- **影响**: 首次部署需要本地准备覆盖文件，但避免泄露和环境漂移。
- **来源**: UNVERIFIED

---

## Module Design

### Module: Platform Workspace

**职责**: 统一管理多个 MCP 服务的根工作区。

**改动概述**: 保留 pnpm workspace / turbo，补齐平台级目录约定和根脚本说明。

**关键接口 / 行为**:

```text
pnpm build
pnpm dev
pnpm test
pnpm new-server
```

**注意事项**:

- 根脚本只提供公共约定，不把服务专属逻辑塞进平台层。
- 旧模板仍可保留，但要变成可复用模板，而不是唯一业务形态。

### Module: Hermes DB Service

**职责**: 承载 `hermes-db` 的源码、构建和部署描述。

**改动概述**: 将服务放入 `packages/hermes-db`，对接统一模板和公共部署脚本。

**关键接口 / 行为**:

```text
服务独立构建镜像
服务独立定义镜像名
服务在 NAS 上按固定方式拉取镜像并启动
```

**注意事项**:

- 首期不要求现有 NAS 容器立刻迁移到新镜像。
- 服务专属配置不要写进平台公共文档正文。

### Module: Deployment Conventions

**职责**: 统一所有 MCP 的镜像构建、推送和 NAS 拉取规则。

**改动概述**: 增加公共部署文档、环境变量模板和本地覆盖文件说明。

**关键接口 / 行为**:

```text
build -> tag -> push -> NAS pull -> run
```

**注意事项**:

- 只允许服务专属差异出现在镜像名、构建上下文和运行参数。
- NAS 私有值必须来自本地文件或环境覆盖。

### Module: Local Private Overlay

**职责**: 保存 NAS 专有配置。

**改动概述**: 添加 `.gitignore` 规则和示例模板文件，确保私有信息不进入开源仓。

**关键接口 / 行为**:

```text
.env.local
deploy/nas.local.yml
deploy/*.local.*
```

**注意事项**:

- 只提交模板，不提交真实私有值。
- 本地覆盖文件格式应尽量保持简单，便于手动维护。

---

## Data Model

本 feature 不引入新的业务实体表，但会引入平台级文件约定：

- 平台级服务目录
- 服务专属镜像名
- NAS 本地覆盖配置

---

## Project Structure

```text
mcps/
├── packages/
│   ├── tpl/
│   ├── weekly/
│   └── hermes-db/
├── deploy/
│   ├── README.md
│   ├── nas.example.env
│   └── services/
├── docs/
│   ├── platform-overview.md
│   └── hermes-db-deployment.md
├── specs/
│   └── hermes-db-mcp-platform-revival/
├── scripts/
└── .gitignore
```

---

## Risks and Tradeoffs

- 旧模板仓升级成平台仓后，目录和脚本会变多，但这是后续持续接 MCP 的前提。
- 迁移分两步走会有过渡期，需要文档清楚写明“源码已迁、运行态待切换”。
- NAS 私有配置不入仓会增加首次部署准备工作，但这是可接受的安全代价。

---

## Evolution Path *(if applicable)*

- **MVP**: 恢复 `mcps` 作为平台仓，迁入 `hermes-db` 的源码与部署规范。
- **成长期**: 后续新增 MCP 时直接复用平台目录、模板和部署骨架。
- **成熟期**: 如果服务数量明显增加，再考虑更细的服务分层、公共库和自动生成器。

---

## Anti-Pattern Check *(if applicable)*

- 是否把成熟期架构套到了 MVP：否。当前只做平台仓恢复和统一部署约定。
- 是否引用了外部模式但没有适配检查：否。这里只把 monorepo / service-per-image 当参考，不强行照搬。
- 是否新增未记录的状态、依赖、缓存、队列或失败模式：否。

---

## Verification Strategy

- 检查 `mcps` 根目录是否恢复为可维护的平台仓结构。
- 检查 `hermes-db` 是否已经进入统一目录、文档和部署约定。
- 检查 `.gitignore` 是否覆盖 NAS 本地配置与私有覆盖文件。
- 检查平台文档能否说明后续新增 MCP 的接入方式。
- 检查迁移方案是否仍保留现有 NAS 运行态可回滚。

---

## Stage Readiness

- 是否需要 `data-model.md`：不需要。本次没有新增业务表或状态机，只涉及仓库结构和部署文件约定。
- 下一步建议：`tasks`
- 阻塞项（如有）：无

---

## Design Artifacts

本次计划涉及的产物：

| 产物 | 是否需要 | 说明 |
|------|---------|------|
| plan.md | 必须 | 主实现计划 |
| data-model.md | 不需要 | 无新增业务实体或状态变化 |
| tasks.md | 后续阶段生成 | 由 `tasks` 阶段产出 |
| acceptance.md | 后续阶段生成 | 用于最终验收结论 |

---

## Notes

- 该计划默认后续所有 MCP 继续采用统一平台仓接入。
- `content-orchestrator-agent` 不纳入本 feature 范围。
- 现有 NAS 运行态切换应作为单独执行步骤安排，不与仓库迁移混做。

---

## Sources

| 决策 | 来源 URL | 备注 |
|------|---------|------|
| 复活 `mcps` 为平台仓 | UNVERIFIED | 基于当前仓库现状与用户确认 |
| `hermes-db` 先迁源码与部署流程 | UNVERIFIED | 基于用户确认的迁移边界 |
| NAS 私有配置隔离 | UNVERIFIED | 基于用户安全约束 |
