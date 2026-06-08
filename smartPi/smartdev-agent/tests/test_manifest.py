"""
ChangeManifest 测试 — Phase 11C Step 1

覆盖：
1. ChangeManifest 数据模型序列化 / 反序列化
2. manifest_from_files：change_type / risk_level / flags 推断
3. manifest_from_git_diff：working_tree_diff 来源（真实 git 仓库）
4. manifest_from_patch_apply：patch_apply 来源
5. manifest_from_git_commit：git_commit 来源
6. save_manifest / load_manifest / load_latest_manifest 持久化
7. git 不可用时 manifest_from_git_diff 不崩溃
8. public_surface_changed 各类公共接口文件触发
9. docs_likely_needed 推断逻辑
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import pytest

from smartdev.core.manifest import (
    ChangeManifest,
    load_latest_manifest,
    load_manifest,
    manifest_from_files,
    manifest_from_git_commit,
    manifest_from_git_diff,
    manifest_from_patch_apply,
    save_manifest,
)


# ── Helpers ────────────────────────────────────────────────


def _git(path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=str(path), capture_output=True, text=True
    )
    return result.stdout.strip()


@pytest.fixture()
def git_repo(tmp_path: Path) -> Path:
    """带一个初始 commit 的干净 git 仓库。"""
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "README.md").write_text("# Test\n")
    _git(tmp_path, "add", "README.md")
    _git(tmp_path, "commit", "-m", "init: initial commit")
    return tmp_path


@pytest.fixture()
def runs_dir(tmp_path: Path) -> Path:
    d = tmp_path / ".smartdev" / "runs"
    d.mkdir(parents=True)
    return d


# ── 数据模型序列化 ─────────────────────────────────────────


class TestChangeManifestModel:
    def test_to_dict_has_required_keys(self):
        m = ChangeManifest(
            run_id="test-run",
            source="working_tree_diff",
            timestamp="2026-06-08T00:00:00Z",
        )
        d = m.to_dict()
        required = {
            "run_id", "source", "timestamp", "changed_files",
            "change_type", "risk_level", "public_surface_changed",
            "cli_changed", "skill_changed", "mcp_changed",
            "docs_likely_needed", "validation",
        }
        assert required.issubset(d.keys())

    def test_roundtrip(self):
        m = ChangeManifest(
            run_id="rt-run",
            source="git_commit",
            timestamp="2026-06-08T12:00:00Z",
            changed_files=["a.py", "b.py"],
            change_type="fix",
            risk_level="R1",
            public_surface_changed=True,
            cli_changed=False,
            skill_changed=True,
            mcp_changed=False,
            docs_likely_needed=True,
            validation=["python -m pytest -q"],
            commit_message="fix(core): something",
        )
        restored = ChangeManifest.from_dict(m.to_dict())
        assert restored.run_id == m.run_id
        assert restored.source == m.source
        assert restored.changed_files == m.changed_files
        assert restored.change_type == m.change_type
        assert restored.risk_level == m.risk_level
        assert restored.public_surface_changed is True
        assert restored.skill_changed is True
        assert restored.docs_likely_needed is True
        assert restored.commit_message == m.commit_message

    def test_to_json_valid_json(self):
        m = ChangeManifest(run_id="json-run", source="patch_apply", timestamp="2026-01-01T00:00:00Z")
        raw = m.to_json()
        parsed = json.loads(raw)
        assert parsed["run_id"] == "json-run"
        assert parsed["source"] == "patch_apply"

    def test_from_dict_defaults(self):
        """from_dict 对缺失字段使用合理默认值。"""
        m = ChangeManifest.from_dict({"run_id": "x", "source": "git_commit", "timestamp": "t"})
        assert m.changed_files == []
        assert m.change_type == "feature"
        assert m.risk_level == "R1"
        assert m.public_surface_changed is False
        assert m.validation == []


# ── manifest_from_files ────────────────────────────────────


class TestManifestFromFiles:
    def test_basic_creation(self):
        m = manifest_from_files(["smartdev/core/foo.py"], "working_tree_diff")
        assert m.source == "working_tree_diff"
        assert "smartdev/core/foo.py" in m.changed_files

    def test_run_id_auto_generated(self):
        m = manifest_from_files([], "working_tree_diff")
        assert m.run_id.startswith("working_tree_diff-")

    def test_run_id_custom(self):
        m = manifest_from_files([], "working_tree_diff", run_id="my-run-001")
        assert m.run_id == "my-run-001"

    def test_timestamp_present(self):
        m = manifest_from_files([], "working_tree_diff")
        assert "T" in m.timestamp  # ISO 格式

    def test_changed_files_sorted(self):
        m = manifest_from_files(["z.py", "a.py", "m.py"], "working_tree_diff")
        assert m.changed_files == sorted(m.changed_files)

    # change_type 推断
    def test_change_type_from_commit_prefix_fix(self):
        m = manifest_from_files(["x.py"], "git_commit", commit_message="fix(x): broken")
        assert m.change_type == "fix"

    def test_change_type_from_commit_prefix_feat(self):
        m = manifest_from_files(["x.py"], "git_commit", commit_message="feat(x): new feature")
        assert m.change_type == "feature"

    def test_change_type_from_commit_prefix_docs(self):
        m = manifest_from_files(["README.md"], "git_commit", commit_message="docs: update readme")
        assert m.change_type == "docs"

    def test_change_type_from_commit_prefix_refactor(self):
        m = manifest_from_files(["x.py"], "git_commit", commit_message="refactor: clean up")
        assert m.change_type == "refactor"

    def test_change_type_inferred_test_files(self):
        m = manifest_from_files(["tests/test_foo.py"], "working_tree_diff")
        assert m.change_type == "test"

    def test_change_type_inferred_doc_files(self):
        m = manifest_from_files(["docs/guide.md"], "working_tree_diff")
        assert m.change_type == "docs"

    def test_change_type_default_feature(self):
        m = manifest_from_files(["smartdev/core/foo.py"], "working_tree_diff")
        assert m.change_type == "feature"

    # risk_level 推断
    def test_risk_r0_no_files(self):
        m = manifest_from_files([], "working_tree_diff")
        assert m.risk_level == "R0"

    def test_risk_r1_single_file(self):
        m = manifest_from_files(["smartdev/core/foo.py"], "working_tree_diff")
        assert m.risk_level == "R1"

    def test_risk_r2_many_files(self):
        files = [f"smartdev/core/f{i}.py" for i in range(6)]
        m = manifest_from_files(files, "working_tree_diff")
        assert m.risk_level == "R2"

    def test_risk_manual_override(self):
        m = manifest_from_files(["x.py"], "working_tree_diff", risk_level="R3")
        assert m.risk_level == "R3"

    # public_surface flags
    def test_cli_changed_flag(self):
        m = manifest_from_files(["smartdev/cli.py"], "working_tree_diff")
        assert m.cli_changed is True
        assert m.public_surface_changed is True

    def test_mcp_changed_flag(self):
        m = manifest_from_files(["smartdev/mcp/tools.py"], "working_tree_diff")
        assert m.mcp_changed is True
        assert m.public_surface_changed is True

    def test_skill_yaml_changed(self):
        m = manifest_from_files(["smartdev/skills/foo/skill.yaml"], "working_tree_diff")
        assert m.skill_changed is True
        assert m.public_surface_changed is True

    def test_skill_py_changed(self):
        m = manifest_from_files(["smartdev/skills/foo/skill.py"], "working_tree_diff")
        assert m.skill_changed is True

    def test_pyproject_toml_changed(self):
        m = manifest_from_files(["pyproject.toml"], "working_tree_diff")
        assert m.public_surface_changed is True

    def test_no_flags_for_unrelated_files(self):
        m = manifest_from_files(["smartdev/core/workflow.py"], "working_tree_diff")
        assert m.cli_changed is False
        assert m.mcp_changed is False

    # docs_likely_needed
    def test_docs_needed_when_public_surface_changed(self):
        m = manifest_from_files(["smartdev/cli.py"], "working_tree_diff")
        assert m.docs_likely_needed is True

    def test_docs_not_needed_for_pure_docs_change(self):
        m = manifest_from_files(["docs/guide.md"], "working_tree_diff", commit_message="docs: update")
        assert m.docs_likely_needed is False

    def test_docs_needed_for_feature_change(self):
        m = manifest_from_files(["smartdev/core/foo.py"], "working_tree_diff")
        assert m.docs_likely_needed is True

    # validation
    def test_default_validation_command(self):
        m = manifest_from_files(["x.py"], "working_tree_diff")
        assert len(m.validation) > 0
        assert any("pytest" in v for v in m.validation)

    # commit_message / patch_id 透传
    def test_commit_message_preserved(self):
        m = manifest_from_files(["x.py"], "git_commit", commit_message="feat: new feature")
        assert m.commit_message == "feat: new feature"

    def test_patch_id_preserved(self):
        m = manifest_from_files(["x.py"], "patch_apply", patch_id="20260608-abc123")
        assert m.patch_id == "20260608-abc123"


# ── manifest_from_patch_apply ──────────────────────────────


class TestManifestFromPatchApply:
    def test_source_is_patch_apply(self):
        m = manifest_from_patch_apply(["x.py"], "p001")
        assert m.source == "patch_apply"

    def test_patch_id_set(self):
        m = manifest_from_patch_apply(["x.py"], "p001")
        assert m.patch_id == "p001"

    def test_changed_files_set(self):
        m = manifest_from_patch_apply(["a.py", "b.py"], "p002")
        assert set(m.changed_files) == {"a.py", "b.py"}


# ── manifest_from_git_commit ───────────────────────────────


class TestManifestFromGitCommit:
    def test_source_is_git_commit(self):
        m = manifest_from_git_commit(["x.py"], "feat: something")
        assert m.source == "git_commit"

    def test_commit_message_set(self):
        m = manifest_from_git_commit(["x.py"], "feat: new skill")
        assert m.commit_message == "feat: new skill"

    def test_change_type_from_message(self):
        m = manifest_from_git_commit(["x.py"], "fix(core): broken import")
        assert m.change_type == "fix"


# ── manifest_from_git_diff（真实 git）────────────────────


class TestManifestFromGitDiff:
    def test_source_is_working_tree_diff(self, git_repo: Path):
        m = manifest_from_git_diff(git_repo)
        assert m.source == "working_tree_diff"

    def test_clean_repo_no_files(self, git_repo: Path):
        m = manifest_from_git_diff(git_repo)
        assert m.changed_files == []

    def test_detects_unstaged_changes(self, git_repo: Path):
        (git_repo / "README.md").write_text("modified\n")
        m = manifest_from_git_diff(git_repo)
        assert "README.md" in m.changed_files

    def test_detects_staged_changes(self, git_repo: Path):
        new_file = git_repo / "new.py"
        new_file.write_text("x = 1\n")
        _git(git_repo, "add", "new.py")
        m = manifest_from_git_diff(git_repo)
        assert "new.py" in m.changed_files

    def test_deduplicates_staged_and_unstaged(self, git_repo: Path):
        """同一文件 stage 后再修改，changed_files 中只出现一次。"""
        f = git_repo / "README.md"
        f.write_text("version 1\n")
        _git(git_repo, "add", "README.md")
        f.write_text("version 2\n")  # unstaged 再改一次
        m = manifest_from_git_diff(git_repo)
        assert m.changed_files.count("README.md") == 1

    def test_non_git_dir_returns_empty_manifest(self, tmp_path: Path):
        """git 不可用（非 git 目录）时返回空 manifest，不崩溃。"""
        m = manifest_from_git_diff(tmp_path)
        assert m.source == "working_tree_diff"
        assert m.changed_files == []

    def test_run_id_custom(self, git_repo: Path):
        m = manifest_from_git_diff(git_repo, run_id="my-custom-run")
        assert m.run_id == "my-custom-run"


# ── 持久化 ────────────────────────────────────────────────


class TestPersistence:
    def test_save_creates_file(self, runs_dir: Path):
        m = manifest_from_files(["x.py"], "working_tree_diff", run_id="run-001")
        out_path = save_manifest(m, runs_dir)
        assert out_path.exists()
        assert out_path.name == "change-manifest.json"

    def test_save_path_contains_run_id(self, runs_dir: Path):
        m = manifest_from_files(["x.py"], "working_tree_diff", run_id="run-abc")
        out_path = save_manifest(m, runs_dir)
        assert "run-abc" in str(out_path)

    def test_save_content_valid_json(self, runs_dir: Path):
        m = manifest_from_files(["x.py"], "working_tree_diff", run_id="run-json")
        out_path = save_manifest(m, runs_dir)
        parsed = json.loads(out_path.read_text())
        assert parsed["run_id"] == "run-json"

    def test_load_manifest_roundtrip(self, runs_dir: Path):
        m = manifest_from_files(
            ["smartdev/cli.py"], "working_tree_diff", run_id="run-load"
        )
        save_manifest(m, runs_dir)
        loaded = load_manifest("run-load", runs_dir)
        assert loaded is not None
        assert loaded.run_id == "run-load"
        assert loaded.cli_changed is True

    def test_load_manifest_missing_returns_none(self, runs_dir: Path):
        result = load_manifest("nonexistent-run", runs_dir)
        assert result is None

    def test_load_latest_manifest_returns_most_recent(self, runs_dir: Path):
        m1 = manifest_from_files(["a.py"], "working_tree_diff", run_id="run-first")
        save_manifest(m1, runs_dir)
        time.sleep(0.01)  # 确保 mtime 不同
        m2 = manifest_from_files(["b.py"], "working_tree_diff", run_id="run-second")
        save_manifest(m2, runs_dir)

        latest = load_latest_manifest(runs_dir)
        assert latest is not None
        assert latest.run_id == "run-second"

    def test_load_latest_manifest_empty_dir(self, runs_dir: Path):
        result = load_latest_manifest(runs_dir)
        assert result is None

    def test_load_latest_manifest_nonexistent_dir(self, tmp_path: Path):
        result = load_latest_manifest(tmp_path / "no_such_dir")
        assert result is None

    def test_save_creates_parent_dirs(self, tmp_path: Path):
        """runs_dir 不存在时 save_manifest 自动创建。"""
        runs_dir = tmp_path / ".smartdev" / "runs"
        m = manifest_from_files(["x.py"], "working_tree_diff", run_id="auto-dir")
        out_path = save_manifest(m, runs_dir)
        assert out_path.exists()
