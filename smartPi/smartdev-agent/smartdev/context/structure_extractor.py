"""
SmartDev Agent 多语言结构提取器（Provider 机制）

设计原理：
─────────
Phase 6-MVP 的 artifact 提取基于正则，能识别"这是一份文档""这是一个配置文件"，
但不能识别"这个文件里有哪些函数、类、方法"。

结构提取器补上这一层：提取代码文件中的结构化符号（函数、类、方法、import）。

Provider 层级（按精度递增）：
───────────────────────────
1. PythonAstExtractor       — Python 标准库 ast，精确解析（confidence = 1.0）
2. JsTsRegexFallbackExtractor — JS/TS 正则 fallback（confidence = 0.55）
                              只提取常见结构，标注 limitations
3. NullStructureExtractor   — 不支持的语言，返回空结果

后续 Phase 6.3 可替换为：
- NodeBabelExtractor        — Node 子进程 + Babel Parser
- TypeScriptCompilerExtractor — TypeScript Compiler API
Phase 7 可替换为：
- TreeSitterExtractor       — 多语言统一解析

为什么需要 Provider 机制？
─────────────────────────
1. 正则不是 JS/TS 的正式解析方案，只是 fallback
2. 后续接入 Babel/TS Compiler API 时，只需注册新 Provider
3. 不同精度的 Provider 可以共存，confidence 字段区分质量

借鉴来源：
- CodeGraph 的 Tree-sitter extraction pipeline
- 理念：确定性结构解析 + LLM 语义理解

对应文档：
- next-phase-code-intelligence.md §11（Phase 6.2：多语言结构提取）
"""

from __future__ import annotations

import ast
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


# ── 数据模型 ──────────────────────────────────────────────

@dataclass
class CodeSymbol:
    """代码符号

    Attributes:
        name: 符号名称（函数名、类名、import 路径等）
        kind: 符号类型（function / class / method / variable / import）
        file_path: 所在文件路径（相对路径）
        start_line: 起始行号
        end_line: 结束行号
        signature: 签名文本（函数签名、import 语句等）
        parent: 所属类名（method 时有值）
        is_exported: 是否导出（非下划线开头）
        confidence: 提取置信度
        extractor: 使用的提取器名称
        limitations: 该提取器的已知限制（供下游决策参考）
    """
    name: str
    kind: str
    file_path: str
    start_line: int
    end_line: int
    signature: str = ""
    parent: str = ""
    is_exported: bool = False
    confidence: float = 1.0
    extractor: str = ""
    limitations: list[str] = field(default_factory=list)


@dataclass
class StructureExtractionResult:
    """结构提取结果"""
    symbols: list[CodeSymbol]
    imports: list[str]  # import 语句列表
    errors: list[str]


# ── Provider 基类 ─────────────────────────────────────────

class StructureExtractorProvider(ABC):
    """结构提取器 Provider 基类

    所有语言的结构提取器必须继承此类。
    注册机制：子类定义 language 属性，StructureExtractor 自动匹配。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """提取器名称（如 'python_ast', 'regex_js_ts_fallback'）"""
        ...

    @property
    @abstractmethod
    def supported_languages(self) -> list[str]:
        """支持的语言列表"""
        ...

    @abstractmethod
    def extract(self, file_path: str, content: str) -> StructureExtractionResult:
        """提取文件结构"""
        ...


# ── Python ast 提取器（精确）──────────────────────────────

class PythonAstExtractor(StructureExtractorProvider):
    """Python 标准库 ast 精确提取

    精确解析：
    - 函数定义（def / async def）
    - 类定义（class）
    - 方法（class 内部的 def）
    - import 语句
    - 模块级赋值变量

    confidence = 1.0
    """

    @property
    def name(self) -> str:
        return "python_ast"

    @property
    def supported_languages(self) -> list[str]:
        return ["python"]

    def extract(self, file_path: str, content: str) -> StructureExtractionResult:
        symbols: list[CodeSymbol] = []
        imports: list[str] = []
        errors: list[str] = []

        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            errors.append(f"Python 语法错误: {e}")
            return StructureExtractionResult(symbols=symbols, imports=imports, errors=errors)

        for node in ast.iter_child_nodes(tree):
            # ── import 语句 ──
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                import_str = ast.get_source_segment(content, node)
                if import_str:
                    imports.append(import_str.strip())
                    if isinstance(node, ast.Import):
                        names = [alias.name for alias in node.names]
                        symbols.append(CodeSymbol(
                            name=", ".join(names),
                            kind="import",
                            file_path=file_path,
                            start_line=node.lineno,
                            end_line=node.end_lineno or node.lineno,
                            signature=import_str.strip(),
                            extractor=self.name,
                        ))
                    elif isinstance(node, ast.ImportFrom):
                        module = node.module or ""
                        names = [alias.name for alias in node.names]
                        symbols.append(CodeSymbol(
                            name=f"from {module} import {', '.join(names)}",
                            kind="import",
                            file_path=file_path,
                            start_line=node.lineno,
                            end_line=node.end_lineno or node.lineno,
                            signature=import_str.strip(),
                            extractor=self.name,
                        ))

            # ── 函数定义 ──
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                sig = self._func_signature(node, content)
                is_async = isinstance(node, ast.AsyncFunctionDef)
                symbols.append(CodeSymbol(
                    name=node.name,
                    kind="function",
                    file_path=file_path,
                    start_line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                    signature=f"{'async ' if is_async else ''}{sig}",
                    is_exported=not node.name.startswith("_"),
                    extractor=self.name,
                ))

            # ── 类定义 ──
            elif isinstance(node, ast.ClassDef):
                bases = self._class_bases(node)
                sig = f"class {node.name}({', '.join(bases)})" if bases else f"class {node.name}"
                symbols.append(CodeSymbol(
                    name=node.name,
                    kind="class",
                    file_path=file_path,
                    start_line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                    signature=sig,
                    is_exported=not node.name.startswith("_"),
                    extractor=self.name,
                ))

                # ── 类内部方法 ──
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_sig = self._func_signature(item, content)
                        is_async = isinstance(item, ast.AsyncFunctionDef)
                        symbols.append(CodeSymbol(
                            name=item.name,
                            kind="method",
                            file_path=file_path,
                            start_line=item.lineno,
                            end_line=item.end_lineno or item.lineno,
                            signature=f"{'async ' if is_async else ''}{method_sig}",
                            parent=node.name,
                            is_exported=not item.name.startswith("_"),
                            extractor=self.name,
                        ))

            # ── 模块级赋值 ──
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        symbols.append(CodeSymbol(
                            name=target.id,
                            kind="variable",
                            file_path=file_path,
                            start_line=node.lineno,
                            end_line=node.end_lineno or node.lineno,
                            is_exported=not target.id.startswith("_"),
                            extractor=self.name,
                        ))

        return StructureExtractionResult(symbols=symbols, imports=imports, errors=errors)

    def _func_signature(self, node: ast.FunctionDef | ast.AsyncFunctionDef,
                        content: str) -> str:
        try:
            source_lines = content.splitlines()
            start = node.lineno - 1
            for i in range(start, min(start + 10, len(source_lines))):
                line = source_lines[i]
                if ":" in line:
                    sig_line = line.strip()
                    if sig_line.startswith("def ") or sig_line.startswith("async "):
                        return sig_line.rstrip(":").strip()
        except (IndexError, ValueError):
            pass
        args = [arg.arg for arg in node.args.args]
        return f"{node.name}({', '.join(args)})"

    def _class_bases(self, node: ast.ClassDef) -> list[str]:
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            else:
                bases.append("...")
        return bases


# ── JS/TS 正则 Fallback 提取器 ───────────────────────────

class JsTsRegexFallbackExtractor(StructureExtractorProvider):
    """JS/TS 正则 fallback 提取器

    ⚠️ 这是 fallback，不是正式 JS/TS 解析方案。

    只提取常见结构（60-70% 覆盖率）：
    - function 声明
    - 箭头函数
    - class 定义
    - import / require

    不处理：
    - 嵌套箭头函数
    - 复杂泛型
    - 装饰器
    - 完整 JSX component 语义
    - 类型别名 / interface / namespace

    confidence = 0.55

    后续升级路径：
    - Phase 6.3: NodeBabelExtractor 或 TypeScriptCompilerExtractor
    - Phase 7: TreeSitterExtractor
    """

    @property
    def name(self) -> str:
        return "regex_js_ts_fallback"

    @property
    def supported_languages(self) -> list[str]:
        return ["javascript", "typescript", "vue", "svelte"]

    @property
    def limitations(self) -> list[str]:
        return [
            "no_nested_scope_resolution",
            "no_type_resolution",
            "no_jsx_component_semantics",
            "no_decorator_handling",
            "no_complex_generic_parsing",
        ]

    # ── 正则模式 ──

    _FUNC = re.compile(
        r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\([^)]*\)',
        re.MULTILINE,
    )
    _ARROW = re.compile(
        r'(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>',
        re.MULTILINE,
    )
    _CLASS = re.compile(
        r'(?:export\s+)?class\s+(\w+)(?:\s+extends\s+[\w.<>, ]+)?(?:\s+implements\s+[\w,<>\s]+)?\s*\{',
        re.MULTILINE,
    )
    _IMPORT = re.compile(
        r'import\s+(?:(?:\{[^}]*\}|\w+(?:\s*,\s*\{[^}]*\})?)\s+from\s+)?["\']([^"\']+)["\']',
        re.MULTILINE,
    )
    _REQUIRE = re.compile(
        r'(?:const|let|var)\s+(\w+)\s*=\s*require\s*\(\s*["\']([^"\']+)["\']\s*\)',
        re.MULTILINE,
    )

    def extract(self, file_path: str, content: str) -> StructureExtractionResult:
        CONFIDENCE = 0.55
        LIMITS = self.limitations
        symbols: list[CodeSymbol] = []
        imports: list[str] = []
        errors: list[str] = []

        # 函数声明
        for m in self._FUNC.finditer(content):
            name = m.group(1)
            line = content[:m.start()].count("\n") + 1
            sig = m.group(0).strip()
            symbols.append(CodeSymbol(
                name=name, kind="function", file_path=file_path,
                start_line=line, end_line=line, signature=sig,
                is_exported="export" in sig, confidence=CONFIDENCE,
                extractor=self.name, limitations=LIMITS,
            ))

        # 箭头函数
        for m in self._ARROW.finditer(content):
            name = m.group(1)
            line = content[:m.start()].count("\n") + 1
            sig = m.group(0).strip()
            symbols.append(CodeSymbol(
                name=name, kind="function", file_path=file_path,
                start_line=line, end_line=line, signature=sig,
                is_exported="export" in sig, confidence=CONFIDENCE,
                extractor=self.name, limitations=LIMITS,
            ))

        # 类
        for m in self._CLASS.finditer(content):
            name = m.group(1)
            line = content[:m.start()].count("\n") + 1
            sig = m.group(0).strip()
            symbols.append(CodeSymbol(
                name=name, kind="class", file_path=file_path,
                start_line=line, end_line=line, signature=sig,
                is_exported="export" in sig, confidence=CONFIDENCE,
                extractor=self.name, limitations=LIMITS,
            ))

        # import
        for m in self._IMPORT.finditer(content):
            module = m.group(1)
            imports.append(module)
            line = content[:m.start()].count("\n") + 1
            symbols.append(CodeSymbol(
                name=module, kind="import", file_path=file_path,
                start_line=line, end_line=line, signature=m.group(0).strip(),
                confidence=CONFIDENCE, extractor=self.name, limitations=LIMITS,
            ))

        # require
        for m in self._REQUIRE.finditer(content):
            module = m.group(2)
            imports.append(module)
            line = content[:m.start()].count("\n") + 1
            symbols.append(CodeSymbol(
                name=module, kind="import", file_path=file_path,
                start_line=line, end_line=line, signature=m.group(0).strip(),
                confidence=CONFIDENCE, extractor=self.name, limitations=LIMITS,
            ))

        return StructureExtractionResult(symbols=symbols, imports=imports, errors=errors)


# ── Null 提取器（不支持的语言）────────────────────────────

class NullStructureExtractor(StructureExtractorProvider):
    """不支持语言的占位提取器"""

    @property
    def name(self) -> str:
        return "null"

    @property
    def supported_languages(self) -> list[str]:
        return []

    def extract(self, file_path: str, content: str) -> StructureExtractionResult:
        return StructureExtractionResult(
            symbols=[], imports=[],
            errors=[],
        )


# ── 主入口：StructureExtractor ────────────────────────────

# 默认 Provider 列表（Phase 6.2）
_DEFAULT_PROVIDERS: list[StructureExtractorProvider] = [
    PythonAstExtractor(),
    JsTsRegexFallbackExtractor(),
]

# 语言 → Provider 快速查找表
_PROVIDER_MAP: dict[str, StructureExtractorProvider] = {}
_NULL_PROVIDER = NullStructureExtractor()


def _build_provider_map(providers: list[StructureExtractorProvider]) -> None:
    """构建语言 → Provider 映射"""
    _PROVIDER_MAP.clear()
    # 反向遍历：先注册的 Provider 优先
    for provider in reversed(providers):
        for lang in provider.supported_languages:
            if lang not in _PROVIDER_MAP:
                _PROVIDER_MAP[lang] = provider


# 初始化
_build_provider_map(_DEFAULT_PROVIDERS)


# ── Node bridge 自动检测 ───────────────────────────────────
# Phase 6.3: 检测 Node.js 运行时，如果可用则自动注册高置信度 JS/TS Provider

def _node_bridge_available() -> bool:
    """检测 Node bridge 是否完整可用（Node 已安装 + 脚本存在 + npm 依赖已安装）"""
    from smartdev.context.node_bridge import is_node_available
    if not is_node_available():
        return False
    bridge_script = Path(__file__).parent / "node_bridge" / "extract_structure.js"
    node_modules = Path(__file__).parent / "node_bridge" / "node_modules"
    return bridge_script.exists() and node_modules.exists()


def _try_create_node_extractor() -> StructureExtractorProvider | None:
    """尝试创建 NodeBridgeExtractor

    失败时静默返回 None（不抛异常，不中断索引流程）。
    Node bridge 的可用性在首次 extract() 时验证（单文件失败不影响索引）。
    """
    try:
        from smartdev.context.node_bridge import NodeBridgeExtractor
        return NodeBridgeExtractor()
    except Exception:
        return None


class StructureExtractor:
    """结构提取器（Provider 管理）

    管理多个语言 Provider，根据文件语言自动选择。

    使用示例：
        extractor = StructureExtractor()
        result = extractor.extract(Path("app.py"), content, "python")

    注册新 Provider：
        extractor.register_provider(TypeScriptCompilerExtractor())

    Phase 6.3 自动检测：
        初始化时自动检测 Node.js 运行时。
        如果可用 → 注册 NodeBridgeExtractor (confidence=0.95)
        如果不可用 → 保持 JsTsRegexFallbackExtractor (confidence=0.55)
    """

    def __init__(
        self,
        providers: list[StructureExtractorProvider] | None = None,
        auto_detect_node: bool = True,
    ) -> None:
        self._providers = list(providers or _DEFAULT_PROVIDERS)
        self._map: dict[str, StructureExtractorProvider] = {}
        self._rebuild_map()

        if auto_detect_node:
            self._try_register_node_bridge()

    def _try_register_node_bridge(self) -> None:
        """检测并注册 Node bridge（如果可用）

        检测顺序：
        1. Node.js 已安装（shutil.which）
        2. extract_structure.js 脚本存在
        3. npm 依赖已安装（node_modules/ 存在）
        4. Node 进程可启动

        任何一步失败 → 静默跳过，保持 regex fallback。
        """
        if not _node_bridge_available():
            return
        provider = _try_create_node_extractor()
        if provider is not None:
            self.register_provider(provider)

    def _rebuild_map(self) -> None:
        self._map.clear()
        # 反向遍历：先注册的 Provider 优先（后注册的不覆盖）
        for provider in reversed(self._providers):
            for lang in provider.supported_languages:
                if lang not in self._map:
                    self._map[lang] = provider

    def register_provider(self, provider: StructureExtractorProvider) -> None:
        """注册新 Provider（替换同语言的旧 Provider，最高优先级）"""
        # 移除已注册同语言的旧 Provider
        new_langs = set(provider.supported_languages)
        self._providers = [
            p for p in self._providers
            if not (set(p.supported_languages) & new_langs)
        ]
        self._providers.insert(0, provider)
        self._rebuild_map()

    def get_provider(self, language: str) -> StructureExtractorProvider:
        """获取语言对应的 Provider"""
        return self._map.get(language, _NULL_PROVIDER)

    def extract(self, file_path: Path, content: str,
                language: str) -> StructureExtractionResult:
        """提取文件的代码结构

        根据语言选择对应的 Provider。

        参数：
            file_path: 文件路径
            content: 文件内容
            language: 语言标识

        返回：
            StructureExtractionResult

        注意：
            - Python 提取使用 ast，confidence = 1.0
            - JS/TS 提取使用 regex fallback，confidence = 0.55
            - 不支持的语言返回空结果，无错误
        """
        provider = self.get_provider(language)
        return provider.extract(str(file_path), content)


# ── 模块级便捷函数（保持向后兼容）──────────────────────────

def extract_structure(file_path: Path, content: str,
                      language: str) -> StructureExtractionResult:
    """提取文件的代码结构（便捷函数）

    使用默认 Provider 集合（含 Phase 6.3 自动检测的 Node bridge）。

    注意：
        - Python 使用 ast，confidence = 1.0
        - JS/TS 优先使用 Node bridge（confidence = 0.95），fallback 到 regex（confidence = 0.55）
        - 不支持的语言返回空结果，无错误
    """
    extractor = StructureExtractor()
    return extractor.extract(file_path, content, language)
