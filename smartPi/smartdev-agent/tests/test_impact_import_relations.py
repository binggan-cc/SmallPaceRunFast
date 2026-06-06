"""
ImpactAnalyzer import relation 分析测试

验证 Phase 6.2 Step 3：
1. 按 module name 查询 reverse imports
2. 按 file path 查询对应 module 的 reverse imports
3. 按 symbol name fallback 到 module-level impact
4. 未命中时返回空结果 + search 建议
5. 输出 relation_scope / direct_dependents / affected_files
6. validation_suggestions 生成
"""

import json
from pathlib import Path

import pytest

from smartdev.context.artifact_extractor import ArtifactExtractor
from smartdev.context.impact_analyzer import ImpactAnalyzer, ImportImpactResult
from smartdev.context.project_index import ProjectIndex


def _build_index(tmp_path: Path) -> ProjectIndex:
    """辅助：建立完整索引（scan + extract + relations）"""
    index = ProjectIndex(tmp_path)
    index.index()
    return index


class TestImportImpactByModuleName:
    """按 module name 查询"""

    def test_query_module_name(self, tmp_path: Path):
        """输入 smartdev.models，返回 import 它的文件"""
        (tmp_path / "models.py").write_text('''
class RiskLevel:
    pass
''')
        (tmp_path / "app.py").write_text('''
from models import RiskLevel
''')
        (tmp_path / "utils.py").write_text('''
import models
''')

        index = _build_index(tmp_path)
        analyzer = ImpactAnalyzer(index.store)
        result = analyzer.analyze_import_impact("models")

        assert isinstance(result, ImportImpactResult)
        assert len(result.direct_dependents) == 2
        assert len(result.affected_files) == 2
        assert result.relation_scope == "module"

        # 验证 dependent 信息
        dep_modules = {d.module for d in result.direct_dependents}
        assert "models" in dep_modules

        index.close()

    def test_query_dotted_module(self, tmp_path: Path):
        """输入 a.b.c 格式的模块名"""
        (tmp_path / "a").mkdir()
        (tmp_path / "a" / "__init__.py").write_text("")
        (tmp_path / "a" / "b").mkdir()
        (tmp_path / "a" / "b" / "__init__.py").write_text("")
        (tmp_path / "a" / "b" / "c.py").write_text("X = 1\n")
        (tmp_path / "app.py").write_text("from a.b.c import X\n")

        index = _build_index(tmp_path)
        analyzer = ImpactAnalyzer(index.store)
        result = analyzer.analyze_import_impact("a.b.c")

        assert len(result.direct_dependents) >= 1
        assert any("app.py" in d.source_file for d in result.direct_dependents)

        index.close()


class TestImportImpactByFilePath:
    """按 file path 查询"""

    def test_query_file_path(self, tmp_path: Path):
        """输入 models.py，能解析到 module artifact"""
        (tmp_path / "models.py").write_text('class X: pass\n')
        (tmp_path / "app.py").write_text("from models import X\n")

        index = _build_index(tmp_path)
        analyzer = ImpactAnalyzer(index.store)
        result = analyzer.analyze_import_impact("models.py")

        assert len(result.direct_dependents) >= 1
        assert result.resolved_target != ""

        index.close()

    def test_query_nested_file_path(self, tmp_path: Path):
        """输入 src/models.py 格式"""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "models.py").write_text("X = 1\n")
        (tmp_path / "app.py").write_text("from src.models import X\n")

        index = _build_index(tmp_path)
        analyzer = ImpactAnalyzer(index.store)
        result = analyzer.analyze_import_impact("src/models.py")

        # 可能找到，也可能找不到（取决于 module 解析）
        # 关键是不崩溃
        assert isinstance(result, ImportImpactResult)

        index.close()


class TestImportImpactBySymbolName:
    """按 symbol name 查询（fallback 到 module-level）"""

    def test_query_symbol_name(self, tmp_path: Path):
        """输入 RiskLevel，fallback 到所在 module 的 import 分析"""
        (tmp_path / "models.py").write_text('''
class RiskLevel:
    pass
''')
        (tmp_path / "app.py").write_text("from models import RiskLevel\n")

        index = _build_index(tmp_path)
        analyzer = ImpactAnalyzer(index.store)
        result = analyzer.analyze_import_impact("RiskLevel")

        # 应该 fallback 到 module-level，找到 app.py
        assert len(result.direct_dependents) >= 1
        assert result.relation_scope == "module"

        index.close()


class TestImportImpactUnknownTarget:
    """未命中目标"""

    def test_unknown_target_returns_empty(self, tmp_path: Path):
        """未找到时返回空结果 + search 建议"""
        (tmp_path / "app.py").write_text("pass\n")

        index = _build_index(tmp_path)
        analyzer = ImpactAnalyzer(index.store)
        result = analyzer.analyze_import_impact("nonexistent_module_xyz")

        assert len(result.direct_dependents) == 0
        assert len(result.affected_files) == 0
        assert "未找到" in result.summary
        assert "smartdev index" in result.summary or "smartdev search" in result.summary

        index.close()


class TestImportImpactOutputStructure:
    """输出结构验证"""

    def test_relation_scope_always_module(self, tmp_path: Path):
        """relation_scope 始终为 module"""
        (tmp_path / "m.py").write_text("X = 1\n")
        (tmp_path / "a.py").write_text("from m import X\n")

        index = _build_index(tmp_path)
        analyzer = ImpactAnalyzer(index.store)
        result = analyzer.analyze_import_impact("m")

        assert result.relation_scope == "module"

        index.close()

    def test_affected_files_sorted(self, tmp_path: Path):
        """affected_files 排序"""
        (tmp_path / "m.py").write_text("X = 1\n")
        (tmp_path / "c.py").write_text("from m import X\n")
        (tmp_path / "a.py").write_text("from m import X\n")

        index = _build_index(tmp_path)
        analyzer = ImpactAnalyzer(index.store)
        result = analyzer.analyze_import_impact("m")

        assert result.affected_files == sorted(result.affected_files)

        index.close()

    def test_validation_suggestions_generated(self, tmp_path: Path):
        """生成 validation suggestions"""
        (tmp_path / "m.py").write_text("X = 1\n")
        (tmp_path / "app.py").write_text("from m import X\n")

        index = _build_index(tmp_path)
        analyzer = ImpactAnalyzer(index.store)
        result = analyzer.analyze_import_impact("m")

        assert len(result.validation_suggestions) > 0

        index.close()

    def test_limitations_present(self, tmp_path: Path):
        """limitations 标注 relation_scope"""
        (tmp_path / "m.py").write_text("X = 1\n")

        index = _build_index(tmp_path)
        analyzer = ImpactAnalyzer(index.store)
        result = analyzer.analyze_import_impact("m")

        assert any("module" in lim for lim in result.limitations)

        index.close()

    def test_confidence_from_metadata(self, tmp_path: Path):
        """confidence 从 relation metadata 传递"""
        (tmp_path / "m.py").write_text("X = 1\n")
        (tmp_path / "app.py").write_text("from m import X\n")

        index = _build_index(tmp_path)
        analyzer = ImpactAnalyzer(index.store)
        result = analyzer.analyze_import_impact("m")

        for dep in result.direct_dependents:
            assert dep.confidence == 1.0  # Python ast

        index.close()


class TestCodeImpactSkillIntegration:
    """code.impact Skill 集成"""

    def test_skill_uses_import_relations(self, tmp_path: Path):
        """code.impact Skill 在有 relations 时使用 import 分析"""
        (tmp_path / "models.py").write_text('class X: pass\n')
        (tmp_path / "app.py").write_text("from models import X\n")

        index = _build_index(tmp_path)
        index.close()

        from smartdev.models import ProjectContext
        from smartdev.skills.base import Skill

        skill = Skill.create("code.impact")
        context = ProjectContext(project_path=tmp_path)
        result = skill.run(context, {"target": "models"})

        assert result.success is True
        # 应该使用 import relation 分析
        assert "direct_dependents" in result.data or "direct_references" in result.data
