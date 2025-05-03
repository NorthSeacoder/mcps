# Weekly MCP Server

本项目是基于 [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) 的服务端实现，适合快速开发和部署自定义 MCP 服务。

---

## 安装依赖

在项目根目录执行：

```bash
pnpm install
```

---

## 构建与运行

在本目录（`packages/weekly`）下：

- 构建服务
  ```bash
  pnpm build
  ```
- 开发模式（自动编译）
  ```bash
  pnpm dev
  ```
- 启动本地进程服务（Stdio，适合本地开发/调试）
  ```bash
  pnpm start
  # 或
  node ./dist/index.js
  ```

---

## 参考资料

- [MCP 官方文档](https://modelcontextprotocol.io/)
- [MCP TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk)
