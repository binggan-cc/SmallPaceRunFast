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
4. Step 1 为纯骨架 — 不接真实 grammar，不提取代码结构

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


# ── 依赖检测 ──────────────────────────────────────────────

def _tree_sitter_available() -> bool:
    """检测 tree-sitter Python binding 是否可用

    在 Provider 注册前判断。不抛异常。
    tree-sitter 包未安装或导入失败 → 返回 False。
    """
    try:
        import tree_sitter  # noqa: F401
        return True
    except ImportError:
        return False


# ── Grammar 加载适配层 ──────────────────────────────────────

def _load_language(language: str):
    """语言 grammar 加载适配层

    封装 grammar 加载的所有变体：
    - tree-sitter-{lang} 预编译 wheel
    - tree_sitter.Language(path, name)
    - 动态 .so 文件
    - 未来可能的其它 tree-sitter language package

    Phase 7 Step 1: 骨架，不接真实 grammar。
    此方法保留为未来扩展点。

    返回：
        Language 对象（成功时）
        None（grammar 不可用时）

    异常不会传播到调用方。
    """
    # Step 1: 不接真实 grammar。返回 None 表示暂不可用。
    return None


# ── TreeSitterProvider ─────────────────────────────────────

class TreeSitterProvider(StructureExtractorProvider):
    """Tree-sitter 多语言结构提取器

    作为 optional multi-language provider，提供 Go/PHP/Rust/Java 等
    语言的代码结构提取。不覆盖 python / javascript / typescript。

    Step 1: 纯骨架 — 实现 Provider 接口，但不接任何真实 grammar。
    extract() 返回空结果 + 说明性 error。

    confidence = 0.98（grammar 正常加载时）
    extractor = tree_sitter

    使用示例：
        provider = TreeSitterProvider()
        if provider.is_available:
            result = provider.extract("main.go", content)
    """

    def __init__(self) -> None:
        self._available = _tree_sitter_available()
        # Step 1: 不加载真实 grammar
        self._languages: dict[str, object] = {}

    @property
    def name(self) -> str:
        return "tree_sitter"

    @property
    def supported_languages(self) -> list[str]:
        """Tree-sitter 支持的语言列表

        Step 1: 声明 go 为试点语言，但不加载 grammar。
        后续 Step 2+ 通过 _load_language("go") 激活。
        """
        return ["go"]

    @property
    def is_available(self) -> bool:
        """tree-sitter 包是否已安装"""
        return self._available

    def extract(self, file_path: str, content: str) -> StructureExtractionResult:
        """提取文件的代码结构

        Step 1: 不接真实 grammar。始终返回空结果 + 说明性 error。
        后续 Step 2 接入 tree-sitter-go 后才做真实解析。
        """
        if not self._available:
            return StructureExtractionResult(
                symbols=[],
                imports=[],
                errors=["tree-sitter Python package not installed"],
            )

        # Step 1: grammar 尚未加载
        errors: list[str] = [
            "tree-sitter grammar not loaded — "
            "Go extraction will be available in Phase 7 Step 2",
        ]

        return StructureExtractionResult(
            symbols=[],
            imports=[],
            errors=errors,
        )
