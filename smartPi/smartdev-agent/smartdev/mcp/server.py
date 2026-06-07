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
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="smartdev_version",
            description=(
                "Returns SmartDev version and the full tool capability list "
                "(including tools not yet available in this step)."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="smartdev_list_tools",
            description=(
                "Lists all currently available MCP tools with their "
                "permission levels and descriptions."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="smartdev_code_search",
            description=(
                "Full-text search over indexed files and artifacts. "
                "Requires running smartdev_code_index first."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search term (file name, function name, artifact type, etc.)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 20)",
                        "default": 20,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="smartdev_code_impact",
            description=(
                "Analyze the change impact of a file, module, or artifact via import reverse lookup. "
                "Returns affected files, risk level, and validation suggestions. "
                "Requires running smartdev_code_index first."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Target to analyze (file path, module name, or artifact name)",
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum depth for impact traversal (default: 3)",
                        "default": 3,
                    },
                },
                "required": ["target"],
            },
        ),
        Tool(
            name="smartdev_project_map",
            description=(
                "Export a project structure map including modules, hotspots, and external dependencies. "
                "Requires running smartdev_code_index first."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="smartdev_graph_validate",
            description=(
                "Validate the health of the project graph: orphan nodes, duplicates, "
                "hotspots, and unresolved imports. "
                "Requires running smartdev_code_index first."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        # ── Step 3: Skill 工具 ────────────────────────────────────
        Tool(
            name="smartdev_repo_scan",
            description=(
                "Scan the project: detect tech stack, entry points, documentation status, "
                "and directory structure."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum directory tree depth (default: 2)",
                        "default": 2,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="smartdev_risk_check",
            description=(
                "Check the risk level of a task. "
                "With an index, uses import-based impact analysis for more accurate results. "
                "Without an index, falls back to keyword matching."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "task_description": {
                        "type": "string",
                        "description": "Description of the task or change to evaluate",
                    },
                    "target": {
                        "type": "string",
                        "description": "(Optional) File path or module name to enhance impact analysis",
                    },
                },
                "required": ["task_description"],
            },
        ),
        Tool(
            name="smartdev_architecture_map",
            description=(
                "Analyze project architecture: dependency graph, circular dependencies, core modules. "
                "With an index, supports multi-language analysis (Python/JS/TS/Go). "
                "Without an index, falls back to Python AST only."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="smartdev_task_plan",
            description=(
                "Generate a three-tier task plan (conservative / recommended / deep) for a task. "
                "With an index, annotates the recommended plan with affected files."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "task_description": {
                        "type": "string",
                        "description": "Description of the development task",
                    },
                    "target": {
                        "type": "string",
                        "description": "(Optional) File path or module to scope impact analysis",
                    },
                },
                "required": ["task_description"],
            },
        ),
        Tool(
            name="smartdev_qa_checklist",
            description=(
                "Generate a structured acceptance checklist for a task, "
                "covering functionality, UI, API, performance, and security."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "task_description": {
                        "type": "string",
                        "description": "Description of the task to generate a checklist for",
                    },
                },
                "required": ["task_description"],
            },
        ),
    ]

    # ── 工具路由表 ────────────────────────────────────────────────

    _HANDLERS = {
        "smartdev_ping":             t.handle_ping,
        "smartdev_version":          t.handle_version,
        "smartdev_list_tools":       t.handle_list_tools,
        "smartdev_code_search":      t.handle_code_search,
        "smartdev_code_impact":      t.handle_code_impact,
        "smartdev_project_map":      t.handle_project_map,
        "smartdev_graph_validate":   t.handle_graph_validate,
        "smartdev_repo_scan":        t.handle_repo_scan,
        "smartdev_risk_check":       t.handle_risk_check,
        "smartdev_architecture_map": t.handle_architecture_map,
        "smartdev_task_plan":        t.handle_task_plan,
        "smartdev_qa_checklist":     t.handle_qa_checklist,
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
