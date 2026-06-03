"""
Skill: risk.check — 风险检查

功能：分析任务的风险等级（R0-R3），输出前置检查清单和回滚建议。
风险：R0（只读，不修改任何文件）
类型：plan

对应文档：
- smartPi/docs/smartdev-agent-core-spec.md §11（风险等级定义）
- smartPi/docs/smartdev-agent-protocol.md §8（任务粒度规范）
"""

from __future__ import annotations

import re

from smartdev.models import RiskLevel, SkillResult, TaskType
from smartdev.skills.base import Skill


# ── 风险规则 ──────────────────────────────────────────────
# 对应 protocol §8 的任务粒度规范
#
# 为什么用规则引擎而非 LLM？
# Phase 1 需要确定性输出，方便测试和验证。
# 规则引擎的输出每次一致，LLM 可能每次不同。
#
# 匹配策略：关键词列表中的每个词独立匹配。
# 任务描述包含任一关键词即命中该风险等级。

# R3 关键词：涉及数据模型、权限、技术栈、目录结构
_R3_KEYWORDS = [
    "数据模型", "数据库", "schema", "migration", "迁移",
    "权限", "permission", "auth", "认证",
    "技术栈", "目录重构", "重构目录", "monorepo",
    "删除核心", "重置数据", "引入大型依赖",
]

# R2 关键词：多文件、多模块、API 调整
_R2_KEYWORDS = [
    "多文件", "跨模块", "API", "接口",
    "布局", "样式系统",
    "Side Panel", "Popup", "Background",
    "数据同步", "状态管理",
]

# R1 关键词：小范围修改
_R1_KEYWORDS = [
    "CSS", "样式", "颜色", "字体", "间距",
    "文案", "注释", "README",
    "工具函数", "辅助函数",
]


def _analyze_risk_level(task_description: str) -> tuple[RiskLevel, list[str], list[str]]:
    """分析任务描述，返回 (风险等级, 风险因素, 判定理由)"""
    task_lower = task_description.lower()
    factors = []
    reasoning = []

    # 检查 R3
    for keyword in _R3_KEYWORDS:
        if keyword.lower() in task_lower:
            factors.append(f"涉及高风险操作：{keyword}")
            reasoning.append(f"任务包含「{keyword}」关键词，属于 R3 高风险")

    if factors:
        return RiskLevel.R3, factors, reasoning

    # 检查 R2
    for keyword in _R2_KEYWORDS:
        if keyword.lower() in task_lower:
            factors.append(f"涉及中风险操作：{keyword}")
            reasoning.append(f"任务包含「{keyword}」关键词，属于 R2 中风险")

    if factors:
        return RiskLevel.R2, factors, reasoning

    # 检查 R1
    for keyword in _R1_KEYWORDS:
        if keyword.lower() in task_lower:
            factors.append(f"涉及低风险操作：{keyword}")
            reasoning.append(f"任务包含「{keyword}」关键词，属于 R1 低风险")

    if factors:
        return RiskLevel.R1, factors, reasoning

    # 默认 R0
    return RiskLevel.R0, [], ["任务未匹配任何风险关键词，默认为 R0 无风险"]


def _build_pre_check_list(risk_level: RiskLevel) -> list[str]:
    """根据风险等级构建前置检查清单"""
    checks = {
        RiskLevel.R0: [
            "确认任务范围清晰",
        ],
        RiskLevel.R1: [
            "确认修改范围（哪些文件）",
            "确认不修改范围（哪些文件不动）",
            "运行现有测试确认基线",
        ],
        RiskLevel.R2: [
            "确认修改范围和影响文件",
            "确认不修改范围",
            "评估是否影响现有功能",
            "准备回滚方案",
            "运行现有测试确认基线",
            "确认数据模型无变化",
        ],
        RiskLevel.R3: [
            "确认修改范围和所有影响文件",
            "确认不修改范围",
            "评估对现有功能的全部影响",
            "准备完整回滚方案",
            "确认数据迁移方案",
            "确认权限模型无变化",
            "运行全部测试确认基线",
            "需要用户确认后才能执行",
        ],
    }
    return checks.get(risk_level, [])


def _build_rollback_suggestion(risk_level: RiskLevel) -> str:
    """根据风险等级给出回滚建议"""
    suggestions = {
        RiskLevel.R0: "无需回滚方案（只读操作）",
        RiskLevel.R1: "可通过 git revert 回滚单次提交",
        RiskLevel.R2: "建议在独立分支开发，完成后合并；回滚用 git revert",
        RiskLevel.R3: "必须在独立分支开发，修改前创建 tag；回滚用 git reset --hard <tag>",
    }
    return suggestions.get(risk_level, "未知风险等级")


class RiskCheckSkill(Skill):
    """风险检查 Skill

    分析任务的风险等级，输出前置检查清单和回滚建议。

    使用示例：
        context = ProjectContext(
            project_path=Path("/path/to/project"),
            task_description="修改数据模型",
        )
        skill = Skill.create("risk.check")
        result = skill.run(context)
    """

    name = "risk.check"
    description = "分析任务风险等级，输出前置检查清单和回滚建议"
    risk_level = RiskLevel.R0
    task_type = TaskType.PLAN

    def can_run(self, context) -> bool:
        """前置条件：有任务描述"""
        return bool(context.task_description.strip())

    def run(self, context, inputs: dict | None = None) -> SkillResult:
        """执行风险检查"""
        task_description = context.task_description

        # 分析风险等级
        risk_level, factors, reasoning = _analyze_risk_level(task_description)

        # 构建检查清单
        pre_check_list = _build_pre_check_list(risk_level)

        # 回滚建议
        rollback = _build_rollback_suggestion(risk_level)

        # 摘要
        summary_parts = [
            f"风险检查完成：{task_description}",
            f"建议风险等级：{risk_level.value}",
            f"风险因素：{len(factors)} 个",
            f"前置检查项：{len(pre_check_list)} 个",
        ]

        return SkillResult(
            success=True,
            summary="\n".join(summary_parts),
            data={
                "task_description": task_description,
                "risk_level": risk_level.value,
                "risk_factors": factors,
                "pre_check_list": pre_check_list,
                "rollback_suggestion": rollback,
                "reasoning": reasoning,
            },
            risks=factors,
            next_steps=[
                f"风险等级为 {risk_level.value}，" + (
                    "可直接执行。" if risk_level == RiskLevel.R0
                    else "建议执行前完成检查清单。" if risk_level == RiskLevel.R1
                    else "需要用户确认后才能执行。"
                ),
            ],
        )
