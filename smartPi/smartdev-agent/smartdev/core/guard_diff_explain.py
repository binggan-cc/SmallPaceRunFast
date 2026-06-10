"""
Guard: diff.explain — Patch 级差异解释（R0 只读）

功能：
─────
在已有 git.diff.explain（仓库级）基础上，增加 patch 专属信号：
  - 逻辑分组（按目录层级将文件分组）
  - 测试伴随（检查是否有对应测试文件）
  - 依赖匹配（manifest 变更 ↔ 源码变更）
  - 跨模块检测
  - 审查顺序建议

设计约束：
─────────
- 零外部依赖（标准库 + Path）
- 确定性规则引擎，不调用模型
- 无 git 环境也能运行（基于显式输入）
- R0 只读 — 不修改任何文件
- 消费 git.diff.explain 既有信号 + patch 专属逻辑分组/测试伴随

对应文档：
- docs/phase-11b-design.md §3.5（diff.explain 详细设计）
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


# ── 文件分类 ──────────────────────────────────────────────────

# 测试文件特征
_TEST_PATTERNS = ("test_", "_test.", "/test/", "/tests/", "spec.", ".spec.")

# 文档文件扩展名
_DOC_EXTS = {".md", ".rst", ".txt", ".adoc"}

# 依赖 manifest 文件名（与 git.diff.explain 保持一致）
_MANIFEST_FILES = {
    "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt",
    "Pipfile", "Pipfile.lock", "poetry.lock", "go.mod", "go.sum",
    "Cargo.toml", "Cargo.lock", "Gemfile", "Gemfile.lock",
    "build.gradle", "pom.xml",
}

# 常规配置文件扩展名
_CONFIG_EXTS = {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env"}
_CONFIG_NAMES = {
    ".gitignore", ".gitattributes", ".editorconfig", "Makefile",
    "Dockerfile", "docker-compose.yml", ".dockerignore",
}

# Lock 文件名（用于依赖匹配检查）
_LOCK_FILES = {
    "poetry.lock", "uv.lock", "package-lock.json", "pnpm-lock.yaml",
    "yarn.lock", "go.sum", "Cargo.lock", "Gemfile.lock", "Pipfile.lock",
}

# 保护目录（不应被随意修改）
_PROTECTED_DIRS = {".git", ".smartdev", "node_modules", "dist", "build"}

# 常见的项目根前缀，这些目录本身不是功能模块而是容器
_PROJECT_ROOT_PREFIXES = {"smartdev", "src", "app", "lib", "pkg", "internal"}


def _classify_file(path: str) -> str:
    """将文件路径分类为：test / doc / manifest / config / source / other。

    与 git.diff.explain 的 _classify_file 保持一致的分类逻辑。
    """
    p = Path(path)
    name = p.name
    name_lower = name.lower()
    path_lower = path.lower()

    if name_lower in _MANIFEST_FILES:
        return "manifest"
    if any(pat in path_lower for pat in _TEST_PATTERNS):
        return "test"
    if p.suffix in _DOC_EXTS:
        return "doc"
    # 配置文件：按文件名（含 dotfiles）或扩展名匹配
    # 注: Path(".env").suffix 返回 ""（因为前导点被当作 stem），
    #      所以需要额外按 name 匹配 dotfile 配置文件名
    if name_lower in _CONFIG_NAMES or p.suffix in _CONFIG_EXTS or name_lower in _CONFIG_EXTS:
        return "config"
    if p.suffix in {".py", ".js", ".ts", ".jsx", ".tsx", ".go",
                    ".java", ".rs", ".cpp", ".c", ".cs", ".rb", ".php"}:
        return "source"
    return "other"


# ── Diff 内容解析 ─────────────────────────────────────────────

def _parse_diff_content(diff_text: str | None) -> tuple[int, int]:
    """解析 unified diff 文本，统计新增行和删除行。

    Args:
        diff_text: unified diff 格式文本，或 None

    Returns:
        (insertions, deletions) 元组
    """
    if not diff_text:
        return 0, 0

    insertions = 0
    deletions = 0
    for line in diff_text.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            insertions += 1
        elif line.startswith("-") and not line.startswith("---"):
            deletions += 1
    return insertions, deletions


# ── 信号计算 ──────────────────────────────────────────────────


def _compute_signals(
    patch_files: list[str],
    diff_content: str | None = None,
    base_signals: dict | None = None,
) -> dict:
    """从 patch 文件列表提取确定性信号。

    Args:
        patch_files:  变更文件列表
        diff_content: unified diff 文本（可选，用于 has_diff_content）
        base_signals: 外部传入的既有信号（如 git.diff.explain 的输出），
                      会与本地计算的信号合并；外部信号同名键不被覆盖

    Returns:
        dict 包含:
        - touches_tests: bool
        - touches_docs: bool
        - touches_dependency_manifest: bool
        - touches_protected_path: bool
        - protected_path_hits: list[str]
        - touches_core: bool
        - touches_mcp: bool
        - cross_module: bool
        - cross_module_count: int
        - has_diff_content: bool
    """
    touches_tests = False
    touches_docs = False
    touches_manifest = False
    touches_protected = False
    protected_hits: list[str] = []
    touches_core = False
    touches_mcp = False

    # 收集 source 文件的顶层目录（用于跨模块检测）
    source_top_dirs: set[str] = set()

    for f in patch_files:
        cat = _classify_file(f)
        if cat == "test":
            touches_tests = True
        elif cat == "doc":
            touches_docs = True
        elif cat == "manifest":
            touches_manifest = True

        # 保护路径检查
        parts = Path(f).parts
        first_part = parts[0] if parts else ""
        if first_part in _PROTECTED_DIRS or f in _PROTECTED_DIRS:
            touches_protected = True
            protected_hits.append(f)

        # core/ 触及
        if first_part == "core" or (len(parts) > 1 and parts[0] in ("smartdev", "src") and "core" in parts):
            touches_core = True

        # mcp/ 触及
        if first_part == "mcp" or (len(parts) > 1 and "mcp" in parts):
            touches_mcp = True

        # source 文件顶层目录（用于跨模块检测）
        # 穿透项目根前缀（smartdev/src/app/lib/pkg），取功能分组键作为模块标识
        if cat == "source" and parts:
            if first_part in _PROJECT_ROOT_PREFIXES and len(parts) >= 2:
                source_top_dirs.add(parts[1])  # 使用第二层作为模块键
            else:
                source_top_dirs.add(first_part)

    cross_module = len(source_top_dirs) >= 2

    # 构建本地信号
    local_signals = {
        "touches_tests": touches_tests,
        "touches_docs": touches_docs,
        "touches_dependency_manifest": touches_manifest,
        "touches_protected_path": touches_protected,
        "protected_path_hits": protected_hits,
        "touches_core": touches_core,
        "touches_mcp": touches_mcp,
        "cross_module": cross_module,
        "cross_module_count": len(source_top_dirs),
        "has_diff_content": bool(diff_content),
    }

    # 合并外部 base_signals（外部信号补充但不覆盖本地计算值）
    if base_signals:
        for key, value in base_signals.items():
            if key not in local_signals:
                local_signals[key] = value

    return local_signals


# ── 逻辑分组 ──────────────────────────────────────────────────

# 顶层目录 → 分组标签映射
_GROUP_LABELS: dict[str, str] = {
    "core": "core logic change",
    "skills": "skill layer change",
    "tests": "test coverage",
    "docs": "documentation",
    "mcp": "MCP layer change",
    "context": "context layer change",
    "detectors": "detector layer change",
    "adapters": "adapter change",
    "smartdev": "framework change",
}


def _effective_group_key(path: str) -> str:
    """计算文件的分组键。

    对于 'smartdev/core/git.py'，顶层是 'smartdev'，但 'core'
    才是功能分组键。此函数穿透容器目录返回最内层有意义的分组键。
    """
    parts = Path(path).parts
    if not parts:
        return "other"

    # 单层路径直接用第一部分
    if len(parts) == 1:
        return parts[0]

    # 如果第一层是项目根前缀（smartdev/src/app/lib/pkg），则用第二层做分组键
    if parts[0] in _PROJECT_ROOT_PREFIXES:
        return parts[1] if len(parts) > 1 else parts[0]

    return parts[0]


def _describe_group(label: str, files: list[str]) -> str:
    """生成分组的自然语言描述。"""
    cat_counts: dict[str, int] = {}
    for f in files:
        cat = _classify_file(f)
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    parts: list[str] = []
    if cat_counts.get("source", 0) > 0:
        parts.append(f"{cat_counts['source']} source")
    if cat_counts.get("test", 0) > 0:
        parts.append(f"{cat_counts['test']} test")
    if cat_counts.get("doc", 0) > 0:
        parts.append(f"{cat_counts['doc']} doc")
    if cat_counts.get("manifest", 0) > 0:
        parts.append(f"{cat_counts['manifest']} manifest")
    if cat_counts.get("config", 0) > 0:
        parts.append(f"{cat_counts['config']} config")
    if cat_counts.get("other", 0) > 0:
        parts.append(f"{cat_counts['other']} other")

    if parts:
        return f"影响 {', '.join(parts)} 文件"
    return f"影响 {len(files)} 个文件"


def _group_files(patch_files: list[str]) -> list[dict]:
    """按目录层级将文件分组。

    规则：
    - 使用 _effective_group_key 计算分组键（穿透 smartdev/src/app/lib/pkg 前缀）
    - 单文件目录合并到 other（保留 core/tests/docs 等重要组独立）
    - 每个组有 label 和 description

    Returns:
        [{"label": str, "files": list[str], "description": str}, ...]
    """
    groups: dict[str, list[str]] = {}
    singles: list[str] = []

    for f in patch_files:
        key = _effective_group_key(f)
        if key in _GROUP_LABELS:
            groups.setdefault(key, []).append(f)
        else:
            singles.append(f)

    # 单文件目录合并
    result: list[dict] = []
    other_files: list[str] = list(singles)

    for key, files in groups.items():
        if len(files) == 1 and key not in ("core", "tests", "docs", "mcp", "skills", "context"):
            other_files.extend(files)
        else:
            label = _GROUP_LABELS.get(key, f"{key} directory change")
            result.append({
                "label": label,
                "files": files,
                "description": _describe_group(label, files),
            })

    if other_files:
        label = "other changes"
        result.append({
            "label": label,
            "files": other_files,
            "description": _describe_group(label, other_files),
        })

    return result


# ── 测试覆盖分析 ──────────────────────────────────────────────


def _infer_test_file(source_path: str) -> str | None:
    """根据源文件路径推断对应的测试文件路径。

    Examples:
        smartdev/core/git.py → tests/test_git.py
        smartdev/skills/foo/skill.py → tests/test_foo.py
        src/utils/helper.ts → tests/helper.test.ts

    Returns:
        推测的测试文件路径，或 None（无法推测时）
    """
    p = Path(source_path)
    name = p.stem  # 不含扩展名的文件名

    # Python: foo.py → test_foo.py
    if p.suffix == ".py":
        return f"tests/test_{name}.py"

    # JS/TS: foo.ts → foo.test.ts or foo.spec.ts
    if p.suffix in (".ts", ".tsx", ".js", ".jsx"):
        return f"tests/{name}.test{p.suffix}"

    # Go: foo.go → foo_test.go
    if p.suffix == ".go":
        # Go 惯用 _test.go 后缀，通常在同一个目录
        return str(p.with_name(f"{name}_test.go"))

    return None


def _analyze_test_coverage(
    patch_files: list[str],
    project_path: Path | None = None,
) -> dict:
    """分析测试伴随情况。

    Returns:
        {
            "has_related_tests": bool,
            "test_files_touched": int,
            "untested_changed_modules": list[str],
            "covered_modules": list[str],
        }
    """
    test_files: list[str] = []
    source_files: list[str] = []

    for f in patch_files:
        if _classify_file(f) == "test":
            test_files.append(f)
        elif _classify_file(f) == "source":
            source_files.append(f)

    # 找出被测试覆盖的模块
    covered_modules: list[str] = []
    untested_modules: list[str] = []

    # 从测试文件名提取被测试模块
    test_module_names: set[str] = set()
    for tf in test_files:
        stem = Path(tf).stem
        # test_foo → foo, foo_test → foo
        for prefix in ("test_", "spec."):
            if stem.startswith(prefix):
                test_module_names.add(stem[len(prefix):])
                break
        for suffix in ("_test", ".test", "_spec", ".spec"):
            if stem.endswith(suffix):
                test_module_names.add(stem[:-len(suffix)])
                break

    for sf in source_files:
        stem = Path(sf).stem
        if stem in test_module_names:
            covered_modules.append(sf)
        else:
            # 也检查对应测试文件是否在 patch_files 中
            inferred = _infer_test_file(sf)
            if inferred and any(inferred in tf for tf in test_files):
                covered_modules.append(sf)
            else:
                untested_modules.append(sf)

    return {
        "has_related_tests": len(test_files) > 0,
        "test_files_touched": len(test_files),
        "untested_changed_modules": untested_modules,
        "covered_modules": covered_modules,
    }


# ── 依赖匹配 ──────────────────────────────────────────────────


def _check_dependency_match(patch_files: list[str]) -> dict:
    """检查依赖 manifest 变更与源码变更是否匹配。

    Returns:
        {
            "manifest_changed": bool,
            "source_changed": bool,
            "matched": bool,
            "detail": str,
        }
    """
    manifest_files: list[str] = []
    lock_files_changed: list[str] = []
    source_files: list[str] = []

    for f in patch_files:
        cat = _classify_file(f)
        if cat == "manifest":
            name_lower = Path(f).name.lower()
            if name_lower in _LOCK_FILES:
                lock_files_changed.append(f)
            else:
                manifest_files.append(f)
        elif cat == "source":
            source_files.append(f)

    manifest_changed = len(manifest_files) > 0
    source_changed = len(source_files) > 0

    detail_parts: list[str] = []
    if manifest_changed and source_changed:
        detail_parts.append(f"manifest 变更（{', '.join(manifest_files)}）伴随源码变更，匹配正常")
    elif manifest_changed and not source_changed:
        detail_parts.append(f"manifest 变更（{', '.join(manifest_files)}）但无源码变更，可能仅更新依赖版本")
    elif not manifest_changed and source_changed:
        detail_parts.append("无 manifest 变更，仅有源码变更")
    else:
        detail_parts.append("无 manifest 或源码变更")

    if lock_files_changed:
        detail_parts.append(f"lock 文件同步变更（{', '.join(lock_files_changed)}）")

    return {
        "manifest_changed": manifest_changed,
        "source_changed": source_changed,
        "matched": not manifest_changed or source_changed,
        "lock_files_changed": lock_files_changed,
        "detail": "；".join(detail_parts),
    }


# ── 风险提示 ──────────────────────────────────────────────────


def _compute_risk_hints(
    signals: dict,
    dep_match: dict,
    test_coverage: dict,
    insertions: int,
    deletions: int,
    n_files: int,
) -> list[str]:
    """基于所有信号生成风险提示列表。"""
    hints: list[str] = []

    if signals["cross_module"] and signals["cross_module_count"] > 2:
        hints.append(
            f"cross_module_change:{signals['cross_module_count']}_top_level_dirs"
        )
    elif signals["cross_module"]:
        hints.append("cross_module_change")

    if dep_match["manifest_changed"] and not dep_match["source_changed"]:
        hints.append("dependency_manifest_changed_without_code")

    if signals["touches_protected_path"]:
        hints.append("touches_protected_path")

    if signals["touches_core"]:
        hints.append("core_module_touched")

    # 测试伴随缺失：source/skill 变更但无测试
    if test_coverage.get("untested_changed_modules"):
        hints.append("missing_related_tests")

    if n_files > 10:
        hints.append(f"large_changeset:{n_files}_files")

    total_lines = insertions + deletions
    if total_lines > 300:
        hints.append(f"large_diff:{total_lines}_lines")

    return hints


# ── 审查顺序建议 ──────────────────────────────────────────────


def _suggest_review_order(
    groups: list[dict],
    signals: dict,
    test_coverage: dict,
) -> list[str]:
    """按依赖关系排序审查顺序。

    优先顺序：core → mcp → manifest → skills → source → tests → docs → config → other
    """
    # 优先级映射（数值越小越先审查）
    _PRIORITY: dict[str, int] = {
        "core logic change": 1,
        "MCP layer change": 2,
        "manifest change": 3,
        "skill layer change": 4,
        "context layer change": 5,
        "detector layer change": 6,
        "framework change": 7,
        "adapter change": 8,
        "source change": 9,
        "test coverage": 10,
        "documentation": 11,
        "config change": 12,
    }

    # 按优先级排序
    sorted_groups = sorted(
        groups,
        key=lambda g: _PRIORITY.get(g["label"], 8),
    )

    suggestions: list[str] = []

    for i, group in enumerate(sorted_groups):
        label = group["label"]
        files = group["files"]

        if len(files) == 1:
            suggestions.append(
                f"{i + 1}. 审查 {files[0]}（{label}）"
            )
        elif len(files) <= 3:
            file_list = "、".join(files)
            suggestions.append(
                f"{i + 1}. 审查 {label}：{file_list}"
            )
        else:
            suggestions.append(
                f"{i + 1}. 先审查 {label}（{len(files)} 个文件，关注核心文件）"
            )

    # 追加测试/覆盖提醒
    if test_coverage["untested_changed_modules"]:
        untested = "、".join(test_coverage["untested_changed_modules"])
        suggestions.append(
            f"{len(suggestions) + 1}. 确认 {untested} 是否需要补充测试"
        )

    if signals["touches_dependency_manifest"]:
        suggestions.append(
            f"{len(suggestions) + 1}. 确认依赖变更的兼容性和必要性"
        )

    return suggestions


# ── 核心入口 ──────────────────────────────────────────────────


@dataclass
class DiffExplainResult:
    """diff.explain 检查结果。

    Attributes:
        summary:           行数统计摘要
        signals:           变更信号
        file_categories:   文件分类结果 {category: [file_paths]}
        logical_groups:    逻辑分组
        risk_hints:        风险提示
        test_coverage:     测试覆盖分析
        suggested_review_order: 审查顺序建议
    """

    summary: dict = field(default_factory=dict)
    signals: dict = field(default_factory=dict)
    file_categories: dict = field(default_factory=dict)
    logical_groups: list[dict] = field(default_factory=list)
    risk_hints: list[str] = field(default_factory=list)
    test_coverage: dict = field(default_factory=dict)
    suggested_review_order: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "summary": self.summary,
            "signals": self.signals,
            "file_categories": self.file_categories,
            "logical_groups": self.logical_groups,
            "risk_hints": self.risk_hints,
            "test_coverage": self.test_coverage,
            "suggested_review_order": self.suggested_review_order,
        }


def explain_diff(
    patch_files: list[str],
    diff_content: str | None = None,
    project_path: Path | None = None,
    base_signals: dict | None = None,
) -> DiffExplainResult:
    """执行 patch 级 diff 解释。

    在 git.diff.explain（仓库级）基础上，增加 patch 专属维度：
    - 逻辑分组（按目录层级）
    - 测试伴随检查
    - 依赖匹配检查
    - 审查顺序建议

    Args:
        patch_files:  patch 涉及的文件列表（相对路径字符串）
        diff_content: unified diff 文本内容（可选，用于行数统计）
        project_path: 项目根目录（可选，用于后续扩展）
        base_signals: 外部传入的既有信号（可选，如 git.diff.explain 的输出），
                      会与本地计算的信号合并；外部信号补充但不覆盖同名键

    Returns:
        DiffExplainResult: 结构化解释结果
    """
    n_files = len(patch_files)

    # 解析 diff 内容统计行数
    insertions, deletions = _parse_diff_content(diff_content)

    # 计算信号（含 base_signals 合并）
    signals = _compute_signals(patch_files, diff_content, base_signals)

    # 文件分类
    file_categories: dict[str, list[str]] = {}
    for f in patch_files:
        cat = _classify_file(f)
        file_categories.setdefault(cat, []).append(f)
    # 确保所有分类键都存在（即使为空列表）
    for cat in ("source", "test", "doc", "manifest", "config", "core", "mcp", "other"):
        file_categories.setdefault(cat, [])

    # 逻辑分组
    logical_groups = _group_files(patch_files)

    # 测试覆盖分析
    test_coverage = _analyze_test_coverage(patch_files, project_path)

    # 依赖匹配
    dep_match = _check_dependency_match(patch_files)

    # 风险提示
    risk_hints = _compute_risk_hints(
        signals, dep_match, test_coverage, insertions, deletions, n_files,
    )

    # 审查顺序
    review_order = _suggest_review_order(logical_groups, signals, test_coverage)

    # 构建 summary
    summary = {
        "files_changed": n_files,
        "insertions": insertions,
        "deletions": deletions,
        "logical_groups": len(logical_groups),
    }

    return DiffExplainResult(
        summary=summary,
        signals=signals,
        file_categories=file_categories,
        logical_groups=logical_groups,
        risk_hints=risk_hints,
        test_coverage=test_coverage,
        suggested_review_order=review_order,
    )
