"""
Skill: token.audit 测试

验证：
1. 自动注册
2. can_run 前置条件
3. 检测 CSS 变量定义
4. 检测硬编码 hex 颜色
5. 检测硬编码 rgb 颜色
6. 多 Token 来源警告
7. 覆盖率计算
"""

from pathlib import Path

from smartdev.models import ProjectContext, RiskLevel, TaskType
from smartdev.skills.base import Skill


class TestTokenAuditSkill:
    """token.audit Skill 测试"""

    def test_registered_in_registry(self):
        """token.audit 已自动注册"""
        assert "token.audit" in Skill.get_registry()

    def test_skill_metadata(self):
        """Skill 元数据正确"""
        skill = Skill.create("token.audit")
        assert skill.risk_level == RiskLevel.R0
        assert skill.task_type == TaskType.UI_GOVERNANCE

    def test_can_run(self, tmp_path: Path):
        """项目路径存在时 can_run 返回 True"""
        skill = Skill.create("token.audit")
        context = ProjectContext(project_path=tmp_path)
        assert skill.can_run(context) is True

    def test_detects_css_variables(self, tmp_path: Path):
        """检测 CSS 变量定义"""
        (tmp_path / "tokens.css").write_text(
            ":root {\n"
            "  --color-primary: #15803d;\n"
            "  --color-secondary: #22c55e;\n"
            "  --spacing-md: 16px;\n"
            "}\n"
        )

        skill = Skill.create("token.audit")
        context = ProjectContext(project_path=tmp_path)
        result = skill.run(context)

        assert result.success is True
        assert len(result.data["token_sources"]) >= 1
        source = result.data["token_sources"][0]
        assert source["variable_count"] == 3

    def test_detects_hardcoded_hex(self, tmp_path: Path):
        """检测硬编码 hex 颜色"""
        (tmp_path / "style.css").write_text(
            ".button {\n"
            "  background-color: #ff0000;\n"
            "  color: #333;\n"
            "}\n"
        )

        skill = Skill.create("token.audit")
        context = ProjectContext(project_path=tmp_path)
        result = skill.run(context)

        assert result.data["summary"]["color_count"] >= 2
        hex_colors = [c for c in result.data["hardcoded_colors"] if c["format"] == "hex"]
        assert len(hex_colors) >= 2

    def test_detects_hardcoded_rgb(self, tmp_path: Path):
        """检测硬编码 rgb 颜色"""
        (tmp_path / "style.css").write_text(
            ".card {\n"
            "  border: 1px solid rgb(200, 200, 200);\n"
            "}\n"
        )

        skill = Skill.create("token.audit")
        context = ProjectContext(project_path=tmp_path)
        result = skill.run(context)

        rgb_colors = [c for c in result.data["hardcoded_colors"] if c["format"] == "rgb"]
        assert len(rgb_colors) >= 1

    def test_multiple_token_sources_warning(self, tmp_path: Path):
        """多个 Token 来源时产生警告"""
        (tmp_path / "tokens.css").write_text(":root { --x: 1; }\n")
        (tmp_path / "variables.css").write_text(":root { --y: 2; }\n")

        skill = Skill.create("token.audit")
        context = ProjectContext(project_path=tmp_path)
        result = skill.run(context)

        assert result.data["summary"]["has_multiple_sources"] is True
        assert len(result.risks) >= 1

    def test_no_tokens_no_colors(self, tmp_path: Path):
        """无 CSS 文件时覆盖率 0"""
        skill = Skill.create("token.audit")
        context = ProjectContext(project_path=tmp_path)
        result = skill.run(context)

        assert result.data["coverage_rate"] == 0.0

    def test_coverage_rate(self, tmp_path: Path):
        """覆盖率计算正确"""
        # 3 个变量 + 1 个硬编码颜色
        (tmp_path / "tokens.css").write_text(
            ":root {\n"
            "  --a: 1;\n"
            "  --b: 2;\n"
            "  --c: 3;\n"
            "}\n"
        )
        (tmp_path / "style.css").write_text(
            ".x { color: #ff0000; }\n"
        )

        skill = Skill.create("token.audit")
        context = ProjectContext(project_path=tmp_path)
        result = skill.run(context)

        # 3 个变量 / (3 变量 + 1 颜色) = 0.75
        assert result.data["coverage_rate"] == 0.75

    def test_recommendations_generated(self, tmp_path: Path):
        """生成替换建议"""
        (tmp_path / "style.css").write_text(
            ".a { color: #000; }\n"
            ".b { color: #fff; }\n"
        )

        skill = Skill.create("token.audit")
        context = ProjectContext(project_path=tmp_path)
        result = skill.run(context)

        assert len(result.data["recommendations"]) >= 1
