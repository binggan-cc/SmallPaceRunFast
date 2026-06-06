"""
ProjectIndex 测试

验证项目索引门面类的端到端功能：
1. 扫描项目文件
2. 建立索引
3. 搜索
4. 统计
"""

from pathlib import Path

import pytest

from smartdev.context.project_index import ProjectIndex


class TestProjectIndex:
    """ProjectIndex 端到端测试"""

    def test_scan_python_project(self, tmp_path: Path):
        """扫描 Python 项目"""
        # 构造项目
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("print('hello')\n")
        (tmp_path / "src" / "utils.py").write_text("def helper(): pass\n")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_main.py").write_text("def test_hello(): pass\n")
        (tmp_path / "README.md").write_text("# Test\n")
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        index = ProjectIndex(tmp_path)
        result = index.scan()

        assert result["total"] >= 4  # 至少 4 个文件
        assert result["updated"] >= 4
        assert index.file_count() >= 4
        index.close()

    def test_scan_with_ignore(self, tmp_path: Path):
        """扫描时忽略 node_modules 等目录"""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("pass\n")
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "pkg").mkdir()
        (tmp_path / "node_modules" / "pkg" / "index.js").write_text("module.exports = {}\n")
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "main.cpython-310.pyc").write_bytes(b"\x00")

        index = ProjectIndex(tmp_path)
        result = index.scan()

        # 不应包含 node_modules 和 __pycache__ 中的文件
        files = index.store.list_files()
        paths = [f.path for f in files]
        assert not any("node_modules" in p for p in paths)
        assert not any("__pycache__" in p for p in paths)
        assert "src/main.py" in paths
        index.close()

    def test_incremental_scan(self, tmp_path: Path):
        """增量扫描：hash 不变时跳过"""
        (tmp_path / "main.py").write_text("x = 1\n")

        index = ProjectIndex(tmp_path)
        result1 = index.scan()
        assert result1["updated"] >= 1

        # 第二次扫描，文件没变
        result2 = index.scan()
        assert result2["skipped"] >= 1
        assert result2["updated"] == 0
        index.close()

    def test_force_reindex(self, tmp_path: Path):
        """强制重新索引"""
        (tmp_path / "main.py").write_text("x = 1\n")

        index = ProjectIndex(tmp_path)
        index.scan()
        result = index.scan(force=True)
        assert result["updated"] >= 1  # 强制模式下全部更新
        index.close()

    def test_search_files(self, tmp_path: Path):
        """搜索文件"""
        (tmp_path / "tokens.css").write_text(":root { --color: red; }\n")
        (tmp_path / "main.py").write_text("pass\n")

        index = ProjectIndex(tmp_path)
        index.scan()
        results = index.search("token")

        assert results["total_files"] >= 1
        assert any("token" in f["path"] for f in results["files"])
        index.close()

    def test_stats(self, tmp_path: Path):
        """统计信息"""
        (tmp_path / "a.py").write_text("pass\n")
        (tmp_path / "b.js").write_text("const x = 1;\n")

        index = ProjectIndex(tmp_path)
        index.scan()
        stats = index.stats()

        assert stats["files"] >= 2
        assert stats["artifacts"] == 0  # 还没提取 artifact
        index.close()

    def test_smartdev_dir_created(self, tmp_path: Path):
        """扫描后创建 .smartdev 目录"""
        (tmp_path / "main.py").write_text("pass\n")

        index = ProjectIndex(tmp_path)
        index.scan()

        assert index.smartdev_dir.exists()
        assert index.db_path.exists()
        index.close()
