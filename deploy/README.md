# 部署约定

本目录定义所有 MCP 服务的公共部署流程。每个服务的差异只体现在镜像名、构建上下文和运行参数。

---

## 发布流程

```
service tag -> GitHub Actions build -> GHCR push -> NAS runner pull/up
```

1. **service tag**：在 Git 中创建服务级版本 tag，例如 `hermes-db-v0.1.1`。
2. **build**：GitHub Actions 根据 `deploy/mcp-services.json` 解析服务、构建上下文和镜像名。
3. **push**：镜像推送到 GHCR，例如 `ghcr.io/northseacoder/hermes-db-mcp:v0.1.1`。
4. **NAS deploy**：NAS self-hosted runner 拉取这个精确版本并重启对应 compose service。

NAS 部署只使用具体版本号，不使用 `latest`、`main` 或 commit sha tag。

---

## 目录结构

```
deploy/
├── README.md              # 本文件
├── mcp-services.json      # 服务清单：镜像、构建上下文、NAS compose 信息
├── nas.example.env        # NAS 环境变量模板（不含真实值）
└── services/
    └── hermes-db.yml      # hermes-db 的 compose 描述（公共部分）
```

GitHub Actions 入口：

```
.github/workflows/mcp-release.yml
```

辅助脚本：

```
scripts/resolve-mcp-release.mjs
scripts/nas-deploy-mcp.sh
```

---

## 发布 hermes-db

```bash
git tag hermes-db-v0.1.1
git push origin hermes-db-v0.1.1
```

触发后 workflow 会：

1. 运行 `packages/hermes-db` 的测试。
2. 构建 `linux/amd64` 镜像。
3. 推送 `ghcr.io/northseacoder/hermes-db-mcp:v0.1.1`。
4. 在 NAS self-hosted runner 上部署该版本。

如果同名镜像 tag 已存在，workflow 会失败，避免覆盖已发布版本。

---

## NAS self-hosted runner

NAS runner 需要注册到本仓库。由于本仓库是 public repo，不应启用默认 runner labels，避免普通 `runs-on: self-hosted` 作业误落到 NAS。

注册时使用：

```bash
./config.sh --unattended \
  --url https://github.com/NorthSeacoder/mcps \
  --token <registration-token> \
  --name nas-mcps-deploy \
  --no-default-labels \
  --labels nas,mcps-deploy \
  --work _work \
  --replace
```

runner 运行用户需要具备：

- 读取本仓库代码的权限。
- 访问 Docker daemon 的权限。
- 读写对应 compose 项目目录的权限，例如 `/vol1/1000/Docker/hermes-db-mcp`。
- 拉取 GHCR 镜像的权限；如果镜像不是公开包，需要提前在 NAS 上执行 `docker login ghcr.io`。

如果 GHCR package 已经存在且没有把本仓库授予写权限，`GITHUB_TOKEN` 可能无法 push。此时在 repo secrets 中添加：

```text
GHCR_TOKEN=<classic PAT with write:packages>
```

workflow 会优先使用 `GHCR_TOKEN`，没有配置时才回退到 `GITHUB_TOKEN`。

部署脚本会在 compose 项目目录生成 `.mcps-release.override.yml`，用来把服务镜像固定到当前发布版本，例如：

```yaml
services:
  hermes-db-mcp:
    image: ghcr.io/northseacoder/hermes-db-mcp:v0.1.1
```

这样现有 NAS compose 文件无需提交真实密钥，也不需要依赖 `latest`。

平台层 compose 模板也要求显式传入版本：

```bash
TAG=v0.1.1 docker compose -f deploy/services/hermes-db.yml --env-file deploy/nas.local.env config
```

---

## NAS 私有配置

NAS 上的真实配置通过本地覆盖文件提供，这些文件被 `.gitignore` 排除：

- `deploy/*.local.*`
- `deploy/services/*.local.yml`
- `.env.local`

首次部署时，复制 `nas.example.env` 为本地文件并填入真实值：

```bash
cp deploy/nas.example.env deploy/nas.local.env
# 编辑 deploy/nas.local.env 填入 NAS 私有值
```

---

## 新增服务

1. 在 `packages/<service>` 下准备源码、测试和 Dockerfile。
2. 在 `deploy/mcp-services.json` 中登记服务名、镜像、构建上下文和 NAS compose 信息。
3. 在 `deploy/services/` 下新增 `<service>.yml`，定义公共 compose 描述。
4. 在 `nas.example.env` 中补充该服务需要的环境变量占位。
5. 在 NAS 本地创建对应的 `.local.` 覆盖文件或 compose 项目目录。
6. 使用 `<service>-vX.Y.Z` tag 发布。
