"""
SmartDev Agent — Tree-sitter Multi-language Provider

设计原理：
─────────
Phase 7 引入 Tree-sitter 作为 optional multi-language code structure extractor。
Tree-sitter 是一个增量解析框架，支持 100+ 语言的语法解析。

TreeSitterProvider 作为第三层 Provider（多语言扩展层），
不替换 PythonAstExtractor 或 NodeBridgeExtractor。

Provider 定位（Phase 7）：
┌────────────────────────────┬──────────────────────────────────┐
│ PythonAstExtractor         │ python           (confidence 1.0) │ ← 不动
│ NodeBridgeExtractor        │ javascript/typescript (0.95)     │ ← 不动
│ TreeSitterProvider         │ go, ...           (0.98)         │ ← 新增
│ JsTsRegexFallbackExtractor │ fallback          (0.55)         │ ← 保留
│ NullStructureExtractor     │ 不支持的语言                        │
└────────────────────────────┴──────────────────────────────────┘

关键设计决策：
1. optional dependency — tree-sitter 包未安装时 Provider 不注册
2. _load_language() 适配层 — 封装 grammar 加载，不写死具体 API
3. 三层 fallback — 包未安装 / grammar 不可用 / 单文件失败
4. P0 提取：function / method / struct / interface / import

对应文档：
- phase-7-design.md（Phase 7 Step 0 设计文档）
"""

from __future__ import annotations

from pathlib import Path

from smartdev.context.structure_extractor import (
    CodeSymbol,
    StructureExtractionResult,
    StructureExtractorProvider,
)

CONFIDENCE = 0.98
EXTRACTOR_NAME = "tree_sitter"


# ── 依赖检测 ──────────────────────────────────────────────

def _tree_sitter_available() -> bool:
    """检测 tree-sitter Python binding 是否可用"""
    try:
        import tree_sitter  # noqa: F401
        return True
    except ImportError:
        return False


# ── Grammar 加载适配层 ──────────────────────────────────────

def _load_language(language: str):
    """语言 grammar 加载适配层

    封装 grammar 加载的所有变体：
    - tree-sitter-{lang} 预编译 wheel（推荐）
    - tree_sitter.Language(path, name)
    - 动态 .so 文件
    - 未来可能的其它 tree-sitter language package

    返回：
        tree_sitter.Language 对象（成功时）
        None（grammar 不可用时）
    """
    try:
        import tree_sitter
    except ImportError:
        return None

    if language == "go":
        try:
            import tree_sitter_go as tsgo
            return tree_sitter.Language(tsgo.language())
        except ImportError:
            return None

    # 未来扩展: php, rust, java ...
    return None


# ── Go AST 提取 ────────────────────────────────────────────

def _extract_go(file_path: str, content: str, lang) -> StructureExtractionResult:
    """提取 Go 文件的代码结构

    提取 P0 符号：
    - function_declaration → function
    - method_declaration → method（parent = receiver type name）
    - type_declaration + struct_type → class（metadata.kind_detail = go_struct）
    - type_declaration + interface_type → interface
    - import_declaration → import

    不做：
    - 函数调用关系
    - struct 字段级 artifact
    - interface 实现关系
    - 类型推断
    - 表达式级解析
    """
    import tree_sitter

    symbols: list[CodeSymbol] = []
    imports: list[str] = []
    errors: list[str] = []

    parser = tree_sitter.Parser()
    parser.language = lang

    try:
        code_bytes = content.encode("utf-8")
        tree = parser.parse(code_bytes)
    except Exception as e:
        errors.append(f"Go parse error: {e}")
        return StructureExtractionResult(symbols=[], imports=[], errors=errors)

    root = tree.root_node
    if root.has_error:
        errors.append("Go parse warning: AST contains error nodes")

    for node in root.named_children:
        try:
            if node.type == "function_declaration":
                sym = _extract_go_function(node, file_path, code_bytes)
                if sym:
                    symbols.append(sym)
            elif node.type == "method_declaration":
                sym = _extract_go_method(node, file_path, code_bytes)
                if sym:
                    symbols.append(sym)
            elif node.type == "type_declaration":
                symbols.extend(_extract_go_type(node, file_path, code_bytes))
            elif node.type == "import_declaration":
                syms, imps = _extract_go_import(node, file_path, code_bytes)
                symbols.extend(syms)
                imports.extend(imps)
        except Exception as e:
            errors.append(f"Extraction error at node {node.type}: {e}")

    return StructureExtractionResult(symbols=symbols, imports=imports, errors=errors)


# ── Go 节点提取辅助函数 ──────────────────────────────────────

def _node_text(node, code_bytes: bytes) -> str:
    """获取节点的源码文本"""
    return code_bytes[node.start_byte:node.end_byte].decode("utf-8")


def _first_line(node, code_bytes: bytes) -> str:
    """获取节点第一行文本"""
    return _node_text(node, code_bytes).split("\n")[0].strip()


def _is_exported(name: str) -> bool:
    """Go 导出约定：首字母大写"""
    return len(name) > 0 and name[0].isupper()


def _extract_go_function(node, file_path: str, code_bytes: bytes) -> CodeSymbol | None:
    """提取 Go function_declaration"""
    name_node = node.child_by_field_name("name")
    if name_node is None:
        return None
    name = _node_text(name_node, code_bytes)
    sig = _first_line(node, code_bytes)

    return CodeSymbol(
        name=name,
        kind="function",
        file_path=file_path,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        signature=sig,
        is_exported=_is_exported(name),
        confidence=CONFIDENCE,
        extractor=EXTRACTOR_NAME,
    )


def _extract_go_method(node, file_path: str, code_bytes: bytes) -> CodeSymbol | None:
    """提取 Go method_declaration

    method 形式: func (receiver Type) MethodName(params) results { ... }
    receiver 信息来自第一个 parameter_list（包含 *Type 或 Type）
    """
    name_node = node.child_by_field_name("name")
    if name_node is None:
        return None
    name = _node_text(name_node, code_bytes)
    sig = _first_line(node, code_bytes)

    # 提取 receiver type（field name = "receiver"）
    receiver_type = ""
    receiver = node.child_by_field_name("receiver")
    if receiver is not None:
        for child in receiver.named_children:
            if child.type == "parameter_declaration":
                # receiver 的 type: 直接找 type_identifier 或 pointer_type
                type_node = child.child_by_field_name("type")
                if type_node is None:
                    for c in child.children:
                        if c.type in ("type_identifier", "pointer_type"):
                            type_node = c
                            break
                if type_node is not None:
                    receiver_type = _node_text(type_node, code_bytes)
                    # 去 * 前缀
                    receiver_type = receiver_type.lstrip("*")
                break

    return CodeSymbol(
        name=name,
        kind="method",
        file_path=file_path,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        signature=sig,
        parent=receiver_type,
        is_exported=_is_exported(name),
        confidence=CONFIDENCE,
        extractor=EXTRACTOR_NAME,
    )


def _extract_go_type(node, file_path: str, code_bytes: bytes) -> list[CodeSymbol]:
    """提取 Go type_declaration（struct / interface）"""
    symbols: list[CodeSymbol] = []

    for spec in node.named_children:
        if spec.type != "type_spec":
            continue

        name_node = spec.child_by_field_name("name")
        if name_node is None:
            continue
        name = _node_text(name_node, code_bytes)
        sig = _first_line(spec, code_bytes)

        # 检测 type 的子类型（struct_type / interface_type）
        for child in spec.named_children:
            if child.type == "struct_type":
                sym = CodeSymbol(
                    name=name,
                    kind="class",
                    file_path=file_path,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    signature=sig,
                    is_exported=_is_exported(name),
                    confidence=CONFIDENCE,
                    extractor=EXTRACTOR_NAME,
                )
                symbols.append(sym)
                break
            elif child.type == "interface_type":
                sym = CodeSymbol(
                    name=name,
                    kind="interface",
                    file_path=file_path,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    signature=sig,
                    is_exported=_is_exported(name),
                    confidence=CONFIDENCE,
                    extractor=EXTRACTOR_NAME,
                )
                symbols.append(sym)
                break

    return symbols


def _extract_go_import(
    node, file_path: str, code_bytes: bytes
) -> tuple[list[CodeSymbol], list[str]]:
    """提取 Go import_declaration

    支持:
    - 单行: import "fmt"
    - 块: import ( "fmt"; alias "net/http" )
    - alias import: alias "path"
    - blank import: _ "path"
    - dot import: . "path"
    """
    symbols: list[CodeSymbol] = []
    imports: list[str] = []

    for spec in node.named_children:
        if spec.type == "import_spec_list":
            # import block: 逐条处理子 import_spec
            for child in spec.named_children:
                if child.type == "import_spec":
                    sym, imp = _extract_single_import(child, file_path, code_bytes)
                    if sym:
                        symbols.append(sym)
                    if imp:
                        imports.append(imp)
        elif spec.type == "import_spec":
            # 单行 import
            sym, imp = _extract_single_import(spec, file_path, code_bytes)
            if sym:
                symbols.append(sym)
            if imp:
                imports.append(imp)

    return symbols, imports


def _extract_single_import(
    spec, file_path: str, code_bytes: bytes
) -> tuple[CodeSymbol | None, str | None]:
    """提取单个 import_spec → CodeSymbol + import string"""
    path = ""
    alias = ""
    is_blank = False
    is_dot = False

    for child in spec.named_children:
        if child.type == "interpreted_string_literal":
            # 提取路径内容（去掉引号）
            raw = _node_text(child, code_bytes)
            path = raw.strip('"').strip("'").strip("`")
        elif child.type == "package_identifier":
            alias = _node_text(child, code_bytes)
        elif child.type == "blank_identifier":
            is_blank = True
        elif child.type == "dot":
            is_dot = True

    if not path:
        return None, None

    sig = _first_line(spec, code_bytes)

    metadata = {
        "path": path,
        "alias": alias,
        "is_blank": is_blank,
        "is_dot": is_dot,
    }

    sym = CodeSymbol(
        name=path,
        kind="import",
        file_path=file_path,
        start_line=spec.start_point[0] + 1,
        end_line=spec.end_point[0] + 1,
        signature=sig,
        confidence=CONFIDENCE,
        extractor=EXTRACTOR_NAME,
    )
    return sym, path


# ── TreeSitterProvider ─────────────────────────────────────

class TreeSitterProvider(StructureExtractorProvider):
    """Tree-sitter 多语言结构提取器

    作为 optional multi-language provider，提供 Go/PHP/Rust/Java 等
    语言的代码结构提取。不覆盖 python / javascript / typescript。

    confidence = 0.98（grammar 正常加载时）
    extractor = tree_sitter

    使用示例：
        provider = TreeSitterProvider()
        if provider.is_available:
            result = provider.extract("main.go", content)
    """

    def __init__(self) -> None:
        self._available = _tree_sitter_available()
        self._languages: dict[str, object] = {}
        self._extractors: dict[str, object] = {}

        if self._available:
            self._languages["go"] = _load_language("go")
            if self._languages["go"] is not None:
                self._extractors["go"] = _extract_go

    @property
    def name(self) -> str:
        return EXTRACTOR_NAME

    @property
    def supported_languages(self) -> list[str]:
        """返回 grammar 已成功加载的语言列表"""
        return list(self._extractors.keys())

    @property
    def is_available(self) -> bool:
        """tree-sitter 包是否已安装"""
        return self._available

    def language_loaded(self, language: str) -> bool:
        """检查特定语言的 grammar 是否已加载"""
        return language in self._extractors

    def extract(self, file_path: str, content: str) -> StructureExtractionResult:
        """提取文件的代码结构

        根据 supported_languages 和文件后缀选择 extractor。
        """
        if not self._available:
            return StructureExtractionResult(
                symbols=[],
                imports=[],
                errors=["tree-sitter Python package not installed"],
            )

        suffix = Path(file_path).suffix.lower()
        language = _suffix_to_language(suffix)
        if language not in self._extractors:
            return StructureExtractionResult(
                symbols=[],
                imports=[],
                errors=[f"tree-sitter grammar not loaded for language: {language}"],
            )

        extractor_fn = self._extractors[language]
        return extractor_fn(file_path, content, self._languages[language])


def _suffix_to_language(suffix: str) -> str:
    """文件后缀 → 语言标识"""
    mapping = {
        ".go": "go",
    }
    return mapping.get(suffix, suffix.lstrip("."))
