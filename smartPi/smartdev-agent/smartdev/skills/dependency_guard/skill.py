"""
Skill: dependency.guard — 依赖变更审查（R0 只读）

功能：在 AI 产出 patch / diff 之后、人 apply 或 commit 之前，
      检查依赖 manifest 是否发生变化，并输出可人工审查的结构化报告：
      - 是否新增/删除/修改依赖版本
      - 是否新增/删除 manifest 文件
      - manifest 变更时对应 lock 文件是否同步
      - 根据语言生态输出建议命令（不调用外部工具）

风险：R0（只读，不修改任何文件）

设计约束（docs/phase-11b-design.md §3.3）：
- 确定性规则引擎，不调用模型
- 无 git 环境也能运行（基于显式输入）
- 支持 4 种 manifest 格式：pyproject.toml / package.json / go.mod / requirements.txt
- 外部工具只输出建议，不执行
"""

from __future__ import annotations

from smartdev.core.guard_dependency import DependencyResult, check_dependency_guard
from smartdev.models import RiskLevel, SkillResult, TaskType
from smartdev.skills.base import Skill


class DependencyGuardSkill(Skill):
    """依赖变更审查 Skill（R0 只读）

    检查项目依赖 manifest 是否发生变更：新增/删除/版本变更。
    检查 manifest 文件新增/删除、lock 文件同步。
    输出结构化 changes / violations / suggestions / summary。

    inputs 参数：
        changed_files:       list[str]            — 变更文件列表（必需）
        diff_content:        str | None           — 完整的 unified diff 文本
        manifest_before:     dict[str, str] | None — 变更前的 manifest 内容
        manifest_after:      dict[str, str] | None — 变更后的 manifest 内容
        lock_files_changed:  list[str] | None      — 明确变更的 lock 文件列表

    使用示例：
        result = Skill.create("dependency.guard").run(context, {
            "changed_files": ["pyproject.toml", "src/main.py"],
            "manifest_before": {"pyproject.toml": "..."},
            "manifest_after": {"pyproject.toml": "..."},
        })
    """

    name = "dependency.guard"
    description = (
        "依赖变更审查：检测 manifest 变更（新增/删除/版本变更）、"
        "lock 文件同步，输出安全审计建议"
    )
    risk_level = RiskLevel.R0
    task_type = TaskType.DIAGNOSE

    def can_run(self, context) -> bool:
        # dependency.guard 不依赖 git，任何时候都能运行
        return True

    def run(self, context, inputs: dict | None = None) -> SkillResult:
        inputs = inputs or {}

        changed_files: list[str] = inputs.get("changed_files", [])
        diff_content: str | None = inputs.get("diff_content")
        manifest_before: dict[str, str] | None = inputs.get("manifest_before")
        manifest_after: dict[str, str] | None = inputs.get("manifest_after")
        lock_files_changed: list[str] | None = inputs.get("lock_files_changed")

        if not changed_files and not manifest_before and not manifest_after:
            return SkillResult(
                success=True,
                summary="dependency.guard：无变更输入，跳过检查",
                data={
                    "passed": True,
                    "manifests_found": [],
                    "changes": [],
                    "violations": [],
                    "warnings": [],
                    "suggestions": [],
                    "summary": "无变更输入",
                },
            )

        result: DependencyResult = check_dependency_guard(
            changed_files=changed_files,
            diff_content=diff_content,
            manifest_before=manifest_before,
            manifest_after=manifest_after,
            lock_files_changed=lock_files_changed,
        )

        next_steps: list[str] = []
        if not result.passed:
            error_count = sum(
                1 for v in result.violations if v.severity == "error"
            )
            next_steps.append(
                f"检测到 {error_count} 个 error 级别违规，"
                f"请人工审查后再继续"
            )
            manifest_removed = [
                v for v in result.violations if v.rule == "manifest_removed"
            ]
            if manifest_removed:
                next_steps.append(
                    "manifest 文件被删除：请确认是否为有意删除"
                )
        else:
            warning_count = sum(
                1 for v in result.violations
                if v.severity in ("warning", "info")
            )
            if warning_count:
                next_steps.append(
                    f"检测到 {warning_count} 个 warning/info 级别提示，"
                    f"建议人工审查变更后再继续"
                )
            else:
                next_steps.append("依赖检查通过，可继续。")

        # 添加审计建议
        if result.suggestions:
            next_steps.append(
                f"安全审计建议: {'; '.join(result.suggestions)}"
            )

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
