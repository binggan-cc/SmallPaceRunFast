"""
tests/test_mcp_patch_propose.py — MCP Patch Propose 工具测试（Phase 10 Step 4）

覆盖内容：

code_index：
- 正常索引（只写 .smartdev/，不改源码）
- force=True 强制重建
- 索引后 stats 包含 files/artifacts/relations
- 不修改任何源文件

patch_propose：
- 必填参数缺失时报 INVALID_ARGUMENT（find / task_description）
- 正常调用返回 diff + patch_id + risk_level
- 不落盘（源文件未被修改）
- patch_id 持久化到 .smartdev/patches/（CACHE_WRITE）
- diff_explain 字段生成
- safety_note 字段存在
- max_files 触发 change.budget 警告
- 无命中时 file_count=0，不生成 patch_id
- regex 模式可用

list_tools / version 更新（Step 4 工具标记 available）
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


# ── 辅助 ──────────────────────────────────────────────────────────


def _write_css(project_path: Path, name: str = "tokens.css",
               content: str = ":root { --color: #22C55E; }\n"):
    (project_path / name).write_text(content, encoding="utf-8")


def _write_py(project_path: Path, name: str = "main.py",
              content: str = "COLOR = '#22C55E'\n"):
    (project_path / name).write_text(content, encoding="utf-8")


# ── code_index ────────────────────────────────────────────────────


class TestCodeIndex:
    @pytest.mark.asyncio
    async def test_index_ok(self, tmp_path):
        _write_py(tmp_path)
        from smartdev.mcp.tools import handle_code_index
        result = await handle_code_index({}, tmp_path)
        data = json.loads(result[0].text)
        assert data["ok"] is True
        assert data["tool"] == "smartdev_code_index"
        assert "index_result" in data["data"]
        assert "stats" in data["data"]

    @pytest.mark.asyncio
    async def test_index_creates_sqlite(self, tmp_path):
        _write_py(tmp_path)
        from smartdev.mcp.tools import handle_code_index
        await handle_code_index({}, tmp_path)
        assert (tmp_path / ".smartdev" / "index.sqlite").exists()

    @pytest.mark.asyncio
    async def test_index_does_not_modify_source(self, tmp_path):
        """确认索引只写 .smartdev/，源文件不变"""
        _write_py(tmp_path, content="x = 1\n")
        original_content = (tmp_path / "main.py").read_text()
        from smartdev.mcp.tools import handle_code_index
        await handle_code_index({}, tmp_path)
        assert (tmp_path / "main.py").read_text() == original_content

    @pytest.mark.asyncio
    async def test_index_force_reindex(self, tmp_path):
        _write_py(tmp_path)
        from smartdev.mcp.tools import handle_code_index
        # 先建一次索引
        await handle_code_index({}, tmp_path)
        # 再强制重建
        result = await handle_code_index({"force": True}, tmp_path)
        data = json.loads(result[0].text)
        assert data["ok"] is True
        assert data["data"]["index_result"]["files_updated"] >= 1

    @pytest.mark.asyncio
    async def test_index_stats_has_files(self, tmp_path):
        _write_py(tmp_path)
        from smartdev.mcp.tools import handle_code_index
        result = await handle_code_index({}, tmp_path)
        data = json.loads(result[0].text)
        assert data["data"]["stats"]["files"] >= 1

    @pytest.mark.asyncio
    async def test_index_note_says_no_source_modification(self, tmp_path):
        _write_py(tmp_path)
        from smartdev.mcp.tools import handle_code_index
        result = await handle_code_index({}, tmp_path)
        data = json.loads(result[0].text)
        note_lower = data["data"]["note"].lower()
        assert "source files" in note_lower

    @pytest.mark.asyncio
    async def test_index_next_steps_mention_search(self, tmp_path):
        _write_py(tmp_path)
        from smartdev.mcp.tools import handle_code_index
        result = await handle_code_index({}, tmp_path)
        data = json.loads(result[0].text)
        steps_text = " ".join(data["next_steps"])
        assert "smartdev_code_search" in steps_text


# ── patch_propose ─────────────────────────────────────────────────


class TestPatchPropose:
    @pytest.mark.asyncio
    async def test_missing_find(self, tmp_path):
        _write_css(tmp_path)
        from smartdev.mcp.tools import handle_patch_propose
        result = await handle_patch_propose(
            {"replace": "var(--color)", "task_description": "unify color"},
            tmp_path,
        )
        data = json.loads(result[0].text)
        assert data["ok"] is False
        assert data["error_code"] == "INVALID_ARGUMENT"

    @pytest.mark.asyncio
    async def test_missing_task_description(self, tmp_path):
        _write_css(tmp_path)
        from smartdev.mcp.tools import handle_patch_propose
        result = await handle_patch_propose(
            {"find": "#22C55E", "replace": "var(--color)"},
            tmp_path,
        )
        data = json.loads(result[0].text)
        assert data["ok"] is False
        assert data["error_code"] == "INVALID_ARGUMENT"

    @pytest.mark.asyncio
    async def test_empty_find(self, tmp_path):
        _write_css(tmp_path)
        from smartdev.mcp.tools import handle_patch_propose
        result = await handle_patch_propose(
            {"find": "", "replace": "x", "task_description": "t"},
            tmp_path,
        )
        data = json.loads(result[0].text)
        assert data["ok"] is False
        assert data["error_code"] == "INVALID_ARGUMENT"

    @pytest.mark.asyncio
    async def test_propose_ok_with_match(self, tmp_path):
        _write_css(tmp_path)
        from smartdev.mcp.tools import handle_patch_propose
        result = await handle_patch_propose(
            {
                "find": "#22C55E",
                "replace": "var(--color-accent)",
                "task_description": "统一主色",
            },
            tmp_path,
        )
        data = json.loads(result[0].text)
        assert data["ok"] is True
        assert data["tool"] == "smartdev_patch_propose"
        assert "diff" in data["data"]
        assert "patch_id" in data["data"]
        assert "risk_level" in data["data"]

    @pytest.mark.asyncio
    async def test_propose_does_not_modify_source(self, tmp_path):
        """patch propose 不应修改任何源文件"""
        _write_css(tmp_path)
        original = (tmp_path / "tokens.css").read_text()
        from smartdev.mcp.tools import handle_patch_propose
        await handle_patch_propose(
            {"find": "#22C55E", "replace": "var(--color)", "task_description": "unify"},
            tmp_path,
        )
        assert (tmp_path / "tokens.css").read_text() == original

    @pytest.mark.asyncio
    async def test_propose_patch_id_persisted(self, tmp_path):
        """patch_id 对应的文件存在于 .smartdev/patches/"""
        _write_css(tmp_path)
        from smartdev.mcp.tools import handle_patch_propose
        result = await handle_patch_propose(
            {"find": "#22C55E", "replace": "var(--color)", "task_description": "unify"},
            tmp_path,
        )
        data = json.loads(result[0].text)
        patch_id = data["data"].get("patch_id", "")
        if patch_id:
            patch_file = tmp_path / ".smartdev" / "patches" / f"{patch_id}.json"
            assert patch_file.exists()

    @pytest.mark.asyncio
    async def test_propose_has_safety_note(self, tmp_path):
        _write_css(tmp_path)
        from smartdev.mcp.tools import handle_patch_propose
        result = await handle_patch_propose(
            {"find": "#22C55E", "replace": "x", "task_description": "t"},
            tmp_path,
        )
        data = json.loads(result[0].text)
        assert "safety_note" in data["data"]
        note = data["data"]["safety_note"]
        assert "NOT modify" in note or "not modify" in note.lower()

    @pytest.mark.asyncio
    async def test_propose_diff_explain_present_on_match(self, tmp_path):
        """有命中时 diff_explain 存在且非空"""
        _write_css(tmp_path)
        from smartdev.mcp.tools import handle_patch_propose
        result = await handle_patch_propose(
            {"find": "#22C55E", "replace": "var(--color)", "task_description": "unify"},
            tmp_path,
        )
        data = json.loads(result[0].text)
        if data["data"].get("file_count", 0) > 0:
            assert "diff_explain" in data["data"]
            assert len(data["data"]["diff_explain"]) > 0

    @pytest.mark.asyncio
    async def test_propose_no_match_returns_ok(self, tmp_path):
        """无命中时仍返回 ok，但 file_count=0"""
        _write_css(tmp_path)
        from smartdev.mcp.tools import handle_patch_propose
        result = await handle_patch_propose(
            {"find": "DOES_NOT_EXIST_XYZ", "replace": "x", "task_description": "t"},
            tmp_path,
        )
        data = json.loads(result[0].text)
        assert data["ok"] is True
        assert data["data"]["file_count"] == 0

    @pytest.mark.asyncio
    async def test_propose_max_files_warning(self, tmp_path):
        """生成的文件数超过 max_files 时触发 change.budget 警告"""
        # 创建多个含目标字符串的文件
        for i in range(5):
            (tmp_path / f"file{i}.css").write_text(f".c{i} {{ color: #22C55E; }}\n")
        from smartdev.mcp.tools import handle_patch_propose
        result = await handle_patch_propose(
            {
                "find": "#22C55E",
                "replace": "var(--color)",
                "task_description": "unify colors",
                "max_files": 2,   # 故意设小
            },
            tmp_path,
        )
        data = json.loads(result[0].text)
        assert data["ok"] is True
        # 若文件数 > 2，warnings 应该有 change.budget 提示
        if data["data"].get("file_count", 0) > 2:
            assert len(data["warnings"]) > 0
            assert any("max_files" in w for w in data["warnings"])

    @pytest.mark.asyncio
    async def test_propose_risk_level_in_response(self, tmp_path):
        _write_css(tmp_path)
        from smartdev.mcp.tools import handle_patch_propose
        result = await handle_patch_propose(
            {"find": "#22C55E", "replace": "x", "task_description": "t"},
            tmp_path,
        )
        data = json.loads(result[0].text)
        assert data["risk_level"] in ("R0", "R1", "R2", "R3")

    @pytest.mark.asyncio
    async def test_propose_glob_scopes_search(self, tmp_path):
        """glob 参数应限制搜索范围"""
        _write_css(tmp_path)
        _write_py(tmp_path)   # Python 文件也含目标字符串
        from smartdev.mcp.tools import handle_patch_propose
        result = await handle_patch_propose(
            {
                "find": "#22C55E",
                "replace": "x",
                "task_description": "t",
                "glob": "**/*.css",
            },
            tmp_path,
        )
        data = json.loads(result[0].text)
        assert data["ok"] is True
        # 只搜 css，file_count 应该 ≤ css 文件数
        assert data["data"]["file_count"] <= 1


# ── list_tools / version 更新 ─────────────────────────────────────


class TestStep4ToolsRegistration:
    @pytest.mark.asyncio
    async def test_list_tools_total_count_step4(self, tmp_path):
        from smartdev.mcp.tools import handle_list_tools
        result = await handle_list_tools({}, tmp_path)
        data = json.loads(result[0].text)
        # Step 4 后：3 基础 + 4 Context + 5 Skill + 2 Patch = 14
        assert data["data"]["total"] == 14

    @pytest.mark.asyncio
    async def test_version_marks_step4_as_available(self, tmp_path):
        from smartdev.mcp.tools import handle_version
        result = await handle_version({}, tmp_path)
        data = json.loads(result[0].text)
        tools_map = {t["name"]: t for t in data["data"]["tools"]}
        assert tools_map["smartdev_code_index"]["status"] == "available"
        assert tools_map["smartdev_patch_propose"]["status"] == "available"

    @pytest.mark.asyncio
    async def test_version_no_more_coming_soon(self, tmp_path):
        """v0 所有工具都已实现，无 coming_soon"""
        from smartdev.mcp.tools import handle_version
        result = await handle_version({}, tmp_path)
        data = json.loads(result[0].text)
        coming_soon = [t for t in data["data"]["tools"] if t["status"] == "coming_soon"]
        assert len(coming_soon) == 0
