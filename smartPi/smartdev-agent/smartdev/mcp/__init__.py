"""
SmartDev Agent — MCP Server 包

对外暴露 create_server() 和 run_mcp_server()。

安装：
    pip install smartdev-agent[mcp]

使用：
    smartdev mcp --project /path/to/project

对应文档：
    docs/phase-10-design.md
"""

from smartdev.mcp.server import create_server, run_mcp_server

__all__ = ["create_server", "run_mcp_server"]
