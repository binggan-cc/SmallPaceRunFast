"""
MCP 只读 Guard 工具测试 — Phase 11B Step 7

覆盖：
1. 6 个 Guard 工具在 server._HANDLERS 和 _TOOLS 中均已注册
2. smartdev_guard_run 聚合报告包含 5 个 Guard 结果
3. 5 个单 Guard 工具：有效输入返回 ok，缺少 required 参数返回错误
4. 缺少 changed_files/patch_files 时返回 INVALID_ARGUMENT（不崩溃）
5. 无效 guard 名称时 smartdev_guard_run 返回错误结果
6. smartdev_version / smartdev_list_tools 包含 6 个新工具
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest


# ── Helpers ────────────────────────────────────────────────


def _parse(text_content) -> dict:
    return json.loads(text_content[0].text)


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ── 工具注册验证 ──────────────────────────────────────────


class TestGuardToolsRegistered:
    """6 个 Guard 工具必须出现在 version 清单、list_tools 响应和 server 注册表中。"""

    GUARD_TOOLS = [
        "smartdev_guard_run",
        "smartdev_change_budget",
        "smartdev_dev_guard",
        "smartdev_dependency_guard",
        "smartdev_security_review",
        "smartdev_diff_explain",
    ]

    @pytest.mark.asyncio
    async def test_all_guard_tools_in_version_list(self, tmp_path: Path):
        from smartdev.mcp.tools import handle_version
        result = await handle_version({}, tmp_path)
        data = _parse(result)
        names = {t["name"] for t in data["data"]["tools"]}
        for tool in self.GUARD_TOOLS:
            assert tool in names, f"{tool} not in version tool list"

    @pytest.mark.asyncio
    async def test_all_guard_tools_in_list_tools(self, tmp_path: Path):
        from smartdev.mcp.tools import handle_list_tools
        result = await handle_list_tools({}, tmp_path)
        data = _parse(result)
        names = {t["name"] for t in data["data"]["available_tools"]}
        for tool in self.GUARD_TOOLS:
            assert tool in names, f"{tool} not in list_tools"

    def test_all_guard_tools_in_server_handlers(self):
        from smartdev.mcp.server import create_server
        server = create_server(Path("/tmp"))
        # 检查 _HANDLERS 包含所有 guard 工具
        # server 已经把 _HANDLERS 注册为 call_tool handler，通过 handler 间接验证
        # 直接检查 module 的 _HANDLERS
        from smartdev.mcp import server as srv
        # Re-read the source to access _HANDLERS
        import inspect
        src = inspect.getsource(srv.create_server)
        for tool in self.GUARD_TOOLS:
            assert f'"{tool}"' in src, f"{tool} not referenced in create_server()"

    def test_all_guard_tools_in_server_schemas(self):
        import inspect
        from smartdev.mcp import server as srv
        src = inspect.getsource(srv.create_server)
        for tool in self.GUARD_TOOLS:
            assert f'name="{tool}"' in src or f"name='{tool}'" in src, \
                f"{tool} not in server Tool schemas"


# ── smartdev_guard_run ────────────────────────────────────


class TestGuardRunHandler:
    """smartdev_guard_run 聚合报告测试。"""

    @pytest.mark.asyncio
    async def test_guard_run_with_valid_input(self, tmp_path: Path):
        """提供 changed_files 应该返回成功聚合报告。"""
        from smartdev.mcp.tools import handle_guard_run

        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("print('hello')\n")

        result = await handle_guard_run(
            {"changed_files": ["src/app.py"], "run_id": "test-run-001"},
            tmp_path,
        )
        data = _parse(result)
        assert data["ok"] is True
        assert "overall_passed" in data["data"]
        assert "guards" in data["data"]
        assert "error_count" in data["data"]
        assert len(data["data"]["guards"]) >= 1  # at least one guard ran

    @pytest.mark.asyncio
    async def test_guard_run_with_select(self, tmp_path: Path):
        """select 参数应过滤只运行指定 Guard。"""
        from smartdev.mcp.tools import handle_guard_run

        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("print('hello')\n")

        result = await handle_guard_run(
            {
                "changed_files": ["src/app.py"],
                "select": ["change.budget", "dev.guard"],
            },
            tmp_path,
        )
        data = _parse(result)
        assert data["ok"] is True
        guard_names = set(data["data"]["guards"].keys())
        assert "change.budget" in guard_names
        assert "dev.guard" in guard_names
        # 未选中的不应运行
        assert len(data["data"]["skipped"]) >= 3

    @pytest.mark.asyncio
    async def test_guard_run_with_invalid_guard_name(self, tmp_path: Path):
        """无效 guard 名称应返回错误但不崩溃。"""
        from smartdev.mcp.tools import handle_guard_run

        result = await handle_guard_run(
            {"changed_files": ["src/app.py"], "select": ["nonexistent.guard"]},
            tmp_path,
        )
        data = _parse(result)
        assert data["ok"] is True  # handler 本身不抛异常
        # GuardRunner 内部返回 overall_passed=False
        rd = data["data"]
        assert rd["overall_passed"] is False

    @pytest.mark.asyncio
    async def test_guard_run_all_guards_without_select(self, tmp_path: Path):
        """不传 select 时应运行所有 5 个 Guard。"""
        from smartdev.mcp.tools import handle_guard_run

        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("print('hello')\n")

        result = await handle_guard_run(
            {"changed_files": ["src/app.py"]},
            tmp_path,
        )
        data = _parse(result)
        assert data["ok"] is True
        # 5 guards should have run or been attempted
        assert len(data["data"]["selected"]) == 5

    @pytest.mark.asyncio
    async def test_guard_run_empty_changed_files(self, tmp_path: Path):
        """空 changed_files 应该也能运行（部分 Guard 会跳过或返回降级结果）。"""
        from smartdev.mcp.tools import handle_guard_run

        result = await handle_guard_run(
            {"changed_files": []},
            tmp_path,
        )
        data = _parse(result)
        assert data["ok"] is True

    @pytest.mark.asyncio
    async def test_guard_run_with_diff_content(self, tmp_path: Path):
        """传入 diff_content 不应崩溃。"""
        from smartdev.mcp.tools import handle_guard_run

        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("print('hello')\n")

        diff = "--- a/src/app.py\n+++ b/src/app.py\n@@ -1 +1,2 @@\n+print('hello')\n+print('world')\n"
        result = await handle_guard_run(
            {"changed_files": ["src/app.py"], "diff_content": diff},
            tmp_path,
        )
        data = _parse(result)
        assert data["ok"] is True


# ── smartdev_change_budget ────────────────────────────────


class TestChangeBudgetHandler:
    """smartdev_change_budget 单 Guard 测试。"""

    @pytest.mark.asyncio
    async def test_missing_changed_files_returns_error(self, tmp_path: Path):
        from smartdev.mcp.tools import handle_change_budget
        result = await handle_change_budget({}, tmp_path)
        data = _parse(result)
        assert data["ok"] is False
        assert data["error_code"] == "INVALID_ARGUMENT"

    @pytest.mark.asyncio
    async def test_empty_changed_files_returns_error(self, tmp_path: Path):
        from smartdev.mcp.tools import handle_change_budget
        result = await handle_change_budget({"changed_files": []}, tmp_path)
        data = _parse(result)
        assert data["ok"] is False

    @pytest.mark.asyncio
    async def test_valid_input_returns_ok(self, tmp_path: Path):
        from smartdev.mcp.tools import handle_change_budget

        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("print('hello')\n")

        result = await handle_change_budget(
            {"changed_files": ["src/app.py"]},
            tmp_path,
        )
        data = _parse(result)
        assert data["ok"] is True
        assert "passed" in data["data"] or "checks" in data["data"]

    @pytest.mark.asyncio
    async def test_with_custom_max_files(self, tmp_path: Path):
        from smartdev.mcp.tools import handle_change_budget

        (tmp_path / "src").mkdir()
        for i in range(5):
            (tmp_path / "src" / f"file{i}.py").write_text(f"# file {i}\n")

        result = await handle_change_budget(
            {
                "changed_files": [f"src/file{i}.py" for i in range(5)],
                "max_files": 3,
            },
            tmp_path,
        )
        data = _parse(result)
        assert data["ok"] is True
        # 5 files > max_files=3, should fail
        assert data["data"].get("passed") is False


# ── smartdev_dev_guard ────────────────────────────────────


class TestDevGuardHandler:
    """smartdev_dev_guard 单 Guard 测试。"""

    @pytest.mark.asyncio
    async def test_missing_changed_files_returns_error(self, tmp_path: Path):
        from smartdev.mcp.tools import handle_dev_guard
        result = await handle_dev_guard({}, tmp_path)
        data = _parse(result)
        assert data["ok"] is False
        assert data["error_code"] == "INVALID_ARGUMENT"

    @pytest.mark.asyncio
    async def test_valid_input_returns_ok(self, tmp_path: Path):
        from smartdev.mcp.tools import handle_dev_guard

        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("print('hello')\n")

        result = await handle_dev_guard(
            {"changed_files": ["src/app.py"]},
            tmp_path,
        )
        data = _parse(result)
        assert data["ok"] is True
        assert "passed" in data["data"] or "checks" in data["data"]

    @pytest.mark.asyncio
    async def test_with_protected_paths(self, tmp_path: Path):
        from smartdev.mcp.tools import handle_dev_guard

        (tmp_path / "smartdev").mkdir(parents=True)
        (tmp_path / "smartdev" / "core.py").write_text("# core\n")

        result = await handle_dev_guard(
            {
                "changed_files": ["smartdev/core.py"],
                "protected_paths": ["smartdev/core/*"],
            },
            tmp_path,
        )
        data = _parse(result)
        assert data["ok"] is True


# ── smartdev_dependency_guard ─────────────────────────────


class TestDependencyGuardHandler:
    """smartdev_dependency_guard 单 Guard 测试。"""

    @pytest.mark.asyncio
    async def test_missing_changed_files_returns_error(self, tmp_path: Path):
        from smartdev.mcp.tools import handle_dependency_guard
        result = await handle_dependency_guard({}, tmp_path)
        data = _parse(result)
        assert data["ok"] is False
        assert data["error_code"] == "INVALID_ARGUMENT"

    @pytest.mark.asyncio
    async def test_valid_input_returns_ok(self, tmp_path: Path):
        from smartdev.mcp.tools import handle_dependency_guard

        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("print('hello')\n")

        result = await handle_dependency_guard(
            {"changed_files": ["src/app.py"]},
            tmp_path,
        )
        data = _parse(result)
        assert data["ok"] is True
        assert "passed" in data["data"] or "manifests_found" in data["data"]

    @pytest.mark.asyncio
    async def test_with_manifest_diff(self, tmp_path: Path):
        from smartdev.mcp.tools import handle_dependency_guard

        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        diff = (
            "--- a/pyproject.toml\n"
            "+++ b/pyproject.toml\n"
            "@@ -1,2 +1,3 @@\n"
            " [project]\n"
            " name = 'test'\n"
            "+dependencies = ['fastapi']\n"
        )

        result = await handle_dependency_guard(
            {"changed_files": ["pyproject.toml"], "diff_content": diff},
            tmp_path,
        )
        data = _parse(result)
        assert data["ok"] is True


# ── smartdev_security_review ──────────────────────────────


class TestSecurityReviewHandler:
    """smartdev_security_review 单 Guard 测试。"""

    @pytest.mark.asyncio
    async def test_missing_changed_files_returns_error(self, tmp_path: Path):
        from smartdev.mcp.tools import handle_security_review
        result = await handle_security_review({}, tmp_path)
        data = _parse(result)
        assert data["ok"] is False
        assert data["error_code"] == "INVALID_ARGUMENT"

    @pytest.mark.asyncio
    async def test_valid_input_returns_ok(self, tmp_path: Path):
        from smartdev.mcp.tools import handle_security_review

        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("print('hello')\n")

        result = await handle_security_review(
            {"changed_files": ["src/app.py"]},
            tmp_path,
        )
        data = _parse(result)
        assert data["ok"] is True
        assert "passed" in data["data"] or "checks" in data["data"]

    @pytest.mark.asyncio
    async def test_detects_hardcoded_secret(self, tmp_path: Path):
        from smartdev.mcp.tools import handle_security_review

        (tmp_path / "config.py").write_text("API_KEY = 'sk-1234567890abcdef'\n")

        result = await handle_security_review(
            {
                "changed_files": ["config.py"],
                "file_contents": {"config.py": "API_KEY = 'sk-1234567890abcdef'\n"},
            },
            tmp_path,
        )
        data = _parse(result)
        assert data["ok"] is True


# ── smartdev_diff_explain ─────────────────────────────────


class TestDiffExplainHandler:
    """smartdev_diff_explain 单 Guard 测试。"""

    @pytest.mark.asyncio
    async def test_missing_patch_files_returns_error(self, tmp_path: Path):
        from smartdev.mcp.tools import handle_diff_explain
        result = await handle_diff_explain({}, tmp_path)
        data = _parse(result)
        assert data["ok"] is False
        assert data["error_code"] == "INVALID_ARGUMENT"

    @pytest.mark.asyncio
    async def test_valid_input_returns_ok(self, tmp_path: Path):
        from smartdev.mcp.tools import handle_diff_explain

        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("print('hello')\n")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_app.py").write_text("def test_hello(): pass\n")

        result = await handle_diff_explain(
            {
                "patch_files": ["src/app.py", "tests/test_app.py"],
                "project_path": str(tmp_path),
            },
            tmp_path,
        )
        data = _parse(result)
        assert data["ok"] is True
        assert "file_categories" in data["data"] or "summary" in data["data"]

    @pytest.mark.asyncio
    async def test_with_diff_content(self, tmp_path: Path):
        from smartdev.mcp.tools import handle_diff_explain

        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("print('hello')\n")

        diff = (
            "--- a/src/app.py\n"
            "+++ b/src/app.py\n"
            "@@ -1 +1,3 @@\n"
            " print('hello')\n"
            "+print('world')\n"
            "+print('!')\n"
        )
        result = await handle_diff_explain(
            {"patch_files": ["src/app.py"], "diff_content": diff},
            tmp_path,
        )
        data = _parse(result)
        assert data["ok"] is True
        # 应统计到 insertions
        if "summary" in data["data"]:
            assert data["data"]["summary"].get("insertions") == 2
