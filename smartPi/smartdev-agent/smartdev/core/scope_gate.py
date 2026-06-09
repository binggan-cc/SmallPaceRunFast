"""
Scope Gate — Phase 11D Step 2 核心交付物（R0 只读）

功能：
─────
读取 .smartdev/runs/<run_id>/scope.json，对比 changed_files 列表，
输出结构化的 passed / violations / warnings / summary。

四条检查规则：
────────────
1. max_files       — changed_files 数量是否超过 scope.max_files
2. denied_paths    — 是否命中 scope.denied_paths（glob 匹配）
3. protected_paths — 是否命中 scope.protected_paths（glob 匹配）
4. allowed_paths   — 是否存在不在 scope.allowed_paths 内的文件

命中任一 → violation，passed=false。所有规则独立执行，一条失败不阻断其他。

设计约束：
─────────
- 零外部依赖（标准库 fnmatch + json + Path）
- 只读 .smartdev/runs/<run_id>/scope.json，不修改任何文件（R0）
- scope.json 缺失或格式错误 → 返回 error 消息，不崩溃
- glob 模式支持 fnmatch 语法（* ? [seq]）

对应文档：
- docs/phase-11d-design.md §6（Scope Gate）
- docs/phase-11d-design.md §8 Step 2
"""

from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass, field
from pathlib import Path


# ── 数据模型 ──────────────────────────────────────────────────


@dataclass
class ScopeViolation:
    """单条 scope 违规。

    Attributes:
        file:     违规文件路径（字符串）
        rule:     违规规则名（max_files / denied_paths / protected_paths / outside_scope）
        severity: 严重程度（error / warning）
        message:  人类可读的违规说明
    """

    file: str
    rule: str
    severity: str
    message: str

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "rule": self.rule,
            "severity": self.severity,
            "message": self.message,
        }


@dataclass
class ScopeGateResult:
    """Scope Gate 检查结果。

    Attributes:
        passed:      是否全部通过（无 violation）
        violations:  违规列表
        warnings:    警告列表（不阻断，但需关注）
        summary:     人类可读的检查摘要
        error:       加载错误消息（scope.json 缺失/格式错误等），None 表示无错误
        scope_config: 加载到的 ScopeConfig 摘要（用于调试）
    """

    passed: bool = True
    violations: list[ScopeViolation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    summary: str = ""
    error: str | None = None
    scope_config: dict | None = None

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "violations": [v.to_dict() for v in self.violations],
            "warnings": self.warnings,
            "summary": self.summary,
            "error": self.error,
            "scope_config": self.scope_config,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


# ── 核心逻辑 ──────────────────────────────────────────────────


def _match_any(file_path: str, patterns: list[str]) -> bool:
    """检查 file_path 是否匹配 patterns 中任意一个（fnmatch glob）。

    对目录模式（如 "smartdev/"），同时检查前缀匹配，使 "smartdev/foo/bar.py"
    能匹配到 "smartdev/"。
    """
    for pattern in patterns:
        # fnmatch 直接匹配（如 "*.pyc"）
        if fnmatch.fnmatch(file_path, pattern):
            return True
        # 前缀匹配：处理 "smartdev/" → 匹配 "smartdev/core/foo.py"
        # 也处理 "tests/" → 匹配 "tests/test_x.py"
        if pattern.endswith("/") and file_path.startswith(pattern):
            return True
        # 也检查纯文件名匹配（"*.pyc" 应对 "foo/bar.pyc"）
        if fnmatch.fnmatch(Path(file_path).name, pattern):
            return True
    return False


def load_scope_config(run_dir: Path) -> tuple[dict | None, str | None]:
    """从 run 目录加载 scope.json。

    Returns:
        (scope_dict, error_message)
        - 成功: (dict, None)
        - 失败: (None, error_message)
    """
    scope_path = run_dir / "scope.json"

    if not scope_path.exists():
        return None, (
            f"scope.json 不存在: {scope_path}。"
            f"请先运行 smartdev run new <run_id> 创建 run artifact"
        )

    try:
        data = json.loads(scope_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return None, f"scope.json 格式错误 ({scope_path}): {e}"

    # 校验必要字段
    required_fields = ["allowed_paths", "denied_paths", "max_files", "protected_paths"]
    missing = [f for f in required_fields if f not in data]
    if missing:
        return None, (
            f"scope.json 缺少必要字段: {', '.join(missing)} ({scope_path})"
        )

    return data, None


def check_scope(
    project_path: Path,
    run_id: str,
    changed_files: list[str],
) -> ScopeGateResult:
    """执行 Scope Gate 检查。

    Args:
        project_path:   项目根目录
        run_id:         任务唯一标识
        changed_files:  变更文件列表（相对项目根目录的路径字符串）

    Returns:
        ScopeGateResult: 结构化检查结果
    """
    # ── 加载 scope.json ────────────────────────────────────────
    run_dir = project_path / ".smartdev" / "runs" / run_id
    scope_data, error = load_scope_config(run_dir)

    if error:
        return ScopeGateResult(
            passed=False,
            error=error,
            summary=f"❌ 无法加载 scope 配置: {error}",
        )

    allowed_paths: list[str] = scope_data["allowed_paths"]
    denied_paths: list[str] = scope_data["denied_paths"]
    max_files: int = scope_data["max_files"]
    protected_paths: list[str] = scope_data["protected_paths"]

    violations: list[ScopeViolation] = []
    warnings: list[str] = []

    # ── 规则 1: max_files ──────────────────────────────────────
    if len(changed_files) > max_files:
        violations.append(ScopeViolation(
            file="*",
            rule="max_files",
            severity="error",
            message=(
                f"变更文件数 {len(changed_files)} 超过上限 {max_files} "
                f"（change.budget）。请拆分变更或调整 scope.json 中的 max_files"
            ),
        ))

    # ── 规则 2-4: 逐文件检查 ───────────────────────────────────
    for f in changed_files:
        # 规则 2: denied_paths
        if _match_any(f, denied_paths):
            violations.append(ScopeViolation(
                file=f,
                rule="denied_paths",
                severity="error",
                message=f"文件 '{f}' 命中 denied_paths，禁止修改",
            ))

        # 规则 3: protected_paths
        if _match_any(f, protected_paths):
            violations.append(ScopeViolation(
                file=f,
                rule="protected_paths",
                severity="error",
                message=(
                    f"文件 '{f}' 命中 protected_paths。"
                    f"修改此文件需人工确认（R3 级别）"
                ),
            ))

        # 规则 4: allowed_paths（scope 外文件）
        if not _match_any(f, allowed_paths):
            violations.append(ScopeViolation(
                file=f,
                rule="outside_scope",
                severity="warning",
                message=(
                    f"文件 '{f}' 不在 allowed_paths 范围内。"
                    f"如果确实需要修改此文件，请更新 scope.json"
                ),
            ))

    # ── 去重同一文件的同一规则（可能同时命中 denied + protected）──
    seen = set()
    deduped: list[ScopeViolation] = []
    for v in violations:
        key = (v.file, v.rule)
        if key not in seen:
            seen.add(key)
            deduped.append(v)

    # ── 构建摘要 ───────────────────────────────────────────────
    severity_count: dict[str, int] = {}
    for v in deduped:
        severity_count[v.severity] = severity_count.get(v.severity, 0) + 1

    passed = len([v for v in deduped if v.severity == "error"]) == 0

    if passed and not deduped:
        summary = (
            f"✅ Scope Gate 通过：{len(changed_files)} 个文件，"
            f"全部在 allowed_paths 范围内，未超过 max_files={max_files}"
        )
    elif passed:
        # 只有 warning
        summary = (
            f"⚠ Scope Gate 通过（有 {len(deduped)} 个警告）："
            + "; ".join(f"{k}={v}" for k, v in severity_count.items())
        )
    else:
        summary = (
            f"❌ Scope Gate 未通过：{len(deduped)} 个问题 "
            + "(" + "; ".join(f"{k}={v}" for k, v in severity_count.items()) + ")"
        )

    return ScopeGateResult(
        passed=passed,
        violations=deduped,
        warnings=warnings,
        summary=summary,
        scope_config={
            "allowed_paths": allowed_paths,
            "denied_paths": denied_paths,
            "max_files": max_files,
            "protected_paths": protected_paths,
        },
    )
