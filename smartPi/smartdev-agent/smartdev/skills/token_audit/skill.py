"""
Skill: token.audit — Token 审计

功能：检查设计令牌来源、重复定义、硬编码颜色、覆盖率。
风险：R0（只读，不修改任何文件）
类型：ui_governance

data 字段结构：
{
    "token_sources": [{"path": "...", "variable_count": 10, "variables": [...]}],
    "hardcoded_colors": [{"file": "...", "line": 42, "value": "#ff0000", "format": "hex"}],
    "coverage_rate": 0.75,
    "summary": {
        "source_count": 2,
        "has_multiple_sources": true,
        "color_count": 15,
        "coverage_rate": 0.75
    },
    "recommendations": ["建议统一 Token 来源"]
}
"""

from __future__ import annotations

from smartdev.detectors.design_tokens import detect_design_tokens
from smartdev.models import RiskLevel, SkillResult, TaskType
from smartdev.skills.base import Skill


class TokenAuditSkill(Skill):
    """Token 审计 Skill

    检查项目中的设计令牌来源、硬编码颜色和覆盖率。

    使用示例：
        context = ProjectContext(project_path=Path("/path/to/project"))
        skill = Skill.create("token.audit")
        result = skill.run(context)
    """

    name = "token.audit"
    description = "检查设计令牌来源、重复定义、硬编码颜色和覆盖率"
    risk_level = RiskLevel.R0
    task_type = TaskType.UI_GOVERNANCE

    def can_run(self, context) -> bool:
        """前置条件：项目路径存在"""
        return context.project_path.exists() and context.project_path.is_dir()

    def run(self, context, inputs: dict | None = None) -> SkillResult:
        """执行 Token 审计"""
        project = context.project_path

        # 检测设计令牌
        result = detect_design_tokens(project)

        # 构建摘要
        summary_parts = [
            f"Token 审计完成：{project.name}",
            f"Token 来源：{result.source_count} 个",
            f"硬编码颜色：{result.color_count} 个",
            f"覆盖率：{result.coverage_rate:.0%}",
        ]

        # 风险
        risks = []
        if result.has_multiple_sources:
            source_names = [s.path for s in result.token_sources]
            risks.append(f"Token 来源不唯一: {', '.join(source_names)}")
        if result.color_count > 0:
            risks.append(f"发现 {result.color_count} 个硬编码颜色，建议替换为 Token 变量")

        # 建议
        recommendations = []
        if result.has_multiple_sources:
            recommendations.append("建议统一 Token 来源为单一文件")
        if result.color_count > 0:
            recommendations.append("建议将硬编码颜色替换为 CSS 变量")
        if result.source_count == 0 and result.color_count == 0:
            recommendations.append("未检测到 CSS 文件或 Token 定义")

        return SkillResult(
            success=True,
            summary="\n".join(summary_parts),
            data={
                "token_sources": [
                    {
                        "path": s.path,
                        "variable_count": s.variable_count,
                        "variables": s.variables[:10],  # 只输出前 10 个
                    }
                    for s in result.token_sources
                ],
                "hardcoded_colors": [
                    {
                        "file": c.file,
                        "line": c.line,
                        "value": c.value,
                        "format": c.format,
                        "context": c.context,
                    }
                    for c in result.hardcoded_colors[:50]  # 只输出前 50 个
                ],
                "coverage_rate": result.coverage_rate,
                "summary": {
                    "source_count": result.source_count,
                    "has_multiple_sources": result.has_multiple_sources,
                    "color_count": result.color_count,
                    "coverage_rate": result.coverage_rate,
                },
                "recommendations": recommendations,
            },
            risks=risks,
            next_steps=[
                "建议运行 task.plan 规划 Token 统一任务",
                "如有重复来源，建议先选定唯一来源再替换",
            ],
        )
