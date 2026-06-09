"""
test_scope_gate.py — Phase 11D Step 2 Scope Gate 聚焦测试

覆盖：
- check_scope passed（全部在范围内）
- check_scope 各项规则触发 violation
- scope.json 缺失/格式错误
- 空 changed_files / 边缘情况
- glob 模式匹配
- ScopeGateResult 序列化

不覆盖：
- handoff code/doc/review（Step 3-5）
- MCP 工具（Step 6）
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from smartdev.core.run_artifact import ScopeConfig, create_run_artifact
from smartdev.core.scope_gate import (
    ScopeGateResult,
    ScopeViolation,
    _match_any,
    check_scope,
    load_scope_config,
)


# ── Fixtures ─────────────────────────────────────────────────


@pytest.fixture
def tmp_project():
    """临时项目目录（含已创建的 run artifact）。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def _setup_run(tmp_project: Path, run_id: str = "test-run", **scope_kwargs):
    """创建 run artifact 并返回项目路径。"""
    scope = ScopeConfig(**scope_kwargs) if scope_kwargs else None
    run_dir, err = create_run_artifact(tmp_project, run_id, scope=scope, force=True)
    if err:
        raise RuntimeError(f"Failed to create run artifact: {err}")
    return tmp_project


# ── _match_any ────────────────────────────────────────────────


class TestMatchAny:
    """glob 匹配逻辑。"""

    def test_exact_match(self):
        assert _match_any("foo.py", ["foo.py"]) is True

    def test_wildcard_match(self):
        assert _match_any("foo.py", ["*.py"]) is True

    def test_directory_prefix_match(self):
        assert _match_any("smartdev/core/foo.py", ["smartdev/"]) is True

    def test_directory_prefix_nested(self):
        assert _match_any("tests/unit/test_x.py", ["tests/"]) is True

    def test_no_match(self):
        assert _match_any("secrets/key.txt", ["src/", "tests/"]) is False

    def test_filename_only_pattern(self):
        assert _match_any("some/deep/path/output.pyc", ["*.pyc"]) is True

    def test_multiple_patterns_first_match(self):
        assert _match_any("src/foo.py", ["tests/", "src/", "docs/"]) is True

    def test_question_mark_wildcard(self):
        assert _match_any("file1.js", ["file?.js"]) is True

    def test_prefix_no_match_different_dir(self):
        assert _match_any("other/foo.py", ["src/"]) is False

    def test_protected_design_doc(self):
        assert _match_any("docs/phase-11d-design.md", ["docs/phase-*-design.md"]) is True


# ── load_scope_config ─────────────────────────────────────────


class TestLoadScopeConfig:
    """scope.json 加载。"""

    def test_loads_valid_scope(self, tmp_project):
        _setup_run(tmp_project, "load-test")
        run_dir = tmp_project / ".smartdev" / "runs" / "load-test"
        data, err = load_scope_config(run_dir)
        assert err is None
        assert "allowed_paths" in data
        assert "max_files" in data

    def test_missing_file_returns_error(self, tmp_project):
        run_dir = tmp_project / ".smartdev" / "runs" / "nonexistent"
        data, err = load_scope_config(run_dir)
        assert data is None
        assert err is not None
        assert "不存在" in err

    def test_malformed_json_returns_error(self, tmp_project):
        run_dir = tmp_project / ".smartdev" / "runs" / "bad-json"
        run_dir.mkdir(parents=True)
        (run_dir / "scope.json").write_text("{not valid json")
        data, err = load_scope_config(run_dir)
        assert data is None
        assert err is not None
        assert "格式错误" in err

    def test_missing_required_fields_returns_error(self, tmp_project):
        run_dir = tmp_project / ".smartdev" / "runs" / "bad-fields"
        run_dir.mkdir(parents=True)
        (run_dir / "scope.json").write_text('{"allowed_paths": ["src/"]}')
        data, err = load_scope_config(run_dir)
        assert data is None
        assert err is not None
        assert "缺少必要字段" in err


# ── check_scope: passed ────────────────────────────────────────


class TestCheckScopePassed:
    """正常通过路径。"""

    def test_all_files_in_scope(self, tmp_project):
        _setup_run(tmp_project, "pass-1", allowed_paths=["src/", "tests/"])
        result = check_scope(tmp_project, "pass-1", ["src/main.py", "tests/test_main.py"])
        assert result.passed is True
        assert len(result.violations) == 0
        assert "通过" in result.summary

    def test_empty_changed_files(self, tmp_project):
        _setup_run(tmp_project, "pass-2")
        result = check_scope(tmp_project, "pass-2", [])
        assert result.passed is True
        assert len(result.violations) == 0

    def test_single_file_under_limit(self, tmp_project):
        _setup_run(tmp_project, "pass-3", max_files=3)
        result = check_scope(tmp_project, "pass-3", ["src/a.py", "src/b.py", "tests/test_a.py"])
        assert result.passed is True

    def test_no_error_when_allowed_matches(self, tmp_project):
        _setup_run(
            tmp_project, "pass-4",
            allowed_paths=["smartdev/", "tests/"],
            denied_paths=["*.pyc"],
            protected_paths=["CHANGELOG.md"],
        )
        result = check_scope(tmp_project, "pass-4", [
            "smartdev/core/foo.py",
            "tests/test_foo.py",
        ])
        assert result.passed is True
        assert len(result.violations) == 0


# ── check_scope: violations ────────────────────────────────────


class TestCheckScopeViolations:
    """各项违规路径。"""

    def test_max_files_exceeded(self, tmp_project):
        _setup_run(tmp_project, "v-max", max_files=2)
        result = check_scope(tmp_project, "v-max", [
            "src/a.py", "src/b.py", "src/c.py",
        ])
        assert result.passed is False
        violations = [v for v in result.violations if v.rule == "max_files"]
        assert len(violations) == 1
        assert "超过上限" in violations[0].message

    def test_denied_path_hit(self, tmp_project):
        _setup_run(tmp_project, "v-denied", denied_paths=["secrets/", "*.key"])
        result = check_scope(
            tmp_project, "v-denied",
            ["secrets/db.key", "src/main.py"],
        )
        # secrets/db.key 命中 denied_paths
        denied = [v for v in result.violations if v.rule == "denied_paths"]
        assert len(denied) >= 1
        assert any("secrets/db.key" in v.file for v in denied)

    def test_protected_path_hit(self, tmp_project):
        _setup_run(tmp_project, "v-protected", protected_paths=["CHANGELOG.md", "pyproject.toml"])
        result = check_scope(
            tmp_project, "v-protected",
            ["src/main.py", "CHANGELOG.md"],
        )
        protected = [v for v in result.violations if v.rule == "protected_paths"]
        assert len(protected) == 1
        assert "CHANGELOG.md" in protected[0].file
        assert "R3" in protected[0].message

    def test_outside_scope(self, tmp_project):
        _setup_run(tmp_project, "v-outside", allowed_paths=["src/"])
        result = check_scope(tmp_project, "v-outside", [
            "src/main.py",          # allowed
            "README.md",            # outside
            "config/secrets.yaml",  # outside
        ])
        outside = [v for v in result.violations if v.rule == "outside_scope"]
        assert len(outside) == 2
        outside_files = {v.file for v in outside}
        assert "README.md" in outside_files
        assert "config/secrets.yaml" in outside_files

    def test_multiple_violations_same_file(self, tmp_project):
        """一个文件同时命中 denied + protected → 两条 violation。"""
        _setup_run(
            tmp_project, "v-multi",
            denied_paths=["CHANGELOG.md"],
            protected_paths=["CHANGELOG.md"],
        )
        result = check_scope(tmp_project, "v-multi", ["CHANGELOG.md"])
        # 应该有两类 violation
        rules = {v.rule for v in result.violations}
        assert "denied_paths" in rules
        assert "protected_paths" in rules


class TestCheckScopeErrors:
    """scope.json 缺失/损坏。"""

    def test_missing_scope_json(self, tmp_project):
        result = check_scope(tmp_project, "nonexistent", ["src/a.py"])
        assert result.passed is False
        assert result.error is not None
        assert "不存在" in result.error

    def test_malformed_scope_json(self, tmp_project):
        run_dir = tmp_project / ".smartdev" / "runs" / "bad-json"
        run_dir.mkdir(parents=True)
        (run_dir / "scope.json").write_text("{broken")
        result = check_scope(tmp_project, "bad-json", ["src/a.py"])
        assert result.passed is False
        assert result.error is not None
        assert "格式错误" in result.error


# ── ScopeGateResult 序列化 ─────────────────────────────────────


class TestScopeGateResultSerialization:
    """结果序列化。"""

    def test_to_dict_passed(self):
        result = ScopeGateResult(passed=True, summary="ok")
        d = result.to_dict()
        assert d["passed"] is True
        assert d["summary"] == "ok"
        assert d["violations"] == []

    def test_to_dict_with_violations(self):
        v = ScopeViolation(
            file="README.md",
            rule="outside_scope",
            severity="warning",
            message="不在范围内",
        )
        result = ScopeGateResult(
            passed=True,
            violations=[v],
            summary="有警告",
        )
        d = result.to_dict()
        assert len(d["violations"]) == 1
        assert d["violations"][0]["file"] == "README.md"

    def test_to_json_roundtrip(self):
        v = ScopeViolation(file="x.py", rule="max_files", severity="error", message="too many")
        result = ScopeGateResult(passed=False, violations=[v], summary="failed")
        json_str = result.to_json()
        loaded = json.loads(json_str)
        assert loaded["passed"] is False
        assert loaded["violations"][0]["rule"] == "max_files"


# ── 集成：通过 run_artifact 创建的 scope.json ──────────────────


class TestScopeGateIntegration:
    """与 run_artifact 的集成测试。"""

    def test_default_scope_passes_normal_files(self, tmp_project):
        _setup_run(tmp_project, "integ-1")  # 使用 Step 1 默认 scope
        result = check_scope(tmp_project, "integ-1", [
            "smartdev/core/foo.py",
            "tests/test_foo.py",
            "docs/README.md",
        ])
        assert result.passed is True

    def test_default_scope_rejects_protected(self, tmp_project):
        _setup_run(tmp_project, "integ-2")  # 默认 protected 含 CHANGELOG.md
        result = check_scope(tmp_project, "integ-2", [
            "smartdev/core/foo.py",
            "CHANGELOG.md",
        ])
        protected = [v for v in result.violations if v.rule == "protected_paths"]
        assert len(protected) >= 1

    def test_default_scope_rejects_denied(self, tmp_project):
        _setup_run(tmp_project, "integ-3")  # 默认 denied 含 __pycache__/
        result = check_scope(tmp_project, "integ-3", [
            "smartdev/core/foo.py",
            "__pycache__/foo.cpython-313.pyc",
        ])
        denied = [v for v in result.violations if v.rule == "denied_paths"]
        assert len(denied) >= 1

    def test_severity_only_warnings_passed_true(self, tmp_project):
        """只有 outside_scope（warning）时 passed=true（warning 不阻断）。"""
        _setup_run(tmp_project, "integ-4", allowed_paths=["smartdev/"])
        result = check_scope(tmp_project, "integ-4", [
            "smartdev/core/foo.py",  # allowed
            "README.md",              # outside → warning
        ])
        # outside_scope 是 warning，不阻断
        assert result.passed is True
        assert len(result.violations) == 1
        assert result.violations[0].severity == "warning"

    def test_custom_max_files_works(self, tmp_project):
        _setup_run(tmp_project, "integ-5", max_files=1)
        result = check_scope(tmp_project, "integ-5", [
            "smartdev/a.py", "smartdev/b.py",
        ])
        assert result.passed is False
        assert any(v.rule == "max_files" for v in result.violations)
