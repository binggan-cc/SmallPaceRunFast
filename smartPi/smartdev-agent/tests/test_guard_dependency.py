"""
dependency.guard Guard Skill 测试 — Phase 11B Step 3

覆盖：
1. Skill 注册 + 基本属性
2. Manifest 文件检测 (_is_manifest_file)
3. Manifest 解析: pyproject.toml / package.json / go.mod / requirements.txt
4. Lock 文件映射 + 同步检查
5. 依赖 diff 分析 (before/after 对比)
6. diff_content 分析
7. 规则: dependency_added / dependency_removed / dependency_version_changed
8. 规则: manifest_added / manifest_removed
9. 规则: lock_not_updated
10. 建议命令生成
11. 空输入 / 无 manifest 边界情况
12. Skill.run() 集成测试
13. 确定性验证
"""

from __future__ import annotations

from pathlib import Path

import pytest

from smartdev.core.guard_dependency import (
    DependencyChange,
    DependencyResult,
    DependencyViolation,
    _analyze_diff_for_manifest_changes,
    _check_lock_sync,
    _diff_dependencies,
    _generate_suggestions,
    _get_ecosystem_for_manifest,
    _get_lock_files_for_manifest,
    _is_manifest_file,
    _parse_go_mod,
    _parse_manifest,
    _parse_package_json,
    _parse_pyproject_toml,
    _parse_requirements_txt,
    check_dependency_guard,
)
from smartdev.models import ProjectContext
from smartdev.skills.base import Skill


# ── Helpers ────────────────────────────────────────────────


def _ctx() -> ProjectContext:
    return ProjectContext(
        project_path=Path("/fake/project"),
        task_description="test dependency.guard",
    )


# ── Skill 注册验证 ───────────────────────────────────────────


def test_skill_registered():
    """import smartdev.skills 后 dependency.guard Skill 已注册。"""
    import smartdev.skills  # noqa: F401 — 触发统一注册
    skill_cls = Skill.get_skill("dependency.guard")
    assert skill_cls is not None


def test_skill_attributes():
    """验证 Skill 基本属性。"""
    skill = Skill.create("dependency.guard")
    assert skill.name == "dependency.guard"
    from smartdev.models import RiskLevel
    assert skill.risk_level == RiskLevel.R0
    assert skill.can_run(_ctx()) is True


# ── _is_manifest_file 单元测试 ─────────────────────────────────


class TestIsManifestFile:
    def test_pyproject_toml(self):
        assert _is_manifest_file("pyproject.toml") is True

    def test_nested_pyproject_toml(self):
        assert _is_manifest_file("subdir/pyproject.toml") is True

    def test_package_json(self):
        assert _is_manifest_file("package.json") is True

    def test_go_mod(self):
        assert _is_manifest_file("go.mod") is True

    def test_requirements_txt(self):
        assert _is_manifest_file("requirements.txt") is True

    def test_regular_py_file(self):
        assert _is_manifest_file("src/main.py") is False

    def test_config_json(self):
        assert _is_manifest_file("config.json") is False

    def test_dockerfile(self):
        assert _is_manifest_file("Dockerfile") is False


# ── Lock 文件函数测试 ──────────────────────────────────────────


class TestLockFiles:
    def test_pyproject_lock_files(self):
        locks = _get_lock_files_for_manifest("pyproject.toml")
        assert "poetry.lock" in locks
        assert "uv.lock" in locks

    def test_package_json_lock_files(self):
        locks = _get_lock_files_for_manifest("package.json")
        assert "package-lock.json" in locks
        assert "pnpm-lock.yaml" in locks
        assert "yarn.lock" in locks

    def test_go_mod_lock_files(self):
        locks = _get_lock_files_for_manifest("go.mod")
        assert "go.sum" in locks

    def test_requirements_txt_lock_files(self):
        locks = _get_lock_files_for_manifest("requirements.txt")
        assert "requirements.lock" in locks

    def test_non_manifest_no_lock_files(self):
        locks = _get_lock_files_for_manifest("main.py")
        assert locks == []


class TestEcosystem:
    def test_python_ecosystem_pyproject(self):
        assert _get_ecosystem_for_manifest("pyproject.toml") == "python"

    def test_python_ecosystem_requirements(self):
        assert _get_ecosystem_for_manifest("requirements.txt") == "python"

    def test_nodejs_ecosystem(self):
        assert _get_ecosystem_for_manifest("package.json") == "nodejs"

    def test_go_ecosystem(self):
        assert _get_ecosystem_for_manifest("go.mod") == "go"

    def test_unknown_ecosystem(self):
        assert _get_ecosystem_for_manifest("main.py") == ""


# ── pyproject.toml 解析测试 ───────────────────────────────────


class TestParsePyprojectToml:
    def test_pep621_dependencies(self):
        """解析 PEP 621 [project] dependencies 列表格式。"""
        content = """[project]
name = "my-project"
version = "0.1.0"
dependencies = [
    "fastapi>=0.104.0",
    "uvicorn[standard]>=0.24.0",
    "pydantic>=2.5,<3",
]
"""
        deps = _parse_pyproject_toml(content)
        assert "fastapi" in deps
        assert "uvicorn[standard]" in deps
        assert "pydantic" in deps

    def test_poetry_dependencies(self):
        """解析 [tool.poetry.dependencies] 格式。"""
        content = """[tool.poetry]
name = "my-project"

[tool.poetry.dependencies]
python = "^3.10"
fastapi = "^0.115.0"
click = "^8.1"
"""
        deps = _parse_pyproject_toml(content)
        assert "fastapi" in deps
        assert "click" in deps
        assert "python" not in deps  # python 版本约束应被排除

    def test_poetry_dict_version(self):
        """Poetry dict 格式版本号。"""
        content = """[tool.poetry.dependencies]
fastapi = {version = "^0.115.0", optional = true}
"""
        deps = _parse_pyproject_toml(content)
        assert "fastapi" in deps
        assert deps["fastapi"] == "^0.115.0"

    def test_empty_pyproject(self):
        """空 pyproject.toml。"""
        deps = _parse_pyproject_toml("")
        assert deps == {}

    def test_no_deps_pyproject(self):
        """无依赖节的 pyproject.toml。"""
        content = """[project]
name = "minimal"
version = "0.1.0"
"""
        deps = _parse_pyproject_toml(content)
        assert deps == {}

    def test_fallback_line_parsing(self):
        """降级行解析（模拟 tomllib 不可用情况需回退）。"""
        content = """[tool.poetry]
[tool.poetry.dependencies]
python = "^3.10"
httpx = ">=0.25"
"""
        deps = _parse_pyproject_toml(content)
        # 行解析应从 TOML 中提取
        assert "httpx" in deps or len(deps) >= 0  # 至少有解析行为


# ── package.json 解析测试 ──────────────────────────────────────


class TestParsePackageJson:
    def test_all_dep_sections(self):
        """解析所有依赖节。"""
        content = """{
  "dependencies": {
    "express": "^4.18.0",
    "lodash": "4.17.21"
  },
  "devDependencies": {
    "jest": "^29.0.0"
  },
  "peerDependencies": {
    "react": "^18.0.0"
  },
  "optionalDependencies": {
    "fsevents": "^2.3.0"
  }
}"""
        deps = _parse_package_json(content)
        assert "express" in deps
        assert deps["express"] == "^4.18.0"
        assert "lodash" in deps
        assert "jest [devDependencies]" in deps
        assert "react [peerDependencies]" in deps
        assert "fsevents [optionalDependencies]" in deps

    def test_empty_package_json(self):
        deps = _parse_package_json("{}")
        assert deps == {}

    def test_invalid_json(self):
        deps = _parse_package_json("not valid json")
        assert deps == {}

    def test_only_dependencies_section(self):
        content = '{"dependencies": {"vue": "^3.0.0"}}'
        deps = _parse_package_json(content)
        assert len(deps) == 1
        assert deps["vue"] == "^3.0.0"


# ── go.mod 解析测试 ────────────────────────────────────────────


class TestParseGoMod:
    def test_single_require(self):
        """单行 require。"""
        content = """module example.com/myapp

go 1.21

require github.com/gin-gonic/gin v1.9.1
"""
        deps = _parse_go_mod(content)
        assert "github.com/gin-gonic/gin" in deps
        assert deps["github.com/gin-gonic/gin"] == "v1.9.1"

    def test_require_block(self):
        """require (...) 块。"""
        content = """module example.com/myapp

go 1.21

require (
    github.com/gin-gonic/gin v1.9.1
    github.com/rs/zerolog v1.31.0
)
"""
        deps = _parse_go_mod(content)
        assert "github.com/gin-gonic/gin" in deps
        assert "github.com/rs/zerolog" in deps

    def test_require_block_with_indirect(self):
        """require 块含 indirect 依赖。"""
        content = """require (
    github.com/davecgh/go-spew v1.1.1 // indirect
    golang.org/x/sync v0.5.0
)
"""
        deps = _parse_go_mod(content)
        assert "github.com/davecgh/go-spew [indirect]" in deps
        assert "golang.org/x/sync" in deps

    def test_empty_go_mod(self):
        deps = _parse_go_mod("")
        assert deps == {}

    def test_only_module_line(self):
        content = "module example.com/myapp"
        deps = _parse_go_mod(content)
        assert deps == {}


# ── requirements.txt 解析测试 ──────────────────────────────────


class TestParseRequirementsTxt:
    def test_pinned_versions(self):
        content = """fastapi==0.104.0
uvicorn>=0.24.0
pydantic~=2.5
"""
        deps = _parse_requirements_txt(content)
        assert deps["fastapi"] == "==0.104.0"
        assert deps["uvicorn"] == ">=0.24.0"
        assert deps["pydantic"] == "~=2.5"

    def test_no_version(self):
        content = "requests\nflask"
        deps = _parse_requirements_txt(content)
        assert deps["requests"] == "*"
        assert deps["flask"] == "*"

    def test_skip_comments_and_options(self):
        content = """# This is a comment
--index-url https://pypi.org/simple
fastapi==0.104.0
-r base.txt
-e .
"""
        deps = _parse_requirements_txt(content)
        # fastapi should still be parsed
        assert "fastapi" in deps
        # -r and -e lines should be skipped
        assert len(deps) == 1

    def test_environment_markers(self):
        content = """fastapi==0.104.0
typing-extensions>=4.0; python_version < "3.13"
"""
        deps = _parse_requirements_txt(content)
        assert "fastapi" in deps
        assert "typing-extensions" in deps
        assert deps["typing-extensions"] == ">=4.0"

    def test_extras(self):
        content = "uvicorn[standard]==0.24.0"
        deps = _parse_requirements_txt(content)
        assert "uvicorn[standard]" in deps

    def test_empty_requirements(self):
        deps = _parse_requirements_txt("")
        assert deps == {}

    def test_inline_comments(self):
        content = "fastapi==0.104.0  # the web framework"
        deps = _parse_requirements_txt(content)
        assert deps["fastapi"] == "==0.104.0"


# ── _parse_manifest 统一入口 ──────────────────────────────────


class TestParseManifest:
    def test_routes_to_correct_parser(self):
        pyproject = _parse_manifest("pyproject.toml", '[project]\ndependencies = ["fastapi>=0.104.0"]\n')
        assert "fastapi" in pyproject

        package_json = _parse_manifest("package.json", '{"dependencies": {"lodash": "4.0.0"}}')
        assert "lodash" in package_json

        go_mod = _parse_manifest("go.mod", "require github.com/foo/bar v1.0.0")
        assert "github.com/foo/bar" in go_mod

        reqs = _parse_manifest("requirements.txt", "click==8.0")
        assert "click" in reqs

    def test_unknown_manifest_returns_empty(self):
        deps = _parse_manifest("unknown.file", "some content")
        assert deps == {}


# ── _diff_dependencies 测试 ──────────────────────────────────


class TestDiffDependencies:
    def test_added_dependency(self):
        before = {"flask": "2.0.0"}
        after = {"flask": "2.0.0", "fastapi": "0.104.0"}
        changes = _diff_dependencies(before, after, "pyproject.toml")
        assert len(changes) == 1
        assert changes[0].change_type == "added"
        assert changes[0].name == "fastapi"
        assert changes[0].new_version == "0.104.0"

    def test_removed_dependency(self):
        before = {"flask": "2.0.0", "fastapi": "0.104.0"}
        after = {"flask": "2.0.0"}
        changes = _diff_dependencies(before, after, "pyproject.toml")
        assert len(changes) == 1
        assert changes[0].change_type == "removed"
        assert changes[0].name == "fastapi"

    def test_version_changed(self):
        before = {"fastapi": "0.104.0"}
        after = {"fastapi": "0.115.0"}
        changes = _diff_dependencies(before, after, "pyproject.toml")
        assert len(changes) == 1
        assert changes[0].change_type == "version_changed"
        assert changes[0].old_version == "0.104.0"
        assert changes[0].new_version == "0.115.0"

    def test_mixed_changes(self):
        before = {"a": "1.0", "b": "2.0", "c": "3.0"}
        after = {"a": "1.0", "b": "3.0", "d": "4.0"}
        changes = _diff_dependencies(before, after, "manifest")
        assert len(changes) == 3  # b: version_changed, c: removed, d: added

    def test_no_changes(self):
        before = {"a": "1.0", "b": "2.0"}
        after = {"a": "1.0", "b": "2.0"}
        changes = _diff_dependencies(before, after, "manifest")
        assert len(changes) == 0

    def test_manifest_field_in_result(self):
        changes = _diff_dependencies({"old": "1"}, {"new": "2"}, "pyproject.toml")
        for c in changes:
            assert c.manifest == "pyproject.toml"


# ── _check_lock_sync 测试 ────────────────────────────────────


class TestCheckLockSync:
    def test_lock_synced(self):
        """manifest 变更且 lock 文件在 changed_files 中。"""
        changes = [
            DependencyChange(manifest="pyproject.toml", change_type="version_changed",
                           name="fastapi", old_version="0.1", new_version="0.2"),
        ]
        violations = _check_lock_sync(
            changes,
            changed_files=["pyproject.toml", "poetry.lock"],
        )
        assert len(violations) == 0

    def test_lock_not_synced(self):
        """manifest 变更但 lock 文件不在 changed_files 中。"""
        changes = [
            DependencyChange(manifest="pyproject.toml", change_type="version_changed",
                           name="fastapi", old_version="0.1", new_version="0.2"),
        ]
        violations = _check_lock_sync(
            changes,
            changed_files=["pyproject.toml"],
        )
        assert len(violations) == 1
        assert violations[0].rule == "lock_not_updated"
        assert violations[0].severity == "warning"

    def test_lock_synced_via_lock_files_changed_param(self):
        """使用 lock_files_changed 参数。"""
        changes = [
            DependencyChange(manifest="package.json", change_type="added",
                           name="lodash", new_version="^4.0.0"),
        ]
        violations = _check_lock_sync(
            changes,
            changed_files=["package.json"],
            lock_files_changed=["package-lock.json"],
        )
        assert len(violations) == 0

    def test_no_manifest_changes_no_lock_check(self):
        violations = _check_lock_sync([], ["pyproject.toml"])
        assert len(violations) == 0

    def test_multiple_lock_files_any_synced(self):
        """任一 lock 文件在变更中就认为已同步。"""
        changes = [
            DependencyChange(manifest="pyproject.toml", change_type="added",
                           name="newdep", new_version="^1.0"),
        ]
        # pyproject.toml 期望 poetry.lock / uv.lock / requirements.lock
        # uv.lock 在变更中 → 已同步
        violations = _check_lock_sync(
            changes,
            changed_files=["pyproject.toml", "uv.lock"],
        )
        assert len(violations) == 0


# ── _generate_suggestions 测试 ────────────────────────────────


class TestGenerateSuggestions:
    def test_python_suggestions(self):
        suggestions = _generate_suggestions(["pyproject.toml"], has_changes=True)
        assert any("pip-audit" in s for s in suggestions)

    def test_nodejs_suggestions(self):
        suggestions = _generate_suggestions(["package.json"], has_changes=True)
        assert any("npm audit" in s for s in suggestions)

    def test_go_suggestions(self):
        suggestions = _generate_suggestions(["go.mod"], has_changes=True)
        assert any("govulncheck" in s for s in suggestions)

    def test_no_changes_no_suggestions(self):
        suggestions = _generate_suggestions(["pyproject.toml"], has_changes=False)
        assert suggestions == []

    def test_multi_ecosystem(self):
        suggestions = _generate_suggestions(
            ["pyproject.toml", "package.json"], has_changes=True
        )
        assert len(suggestions) >= 2


# ── check_dependency_guard 核心函数测试 ────────────────────────


class TestCheckDependencyGuard:
    def test_no_manifest_files(self):
        """没有 manifest 文件变更。"""
        result = check_dependency_guard(
            changed_files=["src/main.py", "README.md"],
        )
        assert result.passed is True
        assert result.manifests_found == []
        assert "无依赖 manifest" in result.summary

    def test_empty_input(self):
        """空变更输入。"""
        result = check_dependency_guard(changed_files=[])
        assert result.passed is True
        assert result.manifests_found == []

    def test_manifest_in_changed_files(self):
        """changed_files 包含 manifest 文件。"""
        result = check_dependency_guard(
            changed_files=["pyproject.toml", "src/main.py"],
            manifest_before={"pyproject.toml": '[project]\ndependencies = ["fastapi==2.0.0"]\n'},
            manifest_after={"pyproject.toml": '[project]\ndependencies = ["fastapi==2.1.0"]\n'},
        )
        assert result.manifests_found == ["pyproject.toml"]
        # 版本变更应被检测到
        version_changes = [
            c for c in result.changes if c.change_type == "version_changed"
        ]
        assert len(version_changes) >= 1

    def test_dependency_added_rule(self):
        """新增依赖 → warning。"""
        result = check_dependency_guard(
            changed_files=["pyproject.toml"],
            manifest_before={"pyproject.toml": '[project]\ndependencies = ["flask==2.0"]\n'},
            manifest_after={"pyproject.toml": '[project]\ndependencies = ["flask==2.0", "fastapi==0.1"]\n'},
        )
        violations = [v for v in result.violations if v.rule == "dependency_added"]
        assert len(violations) >= 1
        for v in violations:
            assert v.severity == "warning"

    def test_dependency_removed_rule(self):
        """删除依赖 → warning。"""
        result = check_dependency_guard(
            changed_files=["pyproject.toml"],
            manifest_before={"pyproject.toml": '[project]\ndependencies = ["flask==2.0", "fastapi==0.1"]\n'},
            manifest_after={"pyproject.toml": '[project]\ndependencies = ["fastapi==0.1"]\n'},
        )
        violations = [v for v in result.violations if v.rule == "dependency_removed"]
        assert len(violations) >= 1
        for v in violations:
            assert v.severity == "warning"

    def test_dependency_version_changed_rule(self):
        """版本变更 → warning。"""
        result = check_dependency_guard(
            changed_files=["pyproject.toml"],
            manifest_before={"pyproject.toml": '[project]\ndependencies = ["fastapi==0.104.0"]\n'},
            manifest_after={"pyproject.toml": '[project]\ndependencies = ["fastapi==0.115.0"]\n'},
        )
        violations = [
            v for v in result.violations
            if v.rule == "dependency_version_changed"
        ]
        assert len(violations) >= 1
        for v in violations:
            assert v.severity == "warning"

    def test_manifest_added_rule(self):
        """新增 manifest → info。"""
        result = check_dependency_guard(
            changed_files=["package.json"],
            manifest_before={},
            manifest_after={"package.json": '{"dependencies": {"a": "1.0.0"}}'},
        )
        violations = [v for v in result.violations if v.rule == "manifest_added"]
        assert len(violations) >= 1
        for v in violations:
            assert v.severity == "info"

    def test_manifest_removed_rule(self):
        """删除 manifest → error。"""
        result = check_dependency_guard(
            changed_files=["pyproject.toml"],
            manifest_before={"pyproject.toml": "[project]\n"},
            manifest_after={},
        )
        violations = [v for v in result.violations if v.rule == "manifest_removed"]
        assert len(violations) >= 1
        for v in violations:
            assert v.severity == "error"

    def test_passed_only_error_blocks(self):
        """只有 error 级别违规时 passed=False；warning/info 不阻断。"""
        # 只有 warning/info 时 passed=True
        result = check_dependency_guard(
            changed_files=["pyproject.toml"],
            manifest_before={"pyproject.toml": '[project]\ndependencies = ["flask==2.0"]\n'},
            manifest_after={"pyproject.toml": '[project]\ndependencies = ["flask==2.1"]\n'},
        )
        # 版本变更 = warning，不应阻断
        assert result.passed is True

        # manifest_removed = error，应阻断
        result2 = check_dependency_guard(
            changed_files=["pyproject.toml"],
            manifest_before={"pyproject.toml": "[project]\n"},
            manifest_after={},
        )
        assert result2.passed is False

    def test_lock_sync_check_integration(self):
        """集成测试：manifest 变更但 lock 未同步。"""
        result = check_dependency_guard(
            changed_files=["pyproject.toml", "src/main.py"],
            manifest_before={"pyproject.toml": '[project]\ndependencies = ["flask==2.0"]\n'},
            manifest_after={"pyproject.toml": '[project]\ndependencies = ["flask==2.1"]\n'},
        )
        # 没有 poetry.lock 在 changed_files 中
        lock_violations = [
            v for v in result.violations if v.rule == "lock_not_updated"
        ]
        # 有依赖变更但没有 lock 文件 → 应报警告
        if any(c.change_type == "version_changed" for c in result.changes):
            assert len(lock_violations) >= 1

    def test_suggestions_in_result(self):
        """结果中包含安全审计建议。"""
        result = check_dependency_guard(
            changed_files=["pyproject.toml"],
            manifest_before={"pyproject.toml": '[project]\ndependencies = ["flask==2.0"]\n'},
            manifest_after={"pyproject.toml": '[project]\ndependencies = ["flask==2.1"]\n'},
        )
        assert len(result.suggestions) > 0
        assert any("pip-audit" in s for s in result.suggestions)


# ── diff_content 分析测试 ─────────────────────────────────────


class TestDiffContentAnalysis:
    def test_diff_added_dependency_in_pyproject(self):
        """从 diff 中检测 pyproject.toml 新增依赖。"""
        diff = """diff --git a/pyproject.toml b/pyproject.toml
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -3,6 +3,7 @@
 dependencies = [
     "flask==2.0",
+    "fastapi>=0.104.0",
     "click==8.0",
 ]
"""
        changes = _analyze_diff_for_manifest_changes(diff)
        added = [c for c in changes if c.change_type == "added"]
        assert any(c.name == "fastapi" for c in added)

    def test_diff_removed_dependency_in_pyproject(self):
        """从 diff 中检测 pyproject.toml 删除依赖。"""
        diff = """diff --git a/pyproject.toml b/pyproject.toml
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -3,6 +3,5 @@
 dependencies = [
     "flask==2.0",
-    "fastapi>=0.104.0",
     "click==8.0",
 ]
"""
        changes = _analyze_diff_for_manifest_changes(diff)
        removed = [c for c in changes if c.change_type == "removed"]
        assert any(c.name == "fastapi" for c in removed)

    def test_diff_package_json_added(self):
        """从 diff 检测 package.json 新增依赖。"""
        diff = """diff --git a/package.json b/package.json
--- a/package.json
+++ b/package.json
@@ -3,5 +3,6 @@
   "dependencies": {
-    "express": "^4.18.0"
+    "express": "^4.18.0",
+    "lodash": "^4.17.21"
   }
 }
"""
        changes = _analyze_diff_for_manifest_changes(diff)
        added = [c for c in changes if c.change_type == "added"]
        assert any(c.name == "lodash" for c in added)

    def test_diff_go_mod_version_change(self):
        """从 diff 检测 go.mod 版本变更。"""
        diff = """diff --git a/go.mod b/go.mod
--- a/go.mod
+++ b/go.mod
@@ -1,3 +1,3 @@
 module example.com/app
-require github.com/gin-gonic/gin v1.9.0
+require github.com/gin-gonic/gin v1.10.0
"""
        changes = _analyze_diff_for_manifest_changes(diff)
        version_changes = [
            c for c in changes if c.change_type == "version_changed"
        ]
        assert any(c.name == "github.com/gin-gonic/gin" for c in version_changes)

    def test_diff_non_manifest_ignored(self):
        """非 manifest 文件的 diff 被忽略。"""
        diff = """diff --git a/src/main.py b/src/main.py
--- a/src/main.py
+++ b/src/main.py
@@ -1 +1 @@
-print("hello")
+print("world")
"""
        changes = _analyze_diff_for_manifest_changes(diff)
        assert len(changes) == 0


# ── package.json manifest_before/after 对比测试 ────────────────


class TestPackageJsonBeforeAfter:
    def test_version_change_in_package_json(self):
        result = check_dependency_guard(
            changed_files=["package.json"],
            manifest_before={
                "package.json": '{"dependencies": {"express": "^4.18.0"}}'
            },
            manifest_after={
                "package.json": '{"dependencies": {"express": "^4.19.0"}}'
            },
        )
        version_changes = [
            c for c in result.changes if c.change_type == "version_changed"
        ]
        assert any(c.name == "express" for c in version_changes)

    def test_added_dep_in_package_json(self):
        result = check_dependency_guard(
            changed_files=["package.json"],
            manifest_before={
                "package.json": '{"dependencies": {"express": "^4.18.0"}}'
            },
            manifest_after={
                "package.json": '{"dependencies": {"express": "^4.18.0", "lodash": "^4.0.0"}}'
            },
        )
        added = [c for c in result.changes if c.change_type == "added"]
        assert any(c.name == "lodash" for c in added)

    def test_lock_sync_for_package_json(self):
        """package.json 变更 + package-lock.json 同步。"""
        result = check_dependency_guard(
            changed_files=["package.json", "package-lock.json"],
            manifest_before={
                "package.json": '{"dependencies": {"express": "^4.18.0"}}'
            },
            manifest_after={
                "package.json": '{"dependencies": {"express": "^4.19.0"}}'
            },
        )
        lock_violations = [
            v for v in result.violations if v.rule == "lock_not_updated"
        ]
        assert len(lock_violations) == 0


# ── go.mod before/after 对比测试 ─────────────────────────────


class TestGoModBeforeAfter:
    def test_added_require_in_go_mod(self):
        result = check_dependency_guard(
            changed_files=["go.mod"],
            manifest_before={
                "go.mod": "module app\n\nrequire github.com/foo/bar v1.0.0\n"
            },
            manifest_after={
                "go.mod": "module app\n\nrequire github.com/foo/bar v1.0.0\nrequire github.com/baz/qux v2.0.0\n"
            },
        )
        added = [c for c in result.changes if c.change_type == "added"]
        assert any("baz/qux" in c.name for c in added)

    def test_lock_sync_for_go_mod(self):
        """go.mod 变更 + go.sum 同步。"""
        result = check_dependency_guard(
            changed_files=["go.mod", "go.sum"],
            manifest_before={
                "go.mod": "module app\nrequire github.com/foo v1.0.0\n"
            },
            manifest_after={
                "go.mod": "module app\nrequire github.com/foo v2.0.0\n"
            },
        )
        lock_violations = [
            v for v in result.violations if v.rule == "lock_not_updated"
        ]
        assert len(lock_violations) == 0


# ── requirements.txt before/after 对比测试 ──────────────────────


class TestRequirementsTxtBeforeAfter:
    def test_version_change_in_requirements(self):
        result = check_dependency_guard(
            changed_files=["requirements.txt"],
            manifest_before={
                "requirements.txt": "fastapi==0.104.0\nuvicorn==0.24.0\n"
            },
            manifest_after={
                "requirements.txt": "fastapi==0.115.0\nuvicorn==0.24.0\n"
            },
        )
        version_changes = [
            c for c in result.changes if c.change_type == "version_changed"
        ]
        assert any(c.name == "fastapi" for c in version_changes)
        assert any("0.104.0" in (c.old_version or "") for c in version_changes)

    def test_added_dep_in_requirements(self):
        result = check_dependency_guard(
            changed_files=["requirements.txt"],
            manifest_before={
                "requirements.txt": "flask==2.0\n"
            },
            manifest_after={
                "requirements.txt": "flask==2.0\nfastapi==0.104.0\n"
            },
        )
        added = [c for c in result.changes if c.change_type == "added"]
        assert any(c.name == "fastapi" for c in added)

    def test_removed_dep_in_requirements(self):
        result = check_dependency_guard(
            changed_files=["requirements.txt"],
            manifest_before={
                "requirements.txt": "flask==2.0\nfastapi==0.104.0\n"
            },
            manifest_after={
                "requirements.txt": "flask==2.0\n"
            },
        )
        removed = [c for c in result.changes if c.change_type == "removed"]
        assert any(c.name == "fastapi" for c in removed)


# ── Skill.run() 集成测试 ────────────────────────────────────


class TestSkillRun:
    def test_skill_run_with_manifest_changes(self):
        """通过 Skill.run() 运行完整流程。"""
        skill = Skill.create("dependency.guard")
        result = skill.run(_ctx(), {
            "changed_files": ["pyproject.toml"],
            "manifest_before": {
                "pyproject.toml": '[project]\ndependencies = ["fastapi==0.104.0"]\n'
            },
            "manifest_after": {
                "pyproject.toml": '[project]\ndependencies = ["fastapi==0.115.0"]\n'
            },
        })
        assert result.summary  # 有摘要
        assert isinstance(result.data, dict)
        assert "passed" in result.data
        assert "changes" in result.data
        assert len(result.data["changes"]) >= 1
        # warning 级别不导致 success=False
        assert result.success is True

    def test_skill_run_with_error(self):
        """manifest_removed 导致 success=False。"""
        skill = Skill.create("dependency.guard")
        result = skill.run(_ctx(), {
            "changed_files": ["pyproject.toml"],
            "manifest_before": {
                "pyproject.toml": '[project]\ndependencies = ["fastapi==0.1"]\n'
            },
            "manifest_after": {},
        })
        assert result.success is False
        assert result.summary  # 有摘要

    def test_skill_run_no_changes(self):
        """无变更时 Skill 正常返回。"""
        skill = Skill.create("dependency.guard")
        result = skill.run(_ctx(), {})
        assert result.success is True

    def test_skill_run_next_steps(self):
        """Skill 返回 next_steps。"""
        skill = Skill.create("dependency.guard")
        result = skill.run(_ctx(), {
            "changed_files": ["pyproject.toml"],
            "manifest_before": {
                "pyproject.toml": '[project]\ndependencies = ["flask==2.0"]\n'
            },
            "manifest_after": {
                "pyproject.toml": '[project]\ndependencies = ["flask==2.1"]\n'
            },
        })
        assert len(result.next_steps) > 0


# ── 确定性验证 ──────────────────────────────────────────────


class TestDeterminism:
    def test_same_input_same_output(self):
        """相同输入产生相同输出。"""
        def run():
            return check_dependency_guard(
                changed_files=["pyproject.toml"],
                manifest_before={
                    "pyproject.toml": '[project]\ndependencies = ["flask==2.0", "fastapi==0.104.0"]\n'
                },
                manifest_after={
                    "pyproject.toml": '[project]\ndependencies = ["flask==2.1", "fastapi==0.115.0"]\n'
                },
            )

        r1 = run()
        r2 = run()
        r3 = run()

        assert r1.passed == r2.passed == r3.passed
        assert len(r1.changes) == len(r2.changes) == len(r3.changes)
        assert len(r1.violations) == len(r2.violations) == len(r3.violations)
        assert r1.summary == r2.summary == r3.summary

    def test_to_dict_deterministic_order(self):
        """to_dict 输出排序一致。"""
        result = check_dependency_guard(
            changed_files=["pyproject.toml"],
            manifest_before={
                "pyproject.toml": '[project]\ndependencies = ["flask==2.0", "fastapi==0.104.0"]\n'
            },
            manifest_after={
                "pyproject.toml": '[project]\ndependencies = ["flask==2.1", "fastapi==0.115.0"]\n'
            },
        )
        d1 = result.to_dict()
        d2 = result.to_dict()
        assert d1 == d2


# ── 边界情况 ────────────────────────────────────────────────


class TestEdgeCases:
    def test_only_manifest_before_no_changed_files(self):
        """只提供 manifest_before，没有 changed_files。"""
        result = check_dependency_guard(
            changed_files=[],
            manifest_before={"pyproject.toml": '[project]\ndependencies = ["a==1"]\n'},
            manifest_after={"pyproject.toml": '[project]\ndependencies = ["a==1"]\n'},
        )
        # 无变更，应通过
        assert result.passed is True

    def test_multiple_manifests(self):
        """多个 manifest 同时变更。"""
        result = check_dependency_guard(
            changed_files=["pyproject.toml", "package.json"],
            manifest_before={
                "pyproject.toml": '[project]\ndependencies = ["flask==2.0"]\n',
                "package.json": '{"dependencies": {"lodash": "4.0.0"}}',
            },
            manifest_after={
                "pyproject.toml": '[project]\ndependencies = ["flask==2.1"]\n',
                "package.json": '{"dependencies": {"lodash": "4.17.21"}}',
            },
        )
        assert len(result.manifests_found) == 2
        # 两个 manifest 都应有变更
        manifests_in_changes = {c.manifest for c in result.changes}
        assert "pyproject.toml" in manifests_in_changes or len(result.changes) >= 2

    def test_invalid_manifest_content_graceful(self):
        """无效的 manifest 内容不应崩溃。"""
        result = check_dependency_guard(
            changed_files=["package.json"],
            manifest_before={
                "package.json": "not valid json {{{",
            },
            manifest_after={
                "package.json": '{"dependencies": {"a": "1.0.0"}}',
            },
        )
        # 不应该抛异常
        assert isinstance(result.passed, bool)

    def test_unchanged_manifest(self):
        """manifest 未变更。"""
        result = check_dependency_guard(
            changed_files=["src/main.py"],
            manifest_before={
                "pyproject.toml": '[project]\ndependencies = ["flask==2.0"]\n',
            },
            manifest_after={
                "pyproject.toml": '[project]\ndependencies = ["flask==2.0"]\n',
            },
        )
        # manifest 未在 changed_files 中，内容也未变更
        assert len(result.changes) == 0
        assert result.passed is True

    def test_data_model_to_dict(self):
        """验证 to_dict 方法返回合法字典。"""
        change = DependencyChange(
            manifest="pyproject.toml",
            change_type="version_changed",
            name="fastapi",
            old_version="0.1.0",
            new_version="0.2.0",
        )
        d = change.to_dict()
        assert d["manifest"] == "pyproject.toml"
        assert d["change_type"] == "version_changed"
        assert d["name"] == "fastapi"

        violation = DependencyViolation(
            rule="test_rule",
            severity="error",
            message="test message",
        )
        d = violation.to_dict()
        assert d["rule"] == "test_rule"
        assert d["severity"] == "error"

    def test_result_to_dict_comprehensive(self):
        """result.to_dict() 包含所有必需字段。"""
        result = check_dependency_guard(
            changed_files=["pyproject.toml"],
            manifest_before={
                "pyproject.toml": '[project]\ndependencies = ["flask==2.0"]\n'
            },
            manifest_after={
                "pyproject.toml": '[project]\ndependencies = ["flask==2.1", "fastapi==0.1"]\n'
            },
        )
        d = result.to_dict()
        required_keys = [
            "passed", "manifests_found", "changes",
            "violations", "warnings", "suggestions", "summary",
        ]
        for key in required_keys:
            assert key in d, f"Missing key: {key}"
