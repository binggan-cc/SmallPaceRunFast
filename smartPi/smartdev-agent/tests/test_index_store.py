"""
IndexStore 测试

验证 SQLite 存储层的完整功能：
1. 表创建（幂等）
2. 文件记录 upsert（插入 + 增量更新）
3. Artifact 记录 upsert
4. Relation 记录添加
5. 搜索功能（FTS5 + LIKE fallback）
6. 统计功能
"""

import json
import time
from pathlib import Path

import pytest

from smartdev.context.index_store import (
    ArtifactRecord,
    FileRecord,
    IndexStore,
    RelationRecord,
    RunRecord,
    classify_file_kind,
    compute_file_hash,
    detect_language,
)


class TestFileHash:
    """文件哈希计算"""

    def test_compute_hash(self, tmp_path: Path):
        """计算文件内容哈希"""
        f = tmp_path / "test.py"
        f.write_text("print('hello')\n")
        h = compute_file_hash(f)
        assert len(h) == 64  # SHA256 hex digest

    def test_same_content_same_hash(self, tmp_path: Path):
        """相同内容产生相同哈希"""
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        content = "x = 1\n"
        f1.write_text(content)
        f2.write_text(content)
        assert compute_file_hash(f1) == compute_file_hash(f2)

    def test_different_content_different_hash(self, tmp_path: Path):
        """不同内容产生不同哈希"""
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        f1.write_text("x = 1\n")
        f2.write_text("x = 2\n")
        assert compute_file_hash(f1) != compute_file_hash(f2)


class TestLanguageDetection:
    """语言检测"""

    def test_python(self):
        assert detect_language(Path("main.py")) == "python"

    def test_javascript(self):
        assert detect_language(Path("app.js")) == "javascript"

    def test_typescript(self):
        assert detect_language(Path("index.ts")) == "typescript"

    def test_css(self):
        assert detect_language(Path("style.css")) == "css"

    def test_markdown(self):
        assert detect_language(Path("README.md")) == "markdown"

    def test_unknown(self):
        assert detect_language(Path("file.xyz")) == "unknown"


class TestFileClassification:
    """文件类型分类"""

    def test_source(self):
        assert classify_file_kind(Path("src/main.py")) == "source"

    def test_config(self):
        assert classify_file_kind(Path("pyproject.toml")) == "config"

    def test_document(self):
        assert classify_file_kind(Path("README.md")) == "document"

    def test_test(self):
        assert classify_file_kind(Path("tests/test_main.py")) == "test"

    def test_asset(self):
        assert classify_file_kind(Path("assets/logo.png")) == "asset"


class TestIndexStore:
    """IndexStore 核心功能"""

    def test_create_tables(self, tmp_path: Path):
        """创建表（幂等）"""
        store = IndexStore(tmp_path / "test.sqlite")
        store.create_tables()
        store.create_tables()  # 第二次不报错
        store.close()

    def test_upsert_file_insert(self, tmp_path: Path):
        """插入新文件记录"""
        store = IndexStore(tmp_path / "test.sqlite")
        store.create_tables()

        record = FileRecord(
            path="main.py",
            content_hash="abc123",
            language="python",
            kind="source",
            size=100,
            modified_at=int(time.time()),
            indexed_at=int(time.time()),
        )
        assert store.upsert_file(record) is True
        assert store.count_files() == 1

        stored = store.get_file("main.py")
        assert stored is not None
        assert stored.path == "main.py"
        assert stored.language == "python"
        store.close()

    def test_upsert_file_skip_same_hash(self, tmp_path: Path):
        """相同 hash 跳过更新"""
        store = IndexStore(tmp_path / "test.sqlite")
        store.create_tables()

        now = int(time.time())
        record = FileRecord(
            path="main.py", content_hash="abc123",
            language="python", kind="source",
            size=100, modified_at=now, indexed_at=now,
        )
        store.upsert_file(record)
        assert store.upsert_file(record) is False  # 跳过
        assert store.count_files() == 1
        store.close()

    def test_upsert_file_update_different_hash(self, tmp_path: Path):
        """不同 hash 更新记录"""
        store = IndexStore(tmp_path / "test.sqlite")
        store.create_tables()

        now = int(time.time())
        record1 = FileRecord(
            path="main.py", content_hash="abc123",
            language="python", kind="source",
            size=100, modified_at=now, indexed_at=now,
        )
        record2 = FileRecord(
            path="main.py", content_hash="def456",
            language="python", kind="source",
            size=200, modified_at=now, indexed_at=now,
        )
        store.upsert_file(record1)
        assert store.upsert_file(record2) is True  # 更新
        assert store.count_files() == 1

        stored = store.get_file("main.py")
        assert stored.content_hash == "def456"
        assert stored.size == 200
        store.close()

    def test_list_files(self, tmp_path: Path):
        """列出文件"""
        store = IndexStore(tmp_path / "test.sqlite")
        store.create_tables()

        now = int(time.time())
        for name, lang, kind in [
            ("a.py", "python", "source"),
            ("b.js", "javascript", "source"),
            ("c.md", "markdown", "document"),
        ]:
            store.upsert_file(FileRecord(
                path=name, content_hash="h", language=lang,
                kind=kind, size=10, modified_at=now, indexed_at=now,
            ))

        # 全部
        assert len(store.list_files()) == 3

        # 按语言
        py_files = store.list_files(language="python")
        assert len(py_files) == 1
        assert py_files[0].path == "a.py"

        # 按类型
        docs = store.list_files(kind="document")
        assert len(docs) == 1
        assert docs[0].path == "c.md"
        store.close()


class TestArtifactOperations:
    """Artifact 操作"""

    def test_upsert_artifact(self, tmp_path: Path):
        """插入工件"""
        store = IndexStore(tmp_path / "test.sqlite")
        store.create_tables()

        record = ArtifactRecord(
            id="api:get_items",
            type="api_endpoint",
            name="get_items",
            file_path="server/main.py",
            start_line=10,
            end_line=20,
            metadata_json=json.dumps({"method": "GET"}),
        )
        assert store.upsert_artifact(record) is True
        assert store.count_artifacts() == 1

        stored = store.get_artifact("api:get_items")
        assert stored is not None
        assert stored.type == "api_endpoint"
        assert stored.name == "get_items"
        store.close()

    def test_list_artifacts_by_type(self, tmp_path: Path):
        """按类型列出工件"""
        store = IndexStore(tmp_path / "test.sqlite")
        store.create_tables()

        for aid, atype, name in [
            ("a1", "api_endpoint", "get_items"),
            ("a2", "api_endpoint", "create_item"),
            ("a3", "design_token", "primary_color"),
        ]:
            store.upsert_artifact(ArtifactRecord(
                id=aid, type=atype, name=name, file_path="f.py",
            ))

        endpoints = store.list_artifacts(artifact_type="api_endpoint")
        assert len(endpoints) == 2

        tokens = store.list_artifacts(artifact_type="design_token")
        assert len(tokens) == 1
        store.close()


class TestRelationOperations:
    """Relation 操作"""

    def test_add_relation(self, tmp_path: Path):
        """添加关系"""
        store = IndexStore(tmp_path / "test.sqlite")
        store.create_tables()

        # 先插入两个 artifact
        store.upsert_artifact(ArtifactRecord(
            id="a1", type="api_endpoint", name="get", file_path="f.py",
        ))
        store.upsert_artifact(ArtifactRecord(
            id="a2", type="model", name="Item", file_path="models.py",
        ))

        rel_id = store.add_relation(RelationRecord(
            source_id="a1", target_id="a2", type="references",
        ))
        assert rel_id > 0
        assert store.count_relations() == 1
        store.close()

    def test_get_relations(self, tmp_path: Path):
        """查询关系"""
        store = IndexStore(tmp_path / "test.sqlite")
        store.create_tables()

        store.upsert_artifact(ArtifactRecord(
            id="a1", type="api_endpoint", name="get", file_path="f.py",
        ))
        store.upsert_artifact(ArtifactRecord(
            id="a2", type="model", name="Item", file_path="models.py",
        ))
        store.upsert_artifact(ArtifactRecord(
            id="a3", type="model", name="User", file_path="models.py",
        ))

        store.add_relation(RelationRecord(source_id="a1", target_id="a2", type="refs"))
        store.add_relation(RelationRecord(source_id="a1", target_id="a3", type="refs"))
        store.add_relation(RelationRecord(source_id="a2", target_id="a3", type="extends"))

        # outgoing from a1
        outgoing = store.get_relations("a1", direction="outgoing")
        assert len(outgoing) == 2

        # incoming to a3
        incoming = store.get_relations("a3", direction="incoming")
        assert len(incoming) == 2

        # both for a2
        both = store.get_relations("a2", direction="both")
        assert len(both) == 2  # 1 outgoing + 1 incoming
        store.close()


class TestSearchOperations:
    """搜索操作"""

    def test_search_artifacts_fts(self, tmp_path: Path):
        """FTS 搜索工件"""
        store = IndexStore(tmp_path / "test.sqlite")
        store.create_tables()

        store.upsert_artifact(ArtifactRecord(
            id="t1", type="design_token", name="primary_color",
            file_path="tokens.css",
        ))
        store.upsert_artifact(ArtifactRecord(
            id="t2", type="design_token", name="font_size",
            file_path="tokens.css",
        ))
        store.upsert_artifact(ArtifactRecord(
            id="e1", type="api_endpoint", name="get_items",
            file_path="server.py",
        ))

        results = store.search_artifacts("token")
        assert len(results) >= 1  # 至少匹配 design_token 类型

        results = store.search_artifacts("color")
        assert len(results) >= 1
        store.close()

    def test_search_files(self, tmp_path: Path):
        """搜索文件"""
        store = IndexStore(tmp_path / "test.sqlite")
        store.create_tables()

        now = int(time.time())
        for path in ["src/main.py", "src/utils.py", "tests/test_main.py"]:
            store.upsert_file(FileRecord(
                path=path, content_hash="h", language="python",
                kind="source", size=100, modified_at=now, indexed_at=now,
            ))

        results = store.search_files("main")
        assert len(results) == 2  # src/main.py + tests/test_main.py
        store.close()


class TestStats:
    """统计功能"""

    def test_stats(self, tmp_path: Path):
        """统计信息"""
        store = IndexStore(tmp_path / "test.sqlite")
        store.create_tables()

        now = int(time.time())
        store.upsert_file(FileRecord(
            path="a.py", content_hash="h", language="python",
            kind="source", size=100, modified_at=now, indexed_at=now,
        ))
        store.upsert_artifact(ArtifactRecord(
            id="a1", type="api_endpoint", name="get", file_path="a.py",
        ))

        stats = store.stats()
        assert stats["files"] == 1
        assert stats["artifacts"] == 1
        assert stats["relations"] == 0
        assert len(stats["languages"]) == 1
        assert stats["languages"][0]["language"] == "python"
        store.close()
