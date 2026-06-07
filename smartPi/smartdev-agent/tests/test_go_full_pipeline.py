"""
Phase 7 Step 3 — Go fixture 全链路验证

验证基于磁盘 fixture 的完整链路：
    index → search → project.map → graph.validate

Fixture 项目结构（tests/fixtures/go_project/）：
    go_project/
    ├── go.mod
    ├── main.go                            # 入口，import 内部包 + stdlib
    ├── pkg/
    │   └── models/
    │       ├── user.go                    # struct + methods
    │       └── types.go                  # interfaces
    └── internal/
        └── service/
            └── user_service.go           # struct + methods + import models

覆盖验证点：
- Go 文件被正确索引（language=go）
- function / struct(class) / interface 被提取为 artifact
- import relations 被构建（外部 + 内部包均建立 external:go:... 关系）
- project.map 能正常导出
- graph.validate 对 Go 项目无误报（孤儿节点等不超过合理阈值）
- 源码文件不可变（fixture 不被写入）
- 现有 Python / JS/TS 链路不受影响

所有测试用 skipif 保护：需要 tree-sitter-go grammar 可用。
"""

import json
import shutil
from pathlib import Path

import pytest

from smartdev.context.graph_validator import validate_graph
from smartdev.context.project_index import ProjectIndex
from smartdev.context.project_map import generate_project_map
from smartdev.context.tree_sitter_provider import (
    _load_language,
    _tree_sitter_available,
)


# ── helpers ────────────────────────────────────────────────────


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "go_project"

GO_FILES = [
    "main.go",
    "pkg/models/user.go",
    "pkg/models/types.go",
    "internal/service/user_service.go",
]


def _go_grammar_available() -> bool:
    if not _tree_sitter_available():
        return False
    return _load_language("go") is not None


def _copy_fixture(tmp_path: Path) -> Path:
    """Copy the go_project fixture to a tmp dir so index writes don't pollute the source."""
    dest = tmp_path / "go_project"
    shutil.copytree(FIXTURE_DIR, dest)
    return dest


# ── fixture exists ─────────────────────────────────────────────


class TestGoFixtureExists:
    """Sanity-check: fixture files are present before tests run."""

    def test_fixture_dir_exists(self):
        assert FIXTURE_DIR.exists(), f"Fixture dir missing: {FIXTURE_DIR}"

    def test_fixture_go_files_present(self):
        for rel in GO_FILES:
            p = FIXTURE_DIR / rel
            assert p.exists(), f"Missing fixture file: {rel}"

    def test_fixture_go_mod_present(self):
        assert (FIXTURE_DIR / "go.mod").exists()

    def test_fixture_source_immutable(self):
        """Fixture 目录中不应存在 .smartdev 索引（上次测试若污染则此测试失败）"""
        smartdev_dir = FIXTURE_DIR / ".smartdev"
        assert not smartdev_dir.exists(), (
            f".smartdev/ exists in fixture source ({smartdev_dir}). "
            "A previous test may have written to the fixture directly."
        )


# ── indexing ───────────────────────────────────────────────────


@pytest.mark.skipif(
    not _go_grammar_available(),
    reason="tree-sitter-go grammar not installed",
)
class TestGoFixtureIndexing:
    """全部 Go 文件能被正确索引。"""

    def test_all_go_files_indexed(self, tmp_path):
        project = _copy_fixture(tmp_path)
        index = ProjectIndex(project)
        result = index.index()
        index.close()

        assert result["files"] >= 4, f"Expected ≥4 files, got {result['files']}"
        assert result["errors"] == 0, f"Indexing errors: {result['errors']}"

    def test_go_files_have_correct_language(self, tmp_path):
        project = _copy_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        conn = index.store.connect()
        go_files = conn.execute(
            "SELECT path, language FROM files WHERE language = 'go'"
        ).fetchall()
        index.close()

        paths = [r["path"] for r in go_files]
        assert len(paths) >= 4
        for rel in GO_FILES:
            assert any(rel in p for p in paths), f"{rel} not indexed as go"

    def test_artifacts_extracted(self, tmp_path):
        project = _copy_fixture(tmp_path)
        index = ProjectIndex(project)
        result = index.index()
        index.close()

        assert result["artifacts"] >= 1, "No artifacts extracted"

    def test_no_source_files_modified(self, tmp_path):
        """索引完成后 fixture 源文件不应被修改。"""
        project = _copy_fixture(tmp_path)
        # Record mtimes before indexing
        before = {
            rel: (project / rel).stat().st_mtime
            for rel in GO_FILES
        }
        index = ProjectIndex(project)
        index.index()
        index.close()

        for rel in GO_FILES:
            after = (project / rel).stat().st_mtime
            assert before[rel] == after, f"{rel} was modified during indexing"


# ── artifact extraction ────────────────────────────────────────


@pytest.mark.skipif(
    not _go_grammar_available(),
    reason="tree-sitter-go grammar not installed",
)
class TestGoFixtureArtifacts:
    """提取的 artifact 类型和内容正确。"""

    def test_function_artifacts_present(self, tmp_path):
        project = _copy_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        conn = index.store.connect()
        # function artifacts
        funcs = conn.execute(
            "SELECT name FROM artifacts WHERE type = 'code:function'"
        ).fetchall()
        index.close()

        names = [r["name"] for r in funcs]
        # main.go exports Run and main; models has NewUser; service has NewUserService
        for expected in ["Run", "NewUser", "NewUserService"]:
            assert expected in names, f"Expected function '{expected}' in artifacts, got: {names}"

    def test_struct_artifacts_present(self, tmp_path):
        """struct は class artifact として登録される。"""
        project = _copy_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        conn = index.store.connect()
        classes = conn.execute(
            "SELECT name FROM artifacts WHERE type = 'code:class'"
        ).fetchall()
        index.close()

        names = [r["name"] for r in classes]
        for expected in ["User", "UserService"]:
            assert expected in names, f"Expected class '{expected}' in artifacts, got: {names}"

    def test_interface_artifacts_present(self, tmp_path):
        project = _copy_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        conn = index.store.connect()
        interfaces = conn.execute(
            "SELECT name FROM artifacts WHERE type = 'code:interface'"
        ).fetchall()
        index.close()

        names = [r["name"] for r in interfaces]
        for expected in ["Stringer", "Validator"]:
            assert expected in names, f"Expected interface '{expected}' in artifacts, got: {names}"

    def test_module_artifacts_have_go_language(self, tmp_path):
        project = _copy_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        conn = index.store.connect()
        modules = conn.execute(
            "SELECT metadata_json FROM artifacts WHERE type = 'code:module' AND file_path LIKE '%.go'"
        ).fetchall()
        index.close()

        assert len(modules) >= 4
        for row in modules:
            meta = json.loads(row["metadata_json"])
            assert meta.get("language") == "go", f"Unexpected language in module: {meta}"


# ── import relations ───────────────────────────────────────────


@pytest.mark.skipif(
    not _go_grammar_available(),
    reason="tree-sitter-go grammar not installed",
)
class TestGoFixtureImportRelations:
    """import relations 被正确构建。"""

    def test_import_relations_created(self, tmp_path):
        project = _copy_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        conn = index.store.connect()
        relations = conn.execute(
            "SELECT * FROM relations WHERE type = 'imports'"
        ).fetchall()
        index.close()

        assert len(relations) >= 1, "No import relations created"

    def test_stdlib_imports_are_external(self, tmp_path):
        """fmt / os / strings 等 stdlib 包应归类为 external:go:..."""
        project = _copy_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        conn = index.store.connect()
        ext_artifacts = conn.execute(
            "SELECT name, id FROM artifacts WHERE type = 'external_module'"
        ).fetchall()
        index.close()

        ext_ids = [r["id"] for r in ext_artifacts]
        # main.go imports fmt and os; service imports fmt and strings
        for pkg in ("fmt", "os", "strings"):
            assert any(pkg in eid for eid in ext_ids), (
                f"stdlib package '{pkg}' not found in external_module artifacts. "
                f"Found: {ext_ids[:10]}"
            )

    def test_internal_package_imports_exist(self, tmp_path):
        """内部包 import 也建立了 imports relation（target 为 external:go:... 形式）"""
        project = _copy_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        conn = index.store.connect()
        # internal package imports: github.com/example/goproject/...
        ext_artifacts = conn.execute(
            "SELECT id FROM artifacts WHERE type = 'external_module' AND id LIKE '%goproject%'"
        ).fetchall()
        index.close()

        # Step 2 不做 go.mod resolution，内部包仍归为 external:go:
        assert len(ext_artifacts) >= 1, (
            "Expected ≥1 external_module artifact for internal go packages. "
            "These are treated as external until go.mod resolution is implemented."
        )


# ── search ─────────────────────────────────────────────────────


@pytest.mark.skipif(
    not _go_grammar_available(),
    reason="tree-sitter-go grammar not installed",
)
class TestGoFixtureSearch:
    """搜索能找到 Go 项目中的符号。"""

    def test_search_function_by_name(self, tmp_path):
        project = _copy_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        results = index.search("NewUser")
        index.close()

        names = [a["name"] for a in results["artifacts"]]
        assert "NewUser" in names, f"'NewUser' not found in search results: {names}"

    def test_search_struct_by_name(self, tmp_path):
        project = _copy_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        results = index.search("UserService")
        index.close()

        names = [a["name"] for a in results["artifacts"]]
        assert "UserService" in names, f"'UserService' not found: {names}"

    def test_search_interface_by_name(self, tmp_path):
        project = _copy_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        results = index.search("Validator")
        index.close()

        names = [a["name"] for a in results["artifacts"]]
        assert "Validator" in names, f"'Validator' not found: {names}"

    def test_search_by_file_path(self, tmp_path):
        project = _copy_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        results = index.search("user_service")
        index.close()

        file_paths = [f["path"] for f in results["files"]]
        assert any("user_service" in p for p in file_paths), (
            f"user_service.go not found in file results: {file_paths}"
        )


# ── project.map ────────────────────────────────────────────────


@pytest.mark.skipif(
    not _go_grammar_available(),
    reason="tree-sitter-go grammar not installed",
)
class TestGoFixtureProjectMap:
    """project.map 能对 Go 项目正常导出。

    generate_project_map 返回 ProjectMap dataclass，通过属性访问。
    """

    def test_project_map_generates(self, tmp_path):
        project = _copy_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        pmap = generate_project_map(index.store, project_name=str(project.name))
        index.close()

        assert pmap is not None
        # summary 字段包含 files 统计
        assert pmap.summary["files"] >= 4

    def test_project_map_has_go_in_languages(self, tmp_path):
        project = _copy_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        pmap = generate_project_map(index.store, project_name=str(project.name))
        index.close()

        # summary["languages"] 是语言字符串列表
        lang_keys = pmap.summary.get("languages", [])
        assert "go" in lang_keys, f"'go' not in project map languages: {lang_keys}"

    def test_project_map_has_modules(self, tmp_path):
        """ProjectMap.modules 包含 Go 模块列表。"""
        project = _copy_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        pmap = generate_project_map(index.store, project_name=str(project.name))
        index.close()

        assert len(pmap.modules) >= 4, (
            f"Expected ≥4 modules in project map, got {len(pmap.modules)}"
        )

    def test_project_map_json_export(self, tmp_path):
        """ProjectMap 能导出为 JSON（通过 export_json 方法）。"""
        project = _copy_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        pmap = generate_project_map(index.store, project_name=str(project.name))
        index.close()

        # to_json() 方法返回 JSON 字符串
        serialized = pmap.to_json()
        assert len(serialized) > 0
        # 确认是合法 JSON，顶层有 "project" 键
        parsed = json.loads(serialized)
        assert "project" in parsed
        assert "summary" in parsed["project"]


# ── graph.validate ─────────────────────────────────────────────


@pytest.mark.skipif(
    not _go_grammar_available(),
    reason="tree-sitter-go grammar not installed",
)
class TestGoFixtureGraphValidation:
    """graph.validate 对 Go 项目无严重错误。

    validate_graph 返回 GraphValidationResult dataclass，通过属性访问。
    """

    def test_graph_validate_runs(self, tmp_path):
        project = _copy_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        report = validate_graph(index.store)
        index.close()

        assert report is not None
        # GraphValidationResult 有 errors / warnings / info / stats 属性
        assert hasattr(report, "errors")
        assert hasattr(report, "warnings")
        assert hasattr(report, "stats")

    def test_no_critical_graph_errors(self, tmp_path):
        """图谱中不应有 error 级别问题（warning 可接受）。"""
        project = _copy_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        report = validate_graph(index.store)
        index.close()

        # errors 是 ValidationIssue 列表
        assert len(report.errors) == 0, (
            f"graph.validate found {len(report.errors)} error(s):\n"
            + "\n".join(str(e) for e in report.errors[:5])
        )

    def test_graph_validate_stats_populated(self, tmp_path):
        """stats 字典包含基础计数。"""
        project = _copy_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        report = validate_graph(index.store)
        index.close()

        assert "artifacts" in report.stats
        assert "relations" in report.stats
        assert report.stats["artifacts"] >= 1
