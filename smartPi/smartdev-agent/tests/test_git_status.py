"""
git.status Skill 测试 — Phase 11A Step 2

覆盖：
1. can_run() 的 git 可用性检测
2. 干净仓库的完整输出结构
3. 脏仓库的 staged / unstaged / untracked 字段
4. policy_hints：protected branch 检测
5. next_steps 建议
6. git 不可用时返回 GIT_NOT_FOUND（不崩溃）
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from smartdev.models import ProjectContext
from smartdev.skills.base import Skill
from smartdev.skills.git_status.skill import GitStatusSkill


# ── Helpers ────────────────────────────────────────────────


def _git(path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=str(path), capture_output=True, text=True
    )
    return result.stdout.strip()


def _make_context(project_path: Path, task: str = "test") -> ProjectContext:
    return ProjectContext(project_path=project_path, task_description=task)


@pytest.fixture()
def git_repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "README.md").write_text("# Test\n")
    _git(tmp_path, "add", "README.md")
    _git(tmp_path, "commit", "-m", "init: initial commit")
    return tmp_path


# ── 注册验证 ──────────────────────────────────────────────


def test_skill_registered():
    """git.status 已通过 __init_subclass__ 自动注册。"""
    from smartdev.skills import Skill as S
    skill = S.get_skill("git.status")
    assert skill is not None
    assert skill.name == "git.status"


# ── can_run ───────────────────────────────────────────────


class TestCanRun:
    def test_true_in_git_repo(self, git_repo: Path):
        ctx = _make_context(git_repo)
        assert GitStatusSkill().can_run(ctx) is True

    def test_false_in_non_git_dir(self, tmp_path: Path):
        ctx = _make_context(tmp_path)
        assert GitStatusSkill().can_run(ctx) is False

    def test_false_for_nonexistent_path(self, tmp_path: Path):
        ctx = _make_context(tmp_path / "no_such")
        assert GitStatusSkill().can_run(ctx) is False


# ── 干净仓库 ──────────────────────────────────────────────


class TestCleanRepo:
    def test_success(self, git_repo: Path):
        result = Skill.create("git.status").run(_make_context(git_repo))
        assert result.success is True

    def test_not_dirty(self, git_repo: Path):
        result = Skill.create("git.status").run(_make_context(git_repo))
        assert result.data["is_dirty"] is False

    def test_branch_returned(self, git_repo: Path):
        result = Skill.create("git.status").run(_make_context(git_repo))
        assert isinstance(result.data["branch"], str)
        assert len(result.data["branch"]) > 0

    def test_empty_staged_unstaged(self, git_repo: Path):
        result = Skill.create("git.status").run(_make_context(git_repo))
        assert result.data["staged"] == []
        assert result.data["unstaged"] == []

    def test_recent_commits_present(self, git_repo: Path):
        result = Skill.create("git.status").run(_make_context(git_repo))
        assert len(result.data["recent_commits"]) >= 1

    def test_has_summary_string(self, git_repo: Path):
        result = Skill.create("git.status").run(_make_context(git_repo))
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0

    def test_recent_commit_count_input(self, git_repo: Path):
        # 生成 5 个额外提交
        for i in range(5):
            f = git_repo / f"f{i}.txt"
            f.write_text(f"content {i}\n")
            _git(git_repo, "add", f.name)
            _git(git_repo, "commit", "-m", f"feat: f{i}")
        result = Skill.create("git.status").run(
            _make_context(git_repo), {"recent_commit_count": 3}
        )
        assert len(result.data["recent_commits"]) <= 3


# ── 脏仓库 ────────────────────────────────────────────────


class TestDirtyRepo:
    def test_is_dirty(self, git_repo: Path):
        (git_repo / "README.md").write_text("modified\n")
        result = Skill.create("git.status").run(_make_context(git_repo))
        assert result.data["is_dirty"] is True

    def test_unstaged_file_detected(self, git_repo: Path):
        (git_repo / "README.md").write_text("modified\n")
        result = Skill.create("git.status").run(_make_context(git_repo))
        paths = [f["path"] for f in result.data["unstaged"]]
        assert "README.md" in paths

    def test_untracked_file_detected(self, git_repo: Path):
        (git_repo / "new.py").write_text("x = 1\n")
        result = Skill.create("git.status").run(_make_context(git_repo))
        assert "new.py" in result.data["untracked"]

    def test_staged_file_detected(self, git_repo: Path):
        (git_repo / "new.py").write_text("x = 1\n")
        _git(git_repo, "add", "new.py")
        result = Skill.create("git.status").run(_make_context(git_repo))
        paths = [f["path"] for f in result.data["staged"]]
        assert "new.py" in paths

    def test_next_steps_suggest_diff_explain(self, git_repo: Path):
        (git_repo / "README.md").write_text("modified\n")
        result = Skill.create("git.status").run(_make_context(git_repo))
        assert any("diff.explain" in s for s in result.next_steps)


# ── policy_hints ──────────────────────────────────────────


class TestPolicyHints:
    def test_no_hint_on_non_protected_branch(self, git_repo: Path):
        # 默认分支名是 master 或 main，我们切换到 feature 分支
        _git(git_repo, "checkout", "-b", "feature/test")
        result = Skill.create("git.status").run(_make_context(git_repo))
        assert result.data["policy_hints"] == []

    def test_hint_on_protected_branch(self, git_repo: Path):
        # 默认 protected: main/master；直接在 init 分支上即可
        branch = result = Skill.create("git.status").run(_make_context(git_repo))
        # 如果当前就是 main 或 master，应有 hint
        current_branch = branch.data["branch"]
        if current_branch in ("main", "master"):
            assert len(branch.data["policy_hints"]) >= 1
        else:
            # 不是 protected branch，hint 应为空
            assert branch.data["policy_hints"] == []


# ── GIT_NOT_FOUND ─────────────────────────────────────────


class TestGitNotFound:
    def test_can_run_false_no_git(self, tmp_path: Path):
        ctx = _make_context(tmp_path)
        assert GitStatusSkill().can_run(ctx) is False

    def test_run_returns_error_gracefully(self, monkeypatch, git_repo: Path):
        """即使 GitService.status() 抛 GitNotAvailable，也不崩溃。"""
        from smartdev.core import git as git_module

        def broken_status(self, **kwargs):
            from smartdev.core.git import GitNotAvailable
            raise GitNotAvailable("forced failure")

        monkeypatch.setattr(git_module.GitService, "status", broken_status)
        ctx = _make_context(git_repo)
        result = GitStatusSkill().run(ctx)
        assert result.success is False
        assert result.data["error"] == "GIT_NOT_FOUND"
