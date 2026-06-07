# SmartDev MCP Server

SmartDev 的 MCP Server，通过 stdio transport 暴露 SmartDev 能力给外部 Agent（Claude / Kiro / Cursor / Codex 等）。

## 安装

```bash
pip install smartdev-agent[mcp]
# 或直接
pip install mcp
```

## 启动

```bash
smartdev mcp --project /path/to/project
```

## 配置（以 Kiro / Claude Desktop 为例）

在 `mcp.json` 中添加：

```json
{
  "mcpServers": {
    "smartdev": {
      "command": "python",
      "args": ["-m", "smartdev", "mcp", "--project", "/path/to/project"],
      "disabled": false
    }
  }
}
```

## Phase 10 Step 1 可用工具

| 工具 | 权限 | 说明 |
|------|------|------|
| `smartdev_ping` | READ | 健康检查 |
| `smartdev_version` | READ | 版本 + 工具能力清单 |
| `smartdev_list_tools` | READ | 当前可用工具列表 |

## 权限模型

| 权限 | 说明 | v0 状态 |
|------|------|---------|
| READ | 只读查询 | ✅ 开放 |
| CACHE_WRITE | 写 .smartdev/ 缓存 | ✅ 开放（Step 4） |
| PATCH_PROPOSE | 生成 diff，不落盘 | ✅ 开放（Step 4） |
| WRITE_CODE | 写源码 | ❌ v0 禁用 |
| EXEC | 执行 shell | ❌ 永久禁用 |

## 统一输出格式

所有工具返回 JSON：

```json
{
  "ok": true,
  "tool": "smartdev_ping",
  "data": {},
  "warnings": [],
  "risk_level": "R0",
  "next_steps": []
}
```

失败时：

```json
{
  "ok": false,
  "tool": "smartdev_ping",
  "error_code": "PROJECT_NOT_FOUND",
  "message": "Project path does not exist: /path/to/project"
}
```

## 设计文档

`docs/phase-10-design.md`
