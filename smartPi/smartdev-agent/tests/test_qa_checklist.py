"""
Skill: qa.checklist 测试

验证：
1. 自动注册
2. 通用检查项包含在所有清单中
3. 功能任务包含 functional 检查项
4. UI 任务包含 ui 检查项
5. API 任务包含 api 检查项
6. 文档任务包含 documentation 检查项
7. 空任务描述拒绝执行
"""

from pathlib import Path

from smartdev.models import ProjectContext, RiskLevel, TaskType
from smartdev.skills.base import Skill


class TestQAChecklistSkill:
    """qa.checklist Skill 测试"""

    def test_registered_in_registry(self):
        """qa.checklist 已自动注册"""
        assert "qa.checklist" in Skill.get_registry()

    def test_skill_metadata(self):
        """Skill 元数据正确"""
        skill = Skill.create("qa.checklist")
        assert skill.risk_level == RiskLevel.R0
        assert skill.task_type == TaskType.PLAN

    def test_can_run_with_task(self, tmp_path: Path):
        """有任务描述时 can_run 返回 True"""
        skill = Skill.create("qa.checklist")
        context = ProjectContext(
            project_path=tmp_path,
            task_description="修复 Bug",
        )
        assert skill.can_run(context) is True

    def test_can_run_without_task(self, tmp_path: Path):
        """无任务描述时 can_run 返回 False"""
        skill = Skill.create("qa.checklist")
        context = ProjectContext(project_path=tmp_path)
        assert skill.can_run(context) is False

    def test_general_always_included(self, tmp_path: Path):
        """通用检查项始终包含"""
        skill = Skill.create("qa.checklist")
        context = ProjectContext(
            project_path=tmp_path,
            task_description="随便什么任务",
        )
        result = skill.run(context)

        categories = result.data["categories"]
        assert "general" in categories

    def test_functional_task(self, tmp_path: Path):
        """功能任务包含 functional 检查项"""
        skill = Skill.create("qa.checklist")
        context = ProjectContext(
            project_path=tmp_path,
            task_description="新增收藏功能",
        )
        result = skill.run(context)

        assert "functional" in result.data["categories"]
        checklist_items = [c["item"] for c in result.data["checklist"]]
        assert "功能入口可见" in checklist_items

    def test_ui_task(self, tmp_path: Path):
        """UI 任务包含 ui 检查项"""
        skill = Skill.create("qa.checklist")
        context = ProjectContext(
            project_path=tmp_path,
            task_description="修改按钮样式",
        )
        result = skill.run(context)

        assert "ui" in result.data["categories"]
        checklist_items = [c["item"] for c in result.data["checklist"]]
        assert "Hover 状态正常" in checklist_items

    def test_api_task(self, tmp_path: Path):
        """API 任务包含 api 检查项"""
        skill = Skill.create("qa.checklist")
        context = ProjectContext(
            project_path=tmp_path,
            task_description="新增搜索接口",
        )
        result = skill.run(context)

        assert "api" in result.data["categories"]
        checklist_items = [c["item"] for c in result.data["checklist"]]
        assert "正常请求返回正确" in checklist_items

    def test_documentation_task(self, tmp_path: Path):
        """文档任务包含 documentation 检查项"""
        skill = Skill.create("qa.checklist")
        context = ProjectContext(
            project_path=tmp_path,
            task_description="更新 README",
        )
        result = skill.run(context)

        assert "documentation" in result.data["categories"]
        checklist_items = [c["item"] for c in result.data["checklist"]]
        assert "README 已更新" in checklist_items

    def test_checklist_items_have_required_fields(self, tmp_path: Path):
        """每个检查项包含必要字段"""
        skill = Skill.create("qa.checklist")
        context = ProjectContext(
            project_path=tmp_path,
            task_description="修复登录 Bug",
        )
        result = skill.run(context)

        for item in result.data["checklist"]:
            assert "category" in item
            assert "item" in item
            assert "passed" in item
            assert item["passed"] is False

    def test_no_duplicate_items(self, tmp_path: Path):
        """检查项无重复"""
        skill = Skill.create("qa.checklist")
        context = ProjectContext(
            project_path=tmp_path,
            task_description="新增功能并更新文档",
        )
        result = skill.run(context)

        items = [c["item"] for c in result.data["checklist"]]
        assert len(items) == len(set(items))
