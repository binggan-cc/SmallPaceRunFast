"""
Guard: change.budget — 变更预算检查（R0 只读）

功能：
─────
检查单次变更是否超出预算上限：
  - 文件数超限（max_files）
  - 行数超限（max_lines）
  - Schema 变更检测（models.py / schema.py / *.sql / migrations/）
  - 单文件变更过大（per_file_limit）

设计约束：
─────────
- 零外部依赖（标准库 + Path）
- 确定性规则引擎，不调用模型
- 无 git 环境也能运行（基于显式输入）
- R0 只读 — 不修改任何文件

对应文档：
- docs/phase-11b-design.md §3.1（change.budget 详细设计）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


# ── 数据模型 ──────────────────────────────────────────────────


@dataclass
class BudgetViolation:
    """单条预算违规。

    Attributes:
        rule:  违规规则名（file_count / line_count / schema_change / per_file_limit）
        severity: 严重程度（error / warning / info）
        message:  人类可读说明
        detail:   补充信息（如 actual vs limit）
    """

    rule: str
    severity: str
    message: str
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "message": self.message,
            "detail": self.detail,
        }


@dataclass
class BudgetResult:
    """change.budget 检查结果。

    Attributes:
        passed:     是否全部通过（无 error 级别违规）
        checks:     各项检查结果
        violations: 违规列表
        summary:    人类可读摘要
    """

    passed: bool = True
    checks: dict = field(default_factory=dict)
    violations: list[BudgetViolation] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "checks": self.checks,
            "violations": [v.to_dict() for v in self.violations],
            "summary": self.summary,
        }


# ── Schema 变更检测 ──────────────────────────────────────────

def _is_schema_file(file_path: str) -> bool:
    """检测文件是否为数据模型/schema 文件。

    匹配规则：
    - models.py / schema.py（任意层级）
    - *.sql 文件
    - migrations/ 或 migration/ 目录下的文件
    - alembic/ 目录下的文件
    """
    p = Path(file_path)
    name = p.name

    # models.py / schema.py
    if name in ("models.py", "schema.py"):
        return True

    # *.sql
    if name.endswith(".sql"):
        return True

    # migrations/ / migration/ / alembic/ 目录
    parts = p.parts
    for part in parts[:-1]:  # 排除文件名自身
        if part in ("migrations", "migration", "alembic"):
            return True

    return False


# ── 核心规则引擎 ──────────────────────────────────────────────


def check_budget(
    changed_files: list[str],
    max_files: int = 10,
    max_lines: int | None = None,
    allow_schema_change: bool = False,
    per_file_limit: int = 200,
    line_counts: dict[str, int] | None = None,
) -> BudgetResult:
    """执行 change.budget 检查。

    Args:
        changed_files:      变更文件列表（相对项目根目录的路径字符串）
        max_files:          文件数上限（默认 10）
        max_lines:          行数上限（None 表示不限制）
        allow_schema_change: 是否允许数据模型变更（默认 False）
        per_file_limit:     单文件变更行数上限（默认 200）
        line_counts:        每个文件的行数变更 {path: lines}（可选，用于精确行数检查）

    Returns:
        BudgetResult: 结构化检查结果
    """
    violations: list[BudgetViolation] = []
    checks: dict = {}
    line_counts = line_counts or {}

    # ── 规则 1: 文件数超限 ────────────────────────────────────
    file_count_actual = len(changed_files)
    file_count_ok = file_count_actual <= max_files
    checks["file_count"] = {
        "actual": file_count_actual,
        "limit": max_files,
        "passed": file_count_ok,
    }
    if not file_count_ok:
        violations.append(BudgetViolation(
            rule="file_count",
            severity="error",
            message=(
                f"变更文件数 {file_count_actual} 超过上限 {max_files}"
            ),
            detail={"actual": file_count_actual, "limit": max_files},
        ))

    # ── 规则 2: 行数超限 ──────────────────────────────────────
    if max_lines is not None:
        total_lines = sum(line_counts.values())
        line_count_ok = total_lines <= max_lines
        checks["line_count"] = {
            "actual": total_lines,
            "limit": max_lines,
            "passed": line_count_ok,
        }
        if not line_count_ok:
            violations.append(BudgetViolation(
                rule="line_count",
                severity="warning",
                message=(
                    f"变更总行数 {total_lines} 超过上限 {max_lines}"
                ),
                detail={"actual": total_lines, "limit": max_lines},
            ))
    else:
        checks["line_count"] = {
            "actual": sum(line_counts.values()) if line_counts else None,
            "limit": None,
            "passed": True,
            "note": "未设置 max_lines，跳过行数检查",
        }

    # ── 规则 3: Schema 变更 ────────────────────────────────────
    schema_files = [f for f in changed_files if _is_schema_file(f)]
    schema_detected = len(schema_files) > 0
    schema_ok = allow_schema_change or not schema_detected
    checks["schema_change"] = {
        "detected": schema_detected,
        "files": schema_files,
        "allow_schema_change": allow_schema_change,
        "passed": schema_ok,
    }
    if schema_detected and not allow_schema_change:
        violations.append(BudgetViolation(
            rule="schema_change",
            severity="error",
            message=(
                f"检测到数据模型变更（{', '.join(schema_files)}），"
                f"但 allow_schema_change=False。"
                f"如需允许，请显式设置 allow_schema_change=True"
            ),
            detail={
                "files": schema_files,
                "allow_schema_change": allow_schema_change,
            },
        ))
    elif schema_detected and allow_schema_change:
        # 允许但保留检查结果
        violations.append(BudgetViolation(
            rule="schema_change",
            severity="info",
            message=(
                f"检测到数据模型变更（{', '.join(schema_files)}），"
                f"已显式允许（allow_schema_change=True）"
            ),
            detail={
                "files": schema_files,
                "allow_schema_change": allow_schema_change,
            },
        ))

    # ── 规则 4: 单文件变更过大 ──────────────────────────────────
    per_file_violations = []
    for f in changed_files:
        lines = line_counts.get(f, 0)
        if lines > per_file_limit:
            per_file_violations.append({"file": f, "lines": lines})
    checks["per_file_limit"] = {
        "limit": per_file_limit,
        "violations": per_file_violations,
        "passed": len(per_file_violations) == 0,
    }
    for pv in per_file_violations:
        violations.append(BudgetViolation(
            rule="per_file_limit",
            severity="warning",
            message=(
                f"文件 '{pv['file']}' 变更 {pv['lines']} 行，"
                f"超过单文件上限 {per_file_limit} 行"
            ),
            detail={"file": pv["file"], "lines": pv["lines"], "limit": per_file_limit},
        ))

    # ── 构建摘要 ───────────────────────────────────────────────
    error_count = sum(1 for v in violations if v.severity == "error")
    warning_count = sum(1 for v in violations if v.severity == "warning")
    passed = error_count == 0

    if passed and not violations:
        summary = (
            f"✅ change.budget 通过：{file_count_actual}/{max_files} 文件"
        )
        if max_lines is not None:
            total = sum(line_counts.values())
            summary += f"，{total}/{max_lines} 行"
        summary += "，无 schema 变更"
    elif passed:
        parts = [f"⚠ change.budget 通过（{warning_count} 个警告）"]
        if not file_count_ok:
            parts.append(f"文件数 {file_count_actual}/{max_files}")
        if schema_detected:
            parts.append(f"schema 变更（已允许）")
        if per_file_violations:
            parts.append(f"{len(per_file_violations)} 个文件超单文件上限")
        summary = "；".join(parts)
    else:
        parts = [f"❌ change.budget 未通过（{error_count} 个错误"]
        if warning_count:
            parts[-1] += f"，{warning_count} 个警告"
        parts[-1] += ")"
        if not file_count_ok:
            parts.append(f"文件数超限：{file_count_actual}/{max_files}")
        if schema_detected and not allow_schema_change:
            parts.append(f"schema 变更未允许")
        summary = "；".join(parts)

    return BudgetResult(
        passed=passed,
        checks=checks,
        violations=violations,
        summary=summary,
    )
