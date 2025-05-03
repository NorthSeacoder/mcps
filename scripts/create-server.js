#!/usr/bin/env node
/* eslint-disable @typescript-eslint/no-var-requires */

const fs = require('fs');
const path = require('path');
const readline = require('readline');

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout
});

// 获取服务器名称
rl.question('请输入 MCP 服务器名称 (例如: my-server): ', (serverName) => {
  if (!serverName) {
    console.error('错误: 服务器名称不能为空');
    rl.close();
    return;
  }

  // 定义路径
  const templateDir = path.join(__dirname, '../packages/tpl');
  const targetDir = path.join(__dirname, '../packages', serverName);
  
  // 检查目标目录是否已存在
  if (fs.existsSync(targetDir)) {
    console.error(`错误: 目录 ${targetDir} 已存在`);
    rl.close();
    return;
  }

  try {
    // 创建目标目录
    fs.mkdirSync(targetDir, { recursive: true });
    
    // 复制模板文件
    copyDirectory(templateDir, targetDir, serverName);
    
    // 更新服务器 package.json
    const packageJsonPath = path.join(targetDir, 'package.json');
    const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf-8'));
    packageJson.name = `@mcps/${serverName}`;
    packageJson.bin = { [serverName]: "dist/index.js" };
    fs.writeFileSync(packageJsonPath, JSON.stringify(packageJson, null, 2));
    
    // 优化 README.md 标题和内容
    const readmePath = path.join(targetDir, 'README.md');
    if (fs.existsSync(readmePath)) {
      let readme = fs.readFileSync(readmePath, 'utf-8');
      // 替换标题和内容
      const serviceTitle = `${capitalize(serverName)} MCP Server`;
      readme = readme.replace(/^# Template MCP Server/m, `# ${serviceTitle}`);
      readme = readme.replace(/Template MCP Server/g, serviceTitle);
      readme = readme.replace(/tpl/g, serverName);
      fs.writeFileSync(readmePath, readme);
    }
    
    // 更新根目录 package.json，添加新服务器的脚本命令
    updateRootPackageJson(serverName);
    
    console.log(`✅ MCP 服务器 "${serverName}" 创建成功!`);
    console.log(`\n下一步:`);
    console.log(`1. 修改 packages/${serverName}/src 中的代码以实现你的服务器功能`);
    console.log(`2. 运行 pnpm install 安装依赖`);
    console.log(`3. 运行 pnpm dev:${serverName} 启动开发环境`);
    console.log(`4. 构建服务器: pnpm build:${serverName}`);
    console.log(`5. 运行服务器: pnpm start:${serverName}`);
    
    rl.close();
  } catch (error) {
    console.error(`创建服务器时出错: ${error.message}`);
    rl.close();
  }
});

// 更新根目录 package.json 文件，添加新服务器的命令
function updateRootPackageJson(serverName) {
  const rootPackageJsonPath = path.join(__dirname, '../package.json');
  const rootPackageJson = JSON.parse(fs.readFileSync(rootPackageJsonPath, 'utf-8'));
  
  // 添加新的脚本命令
  rootPackageJson.scripts[`build:${serverName}`] = `pnpm --filter @mcps/${serverName} build`;
  rootPackageJson.scripts[`dev:${serverName}`] = `pnpm --filter @mcps/${serverName} dev`;
  rootPackageJson.scripts[`start:${serverName}`] = `pnpm --filter @mcps/${serverName} start`;
  
  // 保存更新后的 package.json
  fs.writeFileSync(rootPackageJsonPath, JSON.stringify(rootPackageJson, null, 2));
  
  console.log(`已添加 ${serverName} 的命令到根目录 package.json`);
}

// 复制目录的函数
function copyDirectory(source, target, serverName) {
  // 确保目标目录存在
  if (!fs.existsSync(target)) {
    fs.mkdirSync(target, { recursive: true });
  }

  // 读取源目录中的所有文件和子目录
  const entries = fs.readdirSync(source, { withFileTypes: true });

  // 遍历并复制每个条目
  for (const entry of entries) {
    // 跳过 dist 和 node_modules 目录
    if (entry.name === 'dist' || entry.name === 'node_modules') {
      continue;
    }
    // 跳过 tsconfig.json 文件
    if (entry.name === 'tsconfig.json') {
      continue;
    }

    const sourcePath = path.join(source, entry.name);
    const targetPath = path.join(target, entry.name);

    if (entry.isDirectory()) {
      // 递归复制子目录
      copyDirectory(sourcePath, targetPath, serverName);
    } else {
      // 复制文件并替换模板变量
      let content = fs.readFileSync(sourcePath, 'utf-8');
      // 替换模板变量
      content = content.replace(/@mcps\/tpl/g, `@mcps/${serverName}`);
      content = content.replace(/weather-server/g, serverName);
      fs.writeFileSync(targetPath, content);
    }
  }
}

function capitalize(str) {
  return str.charAt(0).toUpperCase() + str.slice(1);
} 