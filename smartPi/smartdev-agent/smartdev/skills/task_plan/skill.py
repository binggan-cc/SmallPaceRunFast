"""
Skill: task.plan — 任务规划（方案分级）

功能：将需求拆解为可执行的小任务，输出保守/推荐/深度三档方案。
风险：R0（只读，不修改任何文件）
类型：plan

对应文档：
- smartPi/docs/smartdev-agent-core-spec.md §12（方案分级）
- smartPi/docs/smartdev-agent-core-spec.md §5.5（任务拆解）
- smartPi/docs/smartdev-agent-protocol.md §5 步骤 5（方案分级）

data 字段结构：
{
    "task_description": "...",
    "conservative": {
        "name": "保守方案",
        "description": "...",
        "scope": ["修改范围"],
        "risk": "低",
        "effort": "0.5 天",
        "tasks": [{"name": "...", "files": [...], "risk": "R0"}]
    },
    "recommended": { ... },
    "deep": { ... },
    "recommended_task_breakdown": [...]
}
"""

from __future__ import annotations

from dataclasses import dataclass, field

from smartdev.models import RiskLevel, SkillResult, TaskType
from smartdev.skills.base import Skill


@dataclass
class Proposal:
    """单档方案

    Attributes:
        name: 方案名称（保守/推荐/深度）
        description: 方案描述
        scope: 修改范围
        risk: 风险评估
        effort: 预估工作量
        tasks: 任务拆解
    """
    name: str
    description: str
    scope: list[str] = field(default_factory=list)
    risk: str = "低"
    effort: str = ""
    tasks: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "scope": self.scope,
            "risk": self.risk,
            "effort": self.effort,
            "tasks": self.tasks,
        }


def _build_proposals(
    task_description: str,
    project_path_str: str,
    tech_stack: list[str],
    constraints: list[str],
) -> tuple[Proposal, Proposal, Proposal]:
    """构建三档方案

    Phase 1 的方案生成是基于规则的模板匹配，而非 LLM 生成。
    后续可以用 LLM 替换此函数，接口不变。

    为什么用模板而非 LLM？
    Phase 1 需要确定性输出，方便测试和验证。
    LLM 生成的方案每次不同，难以做回归测试。
    """
    # 基于任务类型推断方案
    task_lower = task_description.lower()

    # ── 保守方案：最小改动 ──────────────────────────────────
    conservative = Proposal(
        name="保守方案",
        description=f"最小改动解决「{task_description}」的表层问题",
        scope=["单文件或少量文件修改"],
        risk="低",
        effort="0.5-1 天",
        tasks=[{
            "name": f"快速修复：{task_description}",
            "files": ["（待分析）"],
            "risk": "R1",
        }],
    )

    # ── 推荐方案：解决根因 ──────────────────────────────────
    recommended = Proposal(
        name="推荐方案",
        description=f"解决「{task_description}」的根因，不破坏现有技术栈",
        scope=["相关模块修改", "配置调整"],
        risk="中",
        effort="1-3 天",
        tasks=[
            {
                "name": "分析影响范围",
                "files": ["（待分析）"],
                "risk": "R0",
            },
            {
                "name": f"核心修改：{task_description}",
                "files": ["（待分析）"],
                "risk": "R2",
            },
            {
                "name": "验证与回归",
                "files": [],
                "risk": "R0",
            },
        ],
    )

    # ── 深度方案：长期架构 ──────────────────────────────────
    deep = Proposal(
        name="深度方案",
        description=f"从架构层面彻底解决「{task_description}」，适合长期维护",
        scope=["模块重构", "架构调整", "文档更新"],
        risk="较高",
        effort="3-7 天",
        tasks=[
            {
                "name": "架构分析与设计",
                "files": ["docs/architecture.md"],
                "risk": "R0",
            },
            {
                "name": "模块重构",
                "files": ["（待分析）"],
                "risk": "R3",
            },
            {
                "name": "测试补全",
                "files": ["tests/"],
                "risk": "R1",
            },
            {
                "name": "文档更新",
                "files": ["README.md", "docs/"],
                "risk": "R1",
            },
        ],
    )

    return conservative, recommended, deep


class TaskPlanSkill(Skill):
    """任务规划 Skill

    将需求拆解为可执行的小任务，输出三档方案。
    对应 protocol §5 的步骤 5（方案分级）。

    使用示例：
        context = ProjectContext(
            project_path=Path("/path/to/project"),
            task_description="统一 design tokens",
        )
        skill = Skill.create("task.plan")
        result = skill.run(context)
        # result.data["conservative"]   — 保守方案
        # result.data["recommended"]    — 推荐方案
        # result.data["deep"]           — 深度方案
    """

    name = "task.plan"
    description = "将需求拆解为可执行的小任务，输出保守/推荐/深度三档方案"
    risk_level = RiskLevel.R0
    task_type = TaskType.PLAN

    def can_run(self, context) -> bool:
        """前置条件：项目路径存在且有任务描述"""
        return (
            context.project_path.exists()
            and context.project_path.is_dir()
            and bool(context.task_description.strip())
        )

    def run(self, context, inputs: dict | None = None) -> SkillResult:
        """执行任务规划

        参数：
            context: ProjectContext，必须包含 project_path 和 task_description
            inputs: 可选参数
                - scan_result: repo.scan 的输出结果（如有）
                - tech_stack: 技术栈列表（如有）

        返回：
            SkillResult，data 包含三档方案和任务拆解
        """
        task_description = context.task_description
        project_path_str = str(context.project_path)
        tech_stack = context.tech_stack
        constraints = context.constraints

        # 构建三档方案
        conservative, recommended, deep = _build_proposals(
            task_description=task_description,
            project_path_str=project_path_str,
            tech_stack=tech_stack,
            constraints=constraints,
        )

        # 组装摘要
        summary_parts = [
            f"任务规划完成：{task_description}",
            f"三档方案已生成",
            f"保守方案：{len(conservative.tasks)} 个任务",
            f"推荐方案：{len(recommended.tasks)} 个任务",
            f"深度方案：{len(deep.tasks)} 个任务",
        ]

        return SkillResult(
            success=True,
            summary="\n".join(summary_parts),
            data={
                "task_description": task_description,
                "conservative": conservative.to_dict(),
                "recommended": recommended.to_dict(),
                "deep": deep.to_dict(),
                "recommended_task_breakdown": [
                    {
                        "step": i + 1,
                        "name": t["name"],
                        "risk": t["risk"],
                    }
                    for i, t in enumerate(recommended.tasks)
                ],
            },
            next_steps=[
                "选择方案后，可运行 risk.check 评估风险",
                "确认方案后，可进入执行阶段",
            ],
        )
