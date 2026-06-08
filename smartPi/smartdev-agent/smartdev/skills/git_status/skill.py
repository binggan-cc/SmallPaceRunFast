"""
Skill: git.status — Git 状态快照（R0 只读）

功能：查询当前分支、脏文件、staged/unstaged/untracked 列表、最近提交。
风险：R0（只读，不修改任何文件）

设计约束（phase-11-design.md §3 Q2、§4.3）：
- 通过 GitService 调用系统 git，零外部依赖
- git 不可用时 can_run() 返回 False，不抛异常
- 附加 policy_hints：当前分支是否为 protected branch
- 不执行任何 git 写操作
"""

from __future__ import annotations

from smartdev.core.git import GitNotAvailable, GitService, load_git_policy
from smartdev.models import RiskLevel, SkillResult, TaskType
from smartdev.skills.base import Skill


class GitStatusSkill(Skill):
    """Git 状态快照 Skill（R0 只读）

    查询当前 git 仓库的完整状态快照，供后续 diff.explain、
    commit.plan 等 Skill 消费，也可直接通过 MCP 暴露给外部 Agent。

    inputs 参数：
        recent_commit_count: int  最近提交数量（默认 10）

    使用示例：
        result = Skill.create("git.status").run(context)
    """

    name = "git.status"
    description = "查询 git 状态：当前分支、脏文件、staged/unstaged/untracked、最近提交"
    risk_level = RiskLevel.R0
    task_type = TaskType.DIAGNOSE

    def can_run(self, context) -> bool:
        """前置条件：项目目录存在且 git 可用。"""
        if not context.project_path.exists():
            return False
        return GitService(context.project_path).is_available()

    def run(self, context, inputs: dict | None = None) -> SkillResult:
        inputs = inputs or {}
        project = context.project_path
        recent_count = int(inputs.get("recent_commit_count", 10))

        svc = GitService(project)
        try:
            status = svc.status(recent_commit_count=recent_count)
        except GitNotAvailable as e:
            return SkillResult(
                success=False,
                summary=f"git.status 失败：{e}",
                data={"error": "GIT_NOT_FOUND", "message": str(e)},
                risks=["git 不可用"],
            )

        # policy hints
        policy = load_git_policy(project)
        policy_hints: list[str] = []
        if status.branch in policy.protected_branches:
            policy_hints.append(
                f"当前分支 '{status.branch}' 是 protected branch，"
                "commit/merge 需谨慎"
            )

        # 可读摘要
        dirty_label = "有未提交变更" if status.is_dirty else "干净"
        summary_lines = [
            f"分支：{status.branch}（{dirty_label}）",
            f"staged：{len(status.staged)} 个文件",
            f"unstaged：{len(status.unstaged)} 个文件",
            f"untracked：{len(status.untracked)} 个文件",
            f"最近 {len(status.recent_commits)} 条提交已加载",
        ]
        if policy_hints:
            summary_lines.append(f"⚠️  {policy_hints[0]}")

        return SkillResult(
            success=True,
            summary="\n".join(summary_lines),
            data={
                "branch": status.branch,
                "is_dirty": status.is_dirty,
                "staged": [
                    {"path": f.path, "status": f.status}
                    for f in status.staged
                ],
                "unstaged": [
                    {"path": f.path, "status": f.status}
                    for f in status.unstaged
                ],
                "untracked": status.untracked,
                "recent_commits": status.recent_commits,
                "policy_hints": policy_hints,
            },
            next_steps=_build_next_steps(status, policy_hints),
        )


def _build_next_steps(status, policy_hints: list[str]) -> list[str]:
    steps: list[str] = []
    if not status.is_dirty:
        steps.append("工作区干净，可以安全创建新分支或开始新任务。")
        return steps
    if status.staged:
        steps.append(
            f"{len(status.staged)} 个文件已 stage，运行 git.commit.plan 生成提交建议。"
        )
    if status.unstaged:
        steps.append(
            f"{len(status.unstaged)} 个文件有未 stage 的变更，"
            "运行 git.diff.explain 查看详情。"
        )
    if status.untracked:
        steps.append(
            f"{len(status.untracked)} 个未跟踪文件，确认是否需要 .gitignore 或 stage。"
        )
    if policy_hints:
        steps.append("当前在 protected branch，建议切换到功能分支后再提交。")
    return steps
