"""
git.diff.explain Skill 测试 — Phase 11A Step 2

覆盖：
1. 空 diff 快速返回
2. 文件分类（source / test / doc / manifest / config）
3. 风险信号（touches_tests / touches_docs / touches_manifest）
4. risk_hints（multi_file_change / large_changeset / cross_module）
5. suggested_commit_split 拆分建议
6. staged=True 模式
7. GIT_NOT_FOUND 优雅处理
8. 确定性：相同 diff 输出结构固定（无随机性）
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from smartdev.models import ProjectContext
from smartdev.skills.base import Skill
from smartdev.skills.git_diff_explain.skill import (
    GitDiffExplainSkill,
    _classify_file,
    _compute_signals,
    _compute_risk_hints,
    _suggest_commit_split,
)
from smartdev.core.git import GitDiff, GitFileChange


# ── Helpers ────────────────────────────────────────────────


def _git(path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=str(path), capture_output=True, text=True
    )
    return result.stdout.strip()


def _ctx(project_path: Path) -> ProjectContext:
    return ProjectContext(project_path=project_path, task_description="test")


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
    from smartdev.skills import Skill as S
    assert S.get_skill("git.diff.explain") is not None


# ── _classify_file 单元测试 ───────────────────────────────


class TestClassifyFile:
    def test_python_source(self):
        assert _classify_file("smartdev/core/git.py") == "source"

    def test_test_file_prefix(self):
        assert _classify_file("tests/test_git_service.py") == "test"

    def test_test_file_in_test_dir(self):
        assert _classify_file("src/test/utils.py") == "test"

    def test_markdown_doc(self):
        assert _classify_file("docs/phase-11-design.md") == "doc"

    def test_pyproject_manifest(self):
        assert _classify_file("pyproject.toml") == "manifest"

    def test_package_json_manifest(self):
        assert _classify_file("package.json") == "manifest"

    def test_go_mod_manifest(self):
        assert _classify_file("go.mod") == "manifest"

    def test_json_config(self):
        assert _classify_file(".smartdev/git-policy.json") == "config"

    def test_gitignore_config(self):
        assert _classify_file(".gitignore") == "config"

    def test_unknown_extension(self):
        assert _classify_file("some/file.xyz") == "other"


# ── _compute_signals 单元测试 ─────────────────────────────


def _make_diff(paths: list[str]) -> GitDiff:
    return GitDiff(
        files=[GitFileChange(path=p, status="M", staged=False) for p in paths],
        insertions=10,
        deletions=5,
    )


class TestComputeSignals:
    def test_touches_tests(self):
        diff = _make_diff(["tests/test_foo.py"])
        signals = _compute_signals(diff, [])
        assert signals["touches_tests"] is True
        assert signals["touches_docs"] is False

    def test_touches_docs(self):
        diff = _make_diff(["docs/README.md"])
        signals = _compute_signals(diff, [])
        assert signals["touches_docs"] is True

    def test_touches_manifest(self):
        diff = _make_diff(["pyproject.toml"])
        signals = _compute_signals(diff, [])
        assert signals["touches_dependency_manifest"] is True

    def test_touches_protected_path(self):
        diff = _make_diff([".git/config"])
        signals = _compute_signals(diff, [".git"])
        assert signals["touches_protected_path"] is True
        assert ".git/config" in signals["protected_path_hits"]

    def test_no_signals_on_plain_source(self):
        diff = _make_diff(["src/main.py"])
        signals = _compute_signals(diff, [])
        assert signals["touches_tests"] is False
        assert signals["touches_docs"] is False
        assert signals["touches_dependency_manifest"] is False
        assert signals["touches_protected_path"] is False

    def test_multiple_signals(self):
        diff = _make_diff(["src/main.py", "tests/test_main.py", "pyproject.toml"])
        signals = _compute_signals(diff, [])
        assert signals["touches_tests"] is True
        assert signals["touches_dependency_manifest"] is True


# ── _compute_risk_hints 单元测试 ──────────────────────────


class TestComputeRiskHints:
    def test_large_changeset_hint(self):
        diff = _make_diff([f"src/f{i}.py" for i in range(15)])
        signals = {
            "touches_protected_path": False,
            "touches_dependency_manifest": False,
            "protected_path_hits": [],
        }
        hints = _compute_risk_hints(diff, signals, max_files_per_commit=12)
        assert any("large_changeset" in h for h in hints)

    def test_multi_file_hint(self):
        diff = _make_diff([f"src/f{i}.py" for i in range(7)])
        signals = {"touches_protected_path": False, "touches_dependency_manifest": False, "protected_path_hits": []}
        hints = _compute_risk_hints(diff, signals, max_files_per_commit=12)
        assert any("multi_file" in h for h in hints)

    def test_no_hint_for_small_change(self):
        diff = _make_diff(["src/main.py", "src/utils.py"])
        signals = {"touches_protected_path": False, "touches_dependency_manifest": False, "protected_path_hits": []}
        hints = _compute_risk_hints(diff, signals, max_files_per_commit=12)
        assert hints == []

    def test_manifest_hint(self):
        diff = _make_diff(["pyproject.toml"])
        signals = {"touches_protected_path": False, "touches_dependency_manifest": True, "protected_path_hits": []}
        hints = _compute_risk_hints(diff, signals, max_files_per_commit=12)
        assert "dependency_manifest_changed" in hints

    def test_cross_module_hint(self):
        diff = _make_diff(["api/routes.py", "core/logic.py", "ui/views.py", "cli/main.py"])
        signals = {"touches_protected_path": False, "touches_dependency_manifest": False, "protected_path_hits": []}
        hints = _compute_risk_hints(diff, signals, max_files_per_commit=12)
        assert any("cross_module" in h for h in hints)


# ── _suggest_commit_split 单元测试 ────────────────────────


class TestSuggestCommitSplit:
    def test_single_source_file_no_split(self):
        diff = _make_diff(["src/main.py"])
        split = _suggest_commit_split(diff)
        assert len(split) == 1

    def test_source_and_tests_suggests_split(self):
        diff = _make_diff(["src/main.py", "tests/test_main.py", "tests/test_utils.py"])
        split = _suggest_commit_split(diff)
        assert len(split) >= 2
        assert any("test" in s for s in split)

    def test_manifest_gets_own_commit(self):
        diff = _make_diff(["src/main.py", "pyproject.toml"])
        split = _suggest_commit_split(diff)
        assert any("manifest" in s for s in split)

    def test_docs_gets_own_commit(self):
        diff = _make_diff(["src/main.py", "docs/README.md"])
        split = _suggest_commit_split(diff)
        assert any("doc" in s for s in split)


# ── Skill 集成测试 ────────────────────────────────────────


class TestSkillIntegration:
    def test_empty_diff_returns_success(self, git_repo: Path):
        result = Skill.create("git.diff.explain").run(_ctx(git_repo))
        assert result.success is True
        assert result.data["summary"]["files_changed"] == 0
        assert result.data["risk_hints"] == []

    def test_modified_file_shows_in_diff(self, git_repo: Path):
        (git_repo / "README.md").write_text("# Modified\nline2\nline3\n")
        result = Skill.create("git.diff.explain").run(_ctx(git_repo))
        assert result.success is True
        assert result.data["summary"]["files_changed"] >= 1
        paths = [f["path"] for f in result.data["files"]]
        assert "README.md" in paths

    def test_insertions_counted(self, git_repo: Path):
        (git_repo / "README.md").write_text("# Test\nline2\nline3\nline4\n")
        result = Skill.create("git.diff.explain").run(_ctx(git_repo))
        assert result.data["summary"]["insertions"] >= 1

    def test_test_file_signal(self, git_repo: Path):
        (git_repo / "test_foo.py").write_text("def test_x(): pass\n")
        _git(git_repo, "add", "test_foo.py")
        result = Skill.create("git.diff.explain").run(_ctx(git_repo), {"staged": True})
        assert result.data["signals"]["touches_tests"] is True

    def test_manifest_signal(self, git_repo: Path):
        (git_repo / "pyproject.toml").write_text('[project]\nname="x"\n')
        _git(git_repo, "add", "pyproject.toml")
        result = Skill.create("git.diff.explain").run(_ctx(git_repo), {"staged": True})
        assert result.data["signals"]["touches_dependency_manifest"] is True

    def test_staged_flag(self, git_repo: Path):
        (git_repo / "staged.py").write_text("x = 1\n")
        _git(git_repo, "add", "staged.py")
        result = Skill.create("git.diff.explain").run(_ctx(git_repo), {"staged": True})
        assert result.data["staged"] is True
        paths = [f["path"] for f in result.data["files"]]
        assert "staged.py" in paths

    def test_file_categories_in_output(self, git_repo: Path):
        (git_repo / "app.py").write_text("x = 1\n")
        _git(git_repo, "add", "app.py")
        result = Skill.create("git.diff.explain").run(_ctx(git_repo), {"staged": True})
        assert "file_categories" in result.data
        assert isinstance(result.data["file_categories"], dict)

    def test_next_steps_present(self, git_repo: Path):
        (git_repo / "README.md").write_text("modified\n")
        result = Skill.create("git.diff.explain").run(_ctx(git_repo))
        assert len(result.next_steps) >= 1

    def test_deterministic_output(self, git_repo: Path):
        """相同 diff 输出结构完全相同（无随机性）。"""
        (git_repo / "README.md").write_text("modified\n")
        r1 = Skill.create("git.diff.explain").run(_ctx(git_repo))
        r2 = Skill.create("git.diff.explain").run(_ctx(git_repo))
        assert r1.data["summary"] == r2.data["summary"]
        assert r1.data["signals"] == r2.data["signals"]
        assert r1.data["risk_hints"] == r2.data["risk_hints"]

    def test_can_run_false_non_git(self, tmp_path: Path):
        assert GitDiffExplainSkill().can_run(_ctx(tmp_path)) is False

    def test_git_not_found_graceful(self, monkeypatch, git_repo: Path):
        from smartdev.core import git as git_module

        def broken_diff(self, **kwargs):
            from smartdev.core.git import GitNotAvailable
            raise GitNotAvailable("forced")

        monkeypatch.setattr(git_module.GitService, "diff", broken_diff)
        result = GitDiffExplainSkill().run(_ctx(git_repo))
        assert result.success is False
        assert result.data["error"] == "GIT_NOT_FOUND"
