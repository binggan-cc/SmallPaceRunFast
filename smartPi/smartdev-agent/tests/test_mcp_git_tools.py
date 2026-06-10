"""
MCP 只读 Git 工具测试 — Phase 11A Step 7

覆盖：
1. 5 个工具在 server._HANDLERS 和 _TOOLS 中均已注册
2. 非 git 目录时返回 GIT_NOT_FOUND（不崩溃）
3. 有效 git 仓库时返回成功（ok=True）
4. 各工具的 data 结构包含预期字段
5. smartdev_version 工具清单包含全部 19 个工具
6. handle_git_status / diff_explain / commit_plan / release_plan / merge_check 的 handler 可调用
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path

import pytest

from smartdev.mcp.server import create_server
from smartdev.mcp.tools import (
    get_available_tools,
    handle_git_status,
    handle_git_diff_explain,
    handle_git_commit_plan,
    handle_git_release_plan,
    handle_git_merge_check,
)


# ── Helpers ────────────────────────────────────────────────


def _git(path: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=str(path), capture_output=True, text=True)
    return r.stdout.strip()


def _parse(text_content) -> dict:
    return json.loads(text_content[0].text)


@pytest.fixture()
def git_repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "README.md").write_text("# Test\n")
    _git(tmp_path, "add", "README.md")
    _git(tmp_path, "commit", "-m", "init: initial commit")
    return tmp_path


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ── 工具注册验证 ──────────────────────────────────────────


class TestGitToolsRegistered:
    """5 个 git 工具必须出现在 version 清单和 list_tools 响应中。"""

    GIT_TOOLS = [
        "smartdev_git_status",
        "smartdev_git_diff_explain",
        "smartdev_git_commit_plan",
        "smartdev_git_release_plan",
        "smartdev_git_merge_check",
    ]

    @pytest.mark.asyncio
    async def test_all_git_tools_in_version_list(self, tmp_path: Path):
        from smartdev.mcp.tools import handle_version
        result = await handle_version({}, tmp_path)
        data = _parse(result)
        names = {t["name"] for t in data["data"]["tools"]}
        for tool in self.GIT_TOOLS:
            assert tool in names, f"{tool} not in version tool list"

    @pytest.mark.asyncio
    async def test_total_tool_count_matches_registry(self, tmp_path: Path):
        from smartdev.mcp.tools import handle_version
        result = await handle_version({}, tmp_path)
        data = _parse(result)
        assert len(data["data"]["tools"]) == len(get_available_tools())

    @pytest.mark.asyncio
    async def test_git_tools_in_list_tools(self, tmp_path: Path):
        from smartdev.mcp.tools import handle_list_tools
        result = await handle_list_tools({}, tmp_path)
        data = _parse(result)
        names = {t["name"] for t in data["data"]["available_tools"]}
        for tool in self.GIT_TOOLS:
            assert tool in names, f"{tool} not in list_tools response"


# ── GIT_NOT_FOUND 优雅降级 ────────────────────────────────


class TestGitNotFound:
    """非 git 目录时所有工具返回 GIT_NOT_FOUND，不崩溃。"""

    def test_git_status_not_found(self, tmp_path: Path):
        result = run(handle_git_status({}, tmp_path))
        data = _parse(result)
        assert data["ok"] is False
        assert data["error_code"] == "GIT_NOT_FOUND"

    def test_git_diff_explain_not_found(self, tmp_path: Path):
        result = run(handle_git_diff_explain({}, tmp_path))
        data = _parse(result)
        assert data["ok"] is False
        assert data["error_code"] == "GIT_NOT_FOUND"

    def test_git_commit_plan_not_found(self, tmp_path: Path):
        result = run(handle_git_commit_plan({}, tmp_path))
        data = _parse(result)
        assert data["ok"] is False
        assert data["error_code"] == "GIT_NOT_FOUND"

    def test_git_release_plan_not_found(self, tmp_path: Path):
        result = run(handle_git_release_plan({}, tmp_path))
        data = _parse(result)
        assert data["ok"] is False
        assert data["error_code"] == "GIT_NOT_FOUND"

    def test_git_merge_check_not_found(self, tmp_path: Path):
        result = run(handle_git_merge_check({}, tmp_path))
        data = _parse(result)
        assert data["ok"] is False
        assert data["error_code"] == "GIT_NOT_FOUND"


# ── 有效 git 仓库时的成功响应 ─────────────────────────────


class TestGitStatusTool:
    def test_returns_ok(self, git_repo: Path):
        result = run(handle_git_status({}, git_repo))
        data = _parse(result)
        assert data["ok"] is True

    def test_has_branch(self, git_repo: Path):
        result = run(handle_git_status({}, git_repo))
        data = _parse(result)
        assert "branch" in data["data"]
        assert isinstance(data["data"]["branch"], str)

    def test_has_is_dirty(self, git_repo: Path):
        result = run(handle_git_status({}, git_repo))
        data = _parse(result)
        assert "is_dirty" in data["data"]

    def test_recent_commit_count_param(self, git_repo: Path):
        result = run(handle_git_status({"recent_commit_count": 3}, git_repo))
        data = _parse(result)
        assert data["ok"] is True
        assert len(data["data"]["recent_commits"]) <= 3

    def test_tool_name_in_response(self, git_repo: Path):
        result = run(handle_git_status({}, git_repo))
        data = _parse(result)
        assert data["tool"] == "smartdev_git_status"


class TestGitDiffExplainTool:
    def test_returns_ok(self, git_repo: Path):
        result = run(handle_git_diff_explain({}, git_repo))
        data = _parse(result)
        assert data["ok"] is True

    def test_has_summary(self, git_repo: Path):
        result = run(handle_git_diff_explain({}, git_repo))
        data = _parse(result)
        assert "summary" in data["data"]

    def test_has_signals(self, git_repo: Path):
        result = run(handle_git_diff_explain({}, git_repo))
        data = _parse(result)
        assert "signals" in data["data"]

    def test_staged_param(self, git_repo: Path):
        result = run(handle_git_diff_explain({"staged": True}, git_repo))
        data = _parse(result)
        assert data["ok"] is True
        assert data["data"]["staged"] is True

    def test_clean_repo_empty_diff(self, git_repo: Path):
        result = run(handle_git_diff_explain({}, git_repo))
        data = _parse(result)
        assert data["data"]["summary"]["files_changed"] == 0


class TestGitCommitPlanTool:
    def test_returns_ok(self, git_repo: Path):
        result = run(handle_git_commit_plan({}, git_repo))
        data = _parse(result)
        assert data["ok"] is True

    def test_has_commits_field(self, git_repo: Path):
        result = run(handle_git_commit_plan({}, git_repo))
        data = _parse(result)
        assert "commits" in data["data"]

    def test_has_total_files(self, git_repo: Path):
        result = run(handle_git_commit_plan({}, git_repo))
        data = _parse(result)
        assert "total_files" in data["data"]

    def test_scope_hint_param(self, git_repo: Path):
        result = run(handle_git_commit_plan({"scope_hint": "cli"}, git_repo))
        data = _parse(result)
        assert data["ok"] is True

    def test_staged_only_param(self, git_repo: Path):
        result = run(handle_git_commit_plan({"staged_only": True}, git_repo))
        data = _parse(result)
        assert data["ok"] is True


class TestGitReleasePlanTool:
    def test_returns_ok(self, git_repo: Path):
        result = run(handle_git_release_plan({}, git_repo))
        data = _parse(result)
        assert data["ok"] is True

    def test_has_suggested_bump(self, git_repo: Path):
        result = run(handle_git_release_plan({}, git_repo))
        data = _parse(result)
        assert "suggested_bump" in data["data"]

    def test_has_release_checklist(self, git_repo: Path):
        result = run(handle_git_release_plan({}, git_repo))
        data = _parse(result)
        assert "release_checklist" in data["data"]
        assert isinstance(data["data"]["release_checklist"], list)

    def test_since_tag_param(self, git_repo: Path):
        _git(git_repo, "tag", "v0.1.0")
        result = run(handle_git_release_plan({"since_tag": "v0.1.0"}, git_repo))
        data = _parse(result)
        assert data["ok"] is True
        assert data["data"]["since_tag"] == "v0.1.0"


class TestGitMergeCheckTool:
    def test_returns_ok(self, git_repo: Path):
        result = run(handle_git_merge_check({}, git_repo))
        data = _parse(result)
        assert data["ok"] is True

    def test_has_ready_field(self, git_repo: Path):
        result = run(handle_git_merge_check({}, git_repo))
        data = _parse(result)
        assert "ready" in data["data"]

    def test_has_checks_list(self, git_repo: Path):
        result = run(handle_git_merge_check({}, git_repo))
        data = _parse(result)
        assert "checks" in data["data"]
        assert isinstance(data["data"]["checks"], list)

    def test_has_blockers_and_warnings(self, git_repo: Path):
        result = run(handle_git_merge_check({}, git_repo))
        data = _parse(result)
        assert "blockers" in data["data"]
        assert "warnings" in data["data"]

    def test_target_branch_param(self, git_repo: Path):
        result = run(handle_git_merge_check({"target_branch": "develop"}, git_repo))
        data = _parse(result)
        assert data["ok"] is True
        assert data["data"]["branch_info"]["target"] == "develop"

    def test_dirty_repo_has_blocker(self, git_repo: Path):
        (git_repo / "README.md").write_text("modified\n")
        result = run(handle_git_merge_check({}, git_repo))
        data = _parse(result)
        assert data["data"]["ready"] is False
        assert len(data["data"]["blockers"]) >= 1
