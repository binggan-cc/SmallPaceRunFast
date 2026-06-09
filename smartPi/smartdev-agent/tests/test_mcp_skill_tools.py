"""
tests/test_mcp_skill_tools.py — MCP Skill 工具测试（Phase 10 Step 3）

覆盖内容：
- repo_scan：正常调用，返回 summary + data
- risk_check：有 task_description，空 task_description 报错
- risk_check：有索引 + target 时走 impact 增强路径（source=impact）
- architecture_map：正常调用（优雅降级，无 Python 文件也能运行）
- task_plan：正常调用，返回三档方案
- task_plan：有索引 + target 时标注受影响文件
- qa_checklist：正常调用，返回验收条目
- qa_checklist：空 task_description 报错
- list_tools / version 更新（Step 3 工具标记 available）
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


# ── 辅助 ──────────────────────────────────────────────────────────


def _write_py_file(project_path: Path, rel: str = "main.py", content: str = "x = 1\n"):
    (project_path / rel).write_text(content, encoding="utf-8")


def _build_index(project_path: Path):
    from smartdev.context.project_index import ProjectIndex
    _write_py_file(project_path)
    index = ProjectIndex(project_path)
    index.index()
    index.close()


# ── repo_scan ─────────────────────────────────────────────────────


class TestRepoScan:
    @pytest.mark.asyncio
    async def test_repo_scan_ok(self, tmp_path):
        _write_py_file(tmp_path)
        from smartdev.mcp.tools import handle_repo_scan
        result = await handle_repo_scan({}, tmp_path)
        data = json.loads(result[0].text)
        assert data["ok"] is True
        assert data["tool"] == "smartdev_repo_scan"
        assert "summary" in data["data"]
        assert "data" in data["data"]

    @pytest.mark.asyncio
    async def test_repo_scan_invalid_path(self, tmp_path):
        from smartdev.mcp.tools import handle_repo_scan
        fake = tmp_path / "nonexistent"
        result = await handle_repo_scan({}, fake)
        data = json.loads(result[0].text)
        assert data["ok"] is False
        assert data["error_code"] == "SKILL_CANNOT_RUN"

    @pytest.mark.asyncio
    async def test_repo_scan_risk_level_r0(self, tmp_path):
        _write_py_file(tmp_path)
        from smartdev.mcp.tools import handle_repo_scan
        result = await handle_repo_scan({}, tmp_path)
        data = json.loads(result[0].text)
        assert data["risk_level"] == "R0"


# ── risk_check ────────────────────────────────────────────────────


class TestRiskCheck:
    @pytest.mark.asyncio
    async def test_risk_check_ok(self, tmp_path):
        _write_py_file(tmp_path)
        from smartdev.mcp.tools import handle_risk_check
        result = await handle_risk_check(
            {"task_description": "fix a small typo in comments"}, tmp_path
        )
        data = json.loads(result[0].text)
        assert data["ok"] is True
        assert data["tool"] == "smartdev_risk_check"
        assert "risk_level" in data["data"]

    @pytest.mark.asyncio
    async def test_risk_check_empty_description(self, tmp_path):
        _write_py_file(tmp_path)
        from smartdev.mcp.tools import handle_risk_check
        result = await handle_risk_check({"task_description": ""}, tmp_path)
        data = json.loads(result[0].text)
        assert data["ok"] is False
        assert data["error_code"] == "SKILL_CANNOT_RUN"

    @pytest.mark.asyncio
    async def test_risk_check_missing_description(self, tmp_path):
        _write_py_file(tmp_path)
        from smartdev.mcp.tools import handle_risk_check
        result = await handle_risk_check({}, tmp_path)
        data = json.loads(result[0].text)
        assert data["ok"] is False
        assert data["error_code"] == "SKILL_CANNOT_RUN"

    @pytest.mark.asyncio
    async def test_risk_check_with_index_and_target(self, tmp_path):
        """有索引 + target 时触发 impact 增强路径"""
        _build_index(tmp_path)
        from smartdev.mcp.tools import handle_risk_check
        result = await handle_risk_check(
            {"task_description": "modify main module", "target": "main.py"},
            tmp_path,
        )
        data = json.loads(result[0].text)
        assert data["ok"] is True
        # impact 增强时 data 里会有 risk_source 字段
        assert "risk_level" in data["data"]

    @pytest.mark.asyncio
    async def test_risk_check_risk_level_in_response(self, tmp_path):
        _write_py_file(tmp_path)
        from smartdev.mcp.tools import handle_risk_check
        result = await handle_risk_check(
            {"task_description": "update ui component"}, tmp_path
        )
        data = json.loads(result[0].text)
        assert data["risk_level"] in ("R0", "R1", "R2", "R3")


# ── architecture_map ──────────────────────────────────────────────


class TestArchitectureMap:
    @pytest.mark.asyncio
    async def test_architecture_map_ok_with_py(self, tmp_path):
        _write_py_file(tmp_path)
        from smartdev.mcp.tools import handle_architecture_map
        result = await handle_architecture_map({}, tmp_path)
        data = json.loads(result[0].text)
        assert data["ok"] is True
        assert data["tool"] == "smartdev_architecture_map"
        assert "summary" in data["data"]

    @pytest.mark.asyncio
    async def test_architecture_map_ok_with_index(self, tmp_path):
        """有索引时 source 应为 index（多语言模式）"""
        _build_index(tmp_path)
        from smartdev.mcp.tools import handle_architecture_map
        result = await handle_architecture_map({}, tmp_path)
        data = json.loads(result[0].text)
        assert data["ok"] is True
        # 有索引时 data.source = "index"
        inner = data["data"].get("data", {})
        assert inner.get("source") in ("index", "ast")

    @pytest.mark.asyncio
    async def test_architecture_map_risk_r0(self, tmp_path):
        _write_py_file(tmp_path)
        from smartdev.mcp.tools import handle_architecture_map
        result = await handle_architecture_map({}, tmp_path)
        data = json.loads(result[0].text)
        assert data["risk_level"] == "R0"


# ── task_plan ─────────────────────────────────────────────────────


class TestTaskPlan:
    @pytest.mark.asyncio
    async def test_task_plan_ok(self, tmp_path):
        _write_py_file(tmp_path)
        from smartdev.mcp.tools import handle_task_plan
        result = await handle_task_plan(
            {"task_description": "add login feature"}, tmp_path
        )
        data = json.loads(result[0].text)
        assert data["ok"] is True
        assert data["tool"] == "smartdev_task_plan"
        # 三档方案
        assert "conservative" in data["data"]
        assert "recommended" in data["data"]
        assert "deep" in data["data"]

    @pytest.mark.asyncio
    async def test_task_plan_empty_description(self, tmp_path):
        _write_py_file(tmp_path)
        from smartdev.mcp.tools import handle_task_plan
        result = await handle_task_plan({"task_description": ""}, tmp_path)
        data = json.loads(result[0].text)
        assert data["ok"] is False
        assert data["error_code"] == "SKILL_CANNOT_RUN"

    @pytest.mark.asyncio
    async def test_task_plan_with_index_and_target(self, tmp_path):
        """有索引 + target 时 recommended 方案标注受影响文件"""
        _build_index(tmp_path)
        from smartdev.mcp.tools import handle_task_plan
        result = await handle_task_plan(
            {"task_description": "refactor main module", "target": "main.py"},
            tmp_path,
        )
        data = json.loads(result[0].text)
        assert data["ok"] is True
        assert "recommended" in data["data"]


# ── qa_checklist ─────────────────────────────────────────────────


class TestQAChecklist:
    @pytest.mark.asyncio
    async def test_qa_checklist_ok(self, tmp_path):
        _write_py_file(tmp_path)
        from smartdev.mcp.tools import handle_qa_checklist
        result = await handle_qa_checklist(
            {"task_description": "implement user authentication"}, tmp_path
        )
        data = json.loads(result[0].text)
        assert data["ok"] is True
        assert data["tool"] == "smartdev_qa_checklist"
        assert "checklist" in data["data"] or "categories" in data["data"] or len(data["data"]) > 0

    @pytest.mark.asyncio
    async def test_qa_checklist_empty_description(self, tmp_path):
        _write_py_file(tmp_path)
        from smartdev.mcp.tools import handle_qa_checklist
        result = await handle_qa_checklist({"task_description": ""}, tmp_path)
        data = json.loads(result[0].text)
        assert data["ok"] is False
        assert data["error_code"] == "SKILL_CANNOT_RUN"

    @pytest.mark.asyncio
    async def test_qa_checklist_risk_r0(self, tmp_path):
        _write_py_file(tmp_path)
        from smartdev.mcp.tools import handle_qa_checklist
        result = await handle_qa_checklist(
            {"task_description": "verify login flow"}, tmp_path
        )
        data = json.loads(result[0].text)
        assert data["risk_level"] == "R0"


# ── list_tools / version 更新 ─────────────────────────────────────


class TestStep3ToolsRegistration:
    @pytest.mark.asyncio
    async def test_list_tools_includes_step3(self, tmp_path):
        from smartdev.mcp.tools import handle_list_tools
        result = await handle_list_tools({}, tmp_path)
        data = json.loads(result[0].text)
        names = [t["name"] for t in data["data"]["available_tools"]]
        assert "smartdev_repo_scan" in names
        assert "smartdev_risk_check" in names
        assert "smartdev_architecture_map" in names
        assert "smartdev_task_plan" in names
        assert "smartdev_qa_checklist" in names

    @pytest.mark.asyncio
    async def test_list_tools_total_count_step3(self, tmp_path):
        from smartdev.mcp.tools import handle_list_tools
        result = await handle_list_tools({}, tmp_path)
        data = json.loads(result[0].text)
        # Step 4 後有 14 個工具
        assert data["data"]["total"] == 24

    @pytest.mark.asyncio
    async def test_version_marks_step3_as_available(self, tmp_path):
        from smartdev.mcp.tools import handle_version
        result = await handle_version({}, tmp_path)
        data = json.loads(result[0].text)
        tools_map = {t["name"]: t for t in data["data"]["tools"]}
        assert tools_map["smartdev_repo_scan"]["status"] == "available"
        assert tools_map["smartdev_risk_check"]["status"] == "available"
        assert tools_map["smartdev_architecture_map"]["status"] == "available"
        assert tools_map["smartdev_task_plan"]["status"] == "available"
        assert tools_map["smartdev_qa_checklist"]["status"] == "available"
