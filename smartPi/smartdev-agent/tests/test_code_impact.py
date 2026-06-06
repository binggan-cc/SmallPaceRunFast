"""
Skill: code.impact 测试

验证 code.impact Skill 的完整执行流程：
1. 自动注册
2. can_run 前置条件
3. run 影响分析
4. 风险等级计算
"""

from pathlib import Path

import pytest

from smartdev.context.project_index import ProjectIndex
from smartdev.models import ProjectContext, RiskLevel, SkillResult, TaskType
from smartdev.skills.base import Skill


class TestCodeImpactSkill:
    """code.impact Skill 测试"""

    def test_registered_in_registry(self):
        """code.impact 已自动注册"""
        assert "code.impact" in Skill.get_registry()

    def test_skill_metadata(self):
        """Skill 元数据正确"""
        skill = Skill.create("code.impact")
        assert skill.risk_level == RiskLevel.R0
        assert skill.task_type == TaskType.ANALYZE

    def test_can_run_with_index(self, tmp_path: Path):
        """有索引时 can_run 返回 True"""
        (tmp_path / "main.py").write_text("pass\n")
        index = ProjectIndex(tmp_path)
        index.scan()
        index.close()

        skill = Skill.create("code.impact")
        context = ProjectContext(project_path=tmp_path)
        assert skill.can_run(context) is True

    def test_can_run_without_index(self, tmp_path: Path):
        """无索引时 can_run 返回 False"""
        skill = Skill.create("code.impact")
        context = ProjectContext(project_path=tmp_path)
        assert skill.can_run(context) is False

    def test_run_impact_analysis(self, tmp_path: Path):
        """影响分析"""
        # 构造有 artifact 的项目
        (tmp_path / "tokens.css").write_text(":root { --primary: #3b82f6; }\n")
        (tmp_path / "sidepanel.css").write_text("@import 'tokens.css';\n")
        (tmp_path / "README.md").write_text("# Project\n")

        # 建立索引 + 提取 artifact
        index = ProjectIndex(tmp_path)
        index.scan()
        from smartdev.context.artifact_extractor import ArtifactExtractor
        extractor = ArtifactExtractor()
        extraction = extractor.extract(tmp_path)
        for a in extraction.artifacts:
            index.store.upsert_artifact(a)
        index.close()

        # 分析影响
        skill = Skill.create("code.impact")
        context = ProjectContext(project_path=tmp_path)
        result = skill.run(context, {"target": "tokens.css"})

        assert isinstance(result, SkillResult)
        assert result.success is True
        assert "risk_level" in result.data
        assert result.data["risk_level"] in ("R0", "R1", "R2", "R3")
        assert "verification_items" in result.data

    def test_run_impact_empty_target(self, tmp_path: Path):
        """空目标返回错误"""
        (tmp_path / "main.py").write_text("pass\n")
        index = ProjectIndex(tmp_path)
        index.scan()
        index.close()

        skill = Skill.create("code.impact")
        context = ProjectContext(project_path=tmp_path)
        result = skill.run(context, {"target": ""})

        assert result.success is False

    def test_run_impact_generates_verification(self, tmp_path: Path):
        """影响分析生成验证项"""
        # 有 CSS token 的项目
        (tmp_path / "tokens.css").write_text(":root { --primary: #3b82f6; }\n")

        index = ProjectIndex(tmp_path)
        index.scan()
        from smartdev.context.artifact_extractor import ArtifactExtractor
        extractor = ArtifactExtractor()
        extraction = extractor.extract(tmp_path)
        for a in extraction.artifacts:
            index.store.upsert_artifact(a)
        index.close()

        skill = Skill.create("code.impact")
        context = ProjectContext(project_path=tmp_path)
        result = skill.run(context, {"target": "tokens.css"})

        # 有 design_token artifact 时应生成视觉验证项
        # （即使没有直接引用，也应该有基本验证项）
        assert isinstance(result.data["verification_items"], list)
