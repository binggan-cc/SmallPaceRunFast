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


# ── Phase 8 Step 3: code.impact 接入测试 ──────────────────────


class TestTaskPlanImpactIntegration:
    """task.plan 接入 code.impact 的优雅降级测试

    核心验证：
    - 无 target / 无索引 → 纯三档模板（零回归，无 impact 字段）
    - 有 target + 索引 → 推荐方案标注受影响文件
    - target 可从 inputs 或任务描述中的文件 token 提取
    """

    def _build_indexed_project(self, tmp_path: Path) -> Path:
        project = tmp_path / "pyproj"
        project.mkdir()
        (project / "models.py").write_text("class User:\n    pass\n")
        (project / "service.py").write_text(
            "from models import User\n\ndef f():\n    return User()\n"
        )
        (project / "api.py").write_text(
            "from models import User\n\ndef g():\n    return User()\n"
        )
        from smartdev.context.project_index import ProjectIndex

        index = ProjectIndex(project)
        index.index()
        index.close()
        return project

    def test_no_index_no_impact_field(self, tmp_path: Path):
        """无索引 → 纯模板，无 impact 字段（零回归）"""
        skill = Skill.create("task.plan")
        context = ProjectContext(
            project_path=tmp_path,
            task_description="统一 design tokens",
        )
        result = skill.run(context)
        assert result.success
        assert "impact" not in result.data
        # 推荐方案占位符保持原样
        rec = result.data["recommended"]
        assert any("（待分析）" in t.get("files", []) for t in rec["tasks"])

    def test_target_in_inputs_triggers_impact(self, tmp_path: Path):
        """inputs 提供 target + 索引 → 推荐方案标注受影响文件"""
        project = self._build_indexed_project(tmp_path)
        skill = Skill.create("task.plan")
        context = ProjectContext(
            project_path=project,
            task_description="修改用户模型",
        )
        result = skill.run(context, {"target": "models.py"})
        assert result.success
        assert "impact" in result.data
        affected = result.data["impact"]["affected_files"]
        assert any("service.py" in f for f in affected)
        assert any("api.py" in f for f in affected)

    def test_target_extracted_from_description(self, tmp_path: Path):
        """任务描述含文件 token → 自动提取为 target"""
        project = self._build_indexed_project(tmp_path)
        skill = Skill.create("task.plan")
        context = ProjectContext(
            project_path=project,
            task_description="重构 models.py 的 User 类",
        )
        result = skill.run(context)
        assert result.success
        assert "impact" in result.data
        assert result.data["impact"]["target"] == "models.py"

    def test_recommended_tasks_get_affected_files(self, tmp_path: Path):
        """推荐方案的占位符任务被替换为真实受影响文件"""
        project = self._build_indexed_project(tmp_path)
        skill = Skill.create("task.plan")
        context = ProjectContext(
            project_path=project,
            task_description="修改 models.py",
        )
        result = skill.run(context)
        rec = result.data["recommended"]
        # 不应再有 "（待分析）" 占位符
        all_files = [f for t in rec["tasks"] for f in t.get("files", [])]
        assert "（待分析）" not in all_files
        # 应包含真实文件
        assert any("service.py" in f or "api.py" in f for f in all_files)

    def test_three_tiers_preserved_with_impact(self, tmp_path: Path):
        """接入 impact 后三档结构不变"""
        project = self._build_indexed_project(tmp_path)
        skill = Skill.create("task.plan")
        context = ProjectContext(
            project_path=project,
            task_description="修改 models.py",
        )
        result = skill.run(context)
        for tier in ["conservative", "recommended", "deep"]:
            proposal = result.data[tier]
            assert "name" in proposal
            assert "tasks" in proposal
            assert len(proposal["tasks"]) >= 1

    def test_unresolved_target_no_impact(self, tmp_path: Path):
        """target 在索引中找不到 → 无 impact 字段，退回模板"""
        project = self._build_indexed_project(tmp_path)
        skill = Skill.create("task.plan")
        context = ProjectContext(
            project_path=project,
            task_description="统一配色方案",
        )
        result = skill.run(context, {"target": "nonexistent_xyz"})
        assert result.success
        assert "impact" not in result.data
