"""
GuardRunner — 一键全跑 5 个 Guard Skill + 聚合报告（R0 只读）

功能：
─────
把 Phase 11B 五个 Guard Skill：
  1. change.budget
  2. dev.guard
  3. dependency.guard
  4. security.review
  5. diff.explain

按固定顺序运行，输出统一聚合报告，供 Human 在 apply/commit 前判断
本轮改动是否仍在工程规则内。

设计约束：
─────────
- 零外部依赖（标准库 + Skill 层）
- 不新增检测规则，不改已有 Guard Skill
- R0 只读 — 不修改任何文件
- 基于显式输入运行，不依赖 git 工作区
- 支持 select 过滤，只运行指定 Guard
- 单个 Guard 异常时记录失败，不崩溃

对应文档：
- docs/phase-11b-design.md §6 Step 6（GuardRunner 组合 + CLI 入口）
- docs/phase-11b-design.md §7（聚合报告格式）
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path


# ── 数据模型 ──────────────────────────────────────────────────


@dataclass
class GuardEntryResult:
    """单个 Guard 的运行结果。

    Attributes:
        passed:     是否通过（无 error 级别违规）
        summary:    人类可读摘要
        duration_ms: 执行耗时（毫秒）
        risks:      风险列表
        next_steps: 下一步建议
        error:      异常信息（正常时为 None）
    """

    passed: bool = True
    summary: str = ""
    duration_ms: float = 0.0
    risks: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict:
        d = {
            "passed": self.passed,
            "summary": self.summary,
            "duration_ms": round(self.duration_ms, 2),
            "risks": self.risks,
            "next_steps": self.next_steps,
        }
        if self.error:
            d["error"] = self.error
        return d


@dataclass
class GuardRunResult:
    """GuardRunner 聚合报告。

    Attributes:
        overall_passed:   是否全部通过
        guards:           {guard_name: GuardEntryResult}
        error_count:      错误数量
        warning_count:    警告/信息数量
        suggested_actions: 基于聚合结果的建议操作
        selected:         实际运行的 Guard 名称列表
        skipped:          被跳过的 Guard 名称列表
        summary:          人类可读总体摘要
        run_id:           运行 ID
        timestamp:        ISO 8601 时间戳
    """

    overall_passed: bool = True
    guards: dict = field(default_factory=dict)
    error_count: int = 0
    warning_count: int = 0
    suggested_actions: list[str] = field(default_factory=list)
    selected: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    summary: str = ""
    run_id: str = ""
    timestamp: str = ""

    def to_dict(self) -> dict:
        return {
            "overall_passed": self.overall_passed,
            "guards": {
                name: entry.to_dict() for name, entry in self.guards.items()
            },
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "suggested_actions": self.suggested_actions,
            "selected": self.selected,
            "skipped": self.skipped,
            "summary": self.summary,
            "run_id": self.run_id,
            "timestamp": self.timestamp,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


# ── Guard 定义 ─────────────────────────────────────────────────

# 固定运行顺序
_GUARD_ORDER = [
    "change.budget",
    "dev.guard",
    "dependency.guard",
    "security.review",
    "diff.explain",
]

# 每个 Guard 所需的 Skill.create() 输入映射
# key: guard_name → 传给 skill.run(context, inputs) 的额外 inputs 键
_GUARD_INPUT_KEYS: dict[str, list[str]] = {
    "change.budget": ["changed_files", "max_files", "max_lines"],
    "dev.guard": ["changed_files", "diff_content", "task_description",
                  "protected_paths", "denied_paths"],
    "dependency.guard": ["changed_files", "diff_content"],
    "security.review": ["changed_files", "diff_content"],
    "diff.explain": ["changed_files", "diff_content"],
}

# 每个 Guard 的 inputs 参数到 Skill input key 的映射
# diff.explain 用 'patch_files' 而非 'changed_files'
_GUARD_PARAM_ALIAS: dict[str, dict[str, str]] = {
    "diff.explain": {"changed_files": "patch_files"},
}


def _now_iso() -> str:
    """返回当前 UTC 时间的 ISO 8601 字符串。"""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _count_warning_like_violations(data: dict) -> int:
    """统计 warning/info 级 violation。

    SkillResult.risks 在现有 Guard 中主要承载 error 级风险，不能直接当作
    warning_count。聚合报告的 warning_count 应来自结构化 violations。
    """
    violations = data.get("violations", []) if isinstance(data, dict) else []
    if not isinstance(violations, list):
        return 0

    count = 0
    for violation in violations:
        if not isinstance(violation, dict):
            continue
        if violation.get("severity") in {"warning", "info"}:
            count += 1
    return count


# ── 核心入口 ──────────────────────────────────────────────────


def run_guard_runner(
    project_path: Path,
    changed_files: list[str] | None = None,
    diff_content: str | None = None,
    select: list[str] | None = None,
    task_description: str = "",
    max_files: int = 10,
    max_lines: int | None = None,
    protected_paths: list[str] | None = None,
    denied_paths: list[str] | None = None,
    run_id: str = "",
) -> GuardRunResult:
    """一键运行所有 Guard Skill 并输出聚合报告。

    Args:
        project_path:      项目根目录
        changed_files:     变更文件列表
        diff_content:      unified diff 文本（可选）
        select:            指定运行的 Guard 名称列表（None=全部运行）
        task_description:  任务描述（传给 dev.guard）
        max_files:         文件数上限（传给 change.budget）
        max_lines:         行数上限（传给 change.budget，None=不限制）
        protected_paths:   保护路径列表（传给 dev.guard）
        denied_paths:      禁止路径列表（传给 dev.guard）
        run_id:            运行 ID（可选，用于报告标识）

    Returns:
        GuardRunResult: 聚合报告

    Raises:
        不抛出异常——单个 Guard 失败时记录 error 字段，不中断整体流程。
    """
    import smartdev.skills  # noqa: F401 — 触发所有 Skill 注册
    from smartdev.skills.base import Skill
    from smartdev.models import ProjectContext

    changed_files = changed_files or []
    select = select or list(_GUARD_ORDER)
    protected_paths = protected_paths or []
    denied_paths = denied_paths or []
    timestamp = _now_iso()

    # 验证 select 中的 guard 名称
    invalid = [g for g in select if g not in _GUARD_ORDER]
    if invalid:
        # 返回包含 invalid 信息的错误结果，但不崩溃
        result = GuardRunResult(
            overall_passed=False,
            selected=select,
            skipped=[],
            summary=f"无效 Guard 名称: {', '.join(invalid)}",
            run_id=run_id,
            timestamp=timestamp,
        )
        result.error_count = 1
        result.suggested_actions.append(
            f"可用的 Guard: {', '.join(_GUARD_ORDER)}"
        )
        return result

    # 确定 skipped 列表
    skipped = [g for g in _GUARD_ORDER if g not in select]

    # 构建上下文
    context = ProjectContext(
        project_path=project_path,
        task_description=task_description,
    )

    # 准备公共 inputs
    common_inputs: dict = {
        "changed_files": changed_files,
        "diff_content": diff_content,
        "task_description": task_description,
        "max_files": max_files,
        "max_lines": max_lines,
        "protected_paths": protected_paths,
        "denied_paths": denied_paths,
        "patch_files": changed_files,  # diff.explain 使用 patch_files
    }

    guards: dict[str, GuardEntryResult] = {}
    guard_warning_counts: dict[str, int] = {}

    for guard_name in _GUARD_ORDER:
        if guard_name in skipped:
            continue

        t_start = time.perf_counter()

        try:
            skill = Skill.create(guard_name)
        except KeyError:
            t_end = time.perf_counter()
            guards[guard_name] = GuardEntryResult(
                passed=False,
                summary=f"Skill '{guard_name}' 未注册",
                duration_ms=(t_end - t_start) * 1000,
                error=f"Skill '{guard_name}' 未在注册表中找到",
            )
            continue

        # 构建该 Guard 的 inputs
        # 使用 _GUARD_PARAM_ALIAS 做参数名重映射
        input_keys = _GUARD_INPUT_KEYS.get(guard_name, ["changed_files"])
        guard_inputs: dict = {}
        alias_map = _GUARD_PARAM_ALIAS.get(guard_name, {})

        for key in input_keys:
            mapped_key = alias_map.get(key, key)
            if key in common_inputs:
                guard_inputs[mapped_key] = common_inputs[key]

        # project_path 特殊处理
        if guard_name in ("diff.explain",):
            guard_inputs["project_path"] = str(project_path)

        try:
            result = skill.run(context, guard_inputs)
            t_end = time.perf_counter()

            # 确定 passed：success=False 或 data 中有 passed=False
            passed = result.success
            if isinstance(result.data, dict) and "passed" in result.data:
                passed = bool(result.data["passed"])

            guards[guard_name] = GuardEntryResult(
                passed=passed,
                summary=result.summary,
                duration_ms=(t_end - t_start) * 1000,
                risks=list(result.risks) if result.risks else [],
                next_steps=list(result.next_steps) if result.next_steps else [],
            )
            guard_warning_counts[guard_name] = _count_warning_like_violations(
                result.data
            )
        except Exception as e:
            t_end = time.perf_counter()
            guards[guard_name] = GuardEntryResult(
                passed=False,
                summary=f"执行异常: {e}",
                duration_ms=(t_end - t_start) * 1000,
                error=str(e),
            )

    # ── 聚合 ──────────────────────────────────────────────────
    error_count = 0
    warning_count = 0
    all_passed = True

    for guard_name, entry in guards.items():
        if entry.error:
            error_count += 1
            all_passed = False
        elif not entry.passed:
            error_count += 1
            all_passed = False
        warning_count += guard_warning_counts.get(guard_name, 0)

    # 构建 suggested_actions
    suggested_actions: list[str] = []
    if all_passed:
        suggested_actions.append("所有 Guard 通过，可继续 apply/commit。")
    else:
        failed_names = [n for n, e in guards.items() if not e.passed]
        suggested_actions.append(
            f"以下 Guard 未通过: {', '.join(failed_names)}。请检查违规项后再 apply/commit。"
        )

    if skipped:
        suggested_actions.append(f"已跳过 Guard: {', '.join(skipped)}")

    # 构建总体摘要
    ran_count = len(guards)
    passed_count = sum(1 for e in guards.values() if e.passed and not e.error)
    summary_parts = [
        f"GuardRunner: {passed_count}/{ran_count} 通过"
    ]
    if skipped:
        summary_parts.append(f"{len(skipped)} 个跳过")
    if error_count:
        summary_parts.append(f"{error_count} 个错误")
    if warning_count:
        summary_parts.append(f"{warning_count} 个风险信号")

    return GuardRunResult(
        overall_passed=all_passed,
        guards=guards,
        error_count=error_count,
        warning_count=warning_count,
        suggested_actions=suggested_actions,
        selected=select,
        skipped=skipped,
        summary="，".join(summary_parts),
        run_id=run_id,
        timestamp=timestamp,
    )
