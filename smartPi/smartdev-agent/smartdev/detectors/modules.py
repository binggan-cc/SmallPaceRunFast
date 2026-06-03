"""
模块依赖检测器

设计原理：
─────────
通过解析 Python 源码的 AST（抽象语法树）来分析模块之间的依赖关系。
比正则匹配更准确——不会误匹配注释和字符串中的 import。

为什么用 ast 而非正则？
─────────────────────
1. 正则 `^import xxx` 会匹配注释中的 import
2. 正则无法处理 `from xxx import yyy` 的变体
3. ast 解析的是真实语法树，100% 准确
4. ast 是标准库，零依赖

检测能力：
─────────
1. 模块列表：项目中所有 Python 模块
2. 依赖关系：每个模块 import 了哪些其他模块
3. 外部依赖：哪些 import 不属于项目内部
4. 循环依赖：检测 A→B→A 的循环

对应文档：
- smartPi/docs/smartdev-agent-core-spec.md §5.2（架构分析）
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ModuleInfo:
    """单个模块的信息

    Attributes:
        name: 模块名称（如 "smartdev.core.risk"）
        path: 文件路径
        internal_imports: 项目内部的 import
        external_imports: 外部依赖的 import
        line_count: 代码行数（不含空行和注释）
    """
    name: str
    path: str
    internal_imports: list[str] = field(default_factory=list)
    external_imports: list[str] = field(default_factory=list)
    line_count: int = 0


@dataclass
class ModuleAnalysisResult:
    """模块分析总结果"""
    modules: list[ModuleInfo] = field(default_factory=list)
    circular_deps: list[list[str]] = field(default_factory=list)

    @property
    def module_names(self) -> list[str]:
        return [m.name for m in self.modules]

    def get_module(self, name: str) -> ModuleInfo | None:
        for m in self.modules:
            if m.name == name:
                return m
        return None


def _parse_imports(file_path: Path) -> tuple[list[str], list[str]]:
    """解析单个 Python 文件的 import 语句

    使用 ast 解析，准确识别：
    - import xxx
    - from xxx import yyy
    - from xxx import yyy as zzz

    返回：
        (internal_imports, external_imports)
    """
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError):
        return [], []

    internal = []
    external = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name.split(".")[0]
                internal.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                module = node.module.split(".")[0]
                internal.append(node.module)

    # 去重
    internal = list(dict.fromkeys(internal))
    return internal, external


def _count_lines(file_path: Path) -> int:
    """统计代码行数（不含空行和注释）"""
    try:
        source = file_path.read_text(encoding="utf-8")
        lines = source.splitlines()
        count = 0
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                count += 1
        return count
    except (UnicodeDecodeError, OSError):
        return 0


def _detect_circular_deps(modules: list[ModuleInfo]) -> list[list[str]]:
    """检测循环依赖

    通过 DFS 遍历依赖图，找到环。
    只检测项目内部模块之间的循环。
    """
    # 构建邻接表（只保留项目内部模块）
    module_names = {m.name for m in modules}
    graph: dict[str, list[str]] = {}
    for m in modules:
        graph[m.name] = [
            imp for imp in m.internal_imports
            if imp in module_names and imp != m.name
        ]

    # DFS 检测环
    visited = set()
    rec_stack = set()
    cycles = []

    def _dfs(node: str, path: list[str]) -> None:
        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                _dfs(neighbor, path)
            elif neighbor in rec_stack:
                # 找到环
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:] + [neighbor]
                cycles.append(cycle)

        path.pop()
        rec_stack.discard(node)

    for m in modules:
        if m.name not in visited:
            _dfs(m.name, [])

    return cycles


def detect_modules(project_path: Path) -> ModuleAnalysisResult:
    """检测项目的模块结构和依赖关系

    参数：
        project_path: 项目根目录路径

    返回：
        ModuleAnalysisResult，包含模块列表和循环依赖
    """
    result = ModuleAnalysisResult()
    module_names = set()

    # 第一遍：收集所有 Python 模块
    for py_file in sorted(project_path.rglob("*.py")):
        # 跳过隐藏目录和缓存目录
        parts = py_file.relative_to(project_path).parts
        if any(p.startswith(".") or p in ("__pycache__", "node_modules", ".venv", "venv") for p in parts):
            continue

        # 计算模块名
        rel = py_file.relative_to(project_path)
        module_name = str(rel.with_suffix("")).replace("/", ".").replace("\\", ".")

        # 跳过 __init__.py（不作为独立模块统计）
        if py_file.name == "__init__.py":
            continue

        internal, external = _parse_imports(py_file)
        line_count = _count_lines(py_file)

        module_info = ModuleInfo(
            name=module_name,
            path=str(rel),
            internal_imports=internal,
            external_imports=external,
            line_count=line_count,
        )
        result.modules.append(module_info)
        module_names.add(module_name)

    # 第二遍：过滤 internal_imports，只保留项目内部的
    for m in result.modules:
        m.internal_imports = [
            imp for imp in m.internal_imports
            if imp in module_names
        ]

    # 检测循环依赖
    result.circular_deps = _detect_circular_deps(result.modules)

    return result
