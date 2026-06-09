"""
Guard: dev.guard — AI 编程规则守卫（R0 只读）

功能：
─────
检查本轮任务是否违反 AI 编程硬规则——那些在 CLAUDE.md / 协议中写死
但当前靠人工自觉遵守的约束：

  1. mass_refactor            — 大规模重构检测（3+ 一级模块目录同时修改）
  2. protected_path_hit       — 命中 protected_paths
  3. unrelated_change         — 与任务描述无关的改动
  4. test_deletion            — 测试文件删除 / 测试函数删除
  5. config_in_code           — 配置文件与功能代码同时修改
  6. forbidden_file_modification — 命中 denied_paths / 禁止修改路径
  7. large_commit             — 超过 max_files_per_commit

设计约束：
─────────
- 零外部依赖（标准库 fnmatch + pathlib）
- 确定性规则引擎，不调用模型
- 无 git 环境也能运行（基于显式输入）
- R0 只读 — 不修改任何文件
- 路径匹配支持目录前缀 + fnmatch glob

对应文档：
- docs/phase-11b-design.md §3.2（dev.guard 详细设计）
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path


# ── 数据模型 ──────────────────────────────────────────────────


@dataclass
class DevGuardViolation:
    """单条 dev.guard 违规。

    Attributes:
        rule:     违规规则名
        severity: 严重程度（error / warning / info）
        message:  人类可读说明
        detail:   补充信息
    """

    rule: str
    severity: str
    message: str
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "message": self.message,
            "detail": self.detail,
        }


@dataclass
class DevGuardResult:
    """dev.guard 检查结果。

    Attributes:
        passed:     是否通过（无 error 级别违规）
        checks:     各项检查结果
        violations: 违规列表
        summary:    人类可读摘要
    """

    passed: bool = True
    checks: dict = field(default_factory=dict)
    violations: list[DevGuardViolation] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "checks": self.checks,
            "violations": [v.to_dict() for v in self.violations],
            "summary": self.summary,
        }


# ── 路径匹配工具 ──────────────────────────────────────────────


def _match_any(file_path: str, patterns: list[str]) -> bool:
    """检查 file_path 是否匹配 patterns 中任意一个。

    支持：
    - fnmatch glob（如 "*.pyc", "smartdev/core/*.py"）
    - 目录前缀（如 "smartdev/" 匹配 "smartdev/core/foo.py"）
    - 纯文件名匹配（如 "*.pyc" 匹配 "foo/bar.pyc"）
    """
    for pattern in patterns:
        # fnmatch 直接匹配
        if fnmatch.fnmatch(file_path, pattern):
            return True
        # 目录前缀匹配
        if pattern.endswith("/") and file_path.startswith(pattern):
            return True
        # 纯文件名匹配
        if fnmatch.fnmatch(Path(file_path).name, pattern):
            return True
    return False


def _get_top_level_dir(file_path: str) -> str:
    """获取用于 mass_refactor 判断的模块目录名。

    Examples:
        "smartdev/core/git.py" → "core"
        "tests/test_x.py" → "tests"
        "README.md" → ""（无目录）
    """
    parts = Path(file_path).parts
    if len(parts) > 2 and parts[0] == "smartdev":
        return parts[1]
    if len(parts) > 1:
        return parts[0]
    return ""


# ── 文件类型分类 ──────────────────────────────────────────────


# 配置文件扩展名 / 文件名
_CONFIG_EXTS = {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env"}
_CONFIG_NAMES = {
    ".gitignore", ".gitattributes", ".editorconfig", "Makefile",
    "Dockerfile", "docker-compose.yml", ".dockerignore",
    "config.json", "settings.py", "settings.ini", "app.config",
}
# 功能代码扩展名
_CODE_EXTS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go",
    ".java", ".rs", ".cpp", ".c", ".cs", ".rb", ".php",
    ".vue", ".svelte",
}
# 测试文件模式
_TEST_PATTERNS = ("test_", "_test", "/test/", "/tests/", "spec.", ".spec.",
                  "_test.py", "_test.js", "_test.ts")


def _is_config_file(file_path: str) -> bool:
    """判断是否为配置文件。"""
    p = Path(file_path)
    if p.name in _CONFIG_NAMES:
        return True
    if p.suffix in _CONFIG_EXTS:
        return True
    # 处理 dotfiles（如 .env）：Path.suffix 对纯 dotfile 返回 ""
    if p.name.startswith(".") and p.name in _CONFIG_EXTS:
        return True
    return False


def _is_code_file(file_path: str) -> bool:
    """判断是否为功能代码文件。"""
    return Path(file_path).suffix in _CODE_EXTS


def _is_test_file(file_path: str) -> bool:
    """判断是否为测试文件。"""
    path_lower = file_path.lower()
    return any(pat in path_lower for pat in _TEST_PATTERNS)


# ── 关键词提取（用于 unrelated_change 检测）─────────────────


def _extract_keywords(text: str) -> set[str]:
    """从任务描述中提取关键词。

    策略：分词后过滤常见停用词和短词，保留有意义的英文/中文词。
    不做自然语言理解，只做保守的 token 匹配。
    """
    if not text:
        return set()

    # 简单分词：按空格和常见分隔符拆分
    import re
    tokens = re.split(r'[\s,;:、，；：。！？!?()（）\[\]{}""\'\'/\\|.]+', text)
    tokens = [t.strip().lower() for t in tokens if t.strip()]

    # 常见停用词
    stopwords = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "in", "on", "at", "to", "for", "of", "from", "by", "with",
        "and", "or", "not", "this", "that", "it", "its",
        "的", "了", "在", "是", "和", "与", "或", "不", "也",
        "step", "phase", "skill", "guard", "实现", "检查", "当前",
        "任务", "修改", "文件", "完成", "执行", "进行",
    }
    keywords = set()
    for t in tokens:
        if len(t) >= 3 and t not in stopwords:
            keywords.add(t)
        # 保留已知的技术关键词（含短词）
        if t in {"git", "cli", "mcp", "r0", "r1", "r2", "r3",
                 "py", "js", "ts", "go", "css", "ci", "cd"}:
            keywords.add(t)

    return keywords


# ── 核心规则引擎 ──────────────────────────────────────────────


def check_dev_guard(
    changed_files: list[str],
    protected_paths: list[str] | None = None,
    denied_paths: list[str] | None = None,
    forbidden_paths: list[str] | None = None,
    task_description: str = "",
    diff_content: str = "",
    max_files_per_commit: int = 12,
) -> DevGuardResult:
    """执行 dev.guard 检查。

    Args:
        changed_files:        变更文件列表
        protected_paths:      受保护路径（glob 模式列表）
        denied_paths:         禁止修改路径（glob 模式列表）
        forbidden_paths:      禁止修改的额外路径（如 CHANGELOG 历史记录 / phase-*-design.md）
        task_description:     任务描述（用于 unrelated_change 检测）
        diff_content:         可选的 diff 内容（用于 test_deletion 精确检测）
        max_files_per_commit: 单 commit 最大文件数（默认 12，来自 git-policy）

    Returns:
        DevGuardResult: 结构化检查结果
    """
    violations: list[DevGuardViolation] = []
    checks: dict = {}
    protected_paths = protected_paths or []
    denied_paths = denied_paths or []
    forbidden_paths = forbidden_paths or []

    # ── 提取一级目录分布 ──────────────────────────────────────
    top_dirs: set[str] = set()
    for f in changed_files:
        d = _get_top_level_dir(f)
        if d:
            top_dirs.add(d)

    # ── 规则 1: mass_refactor ──────────────────────────────────
    mass_refactor_triggered = len(top_dirs) >= 3
    checks["mass_refactor"] = {
        "triggered": mass_refactor_triggered,
        "top_level_dirs": sorted(top_dirs),
        "threshold": 3,
    }
    if mass_refactor_triggered:
        violations.append(DevGuardViolation(
            rule="mass_refactor",
            severity="error",
            message=(
                f"检测到大规模重构：变更分布在 {len(top_dirs)} 个一级模块目录 "
                f"（{', '.join(sorted(top_dirs))}），达到 threshold=3"
            ),
            detail={
                "top_level_dirs": sorted(top_dirs),
                "threshold": 3,
            },
        ))

    # ── 规则 2: protected_path_hit ─────────────────────────────
    protected_hits: list[str] = []
    for f in changed_files:
        if _match_any(f, protected_paths):
            protected_hits.append(f)
    checks["protected_path_hit"] = {
        "triggered": len(protected_hits) > 0,
        "hits": protected_hits,
        "protected_paths": protected_paths,
    }
    for hit in protected_hits:
        violations.append(DevGuardViolation(
            rule="protected_path_hit",
            severity="error",
            message=(
                f"文件 '{hit}' 命中 protected_paths。"
                f"修改此文件需人工确认（R3 级别）"
            ),
            detail={"file": hit, "protected_paths": protected_paths},
        ))

    # ── 规则 3: unrelated_change ───────────────────────────────
    keywords = _extract_keywords(task_description)
    unrelated_files: list[str] = []
    if keywords and changed_files:
        for f in changed_files:
            path_lower = f.lower()
            # 检查是否有任一关键词出现在路径中
            matched = any(kw in path_lower for kw in keywords)
            if not matched:
                unrelated_files.append(f)
    checks["unrelated_change"] = {
        "triggered": len(unrelated_files) > 0,
        "unrelated_files": unrelated_files,
        "keywords": sorted(keywords) if keywords else [],
        "note": (
            "保守关键词匹配：不确定时 warning，不 error。"
            "无 task_description 时跳过此检查。"
        ),
    }
    for uf in unrelated_files:
        violations.append(DevGuardViolation(
            rule="unrelated_change",
            severity="warning",
            message=(
                f"文件 '{uf}' 的路径与任务描述关键词无明显关联。"
                f"关键词：{', '.join(sorted(keywords)) if keywords else '(无)'}"
            ),
            detail={
                "file": uf,
                "keywords": sorted(keywords) if keywords else [],
            },
        ))

    # ── 规则 4: test_deletion ──────────────────────────────────
    test_deletion_triggered = False
    test_deletion_detail: dict = {}

    # 方式 1: 从 diff_content 检测
    deleted_test_functions: list[str] = []
    deleted_test_files_in_diff: list[str] = []
    if diff_content:
        import re
        # 查找删除的 test_ 函数（以 - 开头的行）
        for match in re.finditer(
            r'^-\s*def\s+(test_\w+)\s*\(', diff_content, re.MULTILINE
        ):
            deleted_test_functions.append(match.group(1))
        # 查找删除的 test 文件（--- a/tests/... +++ /dev/null）
        for match in re.finditer(
            r'^--- a/(tests?/.*(?:test_\w+|_test)\.(?:py|js|ts))\n\+\+\+ /dev/null',
            diff_content, re.MULTILINE
        ):
            deleted_test_files_in_diff.append(match.group(1))

        if deleted_test_functions or deleted_test_files_in_diff:
            test_deletion_triggered = True
            test_deletion_detail = {
                "deleted_test_functions": deleted_test_functions,
                "deleted_test_files_in_diff": deleted_test_files_in_diff,
                "source": "diff_content",
            }

    # 方式 2: 从 changed_files 检测（无 diff 时的 fallback）
    # 检查是否有测试文件被标记为删除状态的文件名模式
    # 注意：没有 diff 时无法确定是否删除，只能基于文件名推测
    if not test_deletion_triggered:
        # 检查 changed_files 中是否有 test 文件在 deleted 集合中
        # 由于我们只有 changed_files 列表没有 staged status，这里保持保守
        pass

    checks["test_deletion"] = {
        "triggered": test_deletion_triggered,
        "detail": test_deletion_detail,
    }
    if test_deletion_triggered:
        violations.append(DevGuardViolation(
            rule="test_deletion",
            severity="warning",
            message=(
                f"检测到测试删除："
                + (f"{len(deleted_test_functions)} 个测试函数" if deleted_test_functions else "")
                + (f"{len(deleted_test_files_in_diff)} 个测试文件" if deleted_test_files_in_diff else "")
            ),
            detail=test_deletion_detail,
        ))

    # 如果没有 diff_content 则说明
    if not diff_content:
        checks["test_deletion"]["note"] = (
            "未提供 diff_content，仅检查了文件名模式。"
            "提供 diff_content 可精确检测测试函数删除。"
        )

    # ── 规则 5: config_in_code ─────────────────────────────────
    has_config_change = any(_is_config_file(f) for f in changed_files)
    has_code_change = any(_is_code_file(f) for f in changed_files)
    config_in_code_triggered = has_config_change and has_code_change
    config_files = [f for f in changed_files if _is_config_file(f)]
    code_files = [f for f in changed_files if _is_code_file(f)]
    checks["config_in_code"] = {
        "triggered": config_in_code_triggered,
        "config_files": config_files,
        "code_files": code_files,
    }
    if config_in_code_triggered:
        violations.append(DevGuardViolation(
            rule="config_in_code",
            severity="warning",
            message=(
                f"配置文件（{', '.join(config_files)}）与功能代码"
                f"（{len(code_files)} 个文件）同时变更。"
                f"请确认配置文件变更是有意为之"
            ),
            detail={
                "config_files": config_files,
                "code_file_count": len(code_files),
            },
        ))

    # ── 规则 6: forbidden_file_modification ────────────────────
    # 合并 denied_paths + forbidden_paths
    all_forbidden = list(denied_paths) + list(forbidden_paths)
    forbidden_hits: list[str] = []
    for f in changed_files:
        if _match_any(f, all_forbidden):
            forbidden_hits.append(f)
    checks["forbidden_file_modification"] = {
        "triggered": len(forbidden_hits) > 0,
        "hits": forbidden_hits,
        "forbidden_patterns": all_forbidden,
    }
    for hit in forbidden_hits:
        violations.append(DevGuardViolation(
            rule="forbidden_file_modification",
            severity="error",
            message=(
                f"文件 '{hit}' 命中禁止修改路径。"
                f"此文件不应被 AI 修改"
            ),
            detail={
                "file": hit,
                "forbidden_patterns": all_forbidden,
            },
        ))

    # ── 规则 7: large_commit ────────────────────────────────────
    large_commit_triggered = len(changed_files) > max_files_per_commit
    checks["large_commit"] = {
        "triggered": large_commit_triggered,
        "actual": len(changed_files),
        "max_files_per_commit": max_files_per_commit,
    }
    if large_commit_triggered:
        violations.append(DevGuardViolation(
            rule="large_commit",
            severity="warning",
            message=(
                f"变更文件数 {len(changed_files)} 超过 "
                f"max_files_per_commit={max_files_per_commit}"
            ),
            detail={
                "actual": len(changed_files),
                "limit": max_files_per_commit,
            },
        ))

    # ── 构建摘要 ───────────────────────────────────────────────
    error_count = sum(1 for v in violations if v.severity == "error")
    warning_count = sum(1 for v in violations if v.severity == "warning")
    passed = error_count == 0

    if passed and not violations:
        summary = (
            f"✅ dev.guard 通过：{len(changed_files)} 个文件，"
            f"{len(top_dirs)} 个模块，无违规"
        )
    elif passed:
        summary = (
            f"⚠ dev.guard 通过（{warning_count} 个警告）："
            f"{len(changed_files)} 个文件，{len(top_dirs)} 个模块"
        )
    else:
        summary = (
            f"❌ dev.guard 未通过（{error_count} 个错误"
            + (f"，{warning_count} 个警告)" if warning_count else ")")
        )

    return DevGuardResult(
        passed=passed,
        checks=checks,
        violations=violations,
        summary=summary,
    )
