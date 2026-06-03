"""
Skill: risk.check 测试

验证：
1. 自动注册
2. 风险等级判定（R0/R1/R2/R3）
3. 前置检查清单
4. 回滚建议
5. 空任务描述拒绝执行
"""

from pathlib import Path

from smartdev.models import ProjectContext, RiskLevel, TaskType
from smartdev.skills.base import Skill


class TestRiskCheckSkill:
    """risk.check Skill 测试"""

    def test_registered_in_registry(self):
        """risk.check 已自动注册"""
        assert "risk.check" in Skill.get_registry()

    def test_skill_metadata(self):
        """Skill 元数据正确"""
        skill = Skill.create("risk.check")
        assert skill.risk_level == RiskLevel.R0
        assert skill.task_type == TaskType.PLAN

    def test_can_run_with_task(self, tmp_path: Path):
        """有任务描述时 can_run 返回 True"""
        skill = Skill.create("risk.check")
        context = ProjectContext(
            project_path=tmp_path,
            task_description="修复 Bug",
        )
        assert skill.can_run(context) is True

    def test_can_run_without_task(self, tmp_path: Path):
        """无任务描述时 can_run 返回 False"""
        skill = Skill.create("risk.check")
        context = ProjectContext(project_path=tmp_path)
        assert skill.can_run(context) is False

    def test_r0_default(self, tmp_path: Path):
        """无风险关键词时判定为 R0"""
        skill = Skill.create("risk.check")
        context = ProjectContext(
            project_path=tmp_path,
            task_description="继续下一步",
        )
        result = skill.run(context)
        assert result.data["risk_level"] == "R0"

    def test_r1_keyword(self, tmp_path: Path):
        """包含 CSS/样式 关键词时判定为 R1"""
        skill = Skill.create("risk.check")
        context = ProjectContext(
            project_path=tmp_path,
            task_description="修改 CSS 样式",
        )
        result = skill.run(context)
        assert result.data["risk_level"] == "R1"

    def test_r2_keyword(self, tmp_path: Path):
        """包含多文件/API 关键词时判定为 R2"""
        skill = Skill.create("risk.check")
        context = ProjectContext(
            project_path=tmp_path,
            task_description="调整 API 接口",
        )
        result = skill.run(context)
        assert result.data["risk_level"] == "R2"

    def test_r3_keyword(self, tmp_path: Path):
        """包含数据模型/权限 关键词时判定为 R3"""
        skill = Skill.create("risk.check")
        context = ProjectContext(
            project_path=tmp_path,
            task_description="修改数据模型",
        )
        result = skill.run(context)
        assert result.data["risk_level"] == "R3"

    def test_pre_check_list_grows_with_risk(self, tmp_path: Path):
        """风险越高，检查清单越长"""
        skill = Skill.create("risk.check")

        r0 = skill.run(ProjectContext(project_path=tmp_path, task_description="查看代码"))
        r1 = skill.run(ProjectContext(project_path=tmp_path, task_description="修改 CSS"))
        r2 = skill.run(ProjectContext(project_path=tmp_path, task_description="调整布局"))
        r3 = skill.run(ProjectContext(project_path=tmp_path, task_description="修改数据库 schema"))

        assert len(r0.data["pre_check_list"]) < len(r1.data["pre_check_list"])
        assert len(r1.data["pre_check_list"]) < len(r2.data["pre_check_list"])
        assert len(r2.data["pre_check_list"]) < len(r3.data["pre_check_list"])

    def test_rollback_suggestion(self, tmp_path: Path):
        """回滚建议随风险等级变化"""
        skill = Skill.create("risk.check")

        r0 = skill.run(ProjectContext(project_path=tmp_path, task_description="查看代码"))
        r3 = skill.run(ProjectContext(project_path=tmp_path, task_description="重构目录"))

        assert "无需回滚" in r0.data["rollback_suggestion"]
        assert "reset" in r3.data["rollback_suggestion"]

    def test_reasoning_provided(self, tmp_path: Path):
        """输出判定理由"""
        skill = Skill.create("risk.check")
        context = ProjectContext(
            project_path=tmp_path,
            task_description="修改权限配置",
        )
        result = skill.run(context)

        assert len(result.data["reasoning"]) >= 1
        assert "权限" in result.data["reasoning"][0]
