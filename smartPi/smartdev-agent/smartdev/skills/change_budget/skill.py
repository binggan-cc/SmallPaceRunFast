"""
Skill: change.budget — 变更预算检查（R0 只读）

功能：检查单次变更是否超出预算上限：
      - 文件数超限（max_files）
      - 行数超限（max_lines）
      - Schema 变更检测
      - 单文件变更过大（per_file_limit）

风险：R0（只读，不修改任何文件）

设计约束（docs/phase-11b-design.md §3.1）：
- 确定性规则引擎，不调用模型
- 消费 scope.json 的 max_files 字段
- 无 git 环境也能运行（基于显式输入）
- 与 scope_gate 协作：scope_gate 做准入，change.budget 做粒度审查
"""

from __future__ import annotations

from smartdev.core.guard_budget import BudgetResult, check_budget
from smartdev.models import RiskLevel, SkillResult, TaskType
from smartdev.skills.base import Skill


class ChangeBudgetSkill(Skill):
    """变更预算检查 Skill（R0 只读）

    检查单次变更的文件数、行数、schema 变更是否在预算范围内。
    输出结构化 checks / violations / summary。

    inputs 参数：
        changed_files:       list[str]  — 变更文件列表（必需）
        max_files:           int        — 文件数上限（默认 10）
        max_lines:           int | None — 行数上限（None=不限制）
        allow_schema_change: bool       — 是否允许 schema 变更（默认 False）
        per_file_limit:      int        — 单文件变更行数上限（默认 200）
        line_counts:         dict       — 每个文件的行数 {path: lines}

    使用示例：
        result = Skill.create("change.budget").run(context, {
            "changed_files": ["a.py", "b.py", "models.py"],
            "max_files": 5,
            "allow_schema_change": True,
        })
    """

    name = "change.budget"
    description = "变更预算检查：文件数/行数/schema/单文件上限，确定性规则引擎"
    risk_level = RiskLevel.R0
    task_type = TaskType.DIAGNOSE

    def can_run(self, context) -> bool:
        # change.budget 不依赖 git，任何时候都能运行
        return True

    def run(self, context, inputs: dict | None = None) -> SkillResult:
        inputs = inputs or {}

        changed_files: list[str] = inputs.get("changed_files", [])
        max_files: int = int(inputs.get("max_files", 10))
        max_lines: int | None = inputs.get("max_lines")
        allow_schema_change: bool = bool(inputs.get("allow_schema_change", False))
        per_file_limit: int = int(inputs.get("per_file_limit", 200))
        line_counts: dict[str, int] | None = inputs.get("line_counts")

        # 处理 max_lines：None 或显式传入的 None → 不限制
        if max_lines is not None:
            max_lines = int(max_lines)

        if not changed_files:
            return SkillResult(
                success=True,
                summary="change.budget：无变更文件，跳过检查",
                data={
                    "passed": True,
                    "checks": {},
                    "violations": [],
                    "summary": "无变更文件",
                },
            )

        result: BudgetResult = check_budget(
            changed_files=changed_files,
            max_files=max_files,
            max_lines=max_lines,
            allow_schema_change=allow_schema_change,
            per_file_limit=per_file_limit,
            line_counts=line_counts,
        )

        next_steps: list[str] = []
        if not result.passed:
            next_steps.append(
                "建议拆分变更为多次小改动，或调整 scope.json 中的 max_files"
            )
            schema_violations = [
                v for v in result.violations if v.rule == "schema_change"
            ]
            if schema_violations:
                next_steps.append(
                    "Schema 变更需人工审查后，设置 allow_schema_change=True 重新运行"
                )
        else:
            violations = result.violations
            if violations:
                next_steps.append("所有违规为 warning/info 级别，可继续。")
            else:
                next_steps.append("变更预算检查通过，可继续执行。")

        return SkillResult(
            success=result.passed,
            summary=result.summary,
            data=result.to_dict(),
            risks=(
                [v.message for v in result.violations if v.severity == "error"]
                if not result.passed
                else []
            ),
            next_steps=next_steps,
        )
