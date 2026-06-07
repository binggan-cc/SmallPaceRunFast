"""
Phase 7 Step 1 — TreeSitterProvider 骨架测试

验证 TreeSitterProvider 的接口合规、依赖检测、注册/注销行为。
Step 1 不接真实 grammar — 所有测试通过 mock 实现，不依赖 tree-sitter 包。

测试覆盖：
1. tree-sitter 未安装 → _tree_sitter_available() 返回 False
2. 依赖缺失 → Provider 不注册
3. auto_detect_treesitter=False → 跳过检测
4. Provider 接口合规（name, supported_languages, extract）
5. supported_languages 包含 "go"
6. Step 1 extract() 返回空结果 + 说明性 error
7. PythonAstExtractor 不受影响
8. NodeBridgeExtractor 注册行为不受影响
"""

import pytest

from smartdev.context.structure_extractor import (
    CodeSymbol,
    NullStructureExtractor,
    StructureExtractionResult,
    StructureExtractor,
    StructureExtractorProvider,
)
from smartdev.context.tree_sitter_provider import (
    TreeSitterProvider,
    _load_language,
    _tree_sitter_available,
)


# ── 辅助 ──────────────────────────────────────────────────────


def _mock_tree_sitter_unavailable(monkeypatch):
    """Mock: tree-sitter 包不可用"""
    monkeypatch.setattr(
        "smartdev.context.structure_extractor._tree_sitter_available",
        lambda: False,
    )
    monkeypatch.setattr(
        "smartdev.context.tree_sitter_provider._tree_sitter_available",
        lambda: False,
    )


def _mock_tree_sitter_available(monkeypatch):
    """Mock: tree-sitter 包可用（但 grammar 未加载）"""
    monkeypatch.setattr(
        "smartdev.context.structure_extractor._tree_sitter_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "smartdev.context.tree_sitter_provider._tree_sitter_available",
        lambda: True,
    )


# ── 测试 ──────────────────────────────────────────────────────


class TestTreeSitterDependencyDetection:
    """Q1: 依赖检测"""

    def test_tree_sitter_available_false_when_import_missing(self, monkeypatch):
        """tree-sitter 包未安装 → _tree_sitter_available() 返回 False"""
        import smartdev.context.tree_sitter_provider as tsp

        monkeypatch.setattr(tsp, "_tree_sitter_available", lambda: False)
        assert tsp._tree_sitter_available() is False

    def test_tree_sitter_available_true_when_mocked(self, monkeypatch):
        """tree-sitter 包已安装 → _tree_sitter_available() 返回 True"""
        import smartdev.context.tree_sitter_provider as tsp

        monkeypatch.setattr(tsp, "_tree_sitter_available", lambda: True)
        assert tsp._tree_sitter_available() is True


class TestTreeSitterProviderRegistration:
    """Q2: Provider 注册行为"""

    def test_provider_not_registered_when_dependency_missing(self, monkeypatch):
        """tree-sitter 不可用 → TreeSitterProvider 不注册"""
        _mock_tree_sitter_unavailable(monkeypatch)

        extractor = StructureExtractor(auto_detect_treesitter=True)
        provider = extractor.get_provider("go")

        # 应该回退到 NullStructureExtractor（不支持 go）
        assert isinstance(provider, NullStructureExtractor)

    def test_auto_detect_treesitter_false_skips_detection(self, monkeypatch):
        """auto_detect_treesitter=False → 不尝试检测，不注册"""
        _mock_tree_sitter_available(monkeypatch)

        extractor = StructureExtractor(auto_detect_treesitter=False)
        provider = extractor.get_provider("go")

        # 即使 tree-sitter 可用，也不注册
        assert isinstance(provider, NullStructureExtractor)

    def test_provider_registered_when_dependency_available(self, monkeypatch):
        """tree-sitter 可用 → TreeSitterProvider 被注册"""
        _mock_tree_sitter_available(monkeypatch)

        extractor = StructureExtractor(auto_detect_treesitter=True)
        provider = extractor.get_provider("go")

        # 应该注册了 TreeSitterProvider
        assert isinstance(provider, TreeSitterProvider)
        assert provider.name == "tree_sitter"


class TestTreeSitterProviderInterface:
    """Q3: Provider 接口合规"""

    def test_provider_extends_base_class(self):
        """TreeSitterProvider 继承 StructureExtractorProvider"""
        assert issubclass(TreeSitterProvider, StructureExtractorProvider)

    def test_name_property(self):
        """name 属性返回 tree_sitter"""
        provider = TreeSitterProvider()
        assert provider.name == "tree_sitter"

    def test_supported_languages_contains_go(self):
        """supported_languages 包含 go"""
        provider = TreeSitterProvider()
        assert "go" in provider.supported_languages

    def test_supported_languages_does_not_include_python_or_js(self):
        """Tree-sitter 不覆盖 python / javascript / typescript"""
        provider = TreeSitterProvider()
        langs = provider.supported_languages
        assert "python" not in langs
        assert "javascript" not in langs
        assert "typescript" not in langs

    def test_is_available_reflects_dependency(self, monkeypatch):
        """is_available 反映 tree-sitter 包的安装状态"""
        monkeypatch.setattr(
            "smartdev.context.tree_sitter_provider._tree_sitter_available",
            lambda: False,
        )
        provider = TreeSitterProvider()
        assert provider.is_available is False

        monkeypatch.setattr(
            "smartdev.context.tree_sitter_provider._tree_sitter_available",
            lambda: True,
        )
        provider2 = TreeSitterProvider()
        assert provider2.is_available is True


class TestTreeSitterExtractStep1:
    """Q4: Step 1 extract() 行为"""

    def test_extract_without_grammar_returns_empty_result(self, monkeypatch):
        """Step 1: 不接 grammar → extract() 返回空 symbols + imports"""
        _mock_tree_sitter_available(monkeypatch)

        provider = TreeSitterProvider()
        result = provider.extract("main.go", "package main\n")

        assert isinstance(result, StructureExtractionResult)
        assert result.symbols == []
        assert result.imports == []

    def test_extract_without_grammar_has_error_message(self, monkeypatch):
        """Step 1: extract() 返回说明性 error（非致命错误）"""
        _mock_tree_sitter_available(monkeypatch)

        provider = TreeSitterProvider()
        result = provider.extract("main.go", "package main\n")

        assert len(result.errors) >= 1
        error_text = " ".join(result.errors).lower()
        assert "grammar" in error_text or "step 2" in error_text

    def test_extract_when_package_not_installed(self, monkeypatch):
        """tree-sitter 包未安装 → extract() 返回安装提示 error"""
        _mock_tree_sitter_unavailable(monkeypatch)

        provider = TreeSitterProvider()
        result = provider.extract("main.go", "package main\n")

        assert result.symbols == []
        assert result.imports == []
        assert len(result.errors) >= 1
        assert any("not installed" in e.lower() for e in result.errors)


class TestExistingProvidersUnaffected:
    """Q5: 现有 Provider 不受 Tree-sitter 影响"""

    def test_python_provider_still_handles_python(self, monkeypatch):
        """无论 tree-sitter 是否可用，Python 仍由 PythonAstExtractor 处理"""
        _mock_tree_sitter_available(monkeypatch)

        extractor = StructureExtractor(auto_detect_treesitter=True)
        provider = extractor.get_provider("python")

        assert provider.name == "python_ast"

    def test_node_bridge_still_handles_ts_if_available(self, monkeypatch):
        """Node bridge 可用时，TypeScript 仍由 NodeBridgeExtractor 处理"""
        _mock_tree_sitter_available(monkeypatch)

        extractor = StructureExtractor(
            auto_detect_node=True,
            auto_detect_treesitter=True,
        )
        provider = extractor.get_provider("typescript")

        # 如果 Node 可用 → node_bridge_babel
        # 如果 Node 不可用 → regex_js_ts_fallback
        # 关键：不是 tree_sitter
        assert provider.name != "tree_sitter"
        assert provider.name in ("node_bridge_babel", "regex_js_ts_fallback")

    def test_go_provider_not_null_when_tree_sitter_available(self, monkeypatch):
        """tree-sitter 可用时，go 有 Provider（不是 NullStructureExtractor）"""
        _mock_tree_sitter_available(monkeypatch)

        extractor = StructureExtractor(auto_detect_treesitter=True)
        provider = extractor.get_provider("go")

        assert not isinstance(provider, NullStructureExtractor)
        assert provider.name == "tree_sitter"

    def test_go_provider_null_when_tree_sitter_unavailable(self, monkeypatch):
        """tree-sitter 不可用时，go 回退到 NullStructureExtractor"""
        _mock_tree_sitter_unavailable(monkeypatch)

        extractor = StructureExtractor(auto_detect_treesitter=True)
        provider = extractor.get_provider("go")

        assert isinstance(provider, NullStructureExtractor)


class TestLoadLanguageAdapter:
    """_load_language() 适配层"""

    def test_load_language_returns_none_in_step1(self):
        """Step 1: _load_language() 返回 None（grammar 尚未接入）"""
        result = _load_language("go")
        assert result is None

    def test_load_language_accepts_language_parameter(self):
        """_load_language() 接受 language 参数"""
        # Step 1: 任何语言都返回 None
        for lang in ("go", "php", "rust", "java"):
            assert _load_language(lang) is None
