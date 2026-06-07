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


# ── Phase 8 Step 2: index relations 接入测试 ──────────────────


class TestArchitectureMapIndexIntegration:
    """architecture.map 接入 index relations 的优雅降级测试

    核心验证：
    - 无索引 → 退回 Python AST（source=ast，零回归）
    - 有索引 → 用 relations 构建多语言依赖图（source=index）
    - 循环依赖检测在两种数据源下都工作
    """

    def _build_indexed_python_project(self, tmp_path: Path) -> Path:
        """建一个有 import 关系的 Python 项目并索引。"""
        project = tmp_path / "pyproj"
        project.mkdir()
        (project / "models.py").write_text("class User:\n    pass\n")
        (project / "service.py").write_text(
            "from models import User\n\ndef f():\n    return User()\n"
        )
        (project / "api.py").write_text(
            "from models import User\nfrom service import f\n\ndef g():\n    return f()\n"
        )
        from smartdev.context.project_index import ProjectIndex

        index = ProjectIndex(project)
        index.index()
        index.close()
        return project

    def _build_indexed_go_project(self, tmp_path: Path) -> Path:
        """建一个 Go 项目并索引（验证多语言能力）。"""
        project = tmp_path / "goproj"
        (project / "pkg").mkdir(parents=True)
        (project / "main.go").write_text(
            'package main\n\nimport "fmt"\n\nfunc main() {\n\tfmt.Println("hi")\n}\n'
        )
        from smartdev.context.project_index import ProjectIndex

        index = ProjectIndex(project)
        index.index()
        index.close()
        return project

    def test_no_index_falls_back_to_ast(self, tmp_path: Path):
        """无索引 → 退回 Python AST，source=ast"""
        project = tmp_path / "noindex"
        project.mkdir()
        (project / "main.py").write_text("import os\n\ndef f():\n    pass\n")
        skill = Skill.create("architecture.map")
        result = skill.run(ProjectContext(project_path=project))
        assert result.success
        assert result.data["source"] == "ast"

    def test_with_index_uses_index_source(self, tmp_path: Path):
        """有索引 → source=index"""
        project = self._build_indexed_python_project(tmp_path)
        skill = Skill.create("architecture.map")
        result = skill.run(ProjectContext(project_path=project))
        assert result.success
        assert result.data["source"] == "index"

    def test_index_builds_dependency_graph(self, tmp_path: Path):
        """索引模式构建出依赖图：service/api 依赖 models"""
        project = self._build_indexed_python_project(tmp_path)
        skill = Skill.create("architecture.map")
        result = skill.run(ProjectContext(project_path=project))
        graph = result.data["dependency_graph"]
        # service.py imports models.py
        assert any(
            "service.py" in src and any("models.py" in t for t in targets)
            for src, targets in graph.items()
        )

    def test_index_identifies_core_module(self, tmp_path: Path):
        """models 被多个文件 import，应识别为核心模块"""
        project = self._build_indexed_python_project(tmp_path)
        skill = Skill.create("architecture.map")
        result = skill.run(ProjectContext(project_path=project))
        core = result.data["core_modules"]
        assert any("models.py" in c for c in core)

    def test_index_supports_go_project(self, tmp_path: Path):
        """Go 项目（无 .py）在有索引时也能分析——多语言能力"""
        project = self._build_indexed_go_project(tmp_path)
        skill = Skill.create("architecture.map")
        # can_run 应允许（有索引）
        assert skill.can_run(ProjectContext(project_path=project)) is True
        result = skill.run(ProjectContext(project_path=project))
        assert result.success
        assert result.data["source"] == "index"
        # fmt 应在 external deps 中
        assert "fmt" in result.data["external_deps"]

    def test_index_detects_circular_dependency(self, tmp_path: Path):
        """索引模式能检测循环依赖（a → b → a）"""
        project = tmp_path / "circ"
        project.mkdir()
        (project / "a.py").write_text("from b import bb\n\ndef aa():\n    return bb()\n")
        (project / "b.py").write_text("from a import aa\n\ndef bb():\n    return aa()\n")
        from smartdev.context.project_index import ProjectIndex

        index = ProjectIndex(project)
        index.index()
        index.close()

        skill = Skill.create("architecture.map")
        result = skill.run(ProjectContext(project_path=project))
        assert result.data["source"] == "index"
        assert result.data["summary"]["has_circular"] is True
        assert len(result.data["circular_deps"]) >= 1

    def test_can_run_go_without_index_is_false(self, tmp_path: Path):
        """Go 项目无索引且无 .py → can_run False（退回 AST 需 Python）"""
        project = tmp_path / "goonly"
        project.mkdir()
        (project / "main.go").write_text("package main\n")
        skill = Skill.create("architecture.map")
        assert skill.can_run(ProjectContext(project_path=project)) is False
