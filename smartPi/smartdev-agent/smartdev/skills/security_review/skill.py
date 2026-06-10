"""
Skill: security.review — 安全审查清单（R0 只读）

功能：对 patch 或受影响文件做确定性安全 checklist 检查：
      - 输入校验（input_validation）
      - 路径穿越（path_traversal）
      - 命令注入（command_injection）
      - 敏感数据（sensitive_data）
      - 硬编码密钥（hardcoded_secrets）
      - 动态代码执行（eval_exec）

风险：R0（只读，不修改任何文件）

设计约束（docs/phase-11b-design.md §3.4）：
- 确定性规则引擎，不调用模型
- 无 git 环境也能运行（基于显式输入）
- 第一版只做文本模式匹配，不做 AST 解析
- 外部工具只输出建议，不执行（bandit / semgrep）
"""

from __future__ import annotations

from smartdev.core.guard_security import SecurityResult, check_security_review
from smartdev.models import RiskLevel, SkillResult, TaskType
from smartdev.skills.base import Skill


class SecurityReviewSkill(Skill):
    """安全审查清单 Skill（R0 只读）

    对 AI 生成的 patch 做 6 类确定性安全检查。
    输出结构化 checks / violations / suggestions / summary。

    inputs 参数：
        changed_files:  list[str]            — 变更文件列表（必需）
        diff_content:   str | None           — 完整的 unified diff 文本
        file_contents:  dict[str, str] | None — 文件内容映射

    使用示例：
        result = Skill.create("security.review").run(context, {
            "changed_files": ["src/app.py", ".env"],
            "diff_content": "...",
            "file_contents": {"src/app.py": "..."},
        })
    """

    name = "security.review"
    description = (
        "安全审查清单：输入校验/路径穿越/命令注入/敏感数据/"
        "硬编码密钥/动态代码执行"
    )
    risk_level = RiskLevel.R0
    task_type = TaskType.DIAGNOSE

    def can_run(self, context) -> bool:
        # security.review 不依赖 git，任何时候都能运行
        return True

    def run(self, context, inputs: dict | None = None) -> SkillResult:
        inputs = inputs or {}

        changed_files: list[str] = inputs.get("changed_files", [])
        diff_content: str | None = inputs.get("diff_content")
        file_contents: dict[str, str] | None = inputs.get("file_contents")

        if not changed_files and not file_contents:
            return SkillResult(
                success=True,
                summary="security.review：无变更文件，跳过检查",
                data={
                    "passed": True,
                    "checks": {},
                    "violations": [],
                    "suggestions": [],
                    "summary": "无变更文件",
                },
            )

        result: SecurityResult = check_security_review(
            changed_files=changed_files,
            diff_content=diff_content,
            file_contents=file_contents,
        )

        next_steps: list[str] = []
        if not result.passed:
            error_count = sum(
                1 for v in result.violations if v.severity == "error"
            )
            next_steps.append(
                f"检测到 {error_count} 个 error 级别安全问题，"
                f"请在 apply 前修复"
            )
            # 列出 error 涉及的规则
            error_rules = sorted(set(
                v.rule for v in result.violations if v.severity == "error"
            ))
            next_steps.append(f"涉及: {', '.join(error_rules)}")
        else:
            warning_count = sum(
                1 for v in result.violations
                if v.severity in ("warning", "info")
            )
            if warning_count:
                next_steps.append(
                    f"检测到 {warning_count} 个 warning/info 级别问题，"
                    f"建议人工审查"
                )
            else:
                next_steps.append("安全审查通过，可继续。")

        # 添加审计建议
        if result.suggestions:
            next_steps.append(
                f"建议运行外部审计工具: {'; '.join(result.suggestions)}"
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
