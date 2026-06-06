"""
StructureExtractor 测试

验证 Provider 机制和多语言结构提取：
1. PythonAstExtractor — 精确提取（confidence=1.0）
2. JsTsRegexFallbackExtractor — fallback 提取（confidence=0.55）
3. Provider 注册和选择
4. NullStructureExtractor — 不支持语言
5. 边界情况
"""

from pathlib import Path

import pytest

from smartdev.context.structure_extractor import (
    CodeSymbol,
    JsTsRegexFallbackExtractor,
    NullStructureExtractor,
    PythonAstExtractor,
    StructureExtractionResult,
    StructureExtractor,
    extract_structure,
)


# ── Provider 机制测试 ─────────────────────────────────────

class TestProviderMechanism:
    """Provider 注册和选择机制"""

    def test_default_providers(self):
        """默认 Provider 包含 Python ast 和 JS/TS regex"""
        extractor = StructureExtractor()
        py_provider = extractor.get_provider("python")
        js_provider = extractor.get_provider("javascript")
        ts_provider = extractor.get_provider("typescript")

        assert isinstance(py_provider, PythonAstExtractor)
        assert isinstance(js_provider, JsTsRegexFallbackExtractor)
        assert isinstance(ts_provider, JsTsRegexFallbackExtractor)

    def test_unsupported_returns_null(self):
        """不支持的语言返回 NullStructureExtractor"""
        extractor = StructureExtractor()
        go_provider = extractor.get_provider("go")
        assert isinstance(go_provider, NullStructureExtractor)

    def test_register_provider(self):
        """注册新 Provider 会覆盖同语言的旧 Provider"""

        class CustomPythonExtractor(PythonAstExtractor):
            @property
            def name(self):
                return "custom_python"

        extractor = StructureExtractor()
        extractor.register_provider(CustomPythonExtractor())

        provider = extractor.get_provider("python")
        assert provider.name == "custom_python"

    def test_provider_name(self):
        """Provider 名称正确"""
        assert PythonAstExtractor().name == "python_ast"
        assert JsTsRegexFallbackExtractor().name == "regex_js_ts_fallback"

    def test_provider_supported_languages(self):
        """支持的语言列表正确"""
        assert "python" in PythonAstExtractor().supported_languages
        assert "javascript" in JsTsRegexFallbackExtractor().supported_languages
        assert "typescript" in JsTsRegexFallbackExtractor().supported_languages
        assert "vue" in JsTsRegexFallbackExtractor().supported_languages

    def test_regex_fallback_limitations(self):
        """Regex fallback 有明确的 limitations"""
        provider = JsTsRegexFallbackExtractor()
        limits = provider.limitations
        assert "no_nested_scope_resolution" in limits
        assert "no_type_resolution" in limits
        assert "no_jsx_component_semantics" in limits


# ── Python ast 提取 ───────────────────────────────────────

class TestPythonAstExtractor:
    """PythonAstExtractor 精确提取"""

    def test_extract_functions(self):
        """提取 def 和 async def"""
        content = '''
def hello():
    pass

async def fetch_data():
    pass

def greet(name: str) -> str:
    return f"Hello {name}"
'''
        provider = PythonAstExtractor()
        result = provider.extract("app.py", content)
        funcs = [s for s in result.symbols if s.kind == "function"]

        assert len(funcs) == 3
        names = {f.name for f in funcs}
        assert "hello" in names
        assert "fetch_data" in names
        assert "greet" in names

    def test_extract_classes_and_methods(self):
        """提取 class 和内部方法"""
        content = '''
class UserManager:
    def __init__(self):
        self.users = []

    def add_user(self, name):
        self.users.append(name)

    async def fetch_user(self, id):
        pass

class _PrivateHelper:
    pass
'''
        provider = PythonAstExtractor()
        result = provider.extract("models.py", content)

        classes = [s for s in result.symbols if s.kind == "class"]
        assert len(classes) == 2
        class_names = {c.name for c in classes}
        assert "UserManager" in class_names
        assert "_PrivateHelper" in class_names

        methods = [s for s in result.symbols if s.kind == "method"]
        assert len(methods) == 3

        add_user = [m for m in methods if m.name == "add_user"][0]
        assert add_user.parent == "UserManager"

    def test_extract_imports(self):
        """提取 import 和 from...import"""
        content = '''
import os
from pathlib import Path
from smartdev.models import SkillResult, RiskLevel
'''
        provider = PythonAstExtractor()
        result = provider.extract("utils.py", content)

        imports = [s for s in result.symbols if s.kind == "import"]
        assert len(imports) == 3
        assert len(result.imports) == 3

    def test_extract_variables(self):
        """提取模块级变量"""
        content = '''
VERSION = "1.0.0"
MAX_RETRIES = 3
_private = "secret"
'''
        provider = PythonAstExtractor()
        result = provider.extract("config.py", content)
        variables = [s for s in result.symbols if s.kind == "variable"]

        assert len(variables) == 3
        names = {v.name for v in variables}
        assert "VERSION" in names
        assert "MAX_RETRIES" in names

    def test_confidence_is_one(self):
        """Python ast 提取 confidence = 1.0"""
        content = "def f(): pass\n"
        provider = PythonAstExtractor()
        result = provider.extract("a.py", content)
        assert all(s.confidence == 1.0 for s in result.symbols)

    def test_extractor_field(self):
        """extractor 字段标识来源"""
        content = "def f(): pass\n"
        provider = PythonAstExtractor()
        result = provider.extract("a.py", content)
        assert all(s.extractor == "python_ast" for s in result.symbols)

    def test_exported_detection(self):
        """导出 vs 私有"""
        content = '''
def public_func(): pass
def _private_func(): pass
class PublicClass: pass
class _PrivateClass: pass
'''
        provider = PythonAstExtractor()
        result = provider.extract("mod.py", content)
        exported = {s.name for s in result.symbols if s.is_exported}
        private = {s.name for s in result.symbols if not s.is_exported}

        assert "public_func" in exported
        assert "_private_func" in private
        assert "PublicClass" in exported
        assert "_PrivateClass" in private

    def test_syntax_error(self):
        """语法错误返回 errors"""
        content = "def broken(\n  missing paren"
        provider = PythonAstExtractor()
        result = provider.extract("bad.py", content)
        assert len(result.errors) > 0
        assert "语法错误" in result.errors[0]
        assert result.symbols == []


# ── JS/TS regex fallback 提取 ────────────────────────────

class TestJsTsRegexFallbackExtractor:
    """JsTsRegexFallbackExtractor fallback 提取"""

    def test_extract_functions(self):
        """提取 function 声明"""
        content = '''
function hello() { return "world"; }
export async function fetchData() { return await fetch("/api"); }
'''
        provider = JsTsRegexFallbackExtractor()
        result = provider.extract("app.js", content)
        funcs = [s for s in result.symbols if s.kind == "function"]

        assert len(funcs) == 2
        names = {f.name for f in funcs}
        assert "hello" in names
        assert "fetchData" in names

    def test_extract_arrow_functions(self):
        """提取箭头函数"""
        content = '''
const add = (a, b) => a + b;
const multiply = async (x) => x * 2;
'''
        provider = JsTsRegexFallbackExtractor()
        result = provider.extract("utils.js", content)
        funcs = [s for s in result.symbols if s.kind == "function"]

        assert len(funcs) == 2
        names = {f.name for f in funcs}
        assert "add" in names
        assert "multiply" in names

    def test_extract_classes(self):
        """提取 class 定义"""
        content = '''
class UserService { constructor() { this.users = []; } }
export class APIError extends Error { }
'''
        provider = JsTsRegexFallbackExtractor()
        result = provider.extract("classes.js", content)
        classes = [s for s in result.symbols if s.kind == "class"]

        assert len(classes) == 2
        names = {c.name for c in classes}
        assert "UserService" in names
        assert "APIError" in names

    def test_extract_imports(self):
        """提取 import 和 require"""
        content = '''
import React from "react";
import { useState } from "react";
const axios = require("axios");
'''
        provider = JsTsRegexFallbackExtractor()
        result = provider.extract("app.jsx", content)
        imports = [s for s in result.symbols if s.kind == "import"]

        assert len(imports) == 3
        assert len(result.imports) == 3

    def test_confidence_is_low(self):
        """regex fallback confidence = 0.55"""
        content = "function f() {}\n"
        provider = JsTsRegexFallbackExtractor()
        result = provider.extract("a.js", content)
        assert all(s.confidence == 0.55 for s in result.symbols)

    def test_extractor_field(self):
        """extractor 字段标识为 regex fallback"""
        content = "function f() {}\n"
        provider = JsTsRegexFallbackExtractor()
        result = provider.extract("a.js", content)
        assert all(s.extractor == "regex_js_ts_fallback" for s in result.symbols)

    def test_limitations_in_symbols(self):
        """符号包含 limitations 信息"""
        content = "function f() {}\n"
        provider = JsTsRegexFallbackExtractor()
        result = provider.extract("a.js", content)
        for s in result.symbols:
            assert "no_nested_scope_resolution" in s.limitations
            assert "no_type_resolution" in s.limitations


# ── Null 提取器 ──────────────────────────────────────────

class TestNullStructureExtractor:
    """不支持语言的占位"""

    def test_returns_empty(self):
        """不支持语言返回空结果，无错误"""
        provider = NullStructureExtractor()
        result = provider.extract("main.go", "package main")
        assert result.symbols == []
        assert result.imports == []
        assert result.errors == []


# ── 便捷函数 ─────────────────────────────────────────────

class TestExtractConvenienceFunction:
    """extract_structure 便捷函数"""

    def test_python(self):
        """Python 提取"""
        content = "def f(): pass\n"
        result = extract_structure(Path("a.py"), content, "python")
        assert len(result.symbols) == 1
        assert result.symbols[0].confidence == 1.0

    def test_javascript(self):
        """JS 提取"""
        content = "function f() {}\n"
        result = extract_structure(Path("a.js"), content, "javascript")
        assert len(result.symbols) == 1
        assert result.symbols[0].confidence == 0.55

    def test_unsupported(self):
        """不支持语言"""
        result = extract_structure(Path("a.go"), "package main", "go")
        assert result.symbols == []


# ── 真实场景 ──────────────────────────────────────────────

class TestRealWorldScenarios:
    """真实代码场景"""

    def test_python_module(self):
        """提取真实 Python 模块"""
        content = '''"""
SmartDev Agent 项目索引
"""

from __future__ import annotations
from pathlib import Path
import json

MAX_DEPTH = 10

class ProjectIndex:
    """项目索引"""

    def __init__(self, path: Path):
        self.path = path

    def scan(self):
        pass

    async def async_scan(self):
        pass

def create_index(path: Path) -> ProjectIndex:
    return ProjectIndex(path)
'''
        result = extract_structure(Path("index.py"), content, "python")

        kinds = {s.kind for s in result.symbols}
        assert "class" in kinds
        assert "method" in kinds
        assert "function" in kinds
        assert "import" in kinds
        assert "variable" in kinds

        methods = [s for s in result.symbols if s.kind == "method"]
        assert len(methods) == 3

    def test_typescript_file(self):
        """提取 TypeScript 文件"""
        content = '''
import { Component } from "react";

interface Props {
    name: string;
}

export class MyComponent extends Component<Props> {
    render() {
        return null;
    }
}

const helper = () => {};
'''
        result = extract_structure(Path("MyComponent.tsx"), content, "typescript")

        kinds = {s.kind for s in result.symbols}
        assert "import" in kinds
        assert "class" in kinds
        assert "function" in kinds

    def test_mixed_confidence(self):
        """混合语言时 confidence 不同"""
        py_result = extract_structure(Path("a.py"), "def f(): pass\n", "python")
        js_result = extract_structure(Path("a.js"), "function f() {}\n", "javascript")

        assert py_result.symbols[0].confidence == 1.0
        assert js_result.symbols[0].confidence == 0.55
