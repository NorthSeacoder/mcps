# MCP Platform Repo

`mcps` 是统一管理多个 Model Context Protocol (MCP) 服务的平台仓。承载所有 MCP 服务的源码、构建脚本、部署约定与文档，使新增 MCP 服务时只需复用平台骨架，差异只体现在镜像名和构建上下文。

---

## 仓库定位

- **平台层**：根目录保留 pnpm workspace + turbo 的统一管理，提供共享脚本与脚手架。
- **服务层**：每个 MCP 服务独立放在 `packages/<service>` 下，可以是 TypeScript（Node）服务，也可以是 Python（uv）服务。
- **部署层**：`deploy/` 提供统一的镜像构建、推送和 NAS 拉取约定；服务专属差异通过镜像名和 compose 表达。
- **本地覆盖层**：NAS 私有配置（密钥、内网地址、镜像引用）通过 `.gitignore` 排除，不进入开源仓。

---

## 项目结构

```
mcps/
├── packages/                 # 所有 MCP 服务
│   ├── tpl/                  # TypeScript 服务模板
│   ├── weekly/               # 示例 TS 服务
│   └── hermes-db/            # Python MCP 服务（uv 管理）
├── deploy/                   # 公共部署约定与示例配置
│   ├── README.md
│   ├── nas.example.env
│   └── services/
├── docs/                     # 平台与服务接入文档
├── specs/                    # 需求、方案、任务、验收
├── scripts/                  # 平台级脚手架脚本
├── package.json              # 根工作区与平台脚本
├── pnpm-workspace.yaml
└── turbo.json
```

---

## 当前服务

| 服务 | 语言 | 镜像 | 状态 |
|------|------|------|------|
| `tpl` | TypeScript | — | TS 服务模板 |
| `weekly` | TypeScript | — | 示例服务 |
| `hermes-db` | Python (uv) | `ghcr.io/northseacoder/hermes-db-mcp:latest` | 已迁入，源码与部署流程统一管理；NAS 运行态切换待单独安排 |

---

## 平台级命令

TypeScript 服务（基于 turbo）：

```bash
pnpm install               # 安装根依赖
pnpm build                 # 构建所有 TS 服务
pnpm dev                   # 并行开发 TS 服务
pnpm test                  # 运行 TS 服务测试
pnpm new-server            # 一键生成新 TS 服务
```

Python 服务（基于 uv，命令在服务目录内执行）：

```bash
cd packages/hermes-db
uv sync                    # 安装依赖
uv run pytest              # 运行测试
uv run hermes-db-mcp       # 启动服务
```

---

## 新增 MCP 服务

- **TypeScript**：`pnpm new-server`，按提示输入服务名，会从 `packages/tpl` 派生新服务，并补齐根级脚本。
- **Python**：在 `packages/<service>` 下手工创建 `pyproject.toml` + `Dockerfile`，参考 `packages/hermes-db` 的目录布局；并在 `deploy/services/` 增加镜像与运行参数描述。

详见 [`docs/platform-overview.md`](docs/platform-overview.md)。

---

## 部署

所有 MCP 沿用同一套发布流程：`build -> tag -> push -> NAS pull -> run`。详见 [`deploy/README.md`](deploy/README.md)。

NAS 上的私有配置（镜像仓地址、密钥、内网域名）通过 `.gitignore` 隔离的本地覆盖文件提供，例如：

```
deploy/*.local.*
deploy/services/*.local.yml
.env.local
```

---

## 文档索引

- [`docs/platform-overview.md`](docs/platform-overview.md)：平台仓总览与新增 MCP 接入流程
- [`docs/hermes-db-deployment.md`](docs/hermes-db-deployment.md)：`hermes-db` 在平台仓内的源码、构建与部署边界
- [`deploy/README.md`](deploy/README.md)：公共部署流程与镜像约定
- [`specs/`](specs/)：各 feature 的需求、方案、任务与验收

---

## 当前阶段

- 平台仓已从旧模板仓恢复为可承载多服务的形态。
- `hermes-db` 的源码与部署流程已迁入；NAS 运行态切换不在首期范围。
- `content-orchestrator-agent` 不在本仓范围。
- 后续新增 MCP 默认沿用本仓的目录、模板与部署骨架。

---

## 参考资料

- [MCP 官方文档](https://modelcontextprotocol.io/)
- [MCP TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk)
- [Turborepo](https://turbo.build/)
- [pnpm](https://pnpm.io/)
- [uv](https://docs.astral.sh/uv/)
