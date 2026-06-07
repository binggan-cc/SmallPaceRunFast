"""
SmartDev MCP — 工具实现

Phase 10 Step 1：只暴露基础工具
    smartdev_ping            健康检查
    smartdev_version         版本信息 + 能力清单
    smartdev_list_tools      列出所有可用 MCP 工具

后续 Step 2–4 将在此文件追加：
    code_search / code_impact / project_map / graph_validate
    repo_scan / risk_check / architecture_map / task_plan / qa_checklist
    code_index / patch_propose

设计原则：
- 工具始终返回 list[TextContent]，不抛异常到 MCP 层
- 所有输出走 formatter.ok / formatter.error
- MCP 层只做参数解析 + Skill 调用 + 格式化，不含业务逻辑

对应文档：
    docs/phase-10-design.md §3.3
"""

from __future__ import annotations

from pathlib import Path

from mcp.types import TextContent

from smartdev import __version__
from smartdev.mcp import formatter

# ── Step 1 工具：ping / version / list_tools ─────────────────────


async def handle_ping(arguments: dict, project_path: Path) -> list[TextContent]:
    """健康检查，确认 MCP Server 正常运行"""
    return [TextContent(
        type="text",
        text=formatter.ok("smartdev_ping", {"pong": True, "project_path": str(project_path)}),
    )]


async def handle_version(arguments: dict, project_path: Path) -> list[TextContent]:
    """返回版本信息和当前已注册的工具能力清单"""
    # Step 1 只列出当前已实现的工具
    # 后续 Step 加工具时同步更新此列表
    tools = [
        {"name": "smartdev_ping",       "permission": "READ",         "status": "available"},
        {"name": "smartdev_version",     "permission": "READ",         "status": "available"},
        {"name": "smartdev_list_tools",  "permission": "READ",         "status": "available"},
        # Step 2（待实现）
        {"name": "smartdev_code_search",     "permission": "READ",         "status": "coming_soon"},
        {"name": "smartdev_code_impact",     "permission": "READ",         "status": "coming_soon"},
        {"name": "smartdev_project_map",     "permission": "READ",         "status": "coming_soon"},
        {"name": "smartdev_graph_validate",  "permission": "READ",         "status": "coming_soon"},
        # Step 3（待实现）
        {"name": "smartdev_repo_scan",       "permission": "READ",         "status": "coming_soon"},
        {"name": "smartdev_risk_check",      "permission": "READ",         "status": "coming_soon"},
        {"name": "smartdev_architecture_map","permission": "READ",         "status": "coming_soon"},
        {"name": "smartdev_task_plan",       "permission": "READ",         "status": "coming_soon"},
        {"name": "smartdev_qa_checklist",    "permission": "READ",         "status": "coming_soon"},
        # Step 4（待实现）
        {"name": "smartdev_code_index",      "permission": "CACHE_WRITE",  "status": "coming_soon"},
        {"name": "smartdev_patch_propose",   "permission": "PATCH_PROPOSE","status": "coming_soon"},
    ]
    return [TextContent(
        type="text",
        text=formatter.ok("smartdev_version", {
            "version": __version__,
            "mcp_server": "SmartDev MCP Server v0",
            "project_path": str(project_path),
            "tools": tools,
        }),
    )]


async def handle_list_tools(arguments: dict, project_path: Path) -> list[TextContent]:
    """列出当前可用工具，附带权限和说明"""
    available = [
        {
            "name": "smartdev_ping",
            "permission": "READ",
            "description": "Health check. Confirms MCP Server is running.",
        },
        {
            "name": "smartdev_version",
            "permission": "READ",
            "description": "Returns version and full tool capability list.",
        },
        {
            "name": "smartdev_list_tools",
            "permission": "READ",
            "description": "Lists all available tools with permissions.",
        },
    ]
    return [TextContent(
        type="text",
        text=formatter.ok("smartdev_list_tools", {
            "available_tools": available,
            "total": len(available),
            "note": "More tools coming in Step 2–4. Run smartdev_version for full list.",
        }),
    )]
