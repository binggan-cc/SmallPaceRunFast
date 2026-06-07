"""
Phase 7 Step 2 — Go extraction 单元测试

验证 TreeSitterProvider 对 Go 代码的结构提取：
- function / method / struct / interface / import
- receiver parent 提取
- alias / blank / dot import 容错
- 语法错误不崩溃
- Python / JS 链路不受影响

所有需要 tree-sitter-go 的测试通过 skipif 保护。
"""

import json

import pytest

from smartdev.context.artifact_extractor import (
    ArtifactExtractor,
    _build_import_relations,
    _is_go_file,
    _parse_go_imports,
    _resolve_go_import_target,
)
from smartdev.context.index_store import IndexStore
from smartdev.context.project_index import ProjectIndex
from smartdev.context.structure_extractor import (
    CodeSymbol,
    StructureExtractor,
)
from smartdev.context.tree_sitter_provider import (
    TreeSitterProvider,
    _load_language,
    _tree_sitter_available,
)


def _go_grammar_available() -> bool:
    """tree-sitter-go grammar 是否可用"""
    if not _tree_sitter_available():
        return False
    return _load_language("go") is not None


# ── Go Code Snippets ──────────────────────────────────────────


GO_FUNCTION = """\
package main

func Greet(name string) string {
\treturn "Hello, " + name
}

func internalHelper() {
\t// not exported
}
"""

GO_METHOD = """\
package main

type User struct {
\tName string
}

func (u *User) GetName() string {
\treturn u.Name
}

func (u User) SetName(name string) {
\tu.Name = name
}
"""

GO_STRUCT = """\
package main

type User struct {
\tName string
\tAge  int
}

type Config struct {
\tDebug bool
}
"""

GO_INTERFACE = """\
package main

type Reader interface {
\tRead() string
}

type Writer interface {
\tWrite(data []byte) (int, error)
}
"""

GO_SINGLE_IMPORT = """\
package main

import "fmt"
"""

GO_IMPORT_BLOCK = """\
package main

import (
\t"fmt"
\talias "net/http"
\t_ "github.com/lib/pq"
)
"""

GO_MIXED = """\
package main

import "strings"

type Box struct {
\tValue string
}

func NewBox(v string) *Box {
\treturn &Box{Value: strings.ToUpper(v)}
}

func (b *Box) Unwrap() string {
\treturn b.Value
}
"""

GO_SYNTAX_ERROR = """\
package main

func Broken({
\t// missing closing paren
}
"""


# ── 测试 ──────────────────────────────────────────────────────


@pytest.mark.skipif(
    not _go_grammar_available(),
    reason="tree-sitter-go grammar not installed",
)
class TestGoExtraction:
    """Go 代码结构提取"""

    def _extract(self, content: str, file_path: str = "main.go"):
        provider = TreeSitterProvider()
        return provider.extract(file_path, content)

    # ── Function ──

    def test_extract_functions(self):
        """提取 Go function declaration"""
        result = self._extract(GO_FUNCTION)
        funcs = [s for s in result.symbols if s.kind == "function"]
        func_names = {f.name for f in funcs}

        assert len(funcs) == 2
        assert "Greet" in func_names
        assert "internalHelper" in func_names

    def test_function_signature(self):
        """function 的 signature 包含参数和返回值"""
        result = self._extract(GO_FUNCTION)
        greet = [s for s in result.symbols if s.name == "Greet"][0]
        assert "Greet" in greet.signature
        assert "name string" in greet.signature
        assert "string" in greet.signature

    def test_function_exported_detection(self):
        """Go 导出约定：首字母大写 = exported"""
        result = self._extract(GO_FUNCTION)
        greet = [s for s in result.symbols if s.name == "Greet"][0]
        helper = [s for s in result.symbols if s.name == "internalHelper"][0]
        assert greet.is_exported is True
        assert helper.is_exported is False

    def test_function_confidence(self):
        """Tree-sitter 提取的 confidence = 0.98"""
        result = self._extract(GO_FUNCTION)
        for s in result.symbols:
            assert s.confidence == 0.98

    # ── Method ──

    def test_extract_methods(self):
        """提取 Go method declaration，含 receiver parent"""
        result = self._extract(GO_METHOD)
        methods = [s for s in result.symbols if s.kind == "method"]
        method_names = {m.name for m in methods}

        assert len(methods) == 2
        assert "GetName" in method_names
        assert "SetName" in method_names

    def test_method_receiver_parent(self):
        """method 的 parent 字段记录 receiver type"""
        result = self._extract(GO_METHOD)
        get_name = [s for s in result.symbols if s.name == "GetName"][0]
        assert get_name.parent == "User"

    def test_method_exported_detection(self):
        """method 遵循 Go 导出约定"""
        result = self._extract(GO_METHOD)
        get_name = [s for s in result.symbols if s.name == "GetName"][0]
        assert get_name.is_exported is True

    # ── Struct → class ──

    def test_extract_struct_as_class(self):
        """struct type → kind='class'"""
        result = self._extract(GO_STRUCT)
        classes = [s for s in result.symbols if s.kind == "class"]
        class_names = {c.name for c in classes}

        assert len(classes) == 2
        assert "User" in class_names
        assert "Config" in class_names

    def test_struct_exported_detection(self):
        """struct 遵循 Go 导出约定"""
        result = self._extract(GO_STRUCT)
        user = [s for s in result.symbols if s.name == "User"][0]
        assert user.is_exported is True

    # ── Interface ──

    def test_extract_interfaces(self):
        """interface type → kind='interface'"""
        result = self._extract(GO_INTERFACE)
        ifaces = [s for s in result.symbols if s.kind == "interface"]
        iface_names = {i.name for i in ifaces}

        assert len(ifaces) == 2
        assert "Reader" in iface_names
        assert "Writer" in iface_names

    # ── Import ──

    def test_extract_single_import(self):
        """单行 import → kind='import'"""
        result = self._extract(GO_SINGLE_IMPORT)
        imports = [s for s in result.symbols if s.kind == "import"]

        assert len(imports) == 1
        assert imports[0].name == "fmt"

    def test_extract_import_block(self):
        """import block → 多个 import symbols"""
        result = self._extract(GO_IMPORT_BLOCK)
        imports = [s for s in result.symbols if s.kind == "import"]
        import_paths = {i.name for i in imports}

        assert len(imports) == 3
        assert "fmt" in import_paths
        assert "net/http" in import_paths
        assert "github.com/lib/pq" in import_paths

    def test_import_path_in_imports_list(self):
        """import path 也在 result.imports 列表中"""
        result = self._extract(GO_SINGLE_IMPORT)
        assert "fmt" in result.imports

    # ── Syntax error ──

    def test_syntax_error_does_not_crash(self):
        """语法错误的 Go 文件不导致崩溃，返回 errors"""
        result = self._extract(GO_SYNTAX_ERROR, "broken.go")
        # 不抛异常就是成功
        assert isinstance(result.symbols, list)
        # 应该有 error（parse warning）
        assert len(result.errors) >= 1

    # ── Mixed ──

    def test_mixed_file_extracts_all_types(self):
        """包含多种结构的 Go 文件提取所有类型"""
        result = self._extract(GO_MIXED)
        kinds = {s.kind for s in result.symbols}

        assert "function" in kinds
        assert "method" in kinds
        assert "class" in kinds
        assert "import" in kinds


@pytest.mark.skipif(
    not _go_grammar_available(),
    reason="tree-sitter-go grammar not installed",
)
class TestGoImportRelations:
    """Go import relation 构建"""

    def test_parse_go_import_basic(self):
        """Go import symbol → parsed info"""
        sym = CodeSymbol(
            name="fmt",
            kind="import",
            file_path="main.go",
            start_line=3,
            end_line=3,
            signature='import "fmt"',
            confidence=0.98,
            extractor="tree_sitter",
        )
        parsed = _parse_go_imports(sym)
        assert len(parsed) == 1
        assert parsed[0]["module"] == "fmt"
        assert parsed[0]["import_kind"] == "go_import"

    def test_parse_go_import_alias(self):
        """alias import 保留 alias 信息"""
        sym = CodeSymbol(
            name="net/http",
            kind="import",
            file_path="main.go",
            start_line=3,
            end_line=3,
            signature='alias "net/http"',
            confidence=0.98,
            extractor="tree_sitter",
        )
        parsed = _parse_go_imports(sym)
        assert parsed[0]["import_kind"] == "go_import_alias"

    def test_parse_go_import_blank(self):
        """blank import 正确识别"""
        sym = CodeSymbol(
            name="github.com/lib/pq",
            kind="import",
            file_path="main.go",
            start_line=3,
            end_line=3,
            signature='_ "github.com/lib/pq"',
            confidence=0.98,
            extractor="tree_sitter",
        )
        parsed = _parse_go_imports(sym)
        assert parsed[0]["import_kind"] == "go_import_blank"

    def test_go_import_target_external(self):
        """Go import → external:go:{module}"""
        target_id, is_external, name, meta = _resolve_go_import_target(
            "fmt", "main.go"
        )
        assert is_external is True
        assert target_id == "external:go:fmt"
        assert meta["resolution_kind"] == "go_external"

    def test_go_import_target_with_path(self):
        """带路径的 Go import → external:go:{full_path}"""
        target_id, is_external, name, meta = _resolve_go_import_target(
            "github.com/gin-gonic/gin", "main.go"
        )
        assert target_id == "external:go:github.com/gin-gonic/gin"
        assert is_external is True


class TestGoFileDetection:
    """Go 文件检测"""

    def test_is_go_file(self):
        assert _is_go_file("main.go") is True
        assert _is_go_file("src/pkg/handler.go") is True

    def test_is_not_go_file(self):
        assert _is_go_file("main.py") is False
        assert _is_go_file("app.ts") is False
        assert _is_go_file("index.js") is False


@pytest.mark.skipif(
    not _go_grammar_available(),
    reason="tree-sitter-go grammar not installed",
)
class TestGoFullIndexPipeline:
    """Go 文件的全链路 index → artifact → relation"""

    def test_go_module_artifact_created(self, tmp_path):
        """Go 文件索引后生成 code:module artifact"""
        project = tmp_path / "goproj"
        project.mkdir()
        (project / "main.go").write_text(GO_MIXED)

        index = ProjectIndex(project)
        index.index()

        conn = index.store.connect()
        rows = conn.execute(
            "SELECT * FROM artifacts WHERE type = 'code:module' AND file_path LIKE '%.go'"
        ).fetchall()
        assert len(rows) >= 1

        # module artifact 的 language 应该是 "go"
        meta = json.loads(rows[0]["metadata_json"])
        assert meta.get("language") == "go"

        index.close()

    def test_go_imports_creates_external_relations(self, tmp_path):
        """Go import 创建 external_module artifact 和 imports relation"""
        project = tmp_path / "goproj2"
        project.mkdir()
        (project / "main.go").write_text(GO_SINGLE_IMPORT)

        index = ProjectIndex(project)
        index.index()

        conn = index.store.connect()
        # 应有 external:go:fmt
        ext_rows = conn.execute(
            "SELECT * FROM artifacts WHERE type = 'external_module'"
        ).fetchall()
        external_names = [r["name"] for r in ext_rows]
        assert "fmt" in external_names

        # 应有 imports relation
        rel_rows = conn.execute(
            "SELECT * FROM relations WHERE type = 'imports'"
        ).fetchall()
        assert len(rel_rows) >= 1

        index.close()

    def test_go_functions_in_search(self, tmp_path):
        """search 能找到 Go 函数"""
        project = tmp_path / "goproj3"
        project.mkdir()
        (project / "main.go").write_text(GO_MIXED)

        index = ProjectIndex(project)
        index.index()

        results = index.search("NewBox")
        assert results["total_artifacts"] >= 1
        artifact_names = [a["name"] for a in results["artifacts"]]
        assert "NewBox" in artifact_names

        index.close()


class TestExistingProvidersUnaffectedByGo:
    """Python / JS Provider 不受 Go 提取影响"""

    def test_python_still_uses_ast(self):
        extractor = StructureExtractor(auto_detect_treesitter=True)
        provider = extractor.get_provider("python")
        assert provider.name == "python_ast"

    def test_typescript_still_uses_node_or_regex(self):
        extractor = StructureExtractor(auto_detect_treesitter=True)
        provider = extractor.get_provider("typescript")
        # 不应被 tree-sitter 覆盖
        assert provider.name != "tree_sitter"
