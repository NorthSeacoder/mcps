# Tasks: Hermes DB MCP Platform Revival

**Workspace**: `mcps` | **Date**: 2026-05-27  
**Input**: `specs/hermes-db-mcp-platform-revival/spec.md` + `plan.md`  
**Prerequisites**: spec.md (必须), plan.md (必须)

---

## 执行原则

- 先把平台仓结构和公共约定立住，再迁入服务。
- NAS 私有配置只放本地覆盖文件，不进入公共提交。
- 首期只迁源码与部署流程，不把现有 NAS 运行态切换绑定到同一批任务里。
- 任务按依赖顺序组织，后续可以直接进入实现。

---

## Phase 1: 平台仓复活

**目标**: 把 `mcps` 从旧模板仓恢复为可维护的平台仓，并更新根级说明。

- [ ] T001 [Platform] 重写根 README 为平台仓说明
  - scope: `README.md`
  - maps_to: FR-001 / FR-002 / FR-008
  - verify: README 能清楚说明 `mcps` 是平台仓、支持多服务、后续接入方式和当前范围

- [ ] T002 [Platform] 规范根工作区与平台级脚本
  - scope: `package.json`, `pnpm-workspace.yaml`, `turbo.json`, `scripts/create-server.js`
  - maps_to: FR-001 / FR-002 / FR-005
  - verify: 根脚本仍可构建、开发、测试，且新服务创建逻辑不再假设旧模板仓是唯一业务形态

- [ ] T003 [Platform] 固化平台级目录约定
  - scope: `packages/`, `deploy/`, `docs/`, `specs/`
  - maps_to: FR-001 / FR-002 / FR-008
  - verify: 仓库目录能明确区分服务目录、部署约定、文档和规格产物

---

## Phase 2: Hermes DB 迁入

**目标**: 将 `hermes-db` 纳入 `mcps` 的统一管理边界，先覆盖源码、构建和部署描述。

- [ ] T004 [Hermes] 引入 `hermes-db` 服务目录
  - scope: `packages/hermes-db/`
  - maps_to: FR-003 / FR-005
  - verify: `hermes-db` 的源码、Dockerfile、compose/部署说明和服务入口都能在平台仓下定位

- [ ] T005 [Hermes] 对齐服务命名与构建入口
  - scope: `packages/hermes-db/` 内部构建配置与入口脚本
  - maps_to: FR-003 / FR-005
  - verify: 服务构建命令和镜像命名有统一约定，便于后续新增 MCP 复用

- [ ] T006 [Hermes] 更新 `hermes-db` 的平台接入文档
  - scope: `docs/hermes-db-deployment.md`, `packages/hermes-db/README.md`
  - maps_to: FR-003 / FR-007 / FR-008
  - verify: 文档能说明源码位置、构建方式、部署方式以及后续切换边界

---

## Phase 3: 私有配置与部署骨架

**目标**: 建立 NAS 私有配置隔离和统一部署骨架。

- [ ] T007 [Deploy] 建立公共部署目录与模板文件
  - scope: `deploy/`, `deploy/nas.example.env`, `deploy/services/`
  - maps_to: FR-005 / FR-007 / NFR-004
  - verify: 公共仓内有统一的部署说明和示例配置，但不包含私有值

- [ ] T008 [Deploy] 增加 NAS 私有覆盖规则
  - scope: `.gitignore`, `deploy/*.local.*`, `.env.local` 约定
  - maps_to: FR-006 / NFR-002 / NFR-004
  - verify: NAS 专用配置不会被提交，仓库内只保留模板和说明

- [ ] T009 [Deploy] 统一镜像构建与拉取约定
  - scope: `deploy/README.md`, `docs/platform-overview.md`
  - maps_to: FR-005 / NFR-003 / NFR-004
  - verify: 所有 MCP 的公共流程都能通过“构建 -> tag -> push -> NAS pull -> run”描述清楚

---

## Phase 4: 迁移收口与验证

**目标**: 确认迁移后的仓库可持续维护，并保留现有 NAS 运行态的回滚边界。

- [ ] T010 [Migration] 写明 `hermes-db` 首期只迁源码和流程的切换说明
  - scope: `docs/hermes-db-deployment.md`, `docs/platform-overview.md`
  - maps_to: FR-004 / NFR-001
  - verify: 文档明确哪些内容已经迁入 `mcps`，哪些仍保留在原 NAS 运行态

- [ ] T011 [Migration] 补充平台仓使用与新增 MCP 接入说明
  - scope: `docs/platform-overview.md`
  - maps_to: FR-001 / FR-002 / FR-005 / FR-008
  - verify: 新增 MCP 的目录、模板、部署与私有配置规则能被快速复用

- [ ] T012 [Validation] 做一次仓库级完整性检查
  - scope: 全仓
  - maps_to: NFR-001 / NFR-002 / NFR-003 / NFR-004
  - verify: 检查工作区脚本、目录约定、`.gitignore`、部署模板和文档之间没有冲突

---

## 依赖与顺序

- T001-T003 必须先完成，平台仓的根说明和目录约定要先稳定。
- T004-T006 依赖平台仓已复活。
- T007-T009 可以在 T004 之后并行推进，但要和 NAS 私有配置规则保持一致。
- T010-T012 依赖前述所有文档和部署骨架完成。
- 关键路径: T001 → T002 → T003 → T004 → T007 → T008 → T010 → T012

---

## 覆盖检查

| 场景 / 需求 | 对应任务 |
|-------------|----------|
| 复活 mcps 平台仓 | T001, T002, T003 |
| 迁入 hermes-db | T004, T005, T006 |
| NAS 私有配置隔离 | T007, T008 |
| 统一未来 MCP 部署 | T007, T009, T011 |
| 保留现有 NAS 运行态回滚边界 | T010, T012 |

| 架构决策 / 质量属性 | 对应任务 | 验证任务 |
|----------------------|----------|----------|
| ADR-001 平台仓复活 | T001, T002, T003 | T012 |
| ADR-002 先迁源码与流程 | T004, T006, T010 | T012 |
| ADR-003 私有配置隔离 | T007, T008 | T012 |

---

## Notes

- 本次任务清单只覆盖 `mcps` 平台仓复活与 `hermes-db` 迁入的首期边界。
- `content-orchestrator-agent` 不在本 feature 内。
- 后续如果要把某个具体服务纳入平台仓，可直接复用这里的目录和部署约定。

---

## Stage Readiness

- 推荐下一步：`implement`
- 阻塞项（如有）：无
