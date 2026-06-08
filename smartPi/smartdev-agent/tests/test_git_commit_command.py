"""
git commit / git tag CLI Command 测试 — Phase 11A Step 6

覆盖：
1. git commit dry-run：输出计划，不创建 commit
2. git commit --apply：真正创建 commit
3. git commit protected branch 拒绝
4. git commit policy warning（超 max_files）
5. git tag dry-run：输出计划，不创建 tag
6. git tag --apply：真正创建 tag
7. git tag 重复 tag 拒绝
8. git tag annotated（--message）
9. 不存在项目路径返回错误
10. git 不可用返回错误
11. _write_git_audit 静默处理（无索引时不崩溃）
"""

from __future__ import annotations

import subprocess
import sys
from io import StringIO
from pathlib import Path

import pytest

from smartdev.cli import _cmd_git_commit, _cmd_git_tag, _write_git_audit


# ── Helpers ────────────────────────────────────────────────


def _git(path: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=str(path), capture_output=True, text=True)
    return r.stdout.strip()


def _make_args(**kwargs):
    """构造 argparse.Namespace 替代对象。"""
    import argparse
    defaults = {
        "project": ".",
        "message": "feat: test commit",
        "files": None,
        "apply": False,
        "version": "v9.9.9",
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


@pytest.fixture()
def git_repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "README.md").write_text("# Test\n")
    _git(tmp_path, "add", "README.md")
    _git(tmp_path, "commit", "-m", "init: initial commit")
    return tmp_path


@pytest.fixture()
def feature_repo(git_repo: Path) -> Path:
    """切换到 feature 分支的仓库。"""
    _git(git_repo, "checkout", "-b", "feature/test")
    (git_repo / "app.py").write_text("x = 1\n")
    _git(git_repo, "add", "app.py")
    return git_repo


# ── git commit dry-run ────────────────────────────────────


class TestGitCommitDryRun:
    def test_dry_run_returns_zero(self, feature_repo: Path, capsys):
        args = _make_args(project=str(feature_repo), message="feat: add app", apply=False)
        rc = _cmd_git_commit(args)
        assert rc == 0

    def test_dry_run_shows_will_commit(self, feature_repo: Path, capsys):
        args = _make_args(project=str(feature_repo), message="feat: add app", apply=False)
        _cmd_git_commit(args)
        out = capsys.readouterr().out
        assert "Will commit" in out

    def test_dry_run_shows_message(self, feature_repo: Path, capsys):
        args = _make_args(project=str(feature_repo), message="feat: my feature", apply=False)
        _cmd_git_commit(args)
        out = capsys.readouterr().out
        assert "feat: my feature" in out

    def test_dry_run_shows_no_commit_created(self, feature_repo: Path, capsys):
        args = _make_args(project=str(feature_repo), message="feat: test", apply=False)
        _cmd_git_commit(args)
        out = capsys.readouterr().out
        assert "No commit created" in out

    def test_dry_run_does_not_create_commit(self, feature_repo: Path):
        before = _git(feature_repo, "rev-parse", "HEAD")
        args = _make_args(project=str(feature_repo), message="feat: should not commit", apply=False)
        _cmd_git_commit(args)
        after = _git(feature_repo, "rev-parse", "HEAD")
        assert before == after

    def test_dry_run_shows_branch(self, feature_repo: Path, capsys):
        args = _make_args(project=str(feature_repo), message="feat: x", apply=False)
        _cmd_git_commit(args)
        out = capsys.readouterr().out
        assert "feature/test" in out


# ── git commit --apply ────────────────────────────────────


class TestGitCommitApply:
    def test_apply_creates_commit(self, feature_repo: Path):
        before = _git(feature_repo, "rev-parse", "HEAD")
        args = _make_args(
            project=str(feature_repo),
            message="feat: add app.py",
            apply=True,
            files=["app.py"],
        )
        rc = _cmd_git_commit(args)
        assert rc == 0
        after = _git(feature_repo, "rev-parse", "HEAD")
        assert before != after

    def test_apply_commit_message_correct(self, feature_repo: Path):
        args = _make_args(
            project=str(feature_repo),
            message="feat(cli): add git command",
            apply=True,
            files=["app.py"],
        )
        _cmd_git_commit(args)
        log = _git(feature_repo, "log", "--oneline", "-1")
        assert "feat(cli): add git command" in log

    def test_apply_returns_zero_on_success(self, feature_repo: Path):
        args = _make_args(
            project=str(feature_repo),
            message="feat: commit",
            apply=True,
            files=["app.py"],
        )
        rc = _cmd_git_commit(args)
        assert rc == 0


# ── git commit policy ─────────────────────────────────────


class TestGitCommitPolicy:
    def test_protected_branch_rejected(self, git_repo: Path, capsys):
        branch = _git(git_repo, "branch", "--show-current")
        if branch not in ("main", "master"):
            pytest.skip("not on protected branch")
        # 需要有 staged 文件才会走到 policy 检查
        (git_repo / "new.py").write_text("x=1\n")
        _git(git_repo, "add", "new.py")
        args = _make_args(project=str(git_repo), message="feat: x", apply=False)
        rc = _cmd_git_commit(args)
        assert rc == 1
        out = capsys.readouterr().out
        assert "protected" in out or "拒绝" in out

    def test_non_protected_branch_passes(self, feature_repo: Path, capsys):
        args = _make_args(project=str(feature_repo), message="feat: x", apply=False)
        rc = _cmd_git_commit(args)
        assert rc == 0

    def test_policy_warning_shown_for_many_files(self, feature_repo: Path, capsys):
        # 制造超过 max_files_per_commit(12) 的 staged 文件
        for i in range(14):
            f = feature_repo / f"file{i}.py"
            f.write_text(f"x = {i}\n")
            _git(feature_repo, "add", f.name)
        args = _make_args(project=str(feature_repo), message="feat: many", apply=False)
        _cmd_git_commit(args)
        out = capsys.readouterr().out
        assert "max_files" in out or "超过" in out


# ── git commit error handling ─────────────────────────────


class TestGitCommitErrors:
    def test_nonexistent_project_returns_error(self, tmp_path: Path):
        args = _make_args(project=str(tmp_path / "no_such"), message="feat: x")
        rc = _cmd_git_commit(args)
        assert rc == 1

    def test_non_git_dir_returns_error(self, tmp_path: Path):
        args = _make_args(project=str(tmp_path), message="feat: x")
        rc = _cmd_git_commit(args)
        assert rc == 1


# ── git tag dry-run ───────────────────────────────────────


class TestGitTagDryRun:
    def test_dry_run_returns_zero(self, git_repo: Path, capsys):
        args = _make_args(project=str(git_repo), version="v1.0.0", apply=False)
        rc = _cmd_git_tag(args)
        assert rc == 0

    def test_dry_run_shows_will_tag(self, git_repo: Path, capsys):
        args = _make_args(project=str(git_repo), version="v1.0.0", apply=False)
        _cmd_git_tag(args)
        out = capsys.readouterr().out
        assert "Will tag" in out

    def test_dry_run_shows_version(self, git_repo: Path, capsys):
        args = _make_args(project=str(git_repo), version="v2.3.4", apply=False)
        _cmd_git_tag(args)
        out = capsys.readouterr().out
        assert "v2.3.4" in out

    def test_dry_run_shows_no_tag_created(self, git_repo: Path, capsys):
        args = _make_args(project=str(git_repo), version="v1.0.0", apply=False)
        _cmd_git_tag(args)
        out = capsys.readouterr().out
        assert "No tag created" in out

    def test_dry_run_does_not_create_tag(self, git_repo: Path):
        args = _make_args(project=str(git_repo), version="v1.0.0", apply=False)
        _cmd_git_tag(args)
        tags = _git(git_repo, "tag").splitlines()
        assert "v1.0.0" not in tags


# ── git tag --apply ───────────────────────────────────────


class TestGitTagApply:
    def test_apply_creates_tag(self, git_repo: Path):
        args = _make_args(project=str(git_repo), version="v0.1.0", apply=True)
        rc = _cmd_git_tag(args)
        assert rc == 0
        tags = _git(git_repo, "tag").splitlines()
        assert "v0.1.0" in tags

    def test_apply_returns_zero(self, git_repo: Path):
        args = _make_args(project=str(git_repo), version="v0.2.0", apply=True)
        rc = _cmd_git_tag(args)
        assert rc == 0

    def test_apply_annotated_tag(self, git_repo: Path):
        import argparse
        args = argparse.Namespace(
            project=str(git_repo),
            version="v0.3.0",
            message="release 0.3.0",
            apply=True,
        )
        rc = _cmd_git_tag(args)
        assert rc == 0
        tags = _git(git_repo, "tag").splitlines()
        assert "v0.3.0" in tags


# ── git tag policy ────────────────────────────────────────


class TestGitTagPolicy:
    def test_duplicate_tag_rejected(self, git_repo: Path, capsys):
        _git(git_repo, "tag", "v1.0.0")
        args = _make_args(project=str(git_repo), version="v1.0.0", apply=False)
        rc = _cmd_git_tag(args)
        assert rc == 1
        out = capsys.readouterr().out
        assert "已存在" in out or "exist" in out.lower()

    def test_unique_tag_passes(self, git_repo: Path, capsys):
        args = _make_args(project=str(git_repo), version="v9.8.7", apply=False)
        rc = _cmd_git_tag(args)
        assert rc == 0


# ── git tag error handling ────────────────────────────────


class TestGitTagErrors:
    def test_nonexistent_project_returns_error(self, tmp_path: Path):
        args = _make_args(project=str(tmp_path / "no_such"), version="v1.0.0")
        rc = _cmd_git_tag(args)
        assert rc == 1

    def test_non_git_dir_returns_error(self, tmp_path: Path):
        args = _make_args(project=str(tmp_path), version="v1.0.0")
        rc = _cmd_git_tag(args)
        assert rc == 1


# ── _write_git_audit ──────────────────────────────────────


class TestWriteGitAudit:
    def test_no_index_does_not_crash(self, tmp_path: Path):
        """无索引时静默处理，不抛异常。"""
        _write_git_audit(tmp_path, "git.commit", {"branch": "main"})

    def test_with_index_writes_run(self, tmp_path: Path):
        """有索引时写入 runs 表。"""
        import sqlite3
        db = tmp_path / ".smartdev" / "index.sqlite"
        db.parent.mkdir(parents=True)
        conn = sqlite3.connect(str(db))
        conn.execute(
            "CREATE TABLE runs (id TEXT PRIMARY KEY, task TEXT, created_at TEXT, summary_json TEXT)"
        )
        conn.commit()
        conn.close()

        _write_git_audit(tmp_path, "git.commit", {"branch": "feature/x", "message": "feat: x"})

        conn = sqlite3.connect(str(db))
        rows = conn.execute("SELECT task FROM runs").fetchall()
        conn.close()
        assert any(r[0] == "git.commit" for r in rows)
