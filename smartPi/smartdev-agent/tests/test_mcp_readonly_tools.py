"""
tests/test_mcp_readonly_tools.py — MCP 只读 Context 工具测试（Phase 10 Step 2）

覆盖内容：
- INDEX_NOT_FOUND 错误路径（所有 Context 工具在无索引时的行为）
- 空 query 参数错误（code_search / code_impact）
- 有索引时的正常调用路径（基于已有 tests/fixtures/js_ts_project/ 或 tmp_path）
- 返回结构符合 formatter 规范（ok/tool/data/risk_level）
- list_tools 已包含新工具
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


# ── 辅助：建立最小索引 ─────────────────────────────────────────────


def _build_minimal_index(project_path: Path) -> None:
    """在 tmp_path 里建立最小有效索引（复用已有 ProjectIndex）"""
    from smartdev.context.project_index import ProjectIndex
    index = ProjectIndex(project_path)
    # 写一个简单的文件记录
    from smartdev.context.index_store import FileRecord
    import time
    record = FileRecord(
        path="main.py",
        content_hash="abc123",
        language="python",
        kind="source",
        size=100,
        modified_at=int(time.time()),
        indexed_at=int(time.time()),
    )
    index.store.upsert_file(record)
    index.close()


# ── INDEX_NOT_FOUND 错误路径 ──────────────────────────────────────


class TestIndexNotFound:
    @pytest.mark.asyncio
    async def test_code_search_no_index(self, tmp_path):
        from smartdev.mcp.tools import handle_code_search
        result = await handle_code_search({"query": "main"}, tmp_path)
        data = json.loads(result[0].text)
        assert data["ok"] is False
        assert data["error_code"] == "INDEX_NOT_FOUND"
        assert data["suggested_tool"] == "smartdev_code_index"

    @pytest.mark.asyncio
    async def test_code_impact_no_index(self, tmp_path):
        from smartdev.mcp.tools import handle_code_impact
        result = await handle_code_impact({"target": "models.py"}, tmp_path)
        data = json.loads(result[0].text)
        assert data["ok"] is False
        assert data["error_code"] == "INDEX_NOT_FOUND"
        assert data["suggested_tool"] == "smartdev_code_index"

    @pytest.mark.asyncio
    async def test_project_map_no_index(self, tmp_path):
        from smartdev.mcp.tools import handle_project_map
        result = await handle_project_map({}, tmp_path)
        data = json.loads(result[0].text)
        assert data["ok"] is False
        assert data["error_code"] == "INDEX_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_graph_validate_no_index(self, tmp_path):
        from smartdev.mcp.tools import handle_graph_validate
        result = await handle_graph_validate({}, tmp_path)
        data = json.loads(result[0].text)
        assert data["ok"] is False
        assert data["error_code"] == "INDEX_NOT_FOUND"


# ── 参数校验 ──────────────────────────────────────────────────────


class TestArgumentValidation:
    @pytest.mark.asyncio
    async def test_code_search_empty_query(self, tmp_path):
        _build_minimal_index(tmp_path)
        from smartdev.mcp.tools import handle_code_search
        result = await handle_code_search({"query": ""}, tmp_path)
        data = json.loads(result[0].text)
        assert data["ok"] is False
        assert data["error_code"] == "INVALID_ARGUMENT"

    @pytest.mark.asyncio
    async def test_code_search_missing_query(self, tmp_path):
        _build_minimal_index(tmp_path)
        from smartdev.mcp.tools import handle_code_search
        result = await handle_code_search({}, tmp_path)
        data = json.loads(result[0].text)
        assert data["ok"] is False
        assert data["error_code"] == "INVALID_ARGUMENT"

    @pytest.mark.asyncio
    async def test_code_impact_empty_target(self, tmp_path):
        _build_minimal_index(tmp_path)
        from smartdev.mcp.tools import handle_code_impact
        result = await handle_code_impact({"target": ""}, tmp_path)
        data = json.loads(result[0].text)
        assert data["ok"] is False
        assert data["error_code"] == "INVALID_ARGUMENT"


# ── 正常调用路径（有索引）─────────────────────────────────────────


class TestWithIndex:
    @pytest.mark.asyncio
    async def test_code_search_ok(self, tmp_path):
        _build_minimal_index(tmp_path)
        from smartdev.mcp.tools import handle_code_search
        result = await handle_code_search({"query": "main"}, tmp_path)
        data = json.loads(result[0].text)
        assert data["ok"] is True
        assert data["tool"] == "smartdev_code_search"
        assert "files" in data["data"]
        assert "artifacts" in data["data"]

    @pytest.mark.asyncio
    async def test_code_search_returns_risk_level(self, tmp_path):
        _build_minimal_index(tmp_path)
        from smartdev.mcp.tools import handle_code_search
        result = await handle_code_search({"query": "x"}, tmp_path)
        data = json.loads(result[0].text)
        assert "risk_level" in data
        assert data["risk_level"] == "R0"

    @pytest.mark.asyncio
    async def test_code_search_respects_limit(self, tmp_path):
        _build_minimal_index(tmp_path)
        from smartdev.mcp.tools import handle_code_search
        result = await handle_code_search({"query": "main", "limit": 5}, tmp_path)
        data = json.loads(result[0].text)
        assert data["ok"] is True
        # 实际结果数 ≤ limit
        assert len(data["data"]["files"]) <= 5

    @pytest.mark.asyncio
    async def test_code_impact_ok(self, tmp_path):
        _build_minimal_index(tmp_path)
        from smartdev.mcp.tools import handle_code_impact
        result = await handle_code_impact({"target": "main.py"}, tmp_path)
        data = json.loads(result[0].text)
        assert data["ok"] is True
        assert data["tool"] == "smartdev_code_impact"
        assert "affected_files" in data["data"]
        assert "risk_level" in data["data"]
        assert "validation_suggestions" in data["data"]

    @pytest.mark.asyncio
    async def test_code_impact_has_risk_level_in_response(self, tmp_path):
        _build_minimal_index(tmp_path)
        from smartdev.mcp.tools import handle_code_impact
        result = await handle_code_impact({"target": "main.py"}, tmp_path)
        data = json.loads(result[0].text)
        assert data["risk_level"] in ("R0", "R1", "R2", "R3")

    @pytest.mark.asyncio
    async def test_project_map_ok(self, tmp_path):
        _build_minimal_index(tmp_path)
        from smartdev.mcp.tools import handle_project_map
        result = await handle_project_map({}, tmp_path)
        data = json.loads(result[0].text)
        assert data["ok"] is True
        assert data["tool"] == "smartdev_project_map"
        assert "project" in data["data"]
        assert "modules" in data["data"]
        assert "hotspots" in data["data"]

    @pytest.mark.asyncio
    async def test_graph_validate_ok(self, tmp_path):
        _build_minimal_index(tmp_path)
        from smartdev.mcp.tools import handle_graph_validate
        result = await handle_graph_validate({}, tmp_path)
        data = json.loads(result[0].text)
        assert data["ok"] is True
        assert data["tool"] == "smartdev_graph_validate"
        assert "is_healthy" in data["data"]
        assert "stats" in data["data"]
        assert "errors" in data["data"]
        assert "warnings" in data["data"]

    @pytest.mark.asyncio
    async def test_graph_validate_healthy_empty_project(self, tmp_path):
        _build_minimal_index(tmp_path)
        from smartdev.mcp.tools import handle_graph_validate
        result = await handle_graph_validate({}, tmp_path)
        data = json.loads(result[0].text)
        # 只有一个文件、无关系的空项目应该是健康的
        assert data["data"]["is_healthy"] is True
        assert data["data"]["summary"]["error_count"] == 0


# ── list_tools 已包含新工具 ───────────────────────────────────────


class TestListToolsUpdated:
    @pytest.mark.asyncio
    async def test_list_tools_includes_step2_tools(self, tmp_path):
        from smartdev.mcp.tools import handle_list_tools
        result = await handle_list_tools({}, tmp_path)
        data = json.loads(result[0].text)
        names = [t["name"] for t in data["data"]["available_tools"]]
        assert "smartdev_code_search" in names
        assert "smartdev_code_impact" in names
        assert "smartdev_project_map" in names
        assert "smartdev_graph_validate" in names

    @pytest.mark.asyncio
    async def test_list_tools_total_count_updated(self, tmp_path):
        from smartdev.mcp.tools import handle_list_tools
        result = await handle_list_tools({}, tmp_path)
        data = json.loads(result[0].text)
        # Step 4 后有 14 个工具（3 基础 + 4 Context + 5 Skill + 2 Patch）
        assert data["data"]["total"] == 24
    @pytest.mark.asyncio
    async def test_version_marks_step2_as_available(self, tmp_path):
        from smartdev.mcp.tools import handle_version
        result = await handle_version({}, tmp_path)
        data = json.loads(result[0].text)
        tools_map = {t["name"]: t for t in data["data"]["tools"]}
        assert tools_map["smartdev_code_search"]["status"] == "available"
        assert tools_map["smartdev_code_impact"]["status"] == "available"
        assert tools_map["smartdev_project_map"]["status"] == "available"
        assert tools_map["smartdev_graph_validate"]["status"] == "available"


# ── Server 工具注册验证 ───────────────────────────────────────────


class TestServerToolsRegistration:
    def test_server_has_step2_tools(self, tmp_path):
        from smartdev.mcp.server import create_server
        server = create_server(tmp_path)
        # server 不直接暴露工具列表，通过 _TOOLS 间接验证
        # 此测试主要确保 create_server 不抛出异常
        assert server is not None
