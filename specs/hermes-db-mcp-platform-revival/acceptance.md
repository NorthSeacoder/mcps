# Acceptance Record: Hermes DB MCP Platform Revival

**Feature**: hermes-db-mcp-platform-revival  
**Date**: 2026-05-28  
**Verdict**: PASS

---

## Verify 结果

| 检查项 | 结果 | 说明 |
|--------|------|------|
| `pnpm install` | PASS | workspace 解析无误，turbo/tsup/typescript/vitest 就位 |
| `uv sync` (packages/hermes-db) | PASS | 51 包成功构建 hermes-db-mcp 0.1.0 |
| `docker build` | PASS | 多阶段构建成功，镜像 ghcr.io/northseacoder/hermes-db-mcp:verify 生成 |

---

## Closeout Checklist

### 1. 旧逻辑退役

| 项目 | 状态 | 说明 |
|------|------|------|
| 原 hermes-db-mcp 独立仓 | 刻意延后 | spec 明确"首期只迁源码与流程，不切换 NAS 运行态"；原仓保持可用，两者并存 |
| NAS 运行态切换 | 刻意延后 | 切换步骤已写入 `docs/hermes-db-deployment.md`，待单独安排 |

### 2. 发布 / 提交 / CI

| 项目 | 状态 | 说明 |
|------|------|------|
| 本地变更提交 | 待执行 | 所有文件已就位，用户决定何时 commit & push |
| CI/CD 流水线 | 不适用 | 首期不含 CI 配置，后续按需接入 |

### 3. 文档更新

| 文档 | 状态 |
|------|------|
| `README.md` | 已重写为平台仓说明 |
| `docs/platform-overview.md` | 已创建，含分层架构和新增 MCP 流程 |
| `docs/hermes-db-deployment.md` | 已创建，含源码位置、构建、部署和切换步骤 |
| `deploy/README.md` | 已创建，含镜像命名约定和部署流程 |
| `packages/hermes-db/README.md` | 已更新，指向平台仓文档 |

### 4. ADR 保留

三条架构决策记录在 `plan.md` 中：

- ADR-001: 平台仓复活而非新建
- ADR-002: 先迁源码与流程，不绑定 NAS 运行态切换
- ADR-003: 私有配置通过 .gitignore 隔离

无需额外 ADR 文件，plan.md 已充分记录决策理由和边界。

### 5. 架构债与演进触发信号

| 项目 | 类型 | 触发条件 |
|------|------|----------|
| NAS 运行态切换 | 延后任务 | 当准备好将 NAS 从原仓切到平台仓时执行 |
| CI/CD 接入 | 演进方向 | 当需要自动构建/推送镜像时接入 |
| content-orchestrator-agent | 未来 feature | 不在本 feature 范围 |

### 6. 知识同步

- Colima VM DNS 修复：`/etc/resolv.conf` 若为失效软链，需 `rm -f` 后写入真实 nameserver
- 平台仓多语言共存模式：TS 走 turbo，Python 走 uv，互不干扰
- 镜像命名约定：`ghcr.io/northseacoder/<service>:<tag>`

---

## 完成声明

Feature `hermes-db-mcp-platform-revival` 首期目标已全部达成：

1. `mcps` 已从旧模板仓复活为可维护的 MCP 平台仓
2. `hermes-db` 源码、构建和部署描述已迁入
3. NAS 私有配置通过 `.gitignore` 隔离
4. 统一部署骨架已建立，后续 MCP 可直接复用

NAS 运行态切换作为独立后续任务，不阻塞本 feature 收尾。
