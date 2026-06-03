"""
Skill: task.plan 测试

验证：
1. 自动注册
2. 三档方案输出
3. 任务拆解结构
4. can_run 前置条件
5. 空任务描述拒绝执行
"""

from pathlib import Path

from smartdev.models import ProjectContext, RiskLevel, SkillResult, TaskType
from smartdev.skills.base import Skill


class TestTaskPlanSkill:
    """task.plan Skill 测试"""

    def test_registered_in_registry(self):
        """task.plan 已自动注册"""
        assert "task.plan" in Skill.get_registry()

    def test_skill_metadata(self):
        """Skill 元数据正确"""
        skill = Skill.create("task.plan")
        assert skill.risk_level == RiskLevel.R0
        assert skill.task_type == TaskType.PLAN

    def test_can_run_with_valid_context(self, tmp_path: Path):
        """有任务描述时 can_run 返回 True"""
        skill = Skill.create("task.plan")
        context = ProjectContext(
            project_path=tmp_path,
            task_description="统一 design tokens",
        )
        assert skill.can_run(context) is True

    def test_can_run_without_task_description(self, tmp_path: Path):
        """无任务描述时 can_run 返回 False"""
        skill = Skill.create("task.plan")
        context = ProjectContext(project_path=tmp_path)
        assert skill.can_run(context) is False

    def test_can_run_with_empty_task_description(self, tmp_path: Path):
        """空任务描述时 can_run 返回 False"""
        skill = Skill.create("task.plan")
        context = ProjectContext(
            project_path=tmp_path,
            task_description="   ",
        )
        assert skill.can_run(context) is False

    def test_run_generates_three_tiers(self, tmp_path: Path):
        """运行输出三档方案"""
        skill = Skill.create("task.plan")
        context = ProjectContext(
            project_path=tmp_path,
            task_description="统一 design tokens",
        )
        result = skill.run(context)

        assert isinstance(result, SkillResult)
        assert result.success is True

        # 三档方案都存在
        assert "conservative" in result.data
        assert "recommended" in result.data
        assert "deep" in result.data

        # 每档方案有 name 和 tasks
        for tier in ["conservative", "recommended", "deep"]:
            proposal = result.data[tier]
            assert "name" in proposal
            assert "tasks" in proposal
            assert len(proposal["tasks"]) >= 1

    def test_proposals_have_required_fields(self, tmp_path: Path):
        """每档方案包含必要字段"""
        skill = Skill.create("task.plan")
        context = ProjectContext(
            project_path=tmp_path,
            task_description="修复 Side Panel 宽度",
        )
        result = skill.run(context)

        for tier in ["conservative", "recommended", "deep"]:
            proposal = result.data[tier]
            assert "name" in proposal
            assert "description" in proposal
            assert "scope" in proposal
            assert "risk" in proposal
            assert "effort" in proposal
            assert "tasks" in proposal

    def test_task_breakdown_structure(self, tmp_path: Path):
        """推荐方案的任务拆解结构正确"""
        skill = Skill.create("task.plan")
        context = ProjectContext(
            project_path=tmp_path,
            task_description="添加暗色模式",
        )
        result = skill.run(context)

        breakdown = result.data["recommended_task_breakdown"]
        assert len(breakdown) >= 1
        for step in breakdown:
            assert "step" in step
            assert "name" in step
            assert "risk" in step

    def test_conservative_is_smaller_than_recommended(self, tmp_path: Path):
        """保守方案任务数 <= 推荐方案任务数"""
        skill = Skill.create("task.plan")
        context = ProjectContext(
            project_path=tmp_path,
            task_description="重构目录结构",
        )
        result = skill.run(context)

        conservative_tasks = len(result.data["conservative"]["tasks"])
        recommended_tasks = len(result.data["recommended"]["tasks"])
        assert conservative_tasks <= recommended_tasks

    def test_next_steps_generated(self, tmp_path: Path):
        """输出下一步建议"""
        skill = Skill.create("task.plan")
        context = ProjectContext(
            project_path=tmp_path,
            task_description="统一 tokens",
        )
        result = skill.run(context)

        assert len(result.next_steps) >= 1
