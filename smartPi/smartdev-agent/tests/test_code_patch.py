"""
Skill: code.patch 测试

验证：
1. 自动注册
2. 生成补丁
3. unified diff 输出
4. 不修改文件
5. 风险等级正确
"""

from pathlib import Path

from smartdev.models import ProjectContext, RiskLevel, TaskType
from smartdev.skills.base import Skill


class TestCodePatchSkill:
    """code.patch Skill 测试"""

    def test_registered_in_registry(self):
        """code.patch 已自动注册"""
        assert "code.patch" in Skill.get_registry()

    def test_skill_metadata(self):
        """Skill 元数据正确"""
        skill = Skill.create("code.patch")
        assert skill.risk_level == RiskLevel.R1
        assert skill.task_type == TaskType.FEATURE

    def test_can_run_with_task(self, tmp_path: Path):
        """有任务描述时 can_run 返回 True"""
        (tmp_path / "main.py").write_text("pass\n")
        skill = Skill.create("code.patch")
        context = ProjectContext(
            project_path=tmp_path,
            task_description="添加错误处理",
        )
        assert skill.can_run(context) is True

    def test_can_run_without_task(self, tmp_path: Path):
        """无任务描述时 can_run 返回 False"""
        skill = Skill.create("code.patch")
        context = ProjectContext(project_path=tmp_path)
        assert skill.can_run(context) is False

    def test_generates_patch(self, tmp_path: Path):
        """运行生成补丁"""
        (tmp_path / "main.py").write_text("pass\n")

        skill = Skill.create("code.patch")
        context = ProjectContext(
            project_path=tmp_path,
            task_description="添加日志",
        )
        result = skill.run(context)

        assert result.success is True
        assert "diff" in result.data
        assert result.data["file_count"] >= 1

    def test_diff_format(self, tmp_path: Path):
        """diff 是 unified 格式"""
        skill = Skill.create("code.patch")
        context = ProjectContext(
            project_path=tmp_path,
            task_description="测试任务",
        )
        result = skill.run(context)

        diff = result.data["diff"]
        assert "--- " in diff
        assert "+++ " in diff

    def test_does_not_modify_files(self, tmp_path: Path):
        """不直接修改文件"""
        (tmp_path / "main.py").write_text("original\n")
        original = (tmp_path / "main.py").read_text()

        skill = Skill.create("code.patch")
        context = ProjectContext(
            project_path=tmp_path,
            task_description="修改文件",
        )
        skill.run(context)

        # 文件内容不变
        assert (tmp_path / "main.py").read_text() == original

    def test_risk_level_is_r1(self, tmp_path: Path):
        """风险等级是 R1"""
        skill = Skill.create("code.patch")
        context = ProjectContext(
            project_path=tmp_path,
            task_description="任何任务",
        )
        result = skill.run(context)
        assert result.data["risk_level"] == "R1"

    def test_next_steps_include_review(self, tmp_path: Path):
        """下一步建议包含审查"""
        skill = Skill.create("code.patch")
        context = ProjectContext(
            project_path=tmp_path,
            task_description="测试",
        )
        result = skill.run(context)
        assert any("审查" in s or "确认" in s for s in result.next_steps)
