# MCP Monorepo

本项目是基于 TypeScript 的 Model Context Protocol (MCP) 多服务 monorepo，便于统一管理和扩展多个 MCP 服务器。

---

## 项目结构

```
├── packages/               # 所有 MCP 服务器包
│   ├── tpl/                # MCP 服务器模板
│   └── ...                 # 其他自定义 MCP 服务
├── scripts/                # 辅助脚本（如一键生成新服务）
├── package.json            # 根依赖与统一脚本
├── turbo.json              # Turborepo 配置
└── ...                     # 其他配置文件
```

---

## 批量依赖管理与构建

- 安装所有依赖（在根目录）：
  ```bash
  pnpm install
  ```
- 构建所有 MCP 服务：
  ```bash
  pnpm build
  ```
- 并行开发所有 MCP 服务：
  ```bash
  pnpm dev
  ```

---

## 创建新 MCP 服务

使用内置脚本一键生成新服务包：

```bash
pnpm new-server
# 按提示输入服务名（如 search-server）
# 会自动在 packages/ 下生成新服务，并添加相关脚本
```

---

## 各 MCP 服务调用方式

### weekly
```json
{
  "mcpServers": {
    "weekly": {
      "command": "node",
      "args": [
        "/绝对路径/到你的项目/packages/weekly/dist/index.js"
      ]
    }
  }
}
```


---

## 调试与开发建议

- 推荐开发时用 `pnpm dev` 并结合日志调试
- 可用 MCP Inspector 工具辅助调试：https://modelcontextprotocol.io/inspector
- 各服务包内可自定义资源、工具，详见各自 README

---

## 参考资料

- [MCP 官方文档](https://modelcontextprotocol.io/)
- [MCP TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk)
- [Turborepo](https://turbo.build/)
- [pnpm](https://pnpm.io/)