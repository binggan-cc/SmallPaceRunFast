"""
Skill: code.search 测试

验证 code.search Skill 的完整执行流程：
1. 自动注册
2. can_run 前置条件
3. run 搜索功能
4. 空索引处理
"""

from pathlib import Path

import pytest

from smartdev.context.project_index import ProjectIndex
from smartdev.models import ProjectContext, RiskLevel, SkillResult, TaskType
from smartdev.skills.base import Skill


class TestCodeSearchSkill:
    """code.search Skill 测试"""

    def test_registered_in_registry(self):
        """code.search 已自动注册"""
        assert "code.search" in Skill.get_registry()

    def test_skill_metadata(self):
        """Skill 元数据正确"""
        skill = Skill.create("code.search")
        assert skill.risk_level == RiskLevel.R0
        assert skill.task_type == TaskType.ANALYZE

    def test_can_run_with_index(self, tmp_path: Path):
        """有索引时 can_run 返回 True"""
        (tmp_path / "main.py").write_text("pass\n")
        index = ProjectIndex(tmp_path)
        index.scan()
        index.close()

        skill = Skill.create("code.search")
        context = ProjectContext(project_path=tmp_path)
        assert skill.can_run(context) is True

    def test_can_run_without_index(self, tmp_path: Path):
        """无索引时 can_run 返回 False"""
        (tmp_path / "main.py").write_text("pass\n")
        skill = Skill.create("code.search")
        context = ProjectContext(project_path=tmp_path)
        assert skill.can_run(context) is False

    def test_run_search(self, tmp_path: Path):
        """搜索功能"""
        (tmp_path / "tokens.css").write_text(":root { --primary: #3b82f6; }\n")
        (tmp_path / "main.py").write_text("pass\n")
        (tmp_path / "README.md").write_text("# Project\n")

        # 建立索引
        index = ProjectIndex(tmp_path)
        index.scan()
        # 提取 artifact
        from smartdev.context.artifact_extractor import ArtifactExtractor
        extractor = ArtifactExtractor()
        extraction = extractor.extract(tmp_path)
        for a in extraction.artifacts:
            index.store.upsert_artifact(a)
        index.close()

        # 搜索
        skill = Skill.create("code.search")
        context = ProjectContext(project_path=tmp_path)
        result = skill.run(context, {"query": "token"})

        assert isinstance(result, SkillResult)
        assert result.success is True
        assert "token" in result.data["query"]
        # 应该找到 tokens.css
        assert any("token" in f["path"] for f in result.data["files"])

    def test_run_search_empty_query(self, tmp_path: Path):
        """空搜索词返回错误"""
        (tmp_path / "main.py").write_text("pass\n")
        index = ProjectIndex(tmp_path)
        index.scan()
        index.close()

        skill = Skill.create("code.search")
        context = ProjectContext(project_path=tmp_path)
        result = skill.run(context, {"query": ""})

        assert result.success is False

    def test_run_search_no_results(self, tmp_path: Path):
        """无匹配结果"""
        (tmp_path / "main.py").write_text("pass\n")
        index = ProjectIndex(tmp_path)
        index.scan()
        index.close()

        skill = Skill.create("code.search")
        context = ProjectContext(project_path=tmp_path)
        result = skill.run(context, {"query": "zzzznonexistent"})

        assert result.success is True
        assert result.data["total_files"] == 0
