"""
设计令牌检测器

设计原理：
─────────
扫描 CSS/JS 文件，检测：
1. CSS 变量定义（--xxx: value）
2. 硬编码颜色值（hex, rgb, hsl）
3. Token 来源文件（tokens.css / variables.css）

为什么用正则而不用 AST？
─────────────────────────
CSS 没有标准库 AST 解析器。正则扫描颜色模式是行业标准做法：
- Chrome DevTools 用正则检测硬编码颜色
- Stylelint 的 color-no-hex 规则也是正则匹配
- 对于"是否存在"级别的检测，正则足够准确

检测的颜色格式：
─────────────
- Hex: #fff, #ffffff, #ffffff80 (带 alpha)
- RGB: rgb(255, 255, 255), rgba(...)
- HSL: hsl(0, 0%, 100%), hsla(...)
- Named: 在 JS 中直接写 "red", "blue" 等（Phase 1 不检测，噪音太大）

对应文档：
- smartPi/docs/smartdev-agent-core-spec.md §5.4（Token Governance）
- smartPi/docs/smartdev-agent-core-spec.md §9.3（UI Token Adapter）
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class HardcodedColor:
    """硬编码颜色实例

    Attributes:
        file: 文件路径
        line: 行号
        column: 列号
        value: 颜色值（如 "#ff0000"）
        format: 颜色格式（hex / rgb / hsl）
        context: 所在行内容（用于展示上下文）
    """
    file: str
    line: int
    column: int
    value: str
    format: str
    context: str = ""


@dataclass
class TokenSource:
    """Token 来源文件

    Attributes:
        path: 文件路径
        variable_count: 定义的变量数量
        variables: 变量名列表
    """
    path: str
    variable_count: int
    variables: list[str] = field(default_factory=list)


@dataclass
class DesignTokenResult:
    """设计令牌检测总结果"""
    token_sources: list[TokenSource] = field(default_factory=list)
    hardcoded_colors: list[HardcodedColor] = field(default_factory=list)

    @property
    def source_count(self) -> int:
        return len(self.token_sources)

    @property
    def has_multiple_sources(self) -> bool:
        return self.source_count > 1

    @property
    def color_count(self) -> int:
        return len(self.hardcoded_colors)

    @property
    def coverage_rate(self) -> float:
        """Token 覆盖率估算（0.0 ~ 1.0）

        简单估算：如果无硬编码颜色且有 token 定义，覆盖率 100%
        如果有硬编码颜色，按比例降低。
        """
        total = self.color_count + sum(ts.variable_count for ts in self.token_sources)
        if total == 0:
            return 0.0
        return sum(ts.variable_count for ts in self.token_sources) / total


# ── 正则模式 ──────────────────────────────────────────────

# CSS 变量定义: --variable-name: value;
_RE_CSS_VAR = re.compile(r"--([\w-]+)\s*:")

# Hex 颜色: #fff, #ffffff, #ffffff80
_RE_HEX = re.compile(
    r"#(?:[0-9a-fA-F]{3}){1,2}(?:[0-9a-fA-F]{2})?(?!\w)"
)

# RGB/RGBA: rgb(255, 0, 0) or rgba(255, 0, 0, 0.5)
_RE_RGB = re.compile(r"rgba?\(\s*\d+\s*,\s*\d+\s*,\s*\d+(?:\s*,\s*[\d.]+)?\s*\)")

# HSL/HSLA: hsl(0, 100%, 50%) or hsla(0, 100%, 50%, 0.5)
_RE_HSL = re.compile(r"hsla?\(\s*\d+(?:\.\d+)?\s*,\s*[\d.]+%\s*,\s*[\d.]+%(?:\s*,\s*[\d.]+)?\s*\)")


def _is_token_file(file_path: Path) -> bool:
    """判断文件是否可能是 Token 定义文件"""
    name = file_path.name.lower()
    return any(keyword in name for keyword in [
        "token", "variable", "theme", "design",
    ])


def _scan_file_for_tokens(file_path: Path) -> tuple[list[str], list[HardcodedColor]]:
    """扫描单个文件，返回 (变量定义, 硬编码颜色)"""
    try:
        source = file_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return [], []

    lines = source.splitlines()
    variables = []
    colors = []

    for line_num, line in enumerate(lines, 1):
        # 跳过注释
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue

        # 检测 CSS 变量定义
        for match in _RE_CSS_VAR.finditer(line):
            variables.append(match.group(1))

        # 检测硬编码颜色（跳过 CSS 变量定义行中的值）
        if _RE_CSS_VAR.search(line):
            continue  # 变量定义行中的颜色不算硬编码

        for pattern, fmt in [(_RE_HEX, "hex"), (_RE_RGB, "rgb"), (_RE_HSL, "hsl")]:
            for match in pattern.finditer(line):
                colors.append(HardcodedColor(
                    file=str(file_path),
                    line=line_num,
                    column=match.start(),
                    value=match.group(),
                    format=fmt,
                    context=stripped[:100],
                ))

    return variables, colors


def detect_design_tokens(project_path: Path) -> DesignTokenResult:
    """检测项目的设计令牌状态

    参数：
        project_path: 项目根目录路径

    返回：
        DesignTokenResult，包含 Token 来源和硬编码颜色清单
    """
    result = DesignTokenResult()
    skip_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv"}

    # 扫描 CSS 和 JS 文件
    extensions = {".css", ".scss", ".less", ".js", ".ts", ".jsx", ".tsx", ".vue", ".svelte"}

    for ext in extensions:
        for file_path in project_path.rglob(f"*{ext}"):
            # 跳过隐藏目录和缓存
            parts = file_path.relative_to(project_path).parts
            if any(p.startswith(".") or p in skip_dirs for p in parts):
                continue

            variables, colors = _scan_file_for_tokens(file_path)

            # 如果有变量定义，记录为 Token 来源
            if variables:
                result.token_sources.append(TokenSource(
                    path=str(file_path.relative_to(project_path)),
                    variable_count=len(variables),
                    variables=variables,
                ))

            # 记录硬编码颜色
            result.hardcoded_colors.extend(colors)

    return result
