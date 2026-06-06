"""
NodeBridgeExtractor 测试

验证 Node bridge 集成：
1. Node 不存在时 fallback 不报错
2. auto_detect_node=False 可禁用自动检测
3. Node bridge 可用时注册替换 JS/TS provider
4. Node 输出转 CodeSymbol 正确
5. PythonAstExtractor 不受影响
6. register_provider 后 JS/TS 被替换
7. NodeBridgeExtractor 独立测试（使用 mock subprocess）

注意：
- 大部分测试不依赖真实 Node 环境
- 真实 Node 集成测试用 skipif 保护
"""

import json
import shutil
from pathlib import Path

import pytest

from smartdev.context.node_bridge import (
    NodeBridgeExtractor,
    _convert_node_result,
    is_node_available,
)
from smartdev.context.structure_extractor import (
    CodeSymbol,
    JsTsRegexFallbackExtractor,
    PythonAstExtractor,
    StructureExtractor,
)


# ── 辅助函数 ──────────────────────────────────────────────


def _mock_no_node(monkeypatch):
    """Mock: Node.js 不可用"""
    monkeypatch.setattr(shutil, "which", lambda _cmd: None)


def _mock_node_node_modules(monkeypatch, tmp_path):
    """Mock: Node.js 可用但 node_modules 不存在"""
    monkeypatch.setattr(shutil, "which", lambda _cmd: "/usr/local/bin/node")
    # 重写 _node_bridge_available 的路径检查
    import smartdev.context.structure_extractor as se
    monkeypatch.setattr(
        se.Path(__file__).parent,  # noqa
        "parent",
        # 返回 tmp_path，其中不含 node_bridge/
    )
    # 更简洁的方式：直接 mock _node_bridge_available
    monkeypatch.setattr(se, "_node_bridge_available", lambda: False)


# ── 测试类 ────────────────────────────────────────────────


class TestNodeDetection:
    """Node 可用性检测"""

    def test_is_node_available_returns_bool(self):
        """is_node_available 返回 bool"""
        result = is_node_available()
        assert isinstance(result, bool)

    def test_auto_detect_disabled_keeps_regex(self):
        """auto_detect_node=False 时保留 regex fallback"""
        extractor = StructureExtractor(auto_detect_node=False)
        js_provider = extractor.get_provider("javascript")
        ts_provider = extractor.get_provider("typescript")

        assert isinstance(js_provider, JsTsRegexFallbackExtractor)
        assert isinstance(ts_provider, JsTsRegexFallbackExtractor)

    def test_node_not_available_fallback(self, monkeypatch):
        """Node 不存在时：不注册 NodeBridgeExtractor，保持 regex"""
        monkeypatch.setattr(
            "smartdev.context.node_bridge.is_node_available",
            lambda: False,
        )
        monkeypatch.setattr(
            "smartdev.context.structure_extractor._node_bridge_available",
            lambda: False,
        )

        extractor = StructureExtractor()
        js_provider = extractor.get_provider("javascript")
        assert isinstance(js_provider, JsTsRegexFallbackExtractor)

    def test_python_ast_unaffected_by_node_detection(self):
        """无论 Node 是否可用，PythonAstExtractor 始终存在"""
        extractor = StructureExtractor()  # auto detect on
        py_provider = extractor.get_provider("python")
        assert isinstance(py_provider, PythonAstExtractor)


class TestProviderRegistration:
    """Provider 注册和替换"""

    def test_register_node_extractor_manually(self):
        """手动注册 NodeBridgeExtractor 后替换 JS/TS provider"""
        extractor = StructureExtractor(auto_detect_node=False)
        extractor.register_provider(NodeBridgeExtractor())

        js_provider = extractor.get_provider("javascript")
        ts_provider = extractor.get_provider("typescript")

        assert isinstance(js_provider, NodeBridgeExtractor)
        assert isinstance(ts_provider, NodeBridgeExtractor)

    def test_register_custom_provider_preserves_others(self):
        """注册自定义 Provider 后不影响 Python Ast"""
        extractor = StructureExtractor(auto_detect_node=False)
        extractor.register_provider(NodeBridgeExtractor())

        py_provider = extractor.get_provider("python")
        assert isinstance(py_provider, PythonAstExtractor)


class TestNodeResultConversion:
    """Node bridge JSON → Python CodeSymbol 转换"""

    def test_convert_function_symbol(self):
        """function 类型转换正确"""
        result = {
            "symbols": [
                {
                    "name": "App",
                    "kind": "function",
                    "file_path": "src/App.tsx",
                    "start_line": 3,
                    "end_line": 8,
                    "signature": "export default function App()",
                    "parent": "",
                    "is_exported": True,
                    "confidence": 0.95,
                    "extractor": "node_bridge_babel",
                    "limitations": [],
                }
            ],
            "imports": [],
            "errors": [],
        }

        output = _convert_node_result(result, "src/App.tsx")

        assert len(output.symbols) == 1
        sym = output.symbols[0]
        assert sym.name == "App"
        assert sym.kind == "function"
        assert sym.file_path == "src/App.tsx"
        assert sym.start_line == 3
        assert sym.end_line == 8
        assert sym.signature == "export default function App()"
        assert sym.is_exported is True
        assert sym.confidence == 0.95
        assert sym.extractor == "node_bridge_babel"
        assert len(output.errors) == 0

    def test_convert_class_symbol(self):
        """class 类型转换正确"""
        result = {
            "symbols": [
                {
                    "name": "MyComponent",
                    "kind": "class",
                    "file_path": "src/comp.tsx",
                    "start_line": 1,
                    "end_line": 10,
                    "signature": "class MyComponent extends React.Component",
                    "parent": "",
                    "is_exported": True,
                    "confidence": 0.95,
                    "extractor": "node_bridge_babel",
                    "limitations": [],
                }
            ],
            "imports": [],
            "errors": [],
        }

        output = _convert_node_result(result, "src/comp.tsx")
        assert len(output.symbols) == 1
        assert output.symbols[0].name == "MyComponent"
        assert output.symbols[0].kind == "class"

    def test_convert_import_symbol(self):
        """import 类型转换正确（结构化 → raw string）"""
        result = {
            "symbols": [
                {
                    "name": "react",
                    "kind": "import",
                    "file_path": "src/App.tsx",
                    "start_line": 1,
                    "end_line": 1,
                    "signature": "import React from 'react'",
                    "parent": "",
                    "is_exported": False,
                    "confidence": 0.95,
                    "extractor": "node_bridge_babel",
                    "limitations": [],
                }
            ],
            "imports": [
                {
                    "raw": "import React from 'react'",
                    "source": "react",
                    "specifiers": [{"imported": "default", "local": "React"}],
                    "line": 1,
                }
            ],
            "errors": [],
        }

        output = _convert_node_result(result, "src/App.tsx")
        assert len(output.imports) == 1
        assert output.imports[0] == "import React from 'react'"

    def test_convert_includes_errors(self):
        """errors 正确传递"""
        result = {
            "symbols": [],
            "imports": [],
            "errors": ["Parse error: unexpected token"],
        }

        output = _convert_node_result(result, "test.js")
        assert len(output.errors) == 1
        assert "Parse error" in output.errors[0]

    def test_convert_empty_result(self):
        """空结果不出错"""
        result = {"symbols": [], "imports": [], "errors": []}
        output = _convert_node_result(result, "empty.ts")
        assert output.symbols == []
        assert output.imports == []
        assert output.errors == []

    def test_convert_missing_fields_uses_defaults(self):
        """缺少字段时使用默认值"""
        result = {
            "symbols": [{"name": "x"}],
            "imports": [],
            "errors": [],
        }
        output = _convert_node_result(result, "minimal.ts")
        assert output.symbols[0].name == "x"
        assert output.symbols[0].kind == ""
        assert output.symbols[0].start_line == 0
        assert output.symbols[0].confidence == 0.95
        assert output.symbols[0].extractor == "node_bridge_babel"


class TestNodeBridgeExtractorInterface:
    """NodeBridgeExtractor 接口合规"""

    def test_name_property(self):
        """name 正确"""
        extractor = NodeBridgeExtractor()
        assert extractor.name == "node_bridge_babel"

    def test_supported_languages(self):
        """supported_languages 包含 JS/TS"""
        extractor = NodeBridgeExtractor()
        langs = extractor.supported_languages
        assert "javascript" in langs
        assert "typescript" in langs

    def test_extract_returns_structure_extraction_result(self):
        """extract() 始终返回 StructureExtractionResult（不抛异常）"""
        from smartdev.context.structure_extractor import StructureExtractionResult

        extractor = NodeBridgeExtractor()
        result = extractor.extract("test.js", "const x = 1;")
        assert isinstance(result, StructureExtractionResult)
        # Node 可用时：返回 symbols（无 errors）
        # Node 不可用时：返回 errors
        assert isinstance(result.symbols, list)
        assert isinstance(result.imports, list)
        assert isinstance(result.errors, list)


# ── 真实 Node 集成测试（需要 Node 环境）───────────────────


@pytest.mark.skipif(
    shutil.which("node") is None,
    reason="Node.js not installed",
)
class TestNodeBridgeIntegration:
    """需要真实 Node.js 运行时的集成测试"""

    def test_node_bridge_extract_function(self):
        """Node bridge 提取 function"""
        extractor = NodeBridgeExtractor()
        result = extractor.extract(
            "test.js",
            "export function hello() {\n  return 'world';\n}\n",
        )
        assert len(result.symbols) > 0
        func_symbols = [s for s in result.symbols if s.kind == "function"]
        assert len(func_symbols) == 1
        assert func_symbols[0].name == "hello"
        assert func_symbols[0].is_exported is True
        assert func_symbols[0].confidence == 0.95
        assert func_symbols[0].extractor == "node_bridge_babel"

    def test_node_bridge_extract_class(self):
        """Node bridge 提取 class"""
        extractor = NodeBridgeExtractor()
        result = extractor.extract(
            "test.ts",
            "export class MyService {\n  doStuff() {}\n}\n",
        )
        class_symbols = [s for s in result.symbols if s.kind == "class"]
        assert len(class_symbols) == 1
        assert class_symbols[0].name == "MyService"
        assert class_symbols[0].is_exported is True

    def test_node_bridge_extract_import(self):
        """Node bridge 提取 import"""
        extractor = NodeBridgeExtractor()
        result = extractor.extract(
            "test.ts",
            "import { useState, useEffect } from 'react';\n",
        )
        assert len(result.imports) >= 1
        assert any("react" in imp for imp in result.imports)

    def test_node_bridge_extract_arrow_function(self):
        """Node bridge 提取箭头函数"""
        extractor = NodeBridgeExtractor()
        result = extractor.extract(
            "test.tsx",
            "const Button = () => {\n  return <button>Click</button>;\n};\n",
        )
        func_symbols = [s for s in result.symbols if s.kind == "function"]
        assert len(func_symbols) >= 1
        assert any(s.name == "Button" for s in func_symbols)

    def test_node_bridge_registered_in_structure_extractor(self):
        """Node 可用时 StructureExtractor 自动注册 NodeBridgeExtractor"""
        extractor = StructureExtractor()  # auto_detect_node=True (default)
        js_provider = extractor.get_provider("javascript")
        assert isinstance(js_provider, NodeBridgeExtractor)
