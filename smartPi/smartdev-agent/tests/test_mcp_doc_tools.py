"""
MCP 只读 Doc Governance 工具测试 — Phase 11C Step 7

覆盖：
1. 两个工具在 version 清单和 list_tools 中均已注册（当前 30 工具）
2. 项目路径不存在时返回 PROJECT_NOT_FOUND（不崩溃）
3. 有效项目时 handle_doc_consistency 返回成功
4. handle_doc_consistency data 包含预期字段（issue_count / issues / docs_required）
5. handle_doc_update_plan 返回成功
6. handle_doc_update_plan data 包含预期字段（update_count / update_items / no_change_items）
7. handle_doc_update_plan 接受 consistency_issues 参数
8. 工具计数为 30
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from smartdev.mcp.tools import (
    get_available_tools,
    handle_doc_consistency,
    handle_doc_update_plan,
    handle_list_tools,
    handle_version,
)


# ── Helpers ────────────────────────────────────────────────


def _parse(text_content) -> dict:
    return json.loads(text_content[0].text)


# ── 工具注册验证（通过 version / list_tools）────────────────


class TestToolRegistration:
    DOC_TOOLS = ["smartdev_doc_consistency", "smartdev_doc_update_plan"]

    @pytest.mark.asyncio
    async def test_doc_tools_in_version_list(self, tmp_path: Path):
        result = await handle_version({}, tmp_path)
        data = _parse(result)
        names = {t["name"] for t in data["data"]["tools"]}
        for tool in self.DOC_TOOLS:
            assert tool in names, f"{tool} missing from version list"

    @pytest.mark.asyncio
    async def test_total_tool_count_matches_registry(self, tmp_path: Path):
        """MCP 工具总数应与工具注册表一致。"""
        result = await handle_version({}, tmp_path)
        data = _parse(result)
        assert len(data["data"]["tools"]) == len(get_available_tools())

    @pytest.mark.asyncio
    async def test_doc_tools_in_list_tools(self, tmp_path: Path):
        result = await handle_list_tools({}, tmp_path)
        data = _parse(result)
        names = {t["name"] for t in data["data"]["available_tools"]}
        for tool in self.DOC_TOOLS:
            assert tool in names, f"{tool} missing from list_tools"

    @pytest.mark.asyncio
    async def test_doc_consistency_permission_read(self, tmp_path: Path):
        result = await handle_list_tools({}, tmp_path)
        data = _parse(result)
        tools = {t["name"]: t for t in data["data"]["available_tools"]}
        assert tools["smartdev_doc_consistency"]["permission"] == "READ"

    @pytest.mark.asyncio
    async def test_doc_update_plan_permission_read(self, tmp_path: Path):
        result = await handle_list_tools({}, tmp_path)
        data = _parse(result)
        tools = {t["name"]: t for t in data["data"]["available_tools"]}
        assert tools["smartdev_doc_update_plan"]["permission"] == "READ"

    @pytest.mark.asyncio
    async def test_list_tools_total_count_matches_registry(self, tmp_path: Path):
        result = await handle_list_tools({}, tmp_path)
        data = _parse(result)
        assert data["data"]["total"] == len(get_available_tools())


# ── handle_doc_consistency ────────────────────────────────


class TestHandleDocConsistency:
    @pytest.mark.asyncio
    async def test_success_valid_project(self, tmp_path: Path):
        result = await handle_doc_consistency({}, tmp_path)
        data = _parse(result)
        assert data["ok"] is True

    @pytest.mark.asyncio
    async def test_data_has_issue_count(self, tmp_path: Path):
        result = await handle_doc_consistency({}, tmp_path)
        data = _parse(result)
        assert "issue_count" in data["data"]

    @pytest.mark.asyncio
    async def test_data_has_issues_list(self, tmp_path: Path):
        result = await handle_doc_consistency({}, tmp_path)
        data = _parse(result)
        assert "issues" in data["data"]
        assert isinstance(data["data"]["issues"], list)

    @pytest.mark.asyncio
    async def test_data_has_docs_required(self, tmp_path: Path):
        result = await handle_doc_consistency({}, tmp_path)
        data = _parse(result)
        assert "docs_required" in data["data"]

    @pytest.mark.asyncio
    async def test_data_has_severity_summary(self, tmp_path: Path):
        result = await handle_doc_consistency({}, tmp_path)
        data = _parse(result)
        assert "severity_summary" in data["data"]

    @pytest.mark.asyncio
    async def test_data_has_generated_at(self, tmp_path: Path):
        result = await handle_doc_consistency({}, tmp_path)
        data = _parse(result)
        assert "generated_at" in data["data"]

    @pytest.mark.asyncio
    async def test_nonexistent_project_returns_error(self):
        bad_path = Path("/nonexistent/path/xyz_smartdev_test")
        result = await handle_doc_consistency({}, bad_path)
        data = _parse(result)
        assert data["ok"] is False

    @pytest.mark.asyncio
    async def test_accepts_change_manifest_arg(self, tmp_path: Path):
        """传入 change_manifest 参数不崩溃。"""
        manifest = {
            "public_surface_changed": True,
            "timestamp": "2026-06-08T00:00:00Z",
            "changed_files": ["smartdev/cli.py"],
        }
        result = await handle_doc_consistency({"change_manifest": manifest}, tmp_path)
        data = _parse(result)
        assert data["ok"] is True


# ── handle_doc_update_plan ────────────────────────────────


class TestHandleDocUpdatePlan:
    @pytest.mark.asyncio
    async def test_success_valid_project(self, tmp_path: Path):
        result = await handle_doc_update_plan({}, tmp_path)
        data = _parse(result)
        assert data["ok"] is True

    @pytest.mark.asyncio
    async def test_data_has_update_count(self, tmp_path: Path):
        result = await handle_doc_update_plan({}, tmp_path)
        data = _parse(result)
        assert "update_count" in data["data"]

    @pytest.mark.asyncio
    async def test_data_has_update_items(self, tmp_path: Path):
        result = await handle_doc_update_plan({}, tmp_path)
        data = _parse(result)
        assert "update_items" in data["data"]
        assert isinstance(data["data"]["update_items"], list)

    @pytest.mark.asyncio
    async def test_data_has_no_change_items(self, tmp_path: Path):
        result = await handle_doc_update_plan({}, tmp_path)
        data = _parse(result)
        assert "no_change_items" in data["data"]

    @pytest.mark.asyncio
    async def test_data_has_generated_at(self, tmp_path: Path):
        result = await handle_doc_update_plan({}, tmp_path)
        data = _parse(result)
        assert "generated_at" in data["data"]

    @pytest.mark.asyncio
    async def test_nonexistent_project_returns_error(self):
        bad_path = Path("/nonexistent/path/xyz_smartdev_test")
        result = await handle_doc_update_plan({}, bad_path)
        data = _parse(result)
        assert data["ok"] is False

    @pytest.mark.asyncio
    async def test_accepts_empty_consistency_issues(self, tmp_path: Path):
        """传入空 consistency_issues 时 update_count=0。"""
        result = await handle_doc_update_plan({"consistency_issues": []}, tmp_path)
        data = _parse(result)
        assert data["ok"] is True
        assert data["data"]["update_count"] == 0

    @pytest.mark.asyncio
    async def test_consistency_issues_drives_plan(self, tmp_path: Path):
        """传入有效 issues 时 update_plan 应包含对应 update_items。"""
        issues = [{
            "rule": "rule4",
            "type": "stale_test_baseline",
            "severity": "low",
            "doc": "CLAUDE.md",
            "code_fact": "1145 passed",
            "doc_claim": "637 passed",
        }]
        result = await handle_doc_update_plan({"consistency_issues": issues}, tmp_path)
        data = _parse(result)
        assert data["ok"] is True
        update_docs = [i["doc"] for i in data["data"]["update_items"]]
        assert "CLAUDE.md" in update_docs

    @pytest.mark.asyncio
    async def test_non_list_consistency_issues_ignored(self, tmp_path: Path):
        """consistency_issues 传了非 list 类型时不崩溃（忽略，自动运行）。"""
        result = await handle_doc_update_plan(
            {"consistency_issues": "not a list"}, tmp_path
        )
        data = _parse(result)
        assert data["ok"] is True
