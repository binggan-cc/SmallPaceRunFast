"""
Skill: doc.generate 测试

验证：
1. 自动注册
2. 生成 README 草案
3. 生成 CONTRIBUTING 草案
4. 生成 CHANGELOG 条目
5. 检测已存在文件
6. 不支持的类型返回错误
"""

from pathlib import Path

from smartdev.models import ProjectContext, RiskLevel, TaskType
from smartdev.skills.base import Skill


class TestDocGenerateSkill:
    """doc.generate Skill 测试"""

    def test_registered_in_registry(self):
        """doc.generate 已自动注册"""
        assert "doc.generate" in Skill.get_registry()

    def test_skill_metadata(self):
        """Skill 元数据正确"""
        skill = Skill.create("doc.generate")
        assert skill.risk_level == RiskLevel.R1
        assert skill.task_type == TaskType.DOCUMENT

    def test_can_run(self, tmp_path: Path):
        """项目路径存在时 can_run 返回 True"""
        skill = Skill.create("doc.generate")
        context = ProjectContext(project_path=tmp_path)
        assert skill.can_run(context) is True

    def test_generate_readme(self, tmp_path: Path):
        """生成 README 草案"""
        (tmp_path / "requirements.txt").write_text("requests\n")

        skill = Skill.create("doc.generate")
        context = ProjectContext(project_path=tmp_path)
        result = skill.run(context, inputs={"doc_type": "readme"})

        assert result.success is True
        assert result.data["doc_type"] == "readme"
        assert result.data["save_path"] == "README.md"
        assert "# " in result.data["content"]  # 有标题
        assert "技术栈" in result.data["content"]

    def test_generate_contributing(self, tmp_path: Path):
        """生成 CONTRIBUTING 草案"""
        skill = Skill.create("doc.generate")
        context = ProjectContext(project_path=tmp_path)
        result = skill.run(context, inputs={"doc_type": "contributing"})

        assert result.success is True
        assert result.data["doc_type"] == "contributing"
        assert result.data["save_path"] == "CONTRIBUTING.md"
        assert "贡献指南" in result.data["content"]

    def test_generate_changelog(self, tmp_path: Path):
        """生成 CHANGELOG 条目"""
        skill = Skill.create("doc.generate")
        context = ProjectContext(project_path=tmp_path)
        result = skill.run(context, inputs={"doc_type": "changelog"})

        assert result.success is True
        assert result.data["doc_type"] == "changelog"
        assert result.data["save_path"] == "CHANGELOG.md"

    def test_detects_existing_file(self, tmp_path: Path):
        """检测已存在的文件"""
        (tmp_path / "README.md").write_text("# Existing\n")

        skill = Skill.create("doc.generate")
        context = ProjectContext(project_path=tmp_path)
        result = skill.run(context, inputs={"doc_type": "readme"})

        assert result.data["file_exists"] is True
        assert any("已存在" in r for r in result.risks)

    def test_unsupported_type(self, tmp_path: Path):
        """不支持的类型返回错误"""
        skill = Skill.create("doc.generate")
        context = ProjectContext(project_path=tmp_path)
        result = skill.run(context, inputs={"doc_type": "unknown"})

        assert result.success is False
        assert "unsupported_types" in result.data or "不支持" in result.summary

    def test_default_type_is_readme(self, tmp_path: Path):
        """默认文档类型是 readme"""
        skill = Skill.create("doc.generate")
        context = ProjectContext(project_path=tmp_path)
        result = skill.run(context)

        assert result.data["doc_type"] == "readme"

    def test_readme_includes_tech_stack(self, tmp_path: Path):
        """README 包含检测到的技术栈"""
        (tmp_path / "requirements.txt").write_text("fastapi\n")

        skill = Skill.create("doc.generate")
        context = ProjectContext(project_path=tmp_path)
        result = skill.run(context, inputs={"doc_type": "readme"})

        # 技术栈应该出现在 README 中
        content = result.data["content"]
        assert "Python" in content or "FastAPI" in content

    def test_next_steps_include_confirmation(self, tmp_path: Path):
        """下一步建议包含确认步骤"""
        skill = Skill.create("doc.generate")
        context = ProjectContext(project_path=tmp_path)
        result = skill.run(context)

        assert any("确认" in s for s in result.next_steps)
