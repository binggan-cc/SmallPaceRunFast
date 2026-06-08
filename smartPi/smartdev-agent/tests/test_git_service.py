"""
GitService 单元测试 — Phase 11A Step 1

覆盖：
1. GitNotAvailable / is_available()
2. GitStatus 数据模型
3. GitDiff 数据模型
4. GitPolicy 加载（默认值 + JSON 覆盖）
5. subprocess 封装正确性（列表参数、非零返回码处理）
6. commit() / tag() 写操作基本行为

测试策略：
- 用 tmp_path + git init 构造最小 git 仓库，避免依赖真实项目历史
- is_available() 在非 git 目录返回 False
- 非 git 目录调 status() 抛 GitNotAvailable
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from smartdev.core.git import (
    GitDiff,
    GitFileChange,
    GitNotAvailable,
    GitPolicy,
    GitService,
    GitStatus,
    load_git_policy,
)


# ── Fixtures ───────────────────────────────────────────────


def _git(path: Path, *args: str) -> str:
    """在 path 目录执行 git 命令，返回 stdout。"""
    result = subprocess.run(
        ["git", *args],
        cwd=str(path),
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


@pytest.fixture()
def git_repo(tmp_path: Path) -> Path:
    """最小 git 仓库 fixture：init + 初始提交。"""
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    # 初始提交
    readme = tmp_path / "README.md"
    readme.write_text("# Test\n", encoding="utf-8")
    _git(tmp_path, "add", "README.md")
    _git(tmp_path, "commit", "-m", "init: initial commit")
    return tmp_path


@pytest.fixture()
def dirty_repo(git_repo: Path) -> Path:
    """在干净仓库上制造脏状态：新文件 + 修改文件。"""
    # 修改已有文件（unstaged）
    (git_repo / "README.md").write_text("# Test\nmodified\n", encoding="utf-8")
    # 新建未跟踪文件
    (git_repo / "new_file.txt").write_text("hello\n", encoding="utf-8")
    return git_repo


# ── is_available ──────────────────────────────────────────


class TestIsAvailable:
    def test_returns_true_in_git_repo(self, git_repo: Path):
        svc = GitService(git_repo)
        assert svc.is_available() is True

    def test_returns_false_in_non_git_dir(self, tmp_path: Path):
        svc = GitService(tmp_path)
        assert svc.is_available() is False

    def test_returns_false_for_nonexistent_dir(self, tmp_path: Path):
        svc = GitService(tmp_path / "no_such_dir")
        assert svc.is_available() is False


# ── current_branch ────────────────────────────────────────


class TestCurrentBranch:
    def test_returns_branch_name(self, git_repo: Path):
        svc = GitService(git_repo)
        branch = svc.current_branch()
        assert isinstance(branch, str)
        assert len(branch) > 0

    def test_raises_in_non_git_dir(self, tmp_path: Path):
        svc = GitService(tmp_path)
        with pytest.raises(GitNotAvailable):
            svc.current_branch()


# ── status ────────────────────────────────────────────────


class TestStatus:
    def test_clean_repo_not_dirty(self, git_repo: Path):
        svc = GitService(git_repo)
        status = svc.status()
        assert isinstance(status, GitStatus)
        assert status.is_dirty is False
        assert status.staged == []
        assert status.unstaged == []
        assert status.untracked == []

    def test_clean_repo_has_branch(self, git_repo: Path):
        svc = GitService(git_repo)
        status = svc.status()
        assert isinstance(status.branch, str)
        assert len(status.branch) > 0

    def test_clean_repo_has_recent_commits(self, git_repo: Path):
        svc = GitService(git_repo)
        status = svc.status()
        assert len(status.recent_commits) >= 1
        assert "init" in status.recent_commits[0].lower()

    def test_dirty_repo_is_dirty(self, dirty_repo: Path):
        svc = GitService(dirty_repo)
        status = svc.status()
        assert status.is_dirty is True

    def test_dirty_repo_has_unstaged(self, dirty_repo: Path):
        svc = GitService(dirty_repo)
        status = svc.status()
        unstaged_paths = [f.path for f in status.unstaged]
        assert "README.md" in unstaged_paths

    def test_dirty_repo_has_untracked(self, dirty_repo: Path):
        svc = GitService(dirty_repo)
        status = svc.status()
        assert "new_file.txt" in status.untracked

    def test_staged_file_appears_in_staged(self, git_repo: Path):
        (git_repo / "staged.py").write_text("x = 1\n", encoding="utf-8")
        _git(git_repo, "add", "staged.py")
        svc = GitService(git_repo)
        status = svc.status()
        staged_paths = [f.path for f in status.staged]
        assert "staged.py" in staged_paths

    def test_raises_in_non_git_dir(self, tmp_path: Path):
        svc = GitService(tmp_path)
        with pytest.raises(GitNotAvailable):
            svc.status()


# ── diff ──────────────────────────────────────────────────


class TestDiff:
    def test_clean_repo_empty_diff(self, git_repo: Path):
        svc = GitService(git_repo)
        d = svc.diff()
        assert isinstance(d, GitDiff)
        assert d.files == []
        assert d.insertions == 0
        assert d.deletions == 0

    def test_modified_file_appears_in_diff(self, dirty_repo: Path):
        svc = GitService(dirty_repo)
        d = svc.diff()
        paths = [f.path for f in d.files]
        assert "README.md" in paths

    def test_diff_counts_insertions(self, dirty_repo: Path):
        svc = GitService(dirty_repo)
        d = svc.diff()
        # "modified\n" 是新增行，insertions >= 1
        assert d.insertions >= 1

    def test_staged_diff(self, git_repo: Path):
        (git_repo / "staged.py").write_text("x = 1\ny = 2\n", encoding="utf-8")
        _git(git_repo, "add", "staged.py")
        svc = GitService(git_repo)
        d = svc.diff(staged=True)
        paths = [f.path for f in d.files]
        assert "staged.py" in paths
        assert d.staged is True

    def test_raises_in_non_git_dir(self, tmp_path: Path):
        svc = GitService(tmp_path)
        with pytest.raises(GitNotAvailable):
            svc.diff()


# ── tags ──────────────────────────────────────────────────


class TestTags:
    def test_empty_tags_on_fresh_repo(self, git_repo: Path):
        svc = GitService(git_repo)
        assert svc.tags() == []

    def test_tag_appears_after_creation(self, git_repo: Path):
        _git(git_repo, "tag", "v0.1.0")
        svc = GitService(git_repo)
        assert "v0.1.0" in svc.tags()

    def test_multiple_tags_sorted(self, git_repo: Path):
        _git(git_repo, "tag", "v0.2.0")
        _git(git_repo, "tag", "v0.1.0")
        svc = GitService(git_repo)
        tags = svc.tags()
        assert tags == sorted(tags)


# ── log_oneline ───────────────────────────────────────────


class TestLogOneline:
    def test_returns_list_of_strings(self, git_repo: Path):
        svc = GitService(git_repo)
        log = svc.log_oneline(n=5)
        assert isinstance(log, list)
        assert all(isinstance(line, str) for line in log)

    def test_respects_n_limit(self, git_repo: Path):
        # 追加更多 commit
        for i in range(5):
            f = git_repo / f"file{i}.txt"
            f.write_text(f"content {i}\n")
            _git(git_repo, "add", f.name)
            _git(git_repo, "commit", "-m", f"feat: add file{i}")
        svc = GitService(git_repo)
        log = svc.log_oneline(n=3)
        assert len(log) <= 3


# ── GitPolicy 加载 ────────────────────────────────────────


class TestLoadGitPolicy:
    def test_returns_default_policy_when_no_file(self, tmp_path: Path):
        policy = load_git_policy(tmp_path)
        assert isinstance(policy, GitPolicy)
        assert "main" in policy.protected_branches
        assert "master" in policy.protected_branches
        assert policy.forbid_push is True
        assert policy.max_files_per_commit == 12

    def test_loads_smartdev_dir_policy(self, tmp_path: Path):
        smartdev_dir = tmp_path / ".smartdev"
        smartdev_dir.mkdir()
        policy_file = smartdev_dir / "git-policy.json"
        policy_file.write_text(json.dumps({
            "branch": {"protected": ["develop"]},
            "commit": {"max_files_per_commit": 5},
        }), encoding="utf-8")
        policy = load_git_policy(tmp_path)
        assert policy.protected_branches == ["develop"]
        assert policy.max_files_per_commit == 5
        # 未指定的字段保留默认值
        assert policy.forbid_push is True

    def test_loads_root_policy_as_fallback(self, tmp_path: Path):
        policy_file = tmp_path / "smartdev.git.json"
        policy_file.write_text(json.dumps({
            "commit": {"convention": "plain"},
        }), encoding="utf-8")
        policy = load_git_policy(tmp_path)
        assert policy.commit_convention == "plain"

    def test_smartdev_dir_takes_priority_over_root(self, tmp_path: Path):
        smartdev_dir = tmp_path / ".smartdev"
        smartdev_dir.mkdir()
        (smartdev_dir / "git-policy.json").write_text(
            json.dumps({"commit": {"convention": "from_smartdev_dir"}}),
            encoding="utf-8",
        )
        (tmp_path / "smartdev.git.json").write_text(
            json.dumps({"commit": {"convention": "from_root"}}),
            encoding="utf-8",
        )
        policy = load_git_policy(tmp_path)
        assert policy.commit_convention == "from_smartdev_dir"

    def test_malformed_json_falls_back_to_default(self, tmp_path: Path):
        smartdev_dir = tmp_path / ".smartdev"
        smartdev_dir.mkdir()
        (smartdev_dir / "git-policy.json").write_text(
            "{ invalid json !!!", encoding="utf-8"
        )
        policy = load_git_policy(tmp_path)
        assert policy.protected_branches == ["main", "master"]

    def test_all_dangerous_flags_default_true(self, tmp_path: Path):
        policy = load_git_policy(tmp_path)
        assert policy.forbid_push is True
        assert policy.forbid_force_push is True
        assert policy.forbid_reset_hard is True
        assert policy.forbid_rebase is True
        assert policy.forbid_merge_apply is True

    def test_dangerous_flag_can_be_overridden(self, tmp_path: Path):
        smartdev_dir = tmp_path / ".smartdev"
        smartdev_dir.mkdir()
        (smartdev_dir / "git-policy.json").write_text(
            json.dumps({"dangerous": {"forbid_rebase": False}}),
            encoding="utf-8",
        )
        policy = load_git_policy(tmp_path)
        assert policy.forbid_rebase is False
        # 其他 dangerous 保持默认
        assert policy.forbid_push is True


# ── commit / tag 执行方法 ─────────────────────────────────


class TestCommitAndTag:
    """验证 commit / tag 写操作的基本行为。"""

    def test_commit_creates_new_commit(self, git_repo: Path):
        (git_repo / "new.txt").write_text("content\n", encoding="utf-8")
        _git(git_repo, "add", "new.txt")
        svc = GitService(git_repo)
        out = svc.commit("feat: add new.txt")
        assert "new.txt" in out or "feat" in out or "1 file" in out

    def test_commit_with_files_stages_them(self, git_repo: Path):
        (git_repo / "auto_staged.txt").write_text("auto\n", encoding="utf-8")
        svc = GitService(git_repo)
        out = svc.commit("feat: auto stage", files=["auto_staged.txt"])
        assert "auto_staged.txt" in out or "1 file" in out

    def test_tag_creates_lightweight_tag(self, git_repo: Path):
        svc = GitService(git_repo)
        svc.tag("v9.9.9")
        assert "v9.9.9" in svc.tags()

    def test_tag_creates_annotated_tag(self, git_repo: Path):
        svc = GitService(git_repo)
        svc.tag("v9.9.8", message="release 9.9.8")
        assert "v9.9.8" in svc.tags()

    def test_commit_raises_in_non_git_dir(self, tmp_path: Path):
        svc = GitService(tmp_path)
        with pytest.raises(GitNotAvailable):
            svc.commit("feat: should fail")

    def test_tag_raises_in_non_git_dir(self, tmp_path: Path):
        svc = GitService(tmp_path)
        with pytest.raises(GitNotAvailable):
            svc.tag("v0.0.0")
