"""
Import Relations 测试

验证 Python import 关系写入 relations 表：
1. from import → imports relation
2. import statement → imports relation
3. alias 信息进入 metadata
4. external import 创建 placeholder
5. relative import 标注 resolved=false
6. 重复 index 不产生重复 relations
7. 回归：已有 artifact 数量不减少
"""

import json
from pathlib import Path

import pytest

from smartdev.context.artifact_extractor import ArtifactExtractor
from smartdev.context.project_index import ProjectIndex


class TestImportRelationBuilding:
    """import relation 构建逻辑"""

    def test_from_import_creates_relation(self, tmp_path: Path):
        """from import 产生 imports relation"""
        (tmp_path / "models.py").write_text('''
class RiskLevel:
    pass
''')
        (tmp_path / "app.py").write_text('''
from models import RiskLevel
''')

        extractor = ArtifactExtractor()
        result = extractor.extract(tmp_path)

        # 应该有 relation
        assert len(result.relations) >= 1

        # 查找 imports relation
        imports_rels = [r for r in result.relations if r.type == "imports"]
        assert len(imports_rels) >= 1

        rel = imports_rels[0]
        metadata = json.loads(rel.metadata_json)
        assert metadata["module"] == "models"
        assert "RiskLevel" in metadata["names"]
        assert metadata["import_kind"] == "from_import"

    def test_direct_import_creates_relation(self, tmp_path: Path):
        """import statement 产生 imports relation"""
        (tmp_path / "utils.py").write_text('''
import json
''')

        extractor = ArtifactExtractor()
        result = extractor.extract(tmp_path)

        imports_rels = [r for r in result.relations if r.type == "imports"]
        assert len(imports_rels) >= 1

        rel = imports_rels[0]
        metadata = json.loads(rel.metadata_json)
        assert metadata["module"] == "json"
        assert metadata["import_kind"] == "import"

    def test_external_import_creates_placeholder(self, tmp_path: Path):
        """external import 创建 placeholder artifact"""
        (tmp_path / "app.py").write_text('''
import os
from pathlib import Path
''')

        extractor = ArtifactExtractor()
        result = extractor.extract(tmp_path)

        # 查找 external placeholder
        external_arts = [a for a in result.artifacts if a.type == "external_module"]
        external_names = {a.name for a in external_arts}
        assert "os" in external_names
        assert "pathlib" in external_names

    def test_external_import_relation(self, tmp_path: Path):
        """external import 的 relation target 指向 external placeholder"""
        (tmp_path / "app.py").write_text('''
import json
''')

        extractor = ArtifactExtractor()
        result = extractor.extract(tmp_path)

        imports_rels = [r for r in result.relations if r.type == "imports"]
        assert len(imports_rels) >= 1

        rel = imports_rels[0]
        assert rel.target_id.startswith("external:python:")
        metadata = json.loads(rel.metadata_json)
        assert metadata["external"] is True

    def test_relative_import_creates_unresolved(self, tmp_path: Path):
        """相对 import 创建 unresolved placeholder"""
        (tmp_path / "package").mkdir()
        (tmp_path / "package" / "__init__.py").write_text("")
        (tmp_path / "package" / "module_a.py").write_text('''
from .module_b import helper
''')
        (tmp_path / "package" / "module_b.py").write_text('''
def helper():
    pass
''')

        extractor = ArtifactExtractor()
        result = extractor.extract(tmp_path)  # 全项目提取

        imports_rels = [r for r in result.relations if r.type == "imports"]
        assert len(imports_rels) >= 1

        # 查找相对 import 的 relation
        relative_rels = [
            r for r in imports_rels
            if json.loads(r.metadata_json).get("relative_level", 0) > 0
        ]
        assert len(relative_rels) >= 1

        rel = relative_rels[0]
        metadata = json.loads(rel.metadata_json)
        assert metadata["resolved"] is False

    def test_import_with_alias(self, tmp_path: Path):
        """import alias 信息进入 metadata"""
        (tmp_path / "app.py").write_text('''
import numpy as np
from collections import OrderedDict as OD
''')

        extractor = ArtifactExtractor()
        result = extractor.extract(tmp_path)

        imports_rels = [r for r in result.relations if r.type == "imports"]
        # 至少有两个 relation
        assert len(imports_rels) >= 2

        # 检查 alias 信息在 raw 中
        for rel in imports_rels:
            metadata = json.loads(rel.metadata_json)
            assert "module" in metadata
            assert "names" in metadata

    def test_confidence_in_metadata(self, tmp_path: Path):
        """relation metadata 包含 confidence"""
        (tmp_path / "app.py").write_text('''
import json
''')

        extractor = ArtifactExtractor()
        result = extractor.extract(tmp_path)

        imports_rels = [r for r in result.relations if r.type == "imports"]
        for rel in imports_rels:
            metadata = json.loads(rel.metadata_json)
            assert "confidence" in metadata
            assert metadata["confidence"] == 1.0  # Python ast


class TestDeduplication:
    """去重测试"""

    def test_duplicate_index_no_extra_relations(self, tmp_path: Path):
        """重复 index 不产生重复 relations"""
        (tmp_path / "app.py").write_text('''
from models import RiskLevel
import json
''')

        extractor = ArtifactExtractor()

        # 第一次提取
        result1 = extractor.extract(tmp_path)
        rel_count_1 = len(result1.relations)

        # 第二次提取
        result2 = extractor.extract(tmp_path)
        rel_count_2 = len(result2.relations)

        # 关系数量应该相同
        assert rel_count_1 == rel_count_2


class TestRegression:
    """回归测试"""

    def test_artifacts_not_reduced(self, tmp_path: Path):
        """新增 import relations 后 artifact 数量不减少"""
        # 构造一个有 artifact 的项目
        (tmp_path / "tokens.css").write_text(":root { --primary: #3b82f6; }\n")
        (tmp_path / "README.md").write_text("# Project\n")
        (tmp_path / "app.py").write_text('''
import json
from pathlib import Path
def main():
    pass
''')

        extractor = ArtifactExtractor()
        result = extractor.extract(tmp_path)

        # 应该有各种类型的 artifact
        types = {a.type for a in result.artifacts}
        assert "code:function" in types  # 结构提取
        assert "code:import" in types    # import artifact

        # 不应该因为 relation 构建而丢失任何 artifact
        assert len(result.artifacts) > 0

    def test_full_project_index(self, tmp_path: Path):
        """完整项目索引：scan + extract + write"""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "models.py").write_text('''
class RiskLevel:
    pass

class SkillResult:
    pass
''')
        (tmp_path / "src" / "app.py").write_text('''
from models import RiskLevel, SkillResult
import json
import os

def main():
    pass
''')

        # 建立索引
        index = ProjectIndex(tmp_path)
        index.scan()

        # 提取 artifact + relations
        extractor = ArtifactExtractor()
        extraction = extractor.extract(tmp_path)
        for artifact in extraction.artifacts:
            index.store.upsert_artifact(artifact)
        for relation in extraction.relations:
            index.store.add_relation(relation)

        # 验证
        assert index.file_count() >= 2
        assert index.artifact_count() > 0
        assert index.store.count_relations() > 0

        # 验证 relation 内容
        stats = index.store.stats()
        assert stats["relations"] > 0

        index.close()


# ── Step 2A.1 关键测试 ───────────────────────────────────

class TestModuleArtifact:
    """P0-1: module artifact 必须存在"""

    def test_module_artifact_created(self, tmp_path: Path):
        """每个 Python 文件都有 code:module artifact"""
        (tmp_path / "app.py").write_text("pass\n")

        extractor = ArtifactExtractor()
        result = extractor.extract(tmp_path)

        module_arts = [a for a in result.artifacts if a.type == "code:module"]
        assert len(module_arts) == 1
        assert module_arts[0].name == "app"
        assert module_arts[0].file_path == "app.py"

    def test_module_artifact_nested_path(self, tmp_path: Path):
        """嵌套路径的 module artifact"""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "utils.py").write_text("pass\n")

        extractor = ArtifactExtractor()
        result = extractor.extract(tmp_path)

        module_arts = [a for a in result.artifacts if a.type == "code:module"]
        assert any(a.name == "src.utils" for a in module_arts)


class TestRelationIdStability:
    """P0-1/P0-2: source/target ID 对齐"""

    def test_source_points_to_module_artifact(self, tmp_path: Path):
        """relation source_id 指向真实的 module artifact"""
        (tmp_path / "app.py").write_text("import json\n")

        extractor = ArtifactExtractor()
        result = extractor.extract(tmp_path)

        module_ids = {a.id for a in result.artifacts if a.type == "code:module"}
        for rel in result.relations:
            assert rel.source_id in module_ids, f"source_id {rel.source_id} not in module artifacts"

    def test_target_is_artifact_or_placeholder(self, tmp_path: Path):
        """relation target_id 要么是已知 artifact，要么是 placeholder"""
        (tmp_path / "app.py").write_text("import os\nfrom pathlib import Path\n")

        extractor = ArtifactExtractor()
        result = extractor.extract(tmp_path)

        all_ids = {a.id for a in result.artifacts}
        for rel in result.relations:
            assert rel.target_id in all_ids, f"target_id {rel.target_id} not in artifacts"


class TestReindexDeduplication:
    """P0-3: 重复 index 不增加 relations"""

    def test_reindex_same_relations_count(self, tmp_path: Path):
        """重复索引后 relations 数量不变"""
        (tmp_path / "app.py").write_text("import json\nimport os\n")

        index = ProjectIndex(tmp_path)
        index.index()

        count_1 = index.store.count_relations()

        index.index()
        count_2 = index.store.count_relations()

        assert count_1 == count_2, f"relations grew from {count_1} to {count_2}"
        index.close()


class TestRelativeImportNoDuplicate:
    """P1-1: 相对 import 不重复"""

    def test_relative_import_single_relation(self, tmp_path: Path):
        """from .module_b import helper 只产生 1 条 relation"""
        (tmp_path / "pkg").mkdir()
        (tmp_path / "pkg" / "__init__.py").write_text("")
        (tmp_path / "pkg" / "a.py").write_text("from .b import helper\n")
        (tmp_path / "pkg" / "b.py").write_text("def helper(): pass\n")

        extractor = ArtifactExtractor()
        result = extractor.extract(tmp_path)

        # 查找涉及 a.py 的 imports relation
        source_ids = [a.id for a in result.artifacts
                      if a.type == "code:module" and a.file_path == "pkg/a.py"]
        assert len(source_ids) == 1

        rels = [r for r in result.relations if r.source_id == source_ids[0]]
        # 应该只有 1 条 relation（相对 import）
        assert len(rels) == 1


class TestAliasPreserved:
    """P1-2: alias 信息保留在 metadata"""

    def test_from_import_alias(self, tmp_path: Path):
        """from x import Y as Z 保留 alias"""
        (tmp_path / "app.py").write_text("from collections import OrderedDict as OD\n")

        extractor = ArtifactExtractor()
        result = extractor.extract(tmp_path)

        rels = [r for r in result.relations if r.type == "imports"]
        assert len(rels) == 1

        meta = json.loads(rels[0].metadata_json)
        assert meta["aliases"] == {"OrderedDict": "OD"}

    def test_direct_import_alias(self, tmp_path: Path):
        """import numpy as np 保留 alias"""
        (tmp_path / "app.py").write_text("import numpy as np\n")

        extractor = ArtifactExtractor()
        result = extractor.extract(tmp_path)

        rels = [r for r in result.relations if r.type == "imports"]
        assert len(rels) == 1

        meta = json.loads(rels[0].metadata_json)
        assert meta["aliases"] == {"numpy": "np"}

    def test_no_alias_empty_dict(self, tmp_path: Path):
        """无 alias 时 aliases 为空字典"""
        (tmp_path / "app.py").write_text("import json\n")

        extractor = ArtifactExtractor()
        result = extractor.extract(tmp_path)

        rels = [r for r in result.relations if r.type == "imports"]
        meta = json.loads(rels[0].metadata_json)
        assert meta["aliases"] == {}
