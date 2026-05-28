# 部署约定

本目录定义所有 MCP 服务的公共部署流程。每个服务的差异只体现在镜像名、构建上下文和运行参数。

---

## 发布流程

```
build -> tag -> push -> NAS pull -> run
```

1. **build**：在服务目录内构建 Docker 镜像。
2. **tag**：按 `ghcr.io/<owner>/<service>:<version>` 命名。
3. **push**：推送到镜像仓库。
4. **NAS pull**：NAS 通过 `docker compose pull` 拉取最新镜像。
5. **run**：NAS 通过 `docker compose up -d` 启动或更新容器。

---

## 目录结构

```
deploy/
├── README.md              # 本文件
├── nas.example.env        # NAS 环境变量模板（不含真实值）
└── services/
    └── hermes-db.yml      # hermes-db 的 compose 描述（公共部分）
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

1. 在 `deploy/services/` 下新增 `<service>.yml`，定义公共 compose 描述。
2. 在 `nas.example.env` 中补充该服务需要的环境变量占位。
3. 在 NAS 本地创建对应的 `.local.` 覆盖文件。
