"""
Skill: git.merge.check — 合并前检查（R0 只读）

功能：在合并（PR/MR）前检查当前分支的合并就绪状态：
      工作区干净度、patch 备份残留、protected path、policy 合规性。
      不执行任何 merge 操作，只输出检查结果和建议。
风险：R0（只读，不修改任何文件）

设计约束（phase-11-design.md §3 Q3、§4.3）：
- 确定性输出，不用 LLM
- blockers（阻断项）vs warnings（警告项）两级分类
- ready = blockers 为空
- 不调用 graph.validate（避免强依赖索引），但检查索引是否存在作为信号
"""

from __future__ import annotations

from pathlib import Path

from smartdev.core.git import GitNotAvailable, GitService, load_git_policy
from smartdev.models import RiskLevel, SkillResult, TaskType
from smartdev.skills.base import Skill


# ── 检查项定义 ────────────────────────────────────────────


def _check_working_tree(svc: GitService) -> dict:
    """检查工作区是否干净。"""
    try:
        status = svc.status(recent_commit_count=0)
        if status.is_dirty:
            staged_n = len(status.staged)
            unstaged_n = len(status.unstaged)
            untracked_n = len(status.untracked)
            return {
                "name": "working_tree_clean",
                "passed": False,
                "level": "blocker",
                "message": (
                    f"工作区有未提交变更：staged={staged_n}, "
                    f"unstaged={unstaged_n}, untracked={untracked_n}"
                ),
                "fix": "运行 git.commit.plan 拆分提交，或 stash 后再合并",
            }
        return {
            "name": "working_tree_clean",
            "passed": True,
            "level": "ok",
            "message": "工作区干净",
        }
    except GitNotAvailable:
        return {
            "name": "working_tree_clean",
            "passed": False,
            "level": "blocker",
            "message": "无法获取工作区状态（git 不可用）",
        }


def _check_patch_backups(project_path: Path) -> dict:
    """检查是否有未清理的 patch 备份。"""
    backup_dir = project_path / ".smartdev" / "patch_backups"
    if not backup_dir.exists():
        return {
            "name": "patch_backups_clean",
            "passed": True,
            "level": "ok",
            "message": "无 patch 备份残留",
        }
    backups = list(backup_dir.iterdir())
    if not backups:
        return {
            "name": "patch_backups_clean",
            "passed": True,
            "level": "ok",
            "message": "patch_backups 目录为空",
        }
    return {
        "name": "patch_backups_clean",
        "passed": False,
        "level": "warning",
        "message": f".smartdev/patch_backups/ 有 {len(backups)} 个备份，确认已完成或可删除",
        "fix": "手动检查并删除不再需要的备份目录",
    }


def _check_target_branch(
    current_branch: str,
    target_branch: str,
    protected_branches: list[str],
) -> dict:
    """检查合并目标分支是否合理。"""
    # 同分支 merge 直接 blocker（优先级最高）
    if current_branch == target_branch:
        return {
            "name": "source_branch_ok",
            "passed": False,
            "level": "blocker",
            "message": f"source 和 target 是同一分支 '{current_branch}'，无法合并",
        }
    # 当前在 protected branch 上 merge 往往是错误操作
    if current_branch in protected_branches:
        return {
            "name": "source_branch_ok",
            "passed": False,
            "level": "warning",
            "message": (
                f"当前分支 '{current_branch}' 是 protected branch，"
                "通常应从功能分支向 protected branch 合并，而不是反向"
            ),
            "fix": "确认合并方向是否正确",
        }
    return {
        "name": "source_branch_ok",
        "passed": True,
        "level": "ok",
        "message": f"分支方向合理：'{current_branch}' → '{target_branch}'",
    }


def _check_has_commits(svc: GitService, target_branch: str) -> dict:
    """检查当前分支相对目标分支是否有新 commit。"""
    try:
        # git log <target>..<current> --oneline
        raw = svc._run(["git", "log", f"{target_branch}..HEAD", "--oneline"])
        commits = [l for l in raw.splitlines() if l]
        if not commits:
            return {
                "name": "has_new_commits",
                "passed": False,
                "level": "warning",
                "message": f"当前分支相对 '{target_branch}' 无新 commit",
                "fix": "确认是否已完成开发工作",
            }
        return {
            "name": "has_new_commits",
            "passed": True,
            "level": "ok",
            "message": f"有 {len(commits)} 个新 commit 待合并",
            "commit_count": len(commits),
        }
    except GitNotAvailable:
        # target_branch 不存在时 git log 会失败，退回为 warning
        return {
            "name": "has_new_commits",
            "passed": False,
            "level": "warning",
            "message": f"无法对比 '{target_branch}'（分支可能不存在）",
        }


def _check_index_available(project_path: Path) -> dict:
    """检查语义索引是否存在（影响 impact 分析质量）。"""
    db = project_path / ".smartdev" / "index.sqlite"
    if db.exists():
        return {
            "name": "semantic_index_available",
            "passed": True,
            "level": "ok",
            "message": "语义索引存在，impact 分析可正常运行",
        }
    return {
        "name": "semantic_index_available",
        "passed": False,
        "level": "warning",
        "message": "未建立语义索引，合并前建议运行 smartdev_code_index",
        "fix": "运行 `smartdev index` 或 `smartdev_code_index` 建立索引",
    }


class GitMergeCheckSkill(Skill):
    """合并前检查 Skill（R0 只读）

    在合并前输出结构化检查报告：blockers（阻断）和 warnings（警告）。
    ready = blockers 为空。不执行任何 merge 操作。

    inputs 参数：
        target_branch: str  合并目标分支（默认从 policy.protected_branches[0] 取）

    使用示例：
        result = Skill.create("git.merge.check").run(context)
        result = Skill.create("git.merge.check").run(context, {"target_branch": "main"})
    """

    name = "git.merge.check"
    description = "合并前检查：工作区干净度 / patch备份 / 分支方向 / 新commit / 索引状态"
    risk_level = RiskLevel.R0
    task_type = TaskType.PLAN

    def can_run(self, context) -> bool:
        if not context.project_path.exists():
            return False
        return GitService(context.project_path).is_available()

    def run(self, context, inputs: dict | None = None) -> SkillResult:
        inputs = inputs or {}
        project = context.project_path

        svc = GitService(project)
        policy = load_git_policy(project)

        # target_branch：优先 inputs，否则取 policy.protected_branches[0]
        target_branch: str = (
            inputs.get("target_branch")
            or (policy.protected_branches[0] if policy.protected_branches else "main")
        )

        # 当前分支
        try:
            current_branch = svc.current_branch()
        except GitNotAvailable as e:
            return SkillResult(
                success=False,
                summary=f"git.merge.check 失败：{e}",
                data={"error": "GIT_NOT_FOUND", "message": str(e)},
                risks=["git 不可用"],
            )

        # 执行各项检查
        checks = [
            _check_working_tree(svc),
            _check_patch_backups(project),
            _check_target_branch(current_branch, target_branch, policy.protected_branches),
            _check_has_commits(svc, target_branch),
            _check_index_available(project),
        ]

        blockers = [c for c in checks if not c["passed"] and c["level"] == "blocker"]
        warnings = [c for c in checks if not c["passed"] and c["level"] == "warning"]
        ready = len(blockers) == 0

        status_label = "✅ 可以合并" if ready else f"❌ 有 {len(blockers)} 个阻断项"
        summary_lines = [
            f"合并检查：{current_branch} → {target_branch}",
            status_label,
        ]
        if blockers:
            summary_lines.append(f"阻断项：{'; '.join(c['message'] for c in blockers)}")
        if warnings:
            summary_lines.append(f"警告项：{len(warnings)} 个")

        return SkillResult(
            success=True,
            summary="\n".join(summary_lines),
            data={
                "ready": ready,
                "checks": checks,
                "blockers": blockers,
                "warnings": warnings,
                "branch_info": {
                    "current": current_branch,
                    "target": target_branch,
                    "is_current_protected": current_branch in policy.protected_branches,
                },
            },
            next_steps=_build_next_steps(ready, blockers, warnings, current_branch, target_branch),
        )


def _build_next_steps(
    ready: bool,
    blockers: list[dict],
    warnings: list[dict],
    current: str,
    target: str,
) -> list[str]:
    if not ready:
        steps = [f"修复 {len(blockers)} 个阻断项后再合并："]
        for b in blockers:
            fix = b.get("fix", "")
            steps.append(f"  - {b['message']}" + (f"（{fix}）" if fix else ""))
        return steps
    steps = [f"✅ 分支 '{current}' 已就绪，可以合并到 '{target}'。"]
    if warnings:
        steps.append(f"注意 {len(warnings)} 个警告项，建议处理后再合并。")
    return steps
