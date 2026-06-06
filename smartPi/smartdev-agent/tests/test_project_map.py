"""
ProjectMap 测试

验证 Phase 6.2 Step 4：
1. 从 index 生成项目地图
2. 导出 JSON 和 Markdown
3. 识别 hotspots
4. 统计 external dependencies
5. 识别 unresolved imports
6. 不修改被分析项目
"""

import json
from pathlib import Path

import pytest

from smartdev.context.project_index import ProjectIndex
from smartdev.context.project_map import ProjectMap, generate_project_map, save_project_map


def _build_index(tmp_path: Path) -> ProjectIndex:
    """辅助：建立完整索引"""
    index = ProjectIndex(tmp_path)
    index.index()
    return index


class TestProjectMapGeneration:
    """项目地图生成"""

    def test_generate_from_index(self, tmp_path: Path):
        """从索引生成项目地图"""
        (tmp_path / "models.py").write_text('class X: pass\n')
        (tmp_path / "app.py").write_text("from models import X\nimport json\n")

        index = _build_index(tmp_path)
        project_map = generate_project_map(index.store, "test-project")
        index.close()

        assert isinstance(project_map, ProjectMap)
        assert project_map.project_name == "test-project"
        assert project_map.summary["files"] >= 2
        assert project_map.summary["relations"] >= 1

    def test_hotspots_identified(self, tmp_path: Path):
        """识别高依赖模块"""
        (tmp_path / "core.py").write_text("X = 1\n")
        (tmp_path / "a.py").write_text("from core import X\n")
        (tmp_path / "b.py").write_text("from core import X\n")
        (tmp_path / "c.py").write_text("from core import X\n")

        index = _build_index(tmp_path)
        project_map = generate_project_map(index.store, "test")
        index.close()

        # core.py 应该是 hotspot
        hotspot_targets = [h.target for h in project_map.hotspots]
        assert "core" in hotspot_targets

        core_hotspot = [h for h in project_map.hotspots if h.target == "core"][0]
        assert core_hotspot.dependent_count >= 3

    def test_external_dependencies(self, tmp_path: Path):
        """统计外部依赖"""
        (tmp_path / "app.py").write_text("import json\nimport os\nfrom pathlib import Path\n")

        index = _build_index(tmp_path)
        project_map = generate_project_map(index.store, "test")
        index.close()

        ext_names = [e.name for e in project_map.external_dependencies]
        assert "json" in ext_names
        assert "os" in ext_names

    def test_unresolved_imports(self, tmp_path: Path):
        """识别 unresolved imports"""
        (tmp_path / "pkg").mkdir()
        (tmp_path / "pkg" / "__init__.py").write_text("")
        (tmp_path / "pkg" / "a.py").write_text("from .b import helper\n")
        (tmp_path / "pkg" / "b.py").write_text("def helper(): pass\n")

        index = _build_index(tmp_path)
        project_map = generate_project_map(index.store, "test")
        index.close()

        # 应该有 unresolved import
        assert len(project_map.unresolved_imports) >= 1


class TestProjectMapExport:
    """项目地图导出"""

    def test_to_json(self, tmp_path: Path):
        """导出 JSON"""
        (tmp_path / "app.py").write_text("pass\n")

        index = _build_index(tmp_path)
        project_map = generate_project_map(index.store, "test")
        index.close()

        json_str = project_map.to_json()
        data = json.loads(json_str)

        assert "project" in data
        assert "modules" in data
        assert "hotspots" in data
        assert "external_dependencies" in data
        assert data["project"]["name"] == "test"

    def test_to_markdown(self, tmp_path: Path):
        """导出 Markdown"""
        (tmp_path / "models.py").write_text("X = 1\n")
        (tmp_path / "a.py").write_text("from models import X\n")
        (tmp_path / "b.py").write_text("from models import X\n")
        (tmp_path / "app.py").write_text("import json\n")

        index = _build_index(tmp_path)
        project_map = generate_project_map(index.store, "test")
        index.close()

        md = project_map.to_markdown()
        assert "# test — Project Map" in md
        assert "## External Dependencies" in md
        # hotspot 需要 ≥2 依赖方
        if project_map.hotspots:
            assert "## Most Imported Internal Modules" in md

    def test_save_to_files(self, tmp_path: Path):
        """保存到文件"""
        (tmp_path / "app.py").write_text("pass\n")

        index = _build_index(tmp_path)
        project_map = generate_project_map(index.store, "test")
        index.close()

        output_dir = tmp_path / ".smartdev" / "map"
        paths = save_project_map(project_map, output_dir)

        assert paths["json"].exists()
        assert paths["markdown"].exists()

        # 验证 JSON 内容
        data = json.loads(paths["json"].read_text())
        assert data["project"]["name"] == "test"


class TestProjectMapSafety:
    """安全性验证"""

    def test_does_not_modify_project(self, tmp_path: Path):
        """不修改被分析项目源码"""
        (tmp_path / "app.py").write_text("pass\n")
        original_content = (tmp_path / "app.py").read_text()

        index = _build_index(tmp_path)
        project_map = generate_project_map(index.store, "test")
        index.close()

        # 源码不变
        assert (tmp_path / "app.py").read_text() == original_content


class TestProjectMapOnRealProject:
    """对 smartdev-agent 自身生成项目地图"""

    def test_generate_for_self(self):
        """对自身项目生成地图"""
        project_path = Path(__file__).parent.parent
        index = ProjectIndex(project_path)
        index.index()

        project_map = generate_project_map(index.store, "smartdev-agent")
        index.close()

        assert project_map.summary["files"] > 50
        assert project_map.summary["relations"] > 50
        assert len(project_map.hotspots) > 0
        assert len(project_map.external_dependencies) > 0

        # 验证 hotspots 包含核心模块
        hotspot_targets = [h.target for h in project_map.hotspots]
        # smartdev.models 应该是高依赖模块
        assert any("models" in t for t in hotspot_targets)
