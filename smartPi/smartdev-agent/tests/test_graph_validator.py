"""
GraphValidator 测试

验证 Phase 6.2 Step 5：
1. Orphan source 检测
2. Orphan target 检测（允许 external/unresolved）
3. Duplicate relation 检测
4. Missing metadata 检测
5. Hotspot warning
6. Unresolved summary
7. 不修改 index.sqlite
8. Markdown 报告生成
"""

import json
from pathlib import Path

import pytest

from smartdev.context.graph_validator import GraphValidationResult, validate_graph
from smartdev.context.index_store import (
    ArtifactRecord,
    IndexStore,
    RelationRecord,
)
from smartdev.context.project_index import ProjectIndex


def _build_index(tmp_path: Path) -> ProjectIndex:
    """辅助：建立完整索引"""
    index = ProjectIndex(tmp_path)
    index.index()
    return index


class TestOrphanSource:
    """Orphan source 检测"""

    def test_no_orphan_sources(self, tmp_path: Path):
        """正常索引无 orphan source"""
        (tmp_path / "app.py").write_text("import json\n")

        index = _build_index(tmp_path)
        result = validate_graph(index.store)
        index.close()

        assert result.stats["orphan_sources"] == 0

    def test_orphan_source_detected(self, tmp_path: Path):
        """手动插入 orphan source 能被检测"""
        (tmp_path / "app.py").write_text("pass\n")

        index = _build_index(tmp_path)

        # 手动插入一个 orphan relation
        index.store.add_relation(RelationRecord(
            source_id="nonexistent:module",
            target_id="external:python:json",
            type="imports",
        ))

        result = validate_graph(index.store)
        index.close()

        assert result.stats["orphan_sources"] >= 1
        assert not result.is_healthy


class TestOrphanTarget:
    """Orphan target 检测"""

    def test_external_target_allowed(self, tmp_path: Path):
        """external:* target 不算 orphan"""
        (tmp_path / "app.py").write_text("import json\n")

        index = _build_index(tmp_path)
        result = validate_graph(index.store)
        index.close()

        # external targets 应该被允许
        assert result.stats["external"] >= 1
        # 不应该有 orphan target warning
        orphan_warnings = [w for w in result.warnings if w.category == "orphan_target"]
        assert len(orphan_warnings) == 0

    def test_unresolved_target_allowed(self, tmp_path: Path):
        """unresolved:* target 不算 orphan"""
        (tmp_path / "pkg").mkdir()
        (tmp_path / "pkg" / "__init__.py").write_text("")
        (tmp_path / "pkg" / "a.py").write_text("from .b import helper\n")
        (tmp_path / "pkg" / "b.py").write_text("def helper(): pass\n")

        index = _build_index(tmp_path)
        result = validate_graph(index.store)
        index.close()

        # unresolved targets 应该被允许
        assert result.stats["unresolved"] >= 1


class TestDuplicateRelation:
    """Duplicate relation 检测"""

    def test_no_duplicates(self, tmp_path: Path):
        """正常索引无重复"""
        (tmp_path / "app.py").write_text("import json\n")

        index = _build_index(tmp_path)
        result = validate_graph(index.store)
        index.close()

        assert result.stats["duplicates"] == 0

    def test_duplicate_detected(self, tmp_path: Path):
        """手动插入重复 relation 能被检测"""
        (tmp_path / "app.py").write_text("import json\n")

        index = _build_index(tmp_path)

        # 手动插入重复
        index.store.add_relation(RelationRecord(
            source_id="code:module:app.py",
            target_id="external:python:json",
            type="imports",
        ))

        result = validate_graph(index.store)
        index.close()

        assert result.stats["duplicates"] >= 1


class TestMissingMetadata:
    """Missing metadata 检测"""

    def test_no_missing_metadata(self, tmp_path: Path):
        """正常索引无缺失"""
        (tmp_path / "app.py").write_text("import json\n")

        index = _build_index(tmp_path)
        result = validate_graph(index.store)
        index.close()

        assert result.stats["missing_metadata"] == 0

    def test_missing_metadata_detected(self, tmp_path: Path):
        """手动插入缺 metadata 的 relation 能被检测"""
        (tmp_path / "app.py").write_text("pass\n")

        index = _build_index(tmp_path)

        # 插入缺 metadata 的 imports relation
        conn = index.store.connect()
        conn.execute("""
            INSERT INTO relations (source_id, target_id, type, confidence, metadata_json)
            VALUES (?, ?, ?, ?, ?)
        """, ("code:module:app.py", "external:python:json", "imports", 1.0, "{}"))
        conn.commit()

        result = validate_graph(index.store)
        index.close()

        assert result.stats["missing_metadata"] >= 1


class TestHotspot:
    """Hotspot warning"""

    def test_low_threshold_hotspot(self, tmp_path: Path):
        """低阈值 hotspot 能被检测"""
        (tmp_path / "core.py").write_text("X = 1\n")
        for i in range(5):
            (tmp_path / f"m{i}.py").write_text(f"from core import X\n")

        index = _build_index(tmp_path)
        # 用低阈值
        result = validate_graph(index.store, hotspot_threshold=3)
        index.close()

        hotspot_warnings = [w for w in result.warnings if w.category == "hotspot"]
        assert len(hotspot_warnings) >= 1

    def test_high_threshold_no_hotspot(self, tmp_path: Path):
        """高阈值时小项目无 hotspot"""
        (tmp_path / "core.py").write_text("X = 1\n")
        (tmp_path / "app.py").write_text("from core import X\n")

        index = _build_index(tmp_path)
        result = validate_graph(index.store, hotspot_threshold=100)
        index.close()

        hotspot_warnings = [w for w in result.warnings if w.category == "hotspot"]
        assert len(hotspot_warnings) == 0


class TestUnresolved:
    """Unresolved summary"""

    def test_unresolved_counted(self, tmp_path: Path):
        """unresolved import 被统计"""
        (tmp_path / "pkg").mkdir()
        (tmp_path / "pkg" / "__init__.py").write_text("")
        (tmp_path / "pkg" / "a.py").write_text("from .b import helper\n")
        (tmp_path / "pkg" / "b.py").write_text("def helper(): pass\n")

        index = _build_index(tmp_path)
        result = validate_graph(index.store)
        index.close()

        unresolved_info = [i for i in result.info if i.category == "unresolved"]
        assert len(unresolved_info) >= 1


class TestSafety:
    """安全性"""

    def test_does_not_modify_index(self, tmp_path: Path):
        """不修改 index.sqlite"""
        (tmp_path / "app.py").write_text("import json\n")

        index = _build_index(tmp_path)

        # 记录校验前状态
        count_before = index.store.count_relations()

        # 校验
        validate_graph(index.store)

        # 校验后状态不变
        count_after = index.store.count_relations()
        assert count_before == count_after

        index.close()


class TestMarkdownReport:
    """Markdown 报告"""

    def test_report_generation(self, tmp_path: Path):
        """能生成 Markdown 报告"""
        (tmp_path / "app.py").write_text("import json\n")

        index = _build_index(tmp_path)
        result = validate_graph(index.store)
        index.close()

        md = result.to_markdown()
        assert "# Graph Validation Report" in md
        assert "## Summary" in md
        assert "Artifacts:" in md
        assert "Relations:" in md

    def test_is_healthy_property(self, tmp_path: Path):
        """is_healthy 属性正确"""
        (tmp_path / "app.py").write_text("import json\n")

        index = _build_index(tmp_path)
        result = validate_graph(index.store)
        index.close()

        # 正常项目应该健康
        assert result.is_healthy is True


class TestOnRealProject:
    """对 smartdev-agent 自身校验"""

    def test_validate_self(self):
        """对自身项目校验"""
        project_path = Path(__file__).parent.parent
        index = ProjectIndex(project_path)
        index.index()

        result = validate_graph(index.store, hotspot_threshold=15)
        index.close()

        # 基本健康
        assert result.stats["artifacts"] > 100
        assert result.stats["relations"] > 100
        # 不应有 orphan source
        assert result.stats["orphan_sources"] == 0
