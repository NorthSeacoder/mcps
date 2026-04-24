#!/usr/bin/env node
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';

import { createServer } from './server.js';

async function main() {
  const server: McpServer = createServer();
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch(error => {
  process.stderr.write(`Fatal error in main(): ${error}\n`);
  process.exit(1);
});
