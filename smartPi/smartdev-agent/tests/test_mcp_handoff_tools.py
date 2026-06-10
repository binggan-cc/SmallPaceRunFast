"""
MCP Handoff Pack 工具测试 — Phase 11D Step 7

覆盖：
1. 三个工具在 version/list_tools 中已注册（当前 30 工具）
2. handle_handoff_code 成功路径 + 缺失 run_id
3. handle_handoff_doc 成功路径 + 缺失 run_id
4. handle_handoff_review 成功路径 + 缺失 run_id
5. run 目录不存在时返回 GENERATION_FAILED（不崩溃）
6. 工具只写 .smartdev/runs/（不修改源码）
7. 工具权限为 CACHE_WRITE
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from smartdev.core.run_artifact import ScopeConfig, create_run_artifact
from smartdev.mcp.tools import (
    handle_handoff_code,
    handle_handoff_doc,
    handle_handoff_review,
    handle_list_tools,
    handle_version,
)


def _parse(text_content) -> dict:
    return json.loads(text_content[0].text)


def _setup_run(tmp_path: Path, run_id: str = "mcp-handoff"):
    """创建 run artifact + 最小项目骨架。"""
    scope = ScopeConfig(allowed_paths=["smartdev/", "tests/"])
    _, err = create_run_artifact(tmp_path, run_id, scope=scope, force=True)
    if err:
        raise RuntimeError(f"Failed: {err}")
    (tmp_path / "CLAUDE.md").write_text("# C\n\n## 当前阶段\n\nPhase 11D\n", encoding="utf-8")
    (tmp_path / "smartdev").mkdir(exist_ok=True)
    (tmp_path / "smartdev" / "__init__.py").write_text("")


# ── 工具注册验证 ──────────────────────────────────────────────


class TestHandoffToolRegistration:
    TOOLS = ["smartdev_handoff_code", "smartdev_handoff_doc", "smartdev_handoff_review"]

    @pytest.mark.asyncio
    async def test_handoff_tools_in_version_list(self, tmp_path: Path):
        result = await handle_version({}, tmp_path)
        data = _parse(result)
        names = {t["name"] for t in data["data"]["tools"]}
        for tool in self.TOOLS:
            assert tool in names, f"{tool} missing from version list"

    @pytest.mark.asyncio
    async def test_total_tool_count_30(self, tmp_path: Path):
        result = await handle_version({}, tmp_path)
        data = _parse(result)
        assert len(data["data"]["tools"]) == 30

    @pytest.mark.asyncio
    async def test_handoff_tools_in_list_tools(self, tmp_path: Path):
        result = await handle_list_tools({}, tmp_path)
        data = _parse(result)
        names = {t["name"] for t in data["data"]["available_tools"]}
        for tool in self.TOOLS:
            assert tool in names, f"{tool} missing from list_tools"

    @pytest.mark.asyncio
    async def test_handoff_code_permission_cache_write(self, tmp_path: Path):
        result = await handle_list_tools({}, tmp_path)
        data = _parse(result)
        tools = {t["name"]: t for t in data["data"]["available_tools"]}
        assert tools["smartdev_handoff_code"]["permission"] == "CACHE_WRITE"

    @pytest.mark.asyncio
    async def test_handoff_doc_permission_cache_write(self, tmp_path: Path):
        result = await handle_list_tools({}, tmp_path)
        data = _parse(result)
        tools = {t["name"]: t for t in data["data"]["available_tools"]}
        assert tools["smartdev_handoff_doc"]["permission"] == "CACHE_WRITE"

    @pytest.mark.asyncio
    async def test_handoff_review_permission_cache_write(self, tmp_path: Path):
        result = await handle_list_tools({}, tmp_path)
        data = _parse(result)
        tools = {t["name"]: t for t in data["data"]["available_tools"]}
        assert tools["smartdev_handoff_review"]["permission"] == "CACHE_WRITE"


# ── handle_handoff_code ───────────────────────────────────────


class TestHandleHandoffCode:
    @pytest.mark.asyncio
    async def test_success(self, tmp_path: Path):
        _setup_run(tmp_path, "hc1")
        result = await handle_handoff_code({"run_id": "hc1"}, tmp_path)
        data = _parse(result)
        assert data["ok"] is True
        assert data["data"]["run_id"] == "hc1"
        assert "note" in data["data"]
        assert "output_path" in data["data"]
        assert data["data"]["char_count"] > 0
        assert "skipped" in data["data"]

    @pytest.mark.asyncio
    async def test_missing_run_id(self, tmp_path: Path):
        result = await handle_handoff_code({}, tmp_path)
        data = _parse(result)
        assert data["ok"] is False
        assert data["error_code"] == "INVALID_ARGUMENT"

    @pytest.mark.asyncio
    async def test_nonexistent_run_dir(self, tmp_path: Path):
        result = await handle_handoff_code({"run_id": "no-such"}, tmp_path)
        data = _parse(result)
        assert data["ok"] is False
        assert data["error_code"] == "GENERATION_FAILED"

    @pytest.mark.asyncio
    async def test_writes_only_to_smartdev_runs(self, tmp_path: Path):
        _setup_run(tmp_path, "hc4")
        before = {str(f.relative_to(tmp_path)) for f in tmp_path.rglob("*")
                  if f.is_file() and ".smartdev" not in str(f)}
        await handle_handoff_code({"run_id": "hc4"}, tmp_path)
        after = {str(f.relative_to(tmp_path)) for f in tmp_path.rglob("*")
                 if f.is_file() and ".smartdev" not in str(f)}
        assert before == after  # 源码无变化

    @pytest.mark.asyncio
    async def test_pack_file_created(self, tmp_path: Path):
        _setup_run(tmp_path, "hc5")
        await handle_handoff_code({"run_id": "hc5"}, tmp_path)
        pack = tmp_path / ".smartdev" / "runs" / "hc5" / "handoff" / "code-agent-pack.md"
        assert pack.exists()


# ── handle_handoff_doc ────────────────────────────────────────


class TestHandleHandoffDoc:
    @pytest.mark.asyncio
    async def test_success(self, tmp_path: Path):
        _setup_run(tmp_path, "hd1")
        result = await handle_handoff_doc({"run_id": "hd1"}, tmp_path)
        data = _parse(result)
        assert data["ok"] is True
        assert data["data"]["run_id"] == "hd1"
        assert "note" in data["data"]
        assert "output_path" in data["data"]
        assert "skipped" in data["data"]

    @pytest.mark.asyncio
    async def test_missing_run_id(self, tmp_path: Path):
        result = await handle_handoff_doc({}, tmp_path)
        data = _parse(result)
        assert data["ok"] is False
        assert data["error_code"] == "INVALID_ARGUMENT"

    @pytest.mark.asyncio
    async def test_nonexistent_run_dir(self, tmp_path: Path):
        result = await handle_handoff_doc({"run_id": "no-such"}, tmp_path)
        data = _parse(result)
        assert data["ok"] is False
        assert data["error_code"] == "GENERATION_FAILED"

    @pytest.mark.asyncio
    async def test_pack_file_created(self, tmp_path: Path):
        _setup_run(tmp_path, "hd4")
        await handle_handoff_doc({"run_id": "hd4"}, tmp_path)
        pack = tmp_path / ".smartdev" / "runs" / "hd4" / "handoff" / "doc-steward-pack.md"
        assert pack.exists()


# ── handle_handoff_review ─────────────────────────────────────


class TestHandleHandoffReview:
    @pytest.mark.asyncio
    async def test_success(self, tmp_path: Path):
        _setup_run(tmp_path, "hr1")
        result = await handle_handoff_review({"run_id": "hr1"}, tmp_path)
        data = _parse(result)
        assert data["ok"] is True
        assert data["data"]["run_id"] == "hr1"
        assert "note" in data["data"]
        assert "output_path" in data["data"]
        assert "skipped" in data["data"]

    @pytest.mark.asyncio
    async def test_missing_run_id(self, tmp_path: Path):
        result = await handle_handoff_review({}, tmp_path)
        data = _parse(result)
        assert data["ok"] is False
        assert data["error_code"] == "INVALID_ARGUMENT"

    @pytest.mark.asyncio
    async def test_nonexistent_run_dir(self, tmp_path: Path):
        result = await handle_handoff_review({"run_id": "no-such"}, tmp_path)
        data = _parse(result)
        assert data["ok"] is False
        assert data["error_code"] == "GENERATION_FAILED"

    @pytest.mark.asyncio
    async def test_pack_file_created(self, tmp_path: Path):
        _setup_run(tmp_path, "hr4")
        await handle_handoff_review({"run_id": "hr4"}, tmp_path)
        pack = tmp_path / ".smartdev" / "runs" / "hr4" / "handoff" / "reviewer-pack.md"
        assert pack.exists()
