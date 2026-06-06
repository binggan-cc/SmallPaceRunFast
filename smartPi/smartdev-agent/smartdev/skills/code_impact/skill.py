"""
Skill: code.impact — 影响分析

功能：分析某个文件、工件或模型变更的影响范围。
风险：R0（只读，不修改任何文件）
类型：analyze

这是 Phase 6-MVP 的第 5 个交付物。基于规则型影响分析（不做完整调用图）。

分析策略：
1. 直接引用：relations 表中 source_id/target_id 匹配
2. 间接影响：同目录文件、同类型 artifact、文件名模式匹配
3. 风险等级：基于影响范围计算
4. 验证项：根据影响的 artifact 类型自动生成

data 字段结构：
{
    "target": "tokens.css",
    "direct_references": ["references: ...", "calls: ..."],
    "indirect_impacts": ["同目录: ...", "相关工件: ..."],
    "risk_level": "R1",
    "verification_items": ["视觉一致性检查", ...],
    "summary": "..."
}

对应文档：
- next-phase-code-intelligence.md §8.3（code.impact 设计）
- next-phase-code-intelligence.md §9.4（Risk 计算）
- next-phase-code-intelligence.md §11（Task 5：code.impact）
"""

from __future__ import annotations

from pathlib import Path

from smartdev.context.impact_analyzer import ImpactAnalyzer
from smartdev.context.project_index import ProjectIndex
from smartdev.models import RiskLevel, SkillResult, TaskType
from smartdev.skills.base import Skill


class CodeImpactSkill(Skill):
    """影响分析 Skill

    分析修改某个文件或工件可能波及的范围。
    需要先运行 code.index 建立索引。

    使用示例：
        from smartdev.models import ProjectContext
        from smartdev.skills.base import Skill

        context = ProjectContext(project_path=Path("/path/to/project"))
        skill = Skill.create("code.impact")
        result = skill.run(context, {"target": "tokens.css"})
    """

    name = "code.impact"
    description = "分析某个文件、工件或模型变更的影响范围"
    risk_level = RiskLevel.R0
    task_type = TaskType.ANALYZE

    def can_run(self, context) -> bool:
        """前置条件：项目路径存在且已建立索引"""
        if not context.project_path.exists() or not context.project_path.is_dir():
            return False
        db_path = context.project_path / ".smartdev" / "index.sqlite"
        return db_path.exists()

    def run(self, context, inputs: dict | None = None) -> SkillResult:
        """执行影响分析

        参数：
            context: ProjectContext，必须包含 project_path
            inputs: 必须包含
                - target: str 目标文件路径或工件名称
                - max_depth: int 最大分析深度，默认 3

        返回：
            SkillResult，data 包含影响分析结果
        """
        inputs = inputs or {}
        target = inputs.get("target", "")
        max_depth = inputs.get("max_depth", 3)

        if not target:
            return SkillResult(
                success=False,
                summary="错误：分析目标不能为空",
            )

        # 打开索引
        index = ProjectIndex(context.project_path)

        try:
            analyzer = ImpactAnalyzer(index.store)
            result = analyzer.analyze(target, max_depth=max_depth)
        finally:
            index.close()

        return SkillResult(
            success=True,
            summary=result.summary,
            data={
                "target": result.target,
                "direct_references": result.direct_references,
                "indirect_impacts": result.indirect_impacts,
                "risk_level": result.risk_level,
                "verification_items": result.verification_items,
            },
            risks=[] if result.risk_level == "R0" else [
                f"变更 {target} 的风险等级为 {result.risk_level}",
                f"影响范围：{len(result.direct_references)} 个直接引用 + {len(result.indirect_impacts)} 个间接影响",
            ],
        )
