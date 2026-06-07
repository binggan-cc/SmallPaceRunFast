"""
SmartDev MCP Server — 主体

设计原理：
──────────
- stdio transport：外部 Agent 通过 JSON-RPC over stdio 调用
- single project per server instance：启动时绑定 project_path，运行时不切换
- mcp 是 optional dependency：未安装时给出明确提示

Phase 10 Step 1 只注册基础工具：
    smartdev_ping / smartdev_version / smartdev_list_tools

工具实现在 tools.py，server.py 只负责注册和启动。

对应文档：
    docs/phase-10-design.md §3.1 §3.2
"""

from __future__ import annotations

import asyncio
from pathlib import Path


def _require_mcp() -> None:
    """检查 mcp 包是否已安装，未安装时输出提示并退出"""
    try:
        import mcp  # noqa: F401
    except ImportError:
        import sys
        print(
            "错误: MCP Server 需要安装 mcp 包。\n"
            "请运行: pip install smartdev-agent[mcp]\n"
            "或直接: pip install mcp",
            file=sys.stderr,
        )
        sys.exit(1)


def create_server(project_path: Path):
    """创建并返回配置好的 MCP Server 实例

    参数：
        project_path: 已验证存在的项目根目录

    返回：
        mcp.server.Server 实例，已注册所有工具
    """
    from mcp.server import Server
    from mcp.types import Tool

    from smartdev.mcp import tools as t

    server = Server("smartdev")

    # ── 工具 Schema 定义 ──────────────────────────────────────────

    _TOOLS: list[Tool] = [
        Tool(
            name="smartdev_ping",
            description=(
                "Health check. Confirms the SmartDev MCP Server is running "
                "and returns the bound project path."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="smartdev_version",
            description=(
                "Returns SmartDev version and the full tool capability list "
                "(including tools not yet available in this step)."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="smartdev_list_tools",
            description=(
                "Lists all currently available MCP tools with their "
                "permission levels and descriptions."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
    ]

    # ── 工具路由表 ────────────────────────────────────────────────

    _HANDLERS = {
        "smartdev_ping":       t.handle_ping,
        "smartdev_version":    t.handle_version,
        "smartdev_list_tools": t.handle_list_tools,
    }

    # ── 注册 list_tools handler ────────────────────────────────────

    @server.list_tools()
    async def list_tools():
        return _TOOLS

    # ── 注册 call_tool handler ─────────────────────────────────────

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        handler = _HANDLERS.get(name)
        if handler is None:
            from mcp.types import TextContent
            from smartdev.mcp import formatter
            return [TextContent(
                type="text",
                text=formatter.error(
                    name,
                    "UNKNOWN_TOOL",
                    f"Tool '{name}' is not registered in this MCP Server instance.",
                ),
            )]
        return await handler(arguments, project_path)

    return server


def run_mcp_server(project_path: Path) -> None:
    """启动 MCP Server（同步入口，供 CLI 调用）

    使用 stdio transport，阻塞直到连接关闭。
    """
    _require_mcp()

    from mcp.server.stdio import stdio_server

    server = create_server(project_path)

    async def _run() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )

    asyncio.run(_run())
