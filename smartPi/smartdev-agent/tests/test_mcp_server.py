"""
tests/test_mcp_server.py — MCP Server 骨架测试（Phase 10 Step 1）

覆盖内容：
- formatter.ok / formatter.error 输出格式
- create_server() 能正常初始化
- 三个基础工具（ping / version / list_tools）注册和响应
- project_path 不存在时 CLI 报错
- mcp 包未安装时的 fallback（mock）

所有测试不依赖真实 MCP 客户端连接，直接调用 handler 函数验证输出。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# ── formatter 测试 ─────────────────────────────────────────────────


class TestFormatter:
    def test_ok_basic(self):
        from smartdev.mcp.formatter import ok
        result = json.loads(ok("smartdev_ping", {"pong": True}))
        assert result["ok"] is True
        assert result["tool"] == "smartdev_ping"
        assert result["data"]["pong"] is True
        assert result["warnings"] == []
        assert result["risk_level"] == "R0"
        assert result["next_steps"] == []

    def test_ok_with_warnings(self):
        from smartdev.mcp.formatter import ok
        result = json.loads(ok("t", {}, warnings=["w1"], next_steps=["s1"]))
        assert result["warnings"] == ["w1"]
        assert result["next_steps"] == ["s1"]

    def test_error_basic(self):
        from smartdev.mcp.formatter import error
        result = json.loads(error("smartdev_code_search", "INDEX_NOT_FOUND", "No index found."))
        assert result["ok"] is False
        assert result["tool"] == "smartdev_code_search"
        assert result["error_code"] == "INDEX_NOT_FOUND"
        assert result["message"] == "No index found."
        assert "suggested_tool" not in result

    def test_error_with_suggestion(self):
        from smartdev.mcp.formatter import error
        result = json.loads(error("t", "INDEX_NOT_FOUND", "msg", suggested_tool="smartdev_code_index"))
        assert result["suggested_tool"] == "smartdev_code_index"


# ── create_server 测试 ─────────────────────────────────────────────


class TestCreateServer:
    def test_create_server_returns_server(self, tmp_path):
        from smartdev.mcp.server import create_server
        server = create_server(tmp_path)
        assert server is not None
        assert server.name == "smartdev"

    def test_create_server_nonexistent_path(self, tmp_path):
        """create_server 不验证 project_path，那是 CLI 的职责"""
        from smartdev.mcp.server import create_server
        fake = tmp_path / "nonexistent"
        server = create_server(fake)  # 不应抛出异常
        assert server is not None


# ── 工具 handler 测试 ──────────────────────────────────────────────


class TestHandlePing:
    @pytest.mark.asyncio
    async def test_ping_ok(self, tmp_path):
        from smartdev.mcp.tools import handle_ping
        result = await handle_ping({}, tmp_path)
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["ok"] is True
        assert data["tool"] == "smartdev_ping"
        assert data["data"]["pong"] is True
        assert str(tmp_path) in data["data"]["project_path"]

    @pytest.mark.asyncio
    async def test_ping_contains_risk_level(self, tmp_path):
        from smartdev.mcp.tools import handle_ping
        result = await handle_ping({}, tmp_path)
        data = json.loads(result[0].text)
        assert data["risk_level"] == "R0"


class TestHandleVersion:
    @pytest.mark.asyncio
    async def test_version_ok(self, tmp_path):
        from smartdev.mcp.tools import handle_version
        result = await handle_version({}, tmp_path)
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["ok"] is True
        assert data["tool"] == "smartdev_version"

    @pytest.mark.asyncio
    async def test_version_contains_version_string(self, tmp_path):
        from smartdev import __version__
        from smartdev.mcp.tools import handle_version
        result = await handle_version({}, tmp_path)
        data = json.loads(result[0].text)
        assert data["data"]["version"] == __version__

    @pytest.mark.asyncio
    async def test_version_lists_tools(self, tmp_path):
        from smartdev.mcp.tools import handle_version
        result = await handle_version({}, tmp_path)
        data = json.loads(result[0].text)
        tool_names = [t["name"] for t in data["data"]["tools"]]
        # Step 1 的三个基础工具必须在列表里
        assert "smartdev_ping" in tool_names
        assert "smartdev_version" in tool_names
        assert "smartdev_list_tools" in tool_names
        # 后续工具标记为 coming_soon
        assert "smartdev_code_search" in tool_names

    @pytest.mark.asyncio
    async def test_version_tool_has_permission(self, tmp_path):
        from smartdev.mcp.tools import handle_version
        result = await handle_version({}, tmp_path)
        data = json.loads(result[0].text)
        ping = next(t for t in data["data"]["tools"] if t["name"] == "smartdev_ping")
        assert ping["permission"] == "READ"


class TestHandleListTools:
    @pytest.mark.asyncio
    async def test_list_tools_ok(self, tmp_path):
        from smartdev.mcp.tools import handle_list_tools
        result = await handle_list_tools({}, tmp_path)
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["ok"] is True
        assert data["tool"] == "smartdev_list_tools"

    @pytest.mark.asyncio
    async def test_list_tools_contains_step1_tools(self, tmp_path):
        from smartdev.mcp.tools import handle_list_tools
        result = await handle_list_tools({}, tmp_path)
        data = json.loads(result[0].text)
        names = [t["name"] for t in data["data"]["available_tools"]]
        assert "smartdev_ping" in names
        assert "smartdev_version" in names
        assert "smartdev_list_tools" in names

    @pytest.mark.asyncio
    async def test_list_tools_total_count(self, tmp_path):
        from smartdev.mcp.tools import handle_list_tools
        result = await handle_list_tools({}, tmp_path)
        data = json.loads(result[0].text)
        # Step 4 后有 14 个工具（3 基础 + 4 Context + 5 Skill + 2 Patch）
        assert data["data"]["total"] == 19


# ── CLI mcp 子命令测试 ─────────────────────────────────────────────


class TestCliMcp:
    def test_mcp_invalid_project(self, tmp_path):
        """项目路径不存在时退出码为 1"""
        from smartdev.cli import _cmd_mcp

        class Args:
            project = str(tmp_path / "nonexistent")

        result = _cmd_mcp(Args())
        assert result == 1

    def test_mcp_missing_package(self, tmp_path):
        """mcp 包未安装时退出码为 1"""
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "mcp":
                raise ImportError("No module named 'mcp'")
            return real_import(name, *args, **kwargs)

        from smartdev.cli import _cmd_mcp

        class Args:
            project = str(tmp_path)

        with patch("builtins.__import__", side_effect=mock_import):
            result = _cmd_mcp(Args())
        assert result == 1
