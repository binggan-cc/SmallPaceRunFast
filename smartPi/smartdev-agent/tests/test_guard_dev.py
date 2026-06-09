"""
dev.guard Guard Skill 测试 — Phase 11B Step 2

覆盖：
1. Skill 注册 + 基本属性
2. mass_refactor — 大规模重构检测
3. protected_path_hit — 受保护路径命中
4. unrelated_change — 无关改动检测
5. test_deletion — 测试删除检测
6. config_in_code — 配置文件混入检测
7. forbidden_file_modification — 禁止文件修改
8. large_commit — 单 commit 过大
9. Skill.run() 集成测试
10. 工具函数单元测试（_match_any / _extract_keywords / _is_config_file / _is_code_file / _is_test_file）
11. 组合违规测试
12. 确定性验证
"""

from __future__ import annotations

from pathlib import Path

import pytest

from smartdev.core.guard_dev import (
    DevGuardResult,
    DevGuardViolation,
    _extract_keywords,
    _get_top_level_dir,
    _is_code_file,
    _is_config_file,
    _is_test_file,
    _match_any,
    check_dev_guard,
)
from smartdev.models import ProjectContext
from smartdev.skills.base import Skill


# ── Helpers ────────────────────────────────────────────────


def _ctx() -> ProjectContext:
    return ProjectContext(
        project_path=Path("/fake/project"),
        task_description="test dev.guard",
    )


# ── Skill 注册验证 ───────────────────────────────────────────


def test_skill_registered():
    """Skill 通过 __init_subclass__ 自动注册。"""
    from smartdev.skills.dev_guard import skill as _  # noqa: F401 — 触发注册
    skill_cls = Skill.get_skill("dev.guard")
    assert skill_cls is not None


def test_skill_attributes():
    """验证 Skill 基本属性。"""
    from smartdev.models import RiskLevel
    skill = Skill.create("dev.guard")
    assert skill.name == "dev.guard"
    assert skill.risk_level == RiskLevel.R0
    assert skill.can_run(_ctx()) is True


# ── 工具函数单元测试 ────────────────────────────────────────


class TestMatchAny:
    """路径匹配函数测试。"""

    def test_exact_match(self):
        assert _match_any("smartdev/cli.py", ["smartdev/cli.py"]) is True

    def test_directory_prefix(self):
        assert _match_any("smartdev/core/git.py", ["smartdev/"]) is True

    def test_mcp_directory_prefix(self):
        assert _match_any("smartdev/mcp/tools.py", ["smartdev/mcp/"]) is True

    def test_glob_match(self):
        assert _match_any("test_file.pyc", ["*.pyc"]) is True

    def test_glob_in_subdirectory(self):
        assert _match_any("foo/bar.pyc", ["*.pyc"]) is True

    def test_no_match(self):
        assert _match_any("smartdev/core/git.py", ["tests/", "README.md"]) is False

    def test_fnmatch_wildcard(self):
        assert _match_any("smartdev/core/git.py", ["smartdev/core/*.py"]) is True

    def test_empty_patterns(self):
        assert _match_any("any/file.py", []) is False

    def test_multiple_patterns(self):
        assert _match_any("tests/test_x.py", ["smartdev/", "tests/", "docs/"]) is True


class TestGetTopLevelDir:
    def test_nested_path(self):
        assert _get_top_level_dir("smartdev/core/git.py") == "core"

    def test_nested_skill_path(self):
        assert _get_top_level_dir("smartdev/skills/dev_guard/skill.py") == "skills"

    def test_shallow_path(self):
        assert _get_top_level_dir("tests/test_x.py") == "tests"

    def test_root_file(self):
        assert _get_top_level_dir("README.md") == ""

    def test_single_dir(self):
        assert _get_top_level_dir("docs/design.md") == "docs"


class TestExtractKeywords:
    def test_simple_english(self):
        kw = _extract_keywords("implement git status skill")
        assert "git" in kw
        assert "status" in kw

    def test_simple_chinese(self):
        # 中文无空格分词，整段被视为一个 token
        kw = _extract_keywords("实现变更预算检查")
        # 整个 token "实现变更预算检查" >= 3 chars 且非停用词，应被保留
        assert len(kw) >= 1

    def test_empty_string(self):
        assert _extract_keywords("") == set()

    def test_stopwords_filtered(self):
        kw = _extract_keywords("the is a in of for to")
        assert "the" not in kw

    def test_short_words_filtered(self):
        kw = _extract_keywords("a b c ab cd ef")
        assert "a" not in kw
        assert "b" not in kw

    def test_tech_short_words_kept(self):
        kw = _extract_keywords("git cli mcp r0 r2")
        assert "git" in kw
        assert "cli" in kw
        assert "mcp" in kw

    def test_mixed_cn_en(self):
        kw = _extract_keywords("实现 change.budget guard skill 检查")
        # "change.budget" is split, so "change" and "budget" become tokens
        assert "change" in kw
        assert "budget" in kw


class TestFileTypeClassifiers:
    def test_config_json(self):
        assert _is_config_file("config.json") is True

    def test_config_yaml(self):
        assert _is_config_file(".github/workflows/ci.yml") is True

    def test_config_env(self):
        assert _is_config_file(".env") is True

    def test_config_dockerfile(self):
        assert _is_config_file("Dockerfile") is True

    def test_not_config_py_source(self):
        assert _is_config_file("smartdev/core/git.py") is False

    def test_code_python(self):
        assert _is_code_file("app/main.py") is True

    def test_code_typescript(self):
        assert _is_code_file("src/App.tsx") is True

    def test_code_go(self):
        assert _is_code_file("pkg/handler.go") is True

    def test_not_code_markdown(self):
        assert _is_code_file("README.md") is False

    def test_test_file_prefix(self):
        assert _is_test_file("tests/test_guard_dev.py") is True

    def test_test_file_suffix(self):
        assert _is_test_file("guard_dev_test.py") is True

    def test_not_test_regular(self):
        assert _is_test_file("smartdev/core/guard_dev.py") is False


# ── 规则 1: mass_refactor ───────────────────────────────────


class TestMassRefactor:
    def test_two_dirs_no_trigger(self):
        result = check_dev_guard([
            "smartdev/core/a.py", "smartdev/skills/b.py",
        ])
        assert result.checks["mass_refactor"]["triggered"] is False

    def test_three_smartdev_modules_triggers(self):
        result = check_dev_guard([
            "smartdev/core/a.py",
            "smartdev/skills/b.py",
            "smartdev/context/c.py",
        ])
        assert result.checks["mass_refactor"]["triggered"] is True

    def test_three_dirs_is_error(self):
        result = check_dev_guard([
            "smartdev/core/a.py",
            "smartdev/skills/b.py",
            "smartdev/context/c.py",
        ])
        violations = [v for v in result.violations if v.rule == "mass_refactor"]
        assert len(violations) == 1
        assert violations[0].severity == "error"

    def test_four_dirs_triggers(self):
        result = check_dev_guard([
            "smartdev/core/a.py",
            "tests/test_b.py",
            "docs/design.md",
            "external/lib.py",
        ])
        assert result.checks["mass_refactor"]["triggered"] is True
        assert len(result.checks["mass_refactor"]["top_level_dirs"]) >= 3

    def test_cross_project_dirs(self):
        """smartdev 内部按子模块计，项目根目录按第一层计。"""
        result = check_dev_guard([
            "smartdev/core/a.py",
            "tests/test_a.py",
            "docs/design.md",
        ])
        assert result.checks["mass_refactor"]["triggered"] is True
        assert set(result.checks["mass_refactor"]["top_level_dirs"]) == {
            "core", "tests", "docs",
        }

    def test_single_dir_no_trigger(self):
        result = check_dev_guard([
            "smartdev/core/a.py",
            "smartdev/skills/b.py",
        ])
        assert result.checks["mass_refactor"]["triggered"] is False

    def test_empty_files(self):
        result = check_dev_guard([])
        assert result.checks["mass_refactor"]["triggered"] is False


# ── 规则 2: protected_path_hit ──────────────────────────────


class TestProtectedPathHit:
    def test_hit_protected_dir(self):
        result = check_dev_guard(
            ["smartdev/mcp/tools.py"],
            protected_paths=["smartdev/mcp/"],
        )
        assert result.checks["protected_path_hit"]["triggered"] is True

    def test_hit_protected_file(self):
        result = check_dev_guard(
            ["smartdev/cli.py"],
            protected_paths=["smartdev/cli.py"],
        )
        assert result.checks["protected_path_hit"]["triggered"] is True

    def test_is_error(self):
        result = check_dev_guard(
            ["smartdev/mcp/tools.py"],
            protected_paths=["smartdev/mcp/"],
        )
        violations = [v for v in result.violations if v.rule == "protected_path_hit"]
        assert len(violations) == 1
        assert violations[0].severity == "error"

    def test_no_hit(self):
        result = check_dev_guard(
            ["smartdev/core/git.py"],
            protected_paths=["smartdev/mcp/", "smartdev/cli.py"],
        )
        assert result.checks["protected_path_hit"]["triggered"] is False

    def test_multiple_hits(self):
        result = check_dev_guard(
            ["smartdev/mcp/tools.py", "smartdev/mcp/server.py"],
            protected_paths=["smartdev/mcp/"],
        )
        assert len(result.checks["protected_path_hit"]["hits"]) == 2

    def test_empty_protected_paths(self):
        result = check_dev_guard(["any/file.py"])
        assert result.checks["protected_path_hit"]["triggered"] is False


# ── 规则 3: unrelated_change ────────────────────────────────


class TestUnrelatedChange:
    def test_keyword_match_no_violation(self):
        result = check_dev_guard(
            ["smartdev/core/git.py", "tests/test_git.py"],
            task_description="implement git status skill",
        )
        assert result.checks["unrelated_change"]["triggered"] is False

    def test_keyword_mismatch_is_warning(self):
        result = check_dev_guard(
            ["smartdev/core/git.py", "docs/design.md"],
            task_description="implement git status skill",
        )
        # docs/design.md may not match git/status
        # but let's test with clearly unrelated files
        result = check_dev_guard(
            ["smartdev/mcp/tools.py", "smartdev/cli.py"],
            task_description="fix typo in readme",
        )
        violations = [v for v in result.violations if v.rule == "unrelated_change"]
        for v in violations:
            assert v.severity == "warning"  # never error

    def test_no_task_description_skips_check(self):
        result = check_dev_guard(
            ["smartdev/core/git.py", "tests/test_git.py"],
        )
        # No keywords extracted → no unrelated files detected
        assert result.checks["unrelated_change"]["triggered"] is False

    def test_chinese_task_description(self):
        result = check_dev_guard(
            ["smartdev/core/guard_budget.py", "tests/test_guard_budget.py"],
            task_description="实现变更预算检查 guard budget",
        )
        # "budget" should match guard_budget.py
        assert result.checks["unrelated_change"]["triggered"] is False


# ── 规则 4: test_deletion ───────────────────────────────────


class TestTestDeletion:
    def test_diff_with_deleted_test_function(self):
        diff = """--- a/tests/test_x.py
+++ b/tests/test_x.py
@@ -10,7 +10,6 @@
-def test_foo():
-    assert True
 def test_bar():
     assert False
"""
        result = check_dev_guard(
            ["tests/test_x.py"],
            diff_content=diff,
        )
        assert result.checks["test_deletion"]["triggered"] is True

    def test_diff_without_test_deletion(self):
        diff = """--- a/tests/test_x.py
+++ b/tests/test_x.py
@@ -10,6 +10,7 @@
 def test_foo():
     assert True
+def test_bar():
+    assert False
"""
        result = check_dev_guard(
            ["tests/test_x.py"],
            diff_content=diff,
        )
        assert result.checks["test_deletion"]["triggered"] is False

    def test_deleted_test_file_in_diff(self):
        diff = """--- a/tests/test_old.py
+++ /dev/null
@@ -1,3 +0,0 @@
-def test_foo():
-    assert True
"""
        result = check_dev_guard(
            ["tests/test_old.py"],
            diff_content=diff,
        )
        # The regex should match the deleted test file pattern
        assert result.checks["test_deletion"]["triggered"] is True

    def test_no_diff_content(self):
        result = check_dev_guard(["tests/test_x.py"])
        assert "未提供 diff_content" in result.checks["test_deletion"].get("note", "")

    def test_test_deletion_is_warning(self):
        diff = """--- a/tests/test_x.py
+++ b/tests/test_x.py
-def test_foo():
-    assert True
"""
        result = check_dev_guard(
            ["tests/test_x.py"],
            diff_content=diff,
        )
        violations = [v for v in result.violations if v.rule == "test_deletion"]
        if violations:
            assert violations[0].severity == "warning"


# ── 规则 5: config_in_code ──────────────────────────────────


class TestConfigInCode:
    def test_config_and_code_together(self):
        result = check_dev_guard([
            "config.json",
            "smartdev/core/git.py",
        ])
        assert result.checks["config_in_code"]["triggered"] is True

    def test_only_code_no_config(self):
        result = check_dev_guard([
            "smartdev/core/a.py",
            "smartdev/skills/b.py",
        ])
        assert result.checks["config_in_code"]["triggered"] is False

    def test_only_config_no_code(self):
        result = check_dev_guard([
            ".env",
            "config.json",
        ])
        assert result.checks["config_in_code"]["triggered"] is False

    def test_is_warning(self):
        result = check_dev_guard([
            "config.json",
            "smartdev/core/git.py",
        ])
        violations = [v for v in result.violations if v.rule == "config_in_code"]
        assert len(violations) == 1
        assert violations[0].severity == "warning"

    def test_markdown_not_config(self):
        result = check_dev_guard([
            "README.md",
            "smartdev/core/git.py",
        ])
        # README.md is markdown, not a config file
        assert result.checks["config_in_code"]["triggered"] is False

    def test_dockerfile_is_config(self):
        result = check_dev_guard([
            "Dockerfile",
            "smartdev/core/git.py",
        ])
        assert result.checks["config_in_code"]["triggered"] is True


# ── 规则 6: forbidden_file_modification ─────────────────────


class TestForbiddenFileModification:
    def test_hit_denied_paths(self):
        result = check_dev_guard(
            ["smartdev/mcp/tools.py"],
            denied_paths=["smartdev/mcp/"],
        )
        assert result.checks["forbidden_file_modification"]["triggered"] is True

    def test_hit_forbidden_paths(self):
        result = check_dev_guard(
            ["CHANGELOG.md"],
            forbidden_paths=["CHANGELOG.md", "CLAUDE.md"],
        )
        assert result.checks["forbidden_file_modification"]["triggered"] is True

    def test_is_error(self):
        result = check_dev_guard(
            ["CLAUDE.md"],
            forbidden_paths=["CLAUDE.md"],
        )
        violations = [v for v in result.violations
                       if v.rule == "forbidden_file_modification"]
        assert len(violations) == 1
        assert violations[0].severity == "error"

    def test_no_hit(self):
        result = check_dev_guard(
            ["smartdev/core/git.py"],
            denied_paths=["smartdev/mcp/"],
            forbidden_paths=["CHANGELOG.md"],
        )
        assert result.checks["forbidden_file_modification"]["triggered"] is False

    def test_both_denied_and_forbidden_checked(self):
        result = check_dev_guard(
            ["smartdev/mcp/server.py", "CHANGELOG.md"],
            denied_paths=["smartdev/mcp/"],
            forbidden_paths=["CHANGELOG.md"],
        )
        assert len(result.checks["forbidden_file_modification"]["hits"]) == 2


# ── 规则 7: large_commit ────────────────────────────────────


class TestLargeCommit:
    def test_within_limit(self):
        result = check_dev_guard(
            ["f{}.py".format(i) for i in range(5)],
            max_files_per_commit=12,
        )
        assert result.checks["large_commit"]["triggered"] is False

    def test_exceeds_limit(self):
        result = check_dev_guard(
            ["f{}.py".format(i) for i in range(15)],
            max_files_per_commit=12,
        )
        assert result.checks["large_commit"]["triggered"] is True

    def test_is_warning(self):
        result = check_dev_guard(
            ["f{}.py".format(i) for i in range(15)],
            max_files_per_commit=12,
        )
        violations = [v for v in result.violations if v.rule == "large_commit"]
        assert len(violations) == 1
        assert violations[0].severity == "warning"

    def test_default_max_files_per_commit(self):
        result = check_dev_guard(["f{}.py".format(i) for i in range(13)])
        assert result.checks["large_commit"]["triggered"] is True


# ── 组合违规测试 ────────────────────────────────────────────


class TestCombinedViolations:
    def test_mass_refactor_and_protected(self):
        result = check_dev_guard(
            [
                "smartdev/core/a.py",
                "smartdev/skills/b.py",
                "smartdev/context/c.py",
                "smartdev/mcp/tools.py",
            ],
            protected_paths=["smartdev/mcp/"],
        )
        assert result.passed is False
        rules = {v.rule for v in result.violations}
        assert "mass_refactor" in rules
        assert "protected_path_hit" in rules

    def test_all_rules_violated(self):
        diff = """--- a/tests/test_old.py
+++ /dev/null
-def test_foo():
-    assert True
"""
        result = check_dev_guard(
            [
                "smartdev/core/a.py",
                "smartdev/skills/b.py",
                "smartdev/context/c.py",
                "smartdev/mcp/tools.py",
                "config.json",
                "CLAUDE.md",
            ] + ["f{}.py".format(i) for i in range(13)],
            protected_paths=["smartdev/mcp/"],
            denied_paths=[],  # CLAUDE.md goes via forbidden_paths
            forbidden_paths=["CLAUDE.md"],
            task_description="fix typo",
            diff_content=diff,
            max_files_per_commit=10,
        )
        rules = {v.rule for v in result.violations}
        assert result.passed is False
        # At minimum: forbidden_file_modification, protected_path_hit, large_commit
        assert "forbidden_file_modification" in rules
        assert "large_commit" in rules

    def test_warnings_only_passes(self):
        """仅有 warning 时 passed=True。"""
        result = check_dev_guard(
            [
                "config.json",
                "smartdev/core/a.py",
            ],
            task_description="fix typo in readme",
            max_files_per_commit=1,
        )
        # unrelated_change + config_in_code + large_commit are all warnings
        assert result.passed is True


# ── Skill.run() 集成测试 ─────────────────────────────────────


class TestSkillRun:
    def test_run_with_changed_files(self):
        skill = Skill.create("dev.guard")
        result = skill.run(_ctx(), {
            "changed_files": ["smartdev/core/a.py", "tests/test_a.py"],
        })
        assert result.data["passed"] is True
        assert "checks" in result.data
        assert "violations" in result.data
        assert "summary" in result.data

    def test_run_mass_refactor(self):
        skill = Skill.create("dev.guard")
        result = skill.run(_ctx(), {
            "changed_files": [
                "smartdev/core/a.py",
                "tests/test_a.py",
                "docs/design.md",
                "external/lib.py",
            ],
        })
        assert result.data["passed"] is False

    def test_run_with_all_inputs(self):
        skill = Skill.create("dev.guard")
        result = skill.run(_ctx(), {
            "changed_files": ["smartdev/core/a.py", "tests/test_a.py"],
            "protected_paths": ["smartdev/mcp/"],
            "denied_paths": ["smartdev/cli.py"],
            "forbidden_paths": ["CHANGELOG.md"],
            "task_description": "implement core logic",
            "diff_content": "+def test_new(): pass",
            "max_files_per_commit": 5,
        })
        assert result.data["passed"] is True

    def test_run_empty_changed_files(self):
        skill = Skill.create("dev.guard")
        result = skill.run(_ctx(), {"changed_files": []})
        assert result.success is True

    def test_run_no_inputs(self):
        skill = Skill.create("dev.guard")
        result = skill.run(_ctx())
        assert result.success is True
        assert "无变更文件" in result.summary

    def test_run_returns_next_steps(self):
        skill = Skill.create("dev.guard")
        result = skill.run(_ctx(), {
            "changed_files": ["smartdev/core/a.py", "tests/test_a.py"],
        })
        assert len(result.next_steps) > 0

    def test_run_with_protected_path_hit(self):
        skill = Skill.create("dev.guard")
        result = skill.run(_ctx(), {
            "changed_files": ["smartdev/mcp/tools.py"],
            "protected_paths": ["smartdev/mcp/"],
        })
        assert result.success is False


# ── 确定性验证 ───────────────────────────────────────────────


def test_deterministic_output():
    """相同输入 → 相同输出（无随机性）。"""
    args = {
        "changed_files": [
            "smartdev/core/a.py",
            "smartdev/skills/b.py",
            "config.json",
        ],
        "protected_paths": ["smartdev/mcp/"],
        "task_description": "implement core feature",
        "max_files_per_commit": 5,
    }
    r1 = check_dev_guard(**args)
    r2 = check_dev_guard(**args)
    assert r1.passed == r2.passed
    assert r1.summary == r2.summary
    assert len(r1.violations) == len(r2.violations)
    for i, v1 in enumerate(r1.violations):
        assert v1.rule == r2.violations[i].rule
        assert v1.severity == r2.violations[i].severity


# ── 序列化验证 ──────────────────────────────────────────────


def test_dev_guard_result_to_dict():
    result = check_dev_guard(["a.py"])
    d = result.to_dict()
    assert "passed" in d
    assert "checks" in d
    assert "violations" in d
    assert "summary" in d
    assert isinstance(d["violations"], list)
    assert isinstance(d["checks"], dict)


def test_dev_guard_violation_to_dict():
    v = DevGuardViolation(
        rule="mass_refactor",
        severity="error",
        message="test message",
        detail={"top_level_dirs": ["core", "skills"]},
    )
    d = v.to_dict()
    assert d["rule"] == "mass_refactor"
    assert d["severity"] == "error"
    assert d["message"] == "test message"
    assert d["detail"]["top_level_dirs"] == ["core", "skills"]


# ── 摘要输出格式验证 ──────────────────────────────────────────


def test_summary_pass_format():
    result = check_dev_guard(["a.py", "b.py"])
    assert "✅" in result.summary

def test_summary_warning_format():
    result = check_dev_guard(
        ["a.py", "config.json"],
        task_description="fix typo in readme",
    )
    assert "⚠" in result.summary

def test_summary_fail_format():
    result = check_dev_guard(
        ["smartdev/core/a.py", "tests/test_b.py", "docs/design.md"],
    )
    assert "❌" in result.summary
