"""
Skill: git.commit.plan — Commit 拆分建议（R0 只读）

功能：分析当前 diff，建议如何拆成符合 Conventional Commit 规范的多个提交。
      每个建议包含：type / scope / subject / files / reason。
      不执行 commit，不调用 git.commit.message（后者按需单独调用）。
风险：R0（只读，不修改任何文件）

设计约束（phase-11-design.md §3 Q3、§4.3）：
- 确定性输出，不用 LLM
- 复用 git_diff_explain 的文件分类逻辑（_classify_file）
- scope 推导：从文件路径顶层目录 / 文件名启发式推断
- type 推导：基于文件类别 + 状态码（A/M/D）

Conventional Commit type 映射：
  manifest 新增依赖  → build
  manifest 其他     → chore
  doc               → docs
  test              → test
  source 新增文件    → feat
  source 删除文件    → refactor
  source 修改文件    → fix / feat（无法区分时用 fix）
  config            → chore
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from smartdev.core.git import GitDiff, GitFileChange, GitNotAvailable, GitService, load_git_policy
from smartdev.models import RiskLevel, SkillResult, TaskType
from smartdev.skills.base import Skill
from smartdev.skills.git_diff_explain.skill import _classify_file


# ── Conventional Commit type 推导 ─────────────────────────


def _infer_type(category: str, status: str) -> str:
    """从文件类别 + git 状态码推导 Conventional Commit type。

    status: git porcelain status code (A=added, D=deleted, M=modified, R=renamed)
    """
    if category == "doc":
        return "docs"
    if category == "test":
        return "test"
    if category == "manifest":
        # 新增依赖 → build；其他 manifest 改动 → chore
        return "build" if status == "A" else "chore"
    if category == "config":
        return "chore"
    # source / other
    if status == "A":
        return "feat"
    if status == "D":
        return "refactor"
    return "fix"  # M: 修改文件，保守地用 fix，用户可自行改为 feat


def _infer_scope(files: list[GitFileChange], scope_hint: str | None) -> str:
    """从文件路径推导 scope（最多 20 字符）。

    优先级：
    1. 调用方提供的 scope_hint
    2. 所有文件共同的顶层目录（若唯一）
    3. 文件名 stem 中最常见的前缀词
    4. 空字符串（无法推导时）
    """
    if scope_hint:
        return scope_hint[:20]

    # 取顶层目录
    top_dirs: set[str] = set()
    for f in files:
        parts = Path(f.path).parts
        if len(parts) >= 2:
            top_dirs.add(parts[0])

    if len(top_dirs) == 1:
        scope = top_dirs.pop()
        return scope[:20]

    # 多个顶层目录时：尝试取最长公共前缀（至少 3 字符）
    if top_dirs:
        sorted_dirs = sorted(top_dirs)
        prefix = sorted_dirs[0]
        for d in sorted_dirs[1:]:
            while not d.startswith(prefix):
                prefix = prefix[:-1]
                if not prefix:
                    break
        if len(prefix) >= 3:
            return prefix[:20]

    return ""


# ── 建议 commit 数据模型 ──────────────────────────────────


@dataclass
class CommitSuggestion:
    """单个建议 commit 的结构化描述。"""
    type: str                          # Conventional Commit type
    scope: str                         # scope（可空）
    subject: str                       # 一行 subject（自动生成）
    files: list[str] = field(default_factory=list)   # 涉及的文件路径
    reason: str = ""                   # 建议拆分的理由

    def to_dict(self) -> dict:
        header = f"{self.type}"
        if self.scope:
            header += f"({self.scope})"
        header += f": {self.subject}"
        return {
            "type": self.type,
            "scope": self.scope,
            "subject": self.subject,
            "header": header,
            "files": self.files,
            "reason": self.reason,
        }


def _make_subject(category: str, files: list[GitFileChange]) -> str:
    """生成 subject 占位文本（确定性，用户应自行完善）。

    只是建议骨架，外部 Agent 可基于此生成更具体的描述。
    """
    n = len(files)
    names = [Path(f.path).stem for f in files[:3]]
    preview = ", ".join(names)
    if n > 3:
        preview += f" and {n - 3} more"

    if category == "doc":
        return f"update docs ({preview})"
    if category == "test":
        return f"add/update tests ({preview})"
    if category == "manifest":
        return f"update dependencies ({preview})"
    if category == "config":
        return f"update config ({preview})"
    return f"<describe change> ({preview})"


# ── 核心：按类别分组成建议 commit ─────────────────────────


def build_commit_suggestions(
    diff: GitDiff,
    scope_hint: str | None = None,
) -> list[CommitSuggestion]:
    """把 diff 里的文件分组成建议 commit 列表。

    分组逻辑：
    1. 按文件类别分桶（source / test / doc / manifest / config / other）
    2. source 进一步按顶层目录分桶（跨模块时拆开）
    3. 每个桶 → 一个 CommitSuggestion

    返回列表顺序：source commits 在前，test / docs / manifest 在后。
    """
    # 分桶
    by_category: dict[str, list[GitFileChange]] = {}
    for f in diff.files:
        cat = _classify_file(f.path)
        by_category.setdefault(cat, []).append(f)

    suggestions: list[CommitSuggestion] = []

    # ── source / other：按顶层目录拆 ───────────────────────
    source_files = by_category.get("source", []) + by_category.get("other", [])
    if source_files:
        # 按顶层目录分组
        by_top: dict[str, list[GitFileChange]] = {}
        for f in source_files:
            parts = Path(f.path).parts
            top = parts[0] if len(parts) >= 2 else "<root>"
            by_top.setdefault(top, []).append(f)

        for top_dir, files in sorted(by_top.items()):
            commit_type = _infer_type("source", files[0].status)
            scope = scope_hint or (top_dir if top_dir != "<root>" else "")
            scope = scope[:20]
            suggestions.append(CommitSuggestion(
                type=commit_type,
                scope=scope,
                subject=_make_subject("source", files),
                files=[f.path for f in files],
                reason=f"source files in {top_dir!r}",
            ))

    # ── config ─────────────────────────────────────────────
    config_files = by_category.get("config", [])
    if config_files:
        scope = _infer_scope(config_files, scope_hint)
        suggestions.append(CommitSuggestion(
            type="chore",
            scope=scope,
            subject=_make_subject("config", config_files),
            files=[f.path for f in config_files],
            reason="configuration file changes",
        ))

    # ── test ───────────────────────────────────────────────
    test_files = by_category.get("test", [])
    if test_files:
        scope = _infer_scope(test_files, scope_hint)
        suggestions.append(CommitSuggestion(
            type="test",
            scope=scope,
            subject=_make_subject("test", test_files),
            files=[f.path for f in test_files],
            reason="test file changes",
        ))

    # ── docs ───────────────────────────────────────────────
    doc_files = by_category.get("doc", [])
    if doc_files:
        scope = _infer_scope(doc_files, scope_hint)
        suggestions.append(CommitSuggestion(
            type="docs",
            scope=scope,
            subject=_make_subject("doc", doc_files),
            files=[f.path for f in doc_files],
            reason="documentation changes",
        ))

    # ── manifest ───────────────────────────────────────────
    manifest_files = by_category.get("manifest", [])
    if manifest_files:
        commit_type = _infer_type("manifest", manifest_files[0].status)
        scope = _infer_scope(manifest_files, scope_hint)
        suggestions.append(CommitSuggestion(
            type=commit_type,
            scope=scope,
            subject=_make_subject("manifest", manifest_files),
            files=[f.path for f in manifest_files],
            reason="dependency manifest changes",
        ))

    return suggestions


class GitCommitPlanSkill(Skill):
    """Commit 拆分建议 Skill（R0 只读）

    分析当前 diff，建议如何拆成符合 Conventional Commit 规范的多个提交。
    不执行 commit，不调用 GitService.commit()。

    inputs 参数：
        staged_only: bool   True=只看 staged diff（默认 False，全部 diff）
        scope_hint: str     调用方提供的 scope 提示

    使用示例：
        result = Skill.create("git.commit.plan").run(context)
        result = Skill.create("git.commit.plan").run(context, {"scope_hint": "context"})
    """

    name = "git.commit.plan"
    description = "分析 diff，生成 Conventional Commit 拆分建议（不执行 commit）"
    risk_level = RiskLevel.R0
    task_type = TaskType.PLAN

    def can_run(self, context) -> bool:
        if not context.project_path.exists():
            return False
        return GitService(context.project_path).is_available()

    def run(self, context, inputs: dict | None = None) -> SkillResult:
        inputs = inputs or {}
        project = context.project_path
        staged_only = bool(inputs.get("staged_only", False))
        scope_hint = inputs.get("scope_hint") or None

        svc = GitService(project)
        try:
            diff = svc.diff(staged=staged_only)
        except GitNotAvailable as e:
            return SkillResult(
                success=False,
                summary=f"git.commit.plan 失败：{e}",
                data={"error": "GIT_NOT_FOUND", "message": str(e)},
                risks=["git 不可用"],
            )

        if not diff.files:
            return SkillResult(
                success=True,
                summary="无 diff，无需生成 commit 建议。",
                data={
                    "commits": [],
                    "policy_warnings": [],
                    "total_files": 0,
                    "staged_only": staged_only,
                },
                next_steps=["工作区干净，无变更可提交。"],
            )

        policy = load_git_policy(project)
        suggestions = build_commit_suggestions(diff, scope_hint=scope_hint)

        # policy 检查
        policy_warnings: list[str] = []
        total_files = len(diff.files)
        if total_files > policy.max_files_per_commit:
            policy_warnings.append(
                f"总变更文件数 {total_files} 超过 policy.max_files_per_commit={policy.max_files_per_commit}，"
                "建议先拆分任务再提交"
            )
        # protected branch 警告
        try:
            branch = svc.current_branch()
            if branch in policy.protected_branches:
                policy_warnings.append(
                    f"当前在 protected branch '{branch}'，建议切换到功能分支后提交"
                )
        except GitNotAvailable:
            pass

        n_commits = len(suggestions)
        summary = (
            f"建议拆成 {n_commits} 个 commit，共 {total_files} 个文件"
            + (f"，{len(policy_warnings)} 个 policy 警告" if policy_warnings else "")
        )

        return SkillResult(
            success=True,
            summary=summary,
            data={
                "commits": [s.to_dict() for s in suggestions],
                "policy_warnings": policy_warnings,
                "total_files": total_files,
                "staged_only": staged_only,
            },
            next_steps=_build_next_steps(suggestions, policy_warnings),
        )


def _build_next_steps(
    suggestions: list[CommitSuggestion],
    policy_warnings: list[str],
) -> list[str]:
    steps: list[str] = []
    if policy_warnings:
        steps.append(f"⚠️ {policy_warnings[0]}")
    if suggestions:
        steps.append(
            "运行 git.commit.message 为每个建议 commit 生成完整提交消息，"
            "或直接使用 `smartdev git commit --message <msg> --apply` 提交。"
        )
    return steps
