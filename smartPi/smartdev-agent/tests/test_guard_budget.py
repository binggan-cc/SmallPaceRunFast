"""
change.budget Guard Skill 测试 — Phase 11B Step 1

覆盖：
1. 核心规则引擎 check_budget() 所有规则
2. Skill 注册 + 基础属性
3. Skill.run() 输入/输出路径
4. 边界情况（空文件列表 / 无限制 / 全部通过）
5. Schema 变更检测（models.py / schema.py / *.sql / migrations/）
6. per_file_limit 单文件检查
7. 确定性：相同输入→相同输出
"""

from __future__ import annotations

from pathlib import Path

import pytest

from smartdev.core.guard_budget import (
    BudgetResult,
    BudgetViolation,
    _is_schema_file,
    check_budget,
)
from smartdev.models import ProjectContext
from smartdev.skills.base import Skill


# ── Helpers ────────────────────────────────────────────────


def _ctx() -> ProjectContext:
    return ProjectContext(
        project_path=Path("/fake/project"),
        task_description="test change.budget",
    )


# ── Skill 注册验证 ───────────────────────────────────────────


def test_skill_registered():
    """import smartdev.skills 后 Skill 已注册。"""
    import smartdev.skills  # noqa: F401 — 触发统一注册
    skill_cls = Skill.get_skill("change.budget")
    assert skill_cls is not None


def test_skill_attributes():
    """验证 Skill 基本属性。"""
    skill = Skill.create("change.budget")
    assert skill.name == "change.budget"
    from smartdev.models import RiskLevel
    assert skill.risk_level == RiskLevel.R0
    assert skill.can_run(_ctx()) is True


# ── _is_schema_file 单元测试 ──────────────────────────────────


class TestIsSchemaFile:
    def test_models_py(self):
        assert _is_schema_file("models.py") is True

    def test_schema_py(self):
        assert _is_schema_file("schema.py") is True

    def test_nested_models_py(self):
        assert _is_schema_file("smartdev/models.py") is True

    def test_nested_schema_py(self):
        assert _is_schema_file("app/core/schema.py") is True

    def test_sql_file(self):
        assert _is_schema_file("migrations/001_init.sql") is True

    def test_sql_file_root(self):
        assert _is_schema_file("schema.sql") is True

    def test_migrations_dir(self):
        assert _is_schema_file("migrations/versions/abc123.py") is True

    def test_migration_dir(self):
        assert _is_schema_file("migration/env.py") is True

    def test_alembic_dir(self):
        assert _is_schema_file("alembic/versions/def456.py") is True

    def test_regular_python_file(self):
        assert _is_schema_file("smartdev/core/git.py") is False

    def test_regular_test_file(self):
        assert _is_schema_file("tests/test_models.py") is False

    def test_not_schema_named_file(self):
        assert _is_schema_file("utils.py") is False


# ── check_budget 核心规则引擎 ─────────────────────────────────


class TestCheckBudgetBasic:
    """基础功能测试。"""

    def test_empty_changed_files(self):
        """空文件列表：全部通过。"""
        result = check_budget([])
        assert result.passed is True
        assert len(result.violations) == 0
        assert "✅" in result.summary

    def test_all_within_budget(self):
        """所有检查在预算内：全部通过。"""
        result = check_budget(
            changed_files=["a.py", "b.py", "c.py"],
            max_files=10,
            max_lines=500,
            line_counts={"a.py": 50, "b.py": 30, "c.py": 40},
        )
        assert result.passed is True
        assert result.checks["file_count"]["passed"] is True
        assert result.checks["line_count"]["passed"] is True
        assert result.checks["schema_change"]["passed"] is True
        assert result.checks["per_file_limit"]["passed"] is True

    def test_returns_budget_result_type(self):
        result = check_budget(["a.py"])
        assert isinstance(result, BudgetResult)


class TestFileCountRule:
    """规则 1: 文件数超限检查。"""

    def test_within_limit(self):
        result = check_budget(["a.py", "b.py"], max_files=5)
        assert result.checks["file_count"]["passed"] is True
        assert result.checks["file_count"]["actual"] == 2
        assert result.checks["file_count"]["limit"] == 5

    def test_at_limit(self):
        result = check_budget(["a.py", "b.py", "c.py"], max_files=3)
        assert result.checks["file_count"]["passed"] is True

    def test_exceeds_limit(self):
        result = check_budget(["a.py", "b.py", "c.py"], max_files=2)
        assert result.checks["file_count"]["passed"] is False
        assert result.passed is False

    def test_exceeds_produces_error_violation(self):
        result = check_budget(["a.py", "b.py", "c.py", "d.py"], max_files=2)
        violations = [v for v in result.violations if v.rule == "file_count"]
        assert len(violations) == 1
        assert violations[0].severity == "error"
        assert violations[0].detail["actual"] == 4
        assert violations[0].detail["limit"] == 2

    def test_default_max_files(self):
        """默认 max_files=10。"""
        result = check_budget(["f{}.py".format(i) for i in range(9)])
        assert result.checks["file_count"]["passed"] is True

    def test_default_exceeded(self):
        result = check_budget(["f{}.py".format(i) for i in range(11)])
        assert result.checks["file_count"]["passed"] is False


class TestLineCountRule:
    """规则 2: 行数超限检查。"""

    def test_no_max_lines_skips_check(self):
        """max_lines=None 时跳过行数检查。"""
        result = check_budget(
            ["a.py", "b.py"],
            line_counts={"a.py": 500, "b.py": 500},
            max_lines=None,
        )
        assert result.checks["line_count"]["passed"] is True
        assert "未设置 max_lines" in result.checks["line_count"].get("note", "")

    def test_within_line_limit(self):
        result = check_budget(
            ["a.py", "b.py"],
            max_lines=300,
            line_counts={"a.py": 100, "b.py": 50},
        )
        assert result.checks["line_count"]["passed"] is True
        assert result.checks["line_count"]["actual"] == 150
        assert result.checks["line_count"]["limit"] == 300

    def test_exceeds_line_limit(self):
        result = check_budget(
            ["a.py", "b.py"],
            max_lines=100,
            line_counts={"a.py": 80, "b.py": 50},
        )
        assert result.checks["line_count"]["passed"] is False

    def test_exceeds_line_produces_warning(self):
        """行数超限是 warning，不是 error。"""
        result = check_budget(
            ["a.py", "b.py"],
            max_lines=10,
            line_counts={"a.py": 80, "b.py": 50},
        )
        violations = [v for v in result.violations if v.rule == "line_count"]
        assert len(violations) == 1
        assert violations[0].severity == "warning"

    def test_no_line_counts_with_max_lines(self):
        """有 max_lines 但无 line_counts 时，行数和为 0。"""
        result = check_budget(
            ["a.py", "b.py"],
            max_lines=100,
        )
        assert result.checks["line_count"]["passed"] is True
        assert result.checks["line_count"]["actual"] == 0


class TestSchemaChangeRule:
    """规则 3: Schema 变更检查。"""

    def test_no_schema_files(self):
        result = check_budget(["a.py", "b.py"])
        assert result.checks["schema_change"]["detected"] is False
        assert result.checks["schema_change"]["passed"] is True

    def test_models_py_detected(self):
        result = check_budget(["models.py", "a.py"])
        assert result.checks["schema_change"]["detected"] is True
        assert "models.py" in result.checks["schema_change"]["files"]

    def test_schema_py_detected(self):
        result = check_budget(["app/schema.py"])
        assert result.checks["schema_change"]["detected"] is True

    def test_sql_file_detected(self):
        result = check_budget(["migrations/001.sql"])
        assert result.checks["schema_change"]["detected"] is True

    def test_migrations_dir_detected(self):
        result = check_budget(["migrations/versions/abc.py"])
        assert result.checks["schema_change"]["detected"] is True

    def test_schema_change_not_allowed_is_error(self):
        """allow_schema_change=False 时 schema 变更为 error。"""
        result = check_budget(
            ["models.py", "a.py"],
            allow_schema_change=False,
        )
        assert result.checks["schema_change"]["passed"] is False
        assert result.passed is False
        violations = [v for v in result.violations if v.rule == "schema_change"]
        assert len(violations) == 1
        assert violations[0].severity == "error"

    def test_schema_change_allowed_is_info(self):
        """allow_schema_change=True 时 schema 变更不阻断，输出 info。"""
        result = check_budget(
            ["models.py", "a.py"],
            allow_schema_change=True,
        )
        assert result.checks["schema_change"]["passed"] is True
        assert result.passed is True
        violations = [v for v in result.violations if v.rule == "schema_change"]
        assert len(violations) == 1
        assert violations[0].severity == "info"

    def test_alembic_detected(self):
        result = check_budget(["alembic/versions/v1.py"])
        assert result.checks["schema_change"]["detected"] is True

    def test_migrations_file_not_in_migrations_dir(self):
        """文件名含 migrations 但不是目录名时不算。"""
        result = check_budget(["test_migrations.py"])
        assert result.checks["schema_change"]["detected"] is False


class TestPerFileLimitRule:
    """规则 4: 单文件变更过大检查。"""

    def test_all_files_within_limit(self):
        result = check_budget(
            ["a.py", "b.py"],
            per_file_limit=200,
            line_counts={"a.py": 50, "b.py": 100},
        )
        assert result.checks["per_file_limit"]["passed"] is True

    def test_file_exceeds_limit(self):
        result = check_budget(
            ["a.py", "big.py"],
            per_file_limit=200,
            line_counts={"a.py": 50, "big.py": 300},
        )
        assert result.checks["per_file_limit"]["passed"] is False

    def test_file_exceeds_produces_warning(self):
        """单文件过大是 warning。"""
        result = check_budget(
            ["big.py"],
            per_file_limit=200,
            line_counts={"big.py": 300},
        )
        violations = [v for v in result.violations if v.rule == "per_file_limit"]
        assert len(violations) == 1
        assert violations[0].severity == "warning"
        assert violations[0].detail["file"] == "big.py"
        assert violations[0].detail["lines"] == 300

    def test_default_per_file_limit(self):
        """默认 per_file_limit=200。"""
        result = check_budget(
            ["big.py"],
            line_counts={"big.py": 201},
        )
        assert result.checks["per_file_limit"]["passed"] is False

    def test_no_line_counts_no_per_file_violations(self):
        """没有 line_counts 时不触发单文件检查。"""
        result = check_budget(["big.py"])
        assert result.checks["per_file_limit"]["passed"] is True

    def test_multiple_files_exceed(self):
        result = check_budget(
            ["a.py", "b.py", "c.py"],
            per_file_limit=10,
            line_counts={"a.py": 50, "b.py": 30, "c.py": 5},
        )
        violations = [v for v in result.violations if v.rule == "per_file_limit"]
        assert len(violations) == 2  # a.py(50) + b.py(30)


class TestCombinedViolations:
    """多规则同时违规。"""

    def test_file_count_and_schema(self):
        result = check_budget(
            ["a.py", "b.py", "c.py", "models.py"],
            max_files=2,
            allow_schema_change=False,
        )
        assert result.passed is False
        rules = {v.rule for v in result.violations}
        assert "file_count" in rules
        assert "schema_change" in rules

    def test_all_rules_violated(self):
        result = check_budget(
            ["a.py", "b.py", "c.py", "d.py", "models.py", "init.sql"],
            max_files=2,
            max_lines=10,
            allow_schema_change=False,
            per_file_limit=5,
            line_counts={
                "a.py": 100, "b.py": 50, "c.py": 10,
                "d.py": 90, "models.py": 30, "init.sql": 20,
            },
        )
        rules = {v.rule for v in result.violations}
        assert "file_count" in rules
        assert "line_count" in rules
        assert "schema_change" in rules
        assert "per_file_limit" in rules
        assert result.passed is False

    def test_line_count_warning_only_still_passes(self):
        """仅有 warning 级别违规时 passed=True。"""
        result = check_budget(
            ["a.py", "b.py"],
            max_files=10,
            max_lines=10,
            line_counts={"a.py": 50, "b.py": 30},
        )
        assert result.passed is True  # line_count 是 warning，不阻断


# ── Skill.run() 集成测试 ─────────────────────────────────────


class TestSkillRun:
    """通过 Skill 接口运行 change.budget。"""

    def test_run_with_changed_files(self):
        skill = Skill.create("change.budget")
        result = skill.run(_ctx(), {
            "changed_files": ["a.py", "b.py", "c.py"],
            "max_files": 5,
        })
        assert result.success is True
        assert result.data["passed"] is True
        assert "checks" in result.data
        assert "violations" in result.data
        assert "summary" in result.data

    def test_run_exceeds_max_files(self):
        skill = Skill.create("change.budget")
        result = skill.run(_ctx(), {
            "changed_files": ["a.py", "b.py", "c.py"],
            "max_files": 2,
        })
        assert result.success is False
        assert result.data["passed"] is False

    def test_run_no_changed_files(self):
        skill = Skill.create("change.budget")
        result = skill.run(_ctx(), {"changed_files": []})
        assert result.success is True

    def test_run_no_inputs(self):
        skill = Skill.create("change.budget")
        result = skill.run(_ctx())
        assert result.success is True
        assert "无变更文件" in result.summary

    def test_run_with_schema_change(self):
        skill = Skill.create("change.budget")
        result = skill.run(_ctx(), {
            "changed_files": ["a.py", "models.py"],
            "allow_schema_change": False,
        })
        assert result.success is False

    def test_run_with_schema_change_allowed(self):
        skill = Skill.create("change.budget")
        result = skill.run(_ctx(), {
            "changed_files": ["a.py", "models.py"],
            "allow_schema_change": True,
        })
        assert result.success is True

    def test_run_with_line_counts(self):
        skill = Skill.create("change.budget")
        result = skill.run(_ctx(), {
            "changed_files": ["a.py", "b.py"],
            "max_lines": 100,
            "line_counts": {"a.py": 30, "b.py": 20},
        })
        assert result.success is True
        assert result.data["checks"]["line_count"]["actual"] == 50

    def test_run_returns_next_steps(self):
        skill = Skill.create("change.budget")
        result = skill.run(_ctx(), {
            "changed_files": ["a.py"],
        })
        assert len(result.next_steps) > 0


# ── 确定性验证 ───────────────────────────────────────────────


def test_deterministic_output():
    """相同输入 → 相同输出（无随机性）。"""
    args = {
        "changed_files": ["a.py", "b.py", "models.py"],
        "max_files": 5,
        "max_lines": 200,
        "allow_schema_change": True,
        "per_file_limit": 100,
        "line_counts": {"a.py": 30, "b.py": 50, "models.py": 20},
    }
    r1 = check_budget(**args)
    r2 = check_budget(**args)
    assert r1.passed == r2.passed
    assert r1.summary == r2.summary
    assert len(r1.violations) == len(r2.violations)
    for i, v1 in enumerate(r1.violations):
        assert v1.rule == r2.violations[i].rule
        assert v1.severity == r2.violations[i].severity


# ── BudgetResult.to_dict ──────────────────────────────────────


def test_budget_result_to_dict():
    result = check_budget(["a.py"])
    d = result.to_dict()
    assert "passed" in d
    assert "checks" in d
    assert "violations" in d
    assert "summary" in d
    assert isinstance(d["violations"], list)
    assert isinstance(d["checks"], dict)


def test_budget_violation_to_dict():
    v = BudgetViolation(
        rule="file_count",
        severity="error",
        message="test message",
        detail={"actual": 5, "limit": 3},
    )
    d = v.to_dict()
    assert d["rule"] == "file_count"
    assert d["severity"] == "error"
    assert d["message"] == "test message"
    assert d["detail"]["actual"] == 5


# ── 摘要输出格式验证 ──────────────────────────────────────────


def test_summary_pass_format():
    result = check_budget(["a.py", "b.py"], max_files=10)
    assert "✅" in result.summary

def test_summary_warning_format():
    result = check_budget(
        ["a.py", "b.py"],
        max_files=10,
        max_lines=10,
        line_counts={"a.py": 50, "b.py": 50},
    )
    assert "⚠" in result.summary

def test_summary_fail_format():
    result = check_budget(
        ["a.py", "b.py", "c.py", "d.py"],
        max_files=2,
    )
    assert "❌" in result.summary
