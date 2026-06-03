"""
Skill: repo.scan 测试

验证 repo.scan Skill 的完整执行流程：
1. can_run 前置条件检查
2. run 执行扫描
3. SkillResult 数据结构完整性
4. 自动注册可用
"""

from pathlib import Path

import pytest

from smartdev.models import ProjectContext, RiskLevel, SkillResult, TaskType
from smartdev.skills.base import Skill


class TestRepoScanSkill:
    """repo.scan Skill 测试"""

    def test_registered_in_registry(self):
        """repo.scan 已自动注册"""
        assert "repo.scan" in Skill.get_registry()

    def test_skill_metadata(self):
        """Skill 元数据正确"""
        skill = Skill.create("repo.scan")
        assert skill.risk_level == RiskLevel.R0
        assert skill.task_type == TaskType.DIAGNOSE

        desc = skill.describe()
        assert desc["risk_level"] == "R0"
        assert desc["task_type"] == "diagnose"

    def test_can_run_with_valid_project(self, tmp_path: Path):
        """项目路径存在时 can_run 返回 True"""
        (tmp_path / "README.md").write_text("# Test\n")
        skill = Skill.create("repo.scan")
        context = ProjectContext(project_path=tmp_path)

        assert skill.can_run(context) is True

    def test_can_run_with_nonexistent_path(self):
        """项目路径不存在时 can_run 返回 False"""
        skill = Skill.create("repo.scan")
        context = ProjectContext(project_path=Path("/nonexistent/path/abc123"))

        assert skill.can_run(context) is False

    def test_run_on_python_project(self, tmp_path: Path):
        """在 Python 项目上执行扫描"""
        # 构造一个 Python 项目
        (tmp_path / "requirements.txt").write_text("requests>=2.28\n")
        (tmp_path / "main.py").write_text("print('hello')\n")
        (tmp_path / "README.md").write_text("# My Project\n")

        skill = Skill.create("repo.scan")
        context = ProjectContext(project_path=tmp_path)
        result = skill.run(context)

        # 验证返回类型
        assert isinstance(result, SkillResult)
        assert result.success is True

        # 验证 data 结构
        assert "tech_stack" in result.data
        assert "entrypoints" in result.data
        assert "docs_status" in result.data
        assert "directory_tree" in result.data

        # 验证技术栈检测
        tech_names = [t["name"] for t in result.data["tech_stack"]["languages"]]
        assert "Python" in tech_names

        # 验证入口文件检测
        assert len(result.data["entrypoints"]) >= 1

        # 验证文档状态
        assert result.data["docs_status"]["coverage_rate"] > 0
        assert "README.md" in result.data["docs_status"]["existing"]

    def test_run_on_chrome_extension(self, tmp_path: Path):
        """在 Chrome Extension 项目上执行扫描"""
        import json
        manifest = {
            "manifest_version": 3,
            "name": "Test Extension",
            "background": {"service_worker": "background.js"},
            "action": {"default_popup": "popup.html"},
        }
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))
        (tmp_path / "background.js").write_text("chrome.runtime.onInstalled.addListener(() => {});\n")
        (tmp_path / "popup.html").write_text("<html></html>\n")

        skill = Skill.create("repo.scan")
        context = ProjectContext(project_path=tmp_path)
        result = skill.run(context)

        assert result.success is True

        # 验证检测到 Chrome Extension
        platform_names = [t["name"] for t in result.data["tech_stack"]["platforms"]]
        assert "Chrome Extension MV3" in platform_names

        # 验证检测到入口文件
        entry_names = [e["name"] for e in result.data["entrypoints"]]
        assert "service_worker" in entry_names
        assert "popup" in entry_names

    def test_run_generates_directory_tree(self, tmp_path: Path):
        """扫描结果包含目录树"""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("pass\n")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_main.py").write_text("pass\n")
        (tmp_path / "README.md").write_text("# Test\n")

        skill = Skill.create("repo.scan")
        context = ProjectContext(project_path=tmp_path)
        result = skill.run(context)

        tree = result.data["directory_tree"]
        assert "src/" in tree
        assert "main.py" in tree
        assert "tests/" in tree

    def test_risks_include_missing_docs(self, tmp_path: Path):
        """缺失文档时 risks 字段包含提示"""
        # 空项目，没有任何文档
        skill = Skill.create("repo.scan")
        context = ProjectContext(project_path=tmp_path)
        result = skill.run(context)

        # 应该有风险提示（缺失文档）
        assert len(result.risks) > 0

    def test_next_steps_generated(self, tmp_path: Path):
        """扫描后生成下一步建议"""
        skill = Skill.create("repo.scan")
        context = ProjectContext(project_path=tmp_path)
        result = skill.run(context)

        # 空项目应该有建议
        assert len(result.next_steps) > 0
