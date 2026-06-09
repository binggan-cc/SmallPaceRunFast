"""
Skill: dev.guard — AI 编程规则守卫（R0 只读）

功能：检查本轮任务是否违反 AI 编程硬规则：
      - 大规模重构（3+ 一级模块目录同时修改）
      - 命中 protected_paths
      - 与任务描述无关的改动
      - 测试文件/函数删除
      - 配置文件与功能代码同时修改
      - 修改禁止文件
      - 单 commit 过大

风险：R0（只读，不修改任何文件）

设计约束（docs/phase-11b-design.md §3.2）：
- 确定性规则引擎，不调用模型
- 无 git 环境也能运行（基于显式输入）
- unrelated_change 保守关键词匹配，不确定时 warning 不 error
- 路径匹配支持目录前缀 + fnmatch glob
"""

from __future__ import annotations

from smartdev.core.guard_dev import DevGuardResult, check_dev_guard
from smartdev.models import RiskLevel, SkillResult, TaskType
from smartdev.skills.base import Skill


class DevGuardSkill(Skill):
    """AI 编程规则守卫 Skill（R0 只读）

    检查本轮任务是否违反 AI 编程硬规则。
    输出结构化 checks / violations / summary。

    inputs 参数：
        changed_files:         list[str] — 变更文件列表（必需）
        protected_paths:       list[str] — 受保护路径（glob 模式）
        denied_paths:          list[str] — 禁止修改路径（glob 模式）
        forbidden_paths:       list[str] — 额外禁止路径
        task_description:      str      — 任务描述（用于 unrelated_change）
        diff_content:          str      — diff 内容（用于 test_deletion 精确检测）
        max_files_per_commit:  int      — 单 commit 最大文件数（默认 12）

    使用示例：
        result = Skill.create("dev.guard").run(context, {
            "changed_files": ["smartdev/core/git.py", "config.json"],
            "protected_paths": ["smartdev/mcp/", "smartdev/cli.py"],
            "task_description": "实现 git status skill",
        })
    """

    name = "dev.guard"
    description = "AI 编程规则守卫：大规模重构、protected path、无关改动、测试删除、配置文件混入"
    risk_level = RiskLevel.R0
    task_type = TaskType.DIAGNOSE

    def can_run(self, context) -> bool:
        # dev.guard 不依赖 git，任何时候都能运行
        return True

    def run(self, context, inputs: dict | None = None) -> SkillResult:
        inputs = inputs or {}

        changed_files: list[str] = inputs.get("changed_files", [])
        protected_paths: list[str] | None = inputs.get("protected_paths")
        denied_paths: list[str] | None = inputs.get("denied_paths")
        forbidden_paths: list[str] | None = inputs.get("forbidden_paths")
        task_description: str = str(inputs.get("task_description", ""))
        diff_content: str = str(inputs.get("diff_content", ""))
        max_files_per_commit: int = int(inputs.get("max_files_per_commit", 12))

        if not changed_files:
            return SkillResult(
                success=True,
                summary="dev.guard：无变更文件，跳过检查",
                data={
                    "passed": True,
                    "checks": {},
                    "violations": [],
                    "summary": "无变更文件",
                },
            )

        result: DevGuardResult = check_dev_guard(
            changed_files=changed_files,
            protected_paths=protected_paths,
            denied_paths=denied_paths,
            forbidden_paths=forbidden_paths,
            task_description=task_description,
            diff_content=diff_content,
            max_files_per_commit=max_files_per_commit,
        )

        next_steps: list[str] = []
        if not result.passed:
            next_steps.append(
                "建议拆分为多次小改动，每条违规单独处理后再检查"
            )
            mass = next(
                (v for v in result.violations if v.rule == "mass_refactor"), None
            )
            if mass:
                next_steps.append(
                    "大规模重构：请确认是否需要拆分为多个小步变更"
                )
            forbidden = [
                v for v in result.violations
                if v.rule in ("forbidden_file_modification", "protected_path_hit")
            ]
            if forbidden:
                next_steps.append(
                    "禁止/保护文件被修改：请移除这些文件的变更"
                )
        else:
            violations = result.violations
            if violations:
                next_steps.append("所有违规为 warning 级别，可继续。")
            else:
                next_steps.append("AI 编程规则检查通过，可继续。")

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
