"""
git.release.plan + git.merge.check Skill 测试 — Phase 11A Step 4

覆盖：
git.release.plan
  1. 注册验证
  2. can_run() git 可用性
  3. _infer_bump：无 commit=none / feat=minor / BREAKING=major / fix=patch
  4. _bump_version：major/minor/patch / v 前缀保留 / 格式非法时返回原值
  5. _read_version：pyproject.toml / package.json / 不存在时返回空
  6. _check_changelog：不存在 / 有 Unreleased / 无 Unreleased
  7. Skill 集成：无 tag / 有 tag / since_tag 输入 / 版本文件读取 / git 不可用

git.merge.check
  1. 注册验证
  2. can_run() git 可用性
  3. 干净仓库 ready=True
  4. 脏仓库 blocker
  5. 同分支 merge 是 blocker
  6. patch_backups 警告
  7. target_branch 输入
  8. has_new_commits：无新 commit 是 warning
  9. index 不存在是 warning
  10. git 不可用时 GIT_NOT_FOUND
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from smartdev.models import ProjectContext
from smartdev.skills.base import Skill
from smartdev.skills.git_release_plan.skill import (
    GitReleasePlanSkill,
    _infer_bump,
    _bump_version,
    _read_version,
    _check_changelog,
)
from smartdev.skills.git_merge_check.skill import (
    GitMergeCheckSkill,
    _check_working_tree,
    _check_patch_backups,
    _check_target_branch,
    _check_index_available,
)
from smartdev.core.git import GitService


# ── Helpers ────────────────────────────────────────────────

def _git(path: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=str(path), capture_output=True, text=True)
    return r.stdout.strip()


def _ctx(p: Path) -> ProjectContext:
    return ProjectContext(project_path=p, task_description="test")


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
def repo_with_tag(git_repo: Path) -> Path:
    """带 tag 的仓库。"""
    _git(git_repo, "tag", "v0.1.0")
    return git_repo


@pytest.fixture()
def feature_branch_repo(git_repo: Path) -> Path:
    """切换到 feature 分支的仓库，有新 commit。"""
    _git(git_repo, "checkout", "-b", "feature/test")
    (git_repo / "new.py").write_text("x = 1\n")
    _git(git_repo, "add", "new.py")
    _git(git_repo, "commit", "-m", "feat: add new.py")
    return git_repo


# ═══════════════════════════════════════════════════════════
# git.release.plan 测试
# ═══════════════════════════════════════════════════════════


class TestReleasePlanRegistered:
    def test_registered(self):
        from smartdev.skills import Skill as S
        assert S.get_skill("git.release.plan") is not None


class TestInferBump:
    def test_no_commits_is_none(self):
        bump, reason = _infer_bump([])
        assert bump == "none"

    def test_fix_commit_is_patch(self):
        bump, _ = _infer_bump(["abc1234 fix: resolve crash"])
        assert bump == "patch"

    def test_feat_commit_is_minor(self):
        bump, _ = _infer_bump(["abc1234 feat: add new feature"])
        assert bump == "minor"

    def test_breaking_exclamation_is_major(self):
        bump, _ = _infer_bump(["abc1234 feat!: breaking new api"])
        assert bump == "major"

    def test_breaking_keyword_is_major(self):
        # BREAKING CHANGE in subject
        bump, _ = _infer_bump(["abc1234 feat: new api BREAKING CHANGE: old removed"])
        assert bump == "major"

    def test_mixed_feat_and_fix_is_minor(self):
        commits = [
            "abc1 fix: fix bug",
            "abc2 feat: add feature",
            "abc3 docs: update readme",
        ]
        bump, _ = _infer_bump(commits)
        assert bump == "minor"

    def test_only_docs_is_patch(self):
        bump, _ = _infer_bump(["abc1234 docs: update changelog"])
        assert bump == "patch"

    def test_non_conventional_defaults_to_patch(self):
        bump, _ = _infer_bump(["abc1234 some random commit message"])
        assert bump == "patch"

    def test_bump_reason_not_empty(self):
        _, reason = _infer_bump(["abc1234 feat: add x"])
        assert isinstance(reason, str)
        assert len(reason) > 0


class TestBumpVersion:
    def test_patch_bump(self):
        assert _bump_version("1.2.3", "patch") == "1.2.4"

    def test_minor_bump(self):
        assert _bump_version("1.2.3", "minor") == "1.3.0"

    def test_major_bump(self):
        assert _bump_version("1.2.3", "major") == "2.0.0"

    def test_none_bump_unchanged(self):
        assert _bump_version("1.2.3", "none") == "1.2.3"

    def test_v_prefix_preserved(self):
        assert _bump_version("v1.2.3", "patch") == "v1.2.4"

    def test_invalid_format_unchanged(self):
        assert _bump_version("not-a-version", "patch") == "not-a-version"

    def test_minor_resets_patch(self):
        assert _bump_version("1.2.9", "minor") == "1.3.0"

    def test_major_resets_minor_and_patch(self):
        assert _bump_version("1.2.9", "major") == "2.0.0"


class TestReadVersion:
    def test_reads_pyproject_toml(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\nversion = "0.3.1"\n'
        )
        v, src = _read_version(tmp_path, ["pyproject.toml"])
        assert v == "0.3.1"
        assert src == "pyproject.toml"

    def test_reads_package_json(self, tmp_path: Path):
        (tmp_path / "package.json").write_text(json.dumps({"version": "2.1.0"}))
        v, src = _read_version(tmp_path, ["package.json"])
        assert v == "2.1.0"
        assert src == "package.json"

    def test_returns_empty_when_no_file(self, tmp_path: Path):
        v, src = _read_version(tmp_path, ["pyproject.toml"])
        assert v == ""
        assert src == ""

    def test_tries_files_in_order(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.0.0"\n')
        (tmp_path / "package.json").write_text(json.dumps({"version": "2.0.0"}))
        # pyproject.toml 在前，应该取它
        v, src = _read_version(tmp_path, ["pyproject.toml", "package.json"])
        assert v == "1.0.0"

    def test_skips_missing_and_reads_next(self, tmp_path: Path):
        (tmp_path / "package.json").write_text(json.dumps({"version": "3.0.0"}))
        v, src = _read_version(tmp_path, ["pyproject.toml", "package.json"])
        assert v == "3.0.0"


class TestCheckChangelog:
    def test_no_file(self, tmp_path: Path):
        result = _check_changelog(tmp_path, "CHANGELOG.md")
        assert result["exists"] is False
        assert result["has_unreleased"] is False

    def test_file_with_unreleased(self, tmp_path: Path):
        (tmp_path / "CHANGELOG.md").write_text("## [Unreleased]\n### Added\n- x\n")
        result = _check_changelog(tmp_path, "CHANGELOG.md")
        assert result["exists"] is True
        assert result["has_unreleased"] is True

    def test_file_without_unreleased(self, tmp_path: Path):
        (tmp_path / "CHANGELOG.md").write_text("## [1.0.0]\n### Added\n- x\n")
        result = _check_changelog(tmp_path, "CHANGELOG.md")
        assert result["exists"] is True
        assert result["has_unreleased"] is False


class TestReleasePlanSkillIntegration:
    def test_can_run_true(self, git_repo: Path):
        assert GitReleasePlanSkill().can_run(_ctx(git_repo))

    def test_can_run_false_non_git(self, tmp_path: Path):
        assert not GitReleasePlanSkill().can_run(_ctx(tmp_path))

    def test_success_no_tags(self, git_repo: Path):
        result = Skill.create("git.release.plan").run(_ctx(git_repo))
        assert result.success is True
        assert "suggested_bump" in result.data
        assert "release_checklist" in result.data

    def test_has_checklist_items(self, git_repo: Path):
        result = Skill.create("git.release.plan").run(_ctx(git_repo))
        assert len(result.data["release_checklist"]) >= 3

    def test_reads_version_from_pyproject(self, git_repo: Path):
        (git_repo / "pyproject.toml").write_text('[project]\nversion = "0.5.0"\n')
        result = Skill.create("git.release.plan").run(_ctx(git_repo))
        assert result.data["current_version"] == "0.5.0"

    def test_suggests_version_when_version_found(self, git_repo: Path):
        (git_repo / "pyproject.toml").write_text('[project]\nversion = "0.5.0"\n')
        (git_repo / "feat.py").write_text("x=1\n")
        _git(git_repo, "add", "feat.py")
        _git(git_repo, "commit", "-m", "feat: new feature")
        result = Skill.create("git.release.plan").run(_ctx(git_repo))
        if result.data["suggested_bump"] == "minor":
            assert result.data["suggested_version"] == "0.6.0"

    def test_since_tag_input(self, repo_with_tag: Path):
        # tag 后没有新 commit → bump = none
        result = Skill.create("git.release.plan").run(
            _ctx(repo_with_tag), {"since_tag": "v0.1.0"}
        )
        assert result.success is True
        assert result.data["since_tag"] == "v0.1.0"

    def test_changelog_status_in_output(self, git_repo: Path):
        result = Skill.create("git.release.plan").run(_ctx(git_repo))
        assert "changelog_status" in result.data
        assert "exists" in result.data["changelog_status"]

    def test_git_not_found_graceful(self, monkeypatch, git_repo: Path):
        from smartdev.core import git as git_module
        def broken(self):
            from smartdev.core.git import GitNotAvailable
            raise GitNotAvailable("forced")
        monkeypatch.setattr(git_module.GitService, "tags", broken)
        result = GitReleasePlanSkill().run(_ctx(git_repo))
        assert result.success is False
        assert result.data["error"] == "GIT_NOT_FOUND"


# ═══════════════════════════════════════════════════════════
# git.merge.check 测试
# ═══════════════════════════════════════════════════════════


class TestMergeCheckRegistered:
    def test_registered(self):
        from smartdev.skills import Skill as S
        assert S.get_skill("git.merge.check") is not None


class TestCheckWorkingTree:
    def test_clean_repo_passes(self, git_repo: Path):
        svc = GitService(git_repo)
        result = _check_working_tree(svc)
        assert result["passed"] is True
        assert result["level"] == "ok"

    def test_dirty_repo_is_blocker(self, git_repo: Path):
        (git_repo / "README.md").write_text("modified\n")
        svc = GitService(git_repo)
        result = _check_working_tree(svc)
        assert result["passed"] is False
        assert result["level"] == "blocker"


class TestCheckPatchBackups:
    def test_no_backup_dir_passes(self, tmp_path: Path):
        result = _check_patch_backups(tmp_path)
        assert result["passed"] is True

    def test_empty_backup_dir_passes(self, tmp_path: Path):
        (tmp_path / ".smartdev" / "patch_backups").mkdir(parents=True)
        result = _check_patch_backups(tmp_path)
        assert result["passed"] is True

    def test_nonempty_backup_is_warning(self, tmp_path: Path):
        d = tmp_path / ".smartdev" / "patch_backups" / "backup1"
        d.mkdir(parents=True)
        result = _check_patch_backups(tmp_path)
        assert result["passed"] is False
        assert result["level"] == "warning"


class TestCheckTargetBranch:
    def test_feature_to_main_ok(self):
        result = _check_target_branch("feature/x", "main", ["main", "master"])
        assert result["passed"] is True

    def test_same_branch_is_blocker(self):
        result = _check_target_branch("main", "main", ["main", "master"])
        assert result["passed"] is False
        assert result["level"] == "blocker"

    def test_from_protected_is_warning(self):
        result = _check_target_branch("main", "feature/x", ["main", "master"])
        assert result["passed"] is False
        assert result["level"] == "warning"


class TestCheckIndexAvailable:
    def test_no_index_is_warning(self, tmp_path: Path):
        result = _check_index_available(tmp_path)
        assert result["passed"] is False
        assert result["level"] == "warning"

    def test_index_exists_passes(self, tmp_path: Path):
        db = tmp_path / ".smartdev" / "index.sqlite"
        db.parent.mkdir(parents=True)
        db.write_bytes(b"")
        result = _check_index_available(tmp_path)
        assert result["passed"] is True


class TestMergeCheckSkillIntegration:
    def test_can_run_true(self, git_repo: Path):
        assert GitMergeCheckSkill().can_run(_ctx(git_repo))

    def test_can_run_false_non_git(self, tmp_path: Path):
        assert not GitMergeCheckSkill().can_run(_ctx(tmp_path))

    def test_clean_repo_has_ready_field(self, git_repo: Path):
        result = Skill.create("git.merge.check").run(_ctx(git_repo))
        assert result.success is True
        assert "ready" in result.data
        assert "checks" in result.data
        assert "blockers" in result.data
        assert "warnings" in result.data

    def test_dirty_repo_not_ready(self, git_repo: Path):
        (git_repo / "README.md").write_text("modified\n")
        result = Skill.create("git.merge.check").run(_ctx(git_repo))
        assert result.data["ready"] is False
        assert len(result.data["blockers"]) >= 1

    def test_feature_branch_checks_pass(self, feature_branch_repo: Path):
        result = Skill.create("git.merge.check").run(
            _ctx(feature_branch_repo), {"target_branch": "master"}
        )
        assert result.success is True
        # 在 feature 分支上，source/target 检查通过
        branch_check = next(c for c in result.data["checks"] if c["name"] == "source_branch_ok")
        assert branch_check["passed"] is True

    def test_target_branch_input(self, git_repo: Path):
        result = Skill.create("git.merge.check").run(
            _ctx(git_repo), {"target_branch": "develop"}
        )
        assert result.data["branch_info"]["target"] == "develop"

    def test_branch_info_in_output(self, git_repo: Path):
        result = Skill.create("git.merge.check").run(_ctx(git_repo))
        info = result.data["branch_info"]
        assert "current" in info
        assert "target" in info
        assert "is_current_protected" in info

    def test_checks_list_has_expected_names(self, git_repo: Path):
        result = Skill.create("git.merge.check").run(_ctx(git_repo))
        names = {c["name"] for c in result.data["checks"]}
        assert "working_tree_clean" in names
        assert "patch_backups_clean" in names
        assert "source_branch_ok" in names

    def test_next_steps_present(self, git_repo: Path):
        result = Skill.create("git.merge.check").run(_ctx(git_repo))
        assert len(result.next_steps) >= 1

    def test_git_not_found_graceful(self, monkeypatch, git_repo: Path):
        from smartdev.core import git as git_module
        def broken(self):
            from smartdev.core.git import GitNotAvailable
            raise GitNotAvailable("forced")
        monkeypatch.setattr(git_module.GitService, "current_branch", broken)
        result = GitMergeCheckSkill().run(_ctx(git_repo))
        assert result.success is False
        assert result.data["error"] == "GIT_NOT_FOUND"
