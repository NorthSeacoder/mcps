import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";

export function createServer(): McpServer {
  const server = new McpServer({
    name: "Weekly MCP Server",
    version: "0.1.0",
  });

  // 读取 cursorrules 文件内容
  const __filename = fileURLToPath(import.meta.url);
  const __dirname = path.dirname(__filename);
  const cursorRulesPath = path.resolve(__dirname, "./cursorrules");
  const cursorRulesContent = fs.readFileSync(cursorRulesPath, "utf-8");

  // 添加预定义的 prompt
  server.prompt("weekly_editor", async () => ({
    messages: [
      {
        role: "user",
        content: {
          type: "text",
          text: cursorRulesContent,
        },
      },
    ],
  }));

  return server;
}
