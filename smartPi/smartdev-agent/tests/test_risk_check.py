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


# ── Phase 8 Step 1: code.impact 接入测试 ──────────────────────


class TestRiskCheckImpactIntegration:
    """risk.check 接入 code.impact 的优雅降级测试

    核心验证：
    - 无 target → 退回关键词匹配（零回归）
    - 有 target 但无索引 → 退回关键词匹配
    - 有 target 且有索引 → impact 增强 + 风险取最大值
    """

    def _build_python_project(self, tmp_path: Path) -> Path:
        """建一个有 import 关系的小 Python 项目并索引。"""
        project = tmp_path / "pyproj"
        project.mkdir()
        (project / "models.py").write_text(
            "class User:\n    def __init__(self, name):\n        self.name = name\n"
        )
        # 两个文件 import models，构成影响范围
        (project / "service.py").write_text(
            "from models import User\n\ndef make_user(n):\n    return User(n)\n"
        )
        (project / "api.py").write_text(
            "from models import User\n\ndef endpoint():\n    return User('x')\n"
        )
        from smartdev.context.project_index import ProjectIndex

        index = ProjectIndex(project)
        index.index()
        index.close()
        return project

    def test_no_target_falls_back_to_keyword(self, tmp_path: Path):
        """无 target → 纯关键词匹配，risk_source=keyword"""
        skill = Skill.create("risk.check")
        context = ProjectContext(
            project_path=tmp_path,
            task_description="统一 CSS 颜色",
        )
        result = skill.run(context)
        assert result.success
        assert result.data["risk_source"] == "keyword"
        assert "affected_files" not in result.data

    def test_target_without_index_falls_back(self, tmp_path: Path):
        """有 target 但项目无索引 → 退回关键词匹配"""
        project = tmp_path / "noindex"
        project.mkdir()
        skill = Skill.create("risk.check")
        context = ProjectContext(
            project_path=project,
            task_description="修改 models.py",
        )
        result = skill.run(context, {"target": "models.py"})
        assert result.success
        assert result.data["risk_source"] == "keyword"

    def test_target_with_index_enhances_risk(self, tmp_path: Path):
        """有 target 且有索引 → impact 增强，输出受影响文件"""
        project = self._build_python_project(tmp_path)
        skill = Skill.create("risk.check")
        context = ProjectContext(
            project_path=project,
            task_description="修改 User 模型",  # 关键词不含高风险词
        )
        result = skill.run(context, {"target": "models.py"})
        assert result.success
        # impact 应解析到依赖方，risk_source 应包含 impact
        assert result.data["risk_source"] in ("impact", "both")
        assert "affected_files" in result.data
        # service.py 和 api.py 都 import 了 models
        affected = result.data["affected_files"]
        assert any("service.py" in f for f in affected)
        assert any("api.py" in f for f in affected)

    def test_final_risk_is_max_of_keyword_and_impact(self, tmp_path: Path):
        """final_risk = max(keyword_risk, impact_risk)

        任务描述含 R3 关键词（数据模型），即使 impact 只算出较低风险，
        最终也应取 R3。
        """
        project = self._build_python_project(tmp_path)
        skill = Skill.create("risk.check")
        context = ProjectContext(
            project_path=project,
            task_description="修改数据模型 schema",  # R3 关键词
        )
        result = skill.run(context, {"target": "models.py"})
        assert result.success
        # R3 关键词命中，最终风险不应低于 R3
        assert result.data["risk_level"] == "R3"
        assert result.data["risk_source"] == "both"

    def test_unresolved_target_falls_back(self, tmp_path: Path):
        """target 在索引中找不到 → 退回关键词匹配"""
        project = self._build_python_project(tmp_path)
        skill = Skill.create("risk.check")
        context = ProjectContext(
            project_path=project,
            task_description="改个文案",
        )
        result = skill.run(context, {"target": "does_not_exist_xyz"})
        assert result.success
        assert result.data["risk_source"] == "keyword"

    def test_skill_remains_r0_readonly(self, tmp_path: Path):
        """接入 impact 后 risk.check 仍是 R0 只读，不产生 changed_files"""
        project = self._build_python_project(tmp_path)
        skill = Skill.create("risk.check")
        assert skill.risk_level == RiskLevel.R0
        context = ProjectContext(
            project_path=project,
            task_description="修改 User",
        )
        result = skill.run(context, {"target": "models.py"})
        assert result.changed_files == []
