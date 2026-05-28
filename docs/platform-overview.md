# 平台仓总览

`mcps` 是统一管理多个 MCP 服务的平台仓。

---

## 职责分层

| 层 | 目录 | 职责 |
|----|------|------|
| 平台层 | 根目录 | pnpm workspace + turbo，共享脚本与脚手架 |
| 服务层 | `packages/<service>` | 各 MCP 服务的源码、构建和本地开发 |
| 部署层 | `deploy/` | 公共部署约定、镜像命名、compose 模板 |
| 文档层 | `docs/` | 平台与服务接入文档 |
| 规格层 | `specs/` | 需求、方案、任务、验收 |
| 本地覆盖层 | `*.local.*` | NAS 私有配置，被 `.gitignore` 排除 |

---

## 新增 TypeScript MCP

```bash
pnpm new-server
# 按提示输入服务名
# 自动从 packages/tpl 派生新服务
```

生成后：

1. 修改 `packages/<service>/src` 实现业务逻辑。
2. `pnpm --filter @mcps/<service> dev` 启动开发。
3. 在 `deploy/services/` 增加 compose 描述。
4. 在 `deploy/nas.example.env` 补充环境变量占位。

---

## 新增 Python MCP

1. 在 `packages/<service>` 下创建 `pyproject.toml`、`Dockerfile`、`src/` 和 `tests/`。
2. 参考 `packages/hermes-db` 的目录布局。
3. 在 `deploy/services/` 增加 compose 描述。
4. 在 `deploy/nas.example.env` 补充环境变量占位。

Python 服务不参与 turbo 构建，通过 `uv` 独立管理依赖和运行。

---

## 部署流程

所有服务共享同一套发布流程：

```
build -> tag -> push -> NAS pull -> run
```

详见 [`deploy/README.md`](../deploy/README.md)。

---

## 私有配置隔离

NAS 私有值（密钥、内网地址、镜像仓路径）通过本地覆盖文件提供：

- `deploy/*.local.*`
- `deploy/services/*.local.yml`
- `.env.local`

这些文件被 `.gitignore` 排除，不进入开源仓。首次部署时从 `nas.example.env` 复制并填入真实值。
