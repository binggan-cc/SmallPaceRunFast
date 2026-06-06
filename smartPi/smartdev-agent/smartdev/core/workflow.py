"""
Workflow Engine — 工作流引擎

设计原理：
─────────
工作流引擎负责将多个 Skill 串联成一个完整的执行流程。
它不执行具体的 Skill 逻辑，只负责调度和数据传递。

为什么需要工作流引擎？
─────────────────────
1. 单个 Skill 只解决一个问题，真实任务需要多个 Skill 协作
2. 工作流引擎定义了 Skill 之间的执行顺序和数据依赖
3. 每个步骤可独立验证，失败时可以从中断点恢复

工作流阶段（对应 core-spec §6 状态机）：
────────────────────────────────────
  scan → analyze → plan → verify_risk → generate_docs → generate_patch → summary

每个阶段对应一个或多个 Skill。

对应文档：
- smartPi/docs/smartdev-agent-core-spec.md §6（状态机设计）
- smartPi/docs/smartdev-agent-core-spec.md §5（核心能力模块）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from smartdev.core.reporter import format_execution_header
from smartdev.core.risk import RiskController
from smartdev.models import ProjectContext, RiskLevel, SkillResult
from smartdev.skills.base import Skill


@dataclass
class WorkflowStep:
    """工作流步骤

    Attributes:
        name: 步骤名称
        skill_name: Skill 名称
        inputs: 输入参数（从上一步结果中提取）
        required: 是否必须执行（False 则可跳过）
    """
    name: str
    skill_name: str
    inputs: dict = field(default_factory=dict)
    required: bool = True


@dataclass
class WorkflowResult:
    """工作流执行结果

    Attributes:
        project_path: 项目路径
        steps: 每个步骤的执行结果
        success: 整体是否成功
        summary: 执行摘要
    """
    project_path: str
    steps: list[dict] = field(default_factory=list)
    success: bool = True
    summary: str = ""

    def to_markdown(self) -> str:
        """输出为 Markdown 格式的执行报告"""
        lines = [
            "# SmartDev Agent — 执行报告",
            "",
            f"项目: {self.project_path}",
            f"状态: {'成功' if self.success else '失败'}",
            "",
            "## 执行步骤",
            "",
        ]

        for i, step in enumerate(self.steps, 1):
            status = "✅" if step["success"] else "❌"
            skill_name = step["skill_name"]
            risk = step.get("risk_level", "R0")
            first_line = step["summary"].split("\n")[0]
            lines.append(f"{i}. {status} **{skill_name}** [{risk}] — {first_line}")

        lines.extend(["", "## 摘要", "", self.summary])

        return "\n".join(lines)


# ── 默认工作流 ──────────────────────────────────────────
# 对应 core-spec §6 的状态机

DEFAULT_WORKFLOW = [
    WorkflowStep(
        name="项目扫描",
        skill_name="repo.scan",
    ),
    WorkflowStep(
        name="架构分析",
        skill_name="architecture.map",
        required=False,  # 非 Python 项目可跳过
    ),
    WorkflowStep(
        name="Token 审计",
        skill_name="token.audit",
        required=False,  # 非 CSS 项目可跳过
    ),
    WorkflowStep(
        name="风险检查",
        skill_name="risk.check",
        inputs={"task_description": "auto"},
        required=False,  # 无任务时可跳过
    ),
    WorkflowStep(
        name="任务规划",
        skill_name="task.plan",
        inputs={"task_description": "auto"},
        required=False,  # 无任务时可跳过
    ),
    WorkflowStep(
        name="验收清单",
        skill_name="qa.checklist",
        inputs={"task_description": "auto"},
        required=False,  # 无任务时可跳过
    ),
]


class WorkflowEngine:
    """工作流引擎

    串联多个 Skill 执行完整的诊断和规划流程。

    使用示例：
        engine = WorkflowEngine()
        result = engine.run(Path("/path/to/project"), task="统一 tokens")
        print(result.to_markdown())
    """

    def __init__(self, steps: list[WorkflowStep] | None = None):
        self.steps = steps or DEFAULT_WORKFLOW
        self.risk_controller = RiskController()

    def run(
        self,
        project_path: Path,
        task: str = "",
    ) -> WorkflowResult:
        """执行完整工作流

        参数：
            project_path: 项目根目录
            task: 任务描述（可选）

        返回：
            WorkflowResult
        """
        result = WorkflowResult(project_path=str(project_path))

        # 触发 Skill 注册
        import smartdev.skills  # noqa: F401

        # 构建上下文
        context = ProjectContext(
            project_path=project_path,
            task_description=task,
        )

        accumulated_data = {}

        for step in self.steps:
            step_result = self._run_step(step, context, accumulated_data)

            result.steps.append(step_result)

            # 如果步骤失败且必须执行，中断工作流
            if not step_result["success"] and step.required:
                result.success = False
                result.summary = f"工作流在「{step.name}」步骤失败"
                break

            # 累积数据
            if step_result["data"]:
                accumulated_data[step.skill_name] = step_result["data"]

        # 生成摘要
        if result.success:
            result.summary = self._generate_summary(result.steps, accumulated_data)

        return result

    def _run_step(
        self,
        step: WorkflowStep,
        context: ProjectContext,
        accumulated_data: dict,
    ) -> dict:
        """执行单个步骤"""
        try:
            skill = Skill.create(step.skill_name)
        except KeyError:
            return {
                "skill_name": step.skill_name,
                "success": False,
                "summary": f"Skill '{step.skill_name}' 未注册",
                "risk_level": "N/A",
                "data": None,
            }

        # 风险检查
        decision = self.risk_controller.check(skill.risk_level)
        if decision.value == "confirm":
            return {
                "skill_name": step.skill_name,
                "success": False,
                "summary": f"需要用户确认（风险等级 {skill.risk_level.value}）",
                "risk_level": skill.risk_level.value,
                "data": None,
            }

        # 前置条件检查
        if not skill.can_run(context):
            return {
                "skill_name": step.skill_name,
                "success": False,
                "summary": "前置条件不满足，跳过",
                "risk_level": skill.risk_level.value,
                "data": None,
            }

        # 准备输入
        inputs = {}
        for key, value in step.inputs.items():
            if value == "auto":
                inputs[key] = context.task_description
            else:
                inputs[key] = value

        # 执行
        skill_result = skill.run(context, inputs or None)

        return {
            "skill_name": step.skill_name,
            "success": skill_result.success,
            "summary": skill_result.summary,
            "risk_level": skill.risk_level.value,
            "data": skill_result.data,
            "risks": skill_result.risks,
            "next_steps": skill_result.next_steps,
        }

    def _generate_summary(self, steps: list[dict], data: dict) -> str:
        """生成执行摘要"""
        total = len(steps)
        success = sum(1 for s in steps if s["success"])
        failed = total - success

        lines = [
            f"执行完成：{success}/{total} 个步骤成功",
        ]

        if failed > 0:
            lines.append(f"失败步骤：{failed} 个")

        # 从 scan 结果提取技术栈
        scan_data = data.get("repo.scan", {})
        if scan_data:
            tech = scan_data.get("tech_stack", {})
            langs = [t["name"] for t in tech.get("languages", [])]
            platforms = [t["name"] for t in tech.get("platforms", [])]
            all_tech = langs + platforms
            if all_tech:
                lines.append(f"技术栈：{', '.join(all_tech)}")

        # 从 plan 结果提取方案数
        plan_data = data.get("task.plan", {})
        if plan_data:
            conservative = plan_data.get("conservative", {})
            recommended = plan_data.get("recommended", {})
            deep = plan_data.get("deep", {})
            lines.append(
                f"方案：保守 {len(conservative.get('tasks', []))} 任务"
                f" / 推荐 {len(recommended.get('tasks', []))} 任务"
                f" / 深度 {len(deep.get('tasks', []))} 任务"
            )

        return "\n".join(lines)
