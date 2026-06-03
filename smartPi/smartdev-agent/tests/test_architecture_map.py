"""
Skill: architecture.map 测试

验证：
1. 自动注册
2. can_run 前置条件
3. 模块分析正确
4. 依赖关系检测
5. 循环依赖检测
6. 核心模块识别
"""

from pathlib import Path

from smartdev.models import ProjectContext, RiskLevel, TaskType
from smartdev.skills.base import Skill


class TestArchitectureMapSkill:
    """architecture.map Skill 测试"""

    def test_registered_in_registry(self):
        """architecture.map 已自动注册"""
        assert "architecture.map" in Skill.get_registry()

    def test_skill_metadata(self):
        """Skill 元数据正确"""
        skill = Skill.create("architecture.map")
        assert skill.risk_level == RiskLevel.R0
        assert skill.task_type == TaskType.ANALYZE

    def test_can_run_with_python_project(self, tmp_path: Path):
        """有 Python 文件时 can_run 返回 True"""
        (tmp_path / "main.py").write_text("pass\n")
        skill = Skill.create("architecture.map")
        context = ProjectContext(project_path=tmp_path)
        assert skill.can_run(context) is True

    def test_can_run_without_python_files(self, tmp_path: Path):
        """无 Python 文件时 can_run 返回 False"""
        (tmp_path / "readme.txt").write_text("hello\n")
        skill = Skill.create("architecture.map")
        context = ProjectContext(project_path=tmp_path)
        assert skill.can_run(context) is False

    def test_run_analyzes_modules(self, tmp_path: Path):
        """运行分析模块结构"""
        (tmp_path / "module_a.py").write_text("import module_b\n")
        (tmp_path / "module_b.py").write_text("pass\n")

        skill = Skill.create("architecture.map")
        context = ProjectContext(project_path=tmp_path)
        result = skill.run(context)

        assert result.success is True
        assert "modules" in result.data
        assert len(result.data["modules"]) == 2

    def test_dependency_graph(self, tmp_path: Path):
        """依赖图正确反映 import 关系"""
        (tmp_path / "a.py").write_text("import b\n")
        (tmp_path / "b.py").write_text("pass\n")

        skill = Skill.create("architecture.map")
        context = ProjectContext(project_path=tmp_path)
        result = skill.run(context)

        graph = result.data["dependency_graph"]
        # a.py import 了 b
        a_module = [m for m in result.data["modules"] if m["name"] == "a"][0]
        assert "b" in a_module["imports"]

    def test_circular_dependency_detection(self, tmp_path: Path):
        """检测循环依赖"""
        (tmp_path / "x.py").write_text("import y\n")
        (tmp_path / "y.py").write_text("import x\n")

        skill = Skill.create("architecture.map")
        context = ProjectContext(project_path=tmp_path)
        result = skill.run(context)

        assert result.data["summary"]["has_circular"] is True
        assert len(result.data["circular_deps"]) >= 1

    def test_no_circular_dependency(self, tmp_path: Path):
        """无循环依赖时正确报告"""
        (tmp_path / "a.py").write_text("import b\n")
        (tmp_path / "b.py").write_text("import c\n")
        (tmp_path / "c.py").write_text("pass\n")

        skill = Skill.create("architecture.map")
        context = ProjectContext(project_path=tmp_path)
        result = skill.run(context)

        assert result.data["summary"]["has_circular"] is False
        assert result.data["circular_deps"] == []

    def test_core_modules_identified(self, tmp_path: Path):
        """被引用最多的模块被识别为核心模块"""
        (tmp_path / "core.py").write_text("pass\n")
        (tmp_path / "a.py").write_text("import core\n")
        (tmp_path / "b.py").write_text("import core\n")
        (tmp_path / "c.py").write_text("import core\n")

        skill = Skill.create("architecture.map")
        context = ProjectContext(project_path=tmp_path)
        result = skill.run(context)

        assert "core" in result.data["core_modules"]

    def test_line_count(self, tmp_path: Path):
        """代码行数统计正确"""
        (tmp_path / "main.py").write_text("x = 1\ny = 2\nz = 3\n")

        skill = Skill.create("architecture.map")
        context = ProjectContext(project_path=tmp_path)
        result = skill.run(context)

        module = result.data["modules"][0]
        assert module["line_count"] == 3

    def test_risks_for_large_modules(self, tmp_path: Path):
        """大文件产生风险提示"""
        # 创建一个 600 行的文件
        lines = ["x = 1\n"] * 600
        (tmp_path / "big.py").write_text("".join(lines))

        skill = Skill.create("architecture.map")
        context = ProjectContext(project_path=tmp_path)
        result = skill.run(context)

        # 风险提示使用模块名（big），不是文件名（big.py）
        assert any("big" in r for r in result.risks)
