"""
test_run_artifact.py — Phase 11D Step 1 聚焦测试

覆盖：
- ScopeConfig 默认值 / 序列化 / 反序列化
- validate_run_id 格式校验
- create_run_artifact 成功路径
- create_run_artifact 重复 run_id → 报错
- create_run_artifact --force 覆盖
- scope.json 字段完整性

不覆盖：
- Scope Gate 检查逻辑（Step 2）
- handoff code/doc/review（Step 3-5）
- MCP 工具（Step 6）
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from smartdev.core.run_artifact import (
    DEFAULT_ALLOWED_PATHS,
    DEFAULT_DENIED_PATHS,
    DEFAULT_MAX_FILES,
    DEFAULT_PROTECTED_PATHS,
    ScopeConfig,
    create_run_artifact,
    validate_run_id,
)


# ── Fixtures ─────────────────────────────────────────────────


@pytest.fixture
def tmp_project():
    """临时项目目录（不含 .smartdev/）。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def tmp_project_with_smartdev(tmp_project):
    """临时项目目录（含 .smartdev/）。"""
    (tmp_project / ".smartdev").mkdir(exist_ok=True)
    return tmp_project


# ── ScopeConfig ──────────────────────────────────────────────


class TestScopeConfigDefaults:
    """ScopeConfig 默认值校验。"""

    def test_default_allowed_paths(self):
        scope = ScopeConfig()
        assert scope.allowed_paths == DEFAULT_ALLOWED_PATHS
        assert "smartdev/" in scope.allowed_paths

    def test_default_denied_paths(self):
        scope = ScopeConfig()
        assert scope.denied_paths == DEFAULT_DENIED_PATHS
        assert "__pycache__/" in scope.denied_paths

    def test_default_max_files(self):
        scope = ScopeConfig()
        assert scope.max_files == DEFAULT_MAX_FILES

    def test_default_protected_paths(self):
        scope = ScopeConfig()
        assert scope.protected_paths == DEFAULT_PROTECTED_PATHS
        assert "CHANGELOG.md" in scope.protected_paths

    def test_custom_values(self):
        scope = ScopeConfig(
            allowed_paths=["src/"],
            denied_paths=["secrets/"],
            max_files=5,
            protected_paths=["README.md"],
        )
        assert scope.allowed_paths == ["src/"]
        assert scope.denied_paths == ["secrets/"]
        assert scope.max_files == 5
        assert scope.protected_paths == ["README.md"]


class TestScopeConfigSerialization:
    """ScopeConfig JSON 序列化 / 反序列化。"""

    def test_to_dict(self):
        scope = ScopeConfig(allowed_paths=["a/"], max_files=3)
        d = scope.to_dict()
        assert d["allowed_paths"] == ["a/"]
        assert d["max_files"] == 3
        assert "denied_paths" in d
        assert "protected_paths" in d

    def test_to_json_roundtrip(self):
        scope = ScopeConfig(allowed_paths=["src/"], max_files=7)
        json_str = scope.to_json()
        loaded = json.loads(json_str)
        scope2 = ScopeConfig.from_dict(loaded)
        assert scope2.allowed_paths == scope.allowed_paths
        assert scope2.max_files == scope.max_files

    def test_from_dict_partial(self):
        scope = ScopeConfig.from_dict({"max_files": 3})
        # 未提供的字段回退到默认值
        assert scope.max_files == 3
        assert scope.allowed_paths == DEFAULT_ALLOWED_PATHS
        assert scope.denied_paths == DEFAULT_DENIED_PATHS
        assert scope.protected_paths == DEFAULT_PROTECTED_PATHS

    def test_from_dict_empty(self):
        scope = ScopeConfig.from_dict({})
        assert scope.max_files == DEFAULT_MAX_FILES
        assert scope.allowed_paths == DEFAULT_ALLOWED_PATHS


# ── validate_run_id ──────────────────────────────────────────


class TestValidateRunId:
    """run_id 格式校验。"""

    def test_valid_simple(self):
        assert validate_run_id("my-task") is None

    def test_valid_alphanumeric(self):
        assert validate_run_id("task123") is None

    def test_valid_with_dots(self):
        assert validate_run_id("phase.11d.step1") is None

    def test_valid_with_underscore(self):
        assert validate_run_id("fix_bug_42") is None

    def test_valid_longest(self):
        # 64 字符
        rid = "a" * 64
        assert validate_run_id(rid) is None

    def test_invalid_empty(self):
        err = validate_run_id("")
        assert err is not None
        assert "不能为空" in err

    def test_invalid_too_long(self):
        err = validate_run_id("a" * 65)
        assert err is not None

    def test_invalid_starts_with_dash(self):
        err = validate_run_id("-bad")
        assert err is not None

    def test_invalid_special_chars(self):
        err = validate_run_id("bad/name")
        assert err is not None

    def test_invalid_spaces(self):
        err = validate_run_id("bad name")
        assert err is not None

    def test_invalid_chinese(self):
        err = validate_run_id("任务1")
        assert err is not None


# ── create_run_artifact ──────────────────────────────────────


class TestCreateRunArtifactSuccess:
    """create_run_artifact 成功路径。"""

    def test_creates_run_directory(self, tmp_project):
        run_dir, err = create_run_artifact(tmp_project, "test-task")
        assert err is None
        assert run_dir.exists()
        assert run_dir.is_dir()
        assert run_dir.name == "test-task"

    def test_creates_under_smartdev_runs(self, tmp_project):
        run_dir, err = create_run_artifact(tmp_project, "task-1")
        assert err is None
        expected = tmp_project / ".smartdev" / "runs" / "task-1"
        assert run_dir == expected

    def test_scope_json_exists(self, tmp_project):
        run_dir, err = create_run_artifact(tmp_project, "task-2")
        assert err is None
        scope_path = run_dir / "scope.json"
        assert scope_path.exists()

    def test_scope_json_valid_content(self, tmp_project):
        run_dir, err = create_run_artifact(tmp_project, "task-3")
        assert err is None
        scope_path = run_dir / "scope.json"
        data = json.loads(scope_path.read_text(encoding="utf-8"))
        assert "allowed_paths" in data
        assert "denied_paths" in data
        assert "max_files" in data
        assert "protected_paths" in data

    def test_scope_json_default_values(self, tmp_project):
        run_dir, err = create_run_artifact(tmp_project, "task-4")
        assert err is None
        scope_path = run_dir / "scope.json"
        data = json.loads(scope_path.read_text(encoding="utf-8"))
        assert data["allowed_paths"] == DEFAULT_ALLOWED_PATHS
        assert data["max_files"] == DEFAULT_MAX_FILES

    def test_task_card_md_exists(self, tmp_project):
        run_dir, err = create_run_artifact(tmp_project, "task-5")
        assert err is None
        task_card = run_dir / "task-card.md"
        assert task_card.exists()

    def test_task_card_contains_run_id(self, tmp_project):
        run_dir, err = create_run_artifact(tmp_project, "my-feature")
        assert err is None
        content = (run_dir / "task-card.md").read_text(encoding="utf-8")
        assert "my-feature" in content

    def test_task_card_contains_task(self, tmp_project):
        run_dir, err = create_run_artifact(
            tmp_project, "task-6", task="修复登录 Bug"
        )
        assert err is None
        content = (run_dir / "task-card.md").read_text(encoding="utf-8")
        assert "修复登录 Bug" in content

    def test_task_card_contains_scope_info(self, tmp_project):
        run_dir, err = create_run_artifact(tmp_project, "task-7")
        assert err is None
        content = (run_dir / "task-card.md").read_text(encoding="utf-8")
        assert f"max_files: {DEFAULT_MAX_FILES}" in content

    def test_custom_scope_saved_correctly(self, tmp_project):
        custom_scope = ScopeConfig(
            allowed_paths=["src/only/"],
            max_files=3,
        )
        run_dir, err = create_run_artifact(
            tmp_project, "task-8", scope=custom_scope
        )
        assert err is None
        scope_path = run_dir / "scope.json"
        data = json.loads(scope_path.read_text(encoding="utf-8"))
        assert data["allowed_paths"] == ["src/only/"]
        assert data["max_files"] == 3


class TestCreateRunArtifactDuplicate:
    """重复 run_id 行为。"""

    def test_duplicate_fails_by_default(self, tmp_project):
        run_dir1, err1 = create_run_artifact(tmp_project, "dup-task")
        assert err1 is None
        assert run_dir1.exists()

        run_dir2, err2 = create_run_artifact(tmp_project, "dup-task")
        assert err2 is not None
        assert "已存在" in err2

    def test_duplicate_force_overwrites(self, tmp_project):
        # 第一次创建
        run_dir1, err1 = create_run_artifact(
            tmp_project, "dup-task-2",
            task="original task",
        )
        assert err1 is None

        # 写入一个标记文件证明这是旧目录
        (run_dir1 / "old_marker.txt").write_text("old")

        # 强制覆盖
        run_dir2, err2 = create_run_artifact(
            tmp_project, "dup-task-2",
            task="new task",
            force=True,
        )
        assert err2 is None
        assert run_dir2.exists()

        # 旧标记文件应该被删除
        assert not (run_dir2 / "old_marker.txt").exists()
        # 新内容生效
        content = (run_dir2 / "task-card.md").read_text(encoding="utf-8")
        assert "new task" in content

    def test_force_creates_fresh_scope(self, tmp_project):
        # 第一次：自定义 scope
        run_dir1, err1 = create_run_artifact(
            tmp_project, "dup-task-3",
            scope=ScopeConfig(max_files=99),
        )
        assert err1 is None

        # 强制覆盖：默认 scope
        run_dir2, err2 = create_run_artifact(
            tmp_project, "dup-task-3",
            force=True,
        )
        assert err2 is None
        scope_path = run_dir2 / "scope.json"
        data = json.loads(scope_path.read_text(encoding="utf-8"))
        assert data["max_files"] == DEFAULT_MAX_FILES  # 不是 99


class TestCreateRunArtifactInvalidRunId:
    """非法 run_id 行为。"""

    def test_empty_run_id(self, tmp_project):
        _, err = create_run_artifact(tmp_project, "")
        assert err is not None

    def test_special_chars_run_id(self, tmp_project):
        _, err = create_run_artifact(tmp_project, "bad/id")
        assert err is not None

    def test_spaces_run_id(self, tmp_project):
        _, err = create_run_artifact(tmp_project, "bad id")
        assert err is not None

    def test_too_long_run_id(self, tmp_project):
        _, err = create_run_artifact(tmp_project, "a" * 65)
        assert err is not None

    def test_no_file_created_on_invalid(self, tmp_project):
        _, err = create_run_artifact(tmp_project, "")
        assert err is not None
        # 不应该创建任何文件
        runs_dir = tmp_project / ".smartdev" / "runs"
        assert not runs_dir.exists() or not list(runs_dir.iterdir())


class TestCreateRunArtifactEdgeCases:
    """边界情况。"""

    def test_empty_task_defaults_to_placeholder(self, tmp_project):
        run_dir, err = create_run_artifact(tmp_project, "empty-task")
        assert err is None
        content = (run_dir / "task-card.md").read_text(encoding="utf-8")
        assert "（待填写）" in content

    def test_scope_json_is_valid_json(self, tmp_project):
        run_dir, err = create_run_artifact(tmp_project, "valid-json")
        assert err is None
        scope_path = run_dir / "scope.json"
        # 不应抛出异常
        data = json.loads(scope_path.read_text(encoding="utf-8"))
        assert isinstance(data, dict)

    def test_run_dir_only_contains_expected_files(self, tmp_project):
        run_dir, err = create_run_artifact(tmp_project, "clean-dir")
        assert err is None
        files = sorted(f.name for f in run_dir.iterdir())
        assert "scope.json" in files
        assert "task-card.md" in files
        assert "agent-output" in files
        assert "review" in files

    def test_nested_run_id_creates_nested_dirs(self, tmp_project):
        """嵌套 run_id（含点号）不创建嵌套目录。"""
        run_dir, err = create_run_artifact(tmp_project, "phase.11d.step1")
        assert err is None
        # 应该是一个目录，不是嵌套
        assert run_dir.name == "phase.11d.step1"
        assert run_dir.exists()
        assert run_dir.is_dir()

    def test_multiple_runs_independent(self, tmp_project):
        _run_dir1, err1 = create_run_artifact(
            tmp_project, "task-a", task="修复登录页面"
        )
        assert err1 is None
        _run_dir2, err2 = create_run_artifact(
            tmp_project, "task-b", task="更新API文档"
        )
        assert err2 is None

        # 两个目录独立
        content_a = (tmp_project / ".smartdev" / "runs" / "task-a" / "task-card.md").read_text("utf-8")
        content_b = (tmp_project / ".smartdev" / "runs" / "task-b" / "task-card.md").read_text("utf-8")
        assert "修复登录页面" in content_a
        assert "更新API文档" in content_b
        assert "修复登录页面" not in content_b
        assert "更新API文档" not in content_a


class TestAgentOutputAndReviewDirectories:
    """Phase 11D Step 6: agent-output/ 和 review/ 子目录 + 模板文件"""

    def test_agent_output_dir_exists(self, tmp_project):
        run_dir, err = create_run_artifact(tmp_project, "ao-1")
        assert err is None
        ao_dir = run_dir / "agent-output"
        assert ao_dir.exists()
        assert ao_dir.is_dir()

    def test_review_dir_exists(self, tmp_project):
        run_dir, err = create_run_artifact(tmp_project, "ao-2")
        assert err is None
        review_dir = run_dir / "review"
        assert review_dir.exists()
        assert review_dir.is_dir()

    def test_code_agent_result_template_exists(self, tmp_project):
        run_dir, err = create_run_artifact(tmp_project, "ao-3")
        assert err is None
        tmpl = run_dir / "agent-output" / "code-agent-result.template.md"
        assert tmpl.exists()
        content = tmpl.read_text(encoding="utf-8")
        assert "Code Agent Result" in content
        assert "## Status" in content
        assert "## Implemented" in content
        assert "## Changed Files" in content
        assert "## Tests" in content
        assert "## Open Questions" in content

    def test_commit_readiness_template_exists(self, tmp_project):
        run_dir, err = create_run_artifact(tmp_project, "ao-4")
        assert err is None
        tmpl = run_dir / "review" / "commit-readiness.template.md"
        assert tmpl.exists()
        content = tmpl.read_text(encoding="utf-8")
        assert "Commit Readiness" in content
        assert "## Decision" in content
        assert "## Required Fixes" in content
        assert "## Gates" in content
        assert "## Documentation Status" in content
        assert "## Suggested Commits" in content

    def test_templates_contain_run_id(self, tmp_project):
        run_dir, err = create_run_artifact(tmp_project, "ao-5")
        assert err is None
        ca = (run_dir / "agent-output" / "code-agent-result.template.md").read_text("utf-8")
        cr = (run_dir / "review" / "commit-readiness.template.md").read_text("utf-8")
        assert "ao-5" in ca
        assert "ao-5" in cr

    def test_force_recreates_dirs(self, tmp_project):
        """--force 覆盖时也重新创建 agent-output/ 和 review/。"""
        run_dir1, err1 = create_run_artifact(tmp_project, "ao-6")
        assert err1 is None
        # 写入标记文件
        (run_dir1 / "agent-output" / "old.txt").write_text("old")
        # force 覆盖
        run_dir2, err2 = create_run_artifact(tmp_project, "ao-6", force=True)
        assert err2 is None
        # 旧标记应被删除
        assert not (run_dir2 / "agent-output" / "old.txt").exists()
        # 新模板应存在
        assert (run_dir2 / "agent-output" / "code-agent-result.template.md").exists()
        assert (run_dir2 / "review" / "commit-readiness.template.md").exists()
