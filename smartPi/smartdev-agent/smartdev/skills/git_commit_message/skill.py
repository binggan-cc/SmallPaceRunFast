"""
Skill: git.commit.message — Conventional Commit 消息生成（R0 只读）

功能：根据 type / scope / subject / body / breaking_change 生成
      符合 Conventional Commit 规范的 commit 消息字符串。
      不调用任何 git 命令，不依赖项目目录状态。
风险：R0（纯字符串生成，零副作用）

规范参考：https://www.conventionalcommits.org/en/v1.0.0/
格式：
  <type>[optional scope]: <subject>
  [optional body]
  [optional footer(s)]

Breaking change 有两种写法：
  1. type(scope)!: subject
  2. footer: BREAKING CHANGE: description

本实现两种都输出（footer 优先，更明确）。
"""

from __future__ import annotations

from smartdev.models import RiskLevel, SkillResult, TaskType
from smartdev.skills.base import Skill


# ── Conventional Commit 合法 type ────────────────────────

VALID_TYPES = {
    "feat", "fix", "docs", "test", "chore",
    "build", "refactor", "style", "ci", "perf",
}

_TYPE_DESCRIPTIONS = {
    "feat":     "新功能",
    "fix":      "Bug 修复",
    "docs":     "文档变更",
    "test":     "测试变更",
    "chore":    "杂项（不影响代码逻辑）",
    "build":    "构建系统或依赖变更",
    "refactor": "代码重构（不修 bug 不加功能）",
    "style":    "格式变更（空白、分号等）",
    "ci":       "CI 配置变更",
    "perf":     "性能优化",
}


# ── 格式校验 ──────────────────────────────────────────────


def validate_commit_inputs(
    commit_type: str,
    subject: str,
    scope: str,
) -> list[str]:
    """校验 commit 参数，返回问题列表（空列表=合法）。"""
    issues: list[str] = []

    if commit_type not in VALID_TYPES:
        issues.append(
            f"type '{commit_type}' 不在 Conventional Commit 合法列表中。"
            f"合法值：{', '.join(sorted(VALID_TYPES))}"
        )
    if not subject.strip():
        issues.append("subject 不能为空")
        return issues  # 空 subject 无需继续检查其他规则
    if len(subject) > 72:
        issues.append(f"subject 长度 {len(subject)} 超过建议的 72 字符")
    if subject[0].isupper() and len(subject) > 1:
        issues.append("subject 建议以小写字母开头（Conventional Commit 惯例）")
    if subject.endswith("."):
        issues.append("subject 不应以句号结尾")
    if scope and len(scope) > 30:
        issues.append(f"scope 长度 {len(scope)} 超过建议的 30 字符")

    return issues


# ── 消息组装 ──────────────────────────────────────────────


def build_commit_message(
    commit_type: str,
    subject: str,
    scope: str = "",
    body: str = "",
    breaking_change: str = "",
    co_authors: list[str] | None = None,
) -> str:
    """组装符合 Conventional Commit 规范的 commit 消息。

    Args:
        commit_type:     Conventional Commit type（feat / fix 等）
        subject:         一行描述
        scope:           影响范围（可空）
        body:            详细描述（可空，多段用 \\n\\n 分隔）
        breaking_change: BREAKING CHANGE 描述（非空时加 footer + ! 标记）
        co_authors:      Co-authored-by 列表

    Returns:
        完整 commit 消息字符串
    """
    # header
    is_breaking = bool(breaking_change)
    if scope:
        header = f"{commit_type}({scope})"
    else:
        header = commit_type
    if is_breaking:
        header += "!"
    header += f": {subject.strip()}"

    parts = [header]

    # body（空行分隔）
    if body and body.strip():
        parts.append("")
        parts.append(body.strip())

    # footers
    footers: list[str] = []
    if is_breaking:
        footers.append(f"BREAKING CHANGE: {breaking_change.strip()}")
    if co_authors:
        for author in co_authors:
            footers.append(f"Co-authored-by: {author.strip()}")

    if footers:
        parts.append("")
        parts.extend(footers)

    return "\n".join(parts)


class GitCommitMessageSkill(Skill):
    """Conventional Commit 消息生成 Skill（R0 只读）

    纯字符串生成，不调用任何 git 命令，不读项目目录。
    can_run() 只检查必须输入是否提供。

    inputs 参数（全部通过 inputs dict 传入）：
        type: str              必须，Conventional Commit type
        subject: str           必须，一行描述
        scope: str             可选，影响范围
        body: str              可选，详细描述
        breaking_change: str   可选，BREAKING CHANGE 描述
        co_authors: list[str]  可选，Co-authored-by 列表

    使用示例：
        result = Skill.create("git.commit.message").run(context, {
            "type": "feat",
            "scope": "context",
            "subject": "add git status skill",
        })
    """

    name = "git.commit.message"
    description = "生成符合 Conventional Commit 规范的 commit 消息（不执行 commit）"
    risk_level = RiskLevel.R0
    task_type = TaskType.PLAN

    def can_run(self, context) -> bool:
        """只要项目目录存在即可运行（不依赖 git 可用性）。"""
        return context.project_path.exists()

    def run(self, context, inputs: dict | None = None) -> SkillResult:
        inputs = inputs or {}
        commit_type = str(inputs.get("type", "")).strip()
        subject = str(inputs.get("subject", "")).strip()
        scope = str(inputs.get("scope", "")).strip()
        body = str(inputs.get("body", "")).strip()
        breaking_change = str(inputs.get("breaking_change", "")).strip()
        co_authors = list(inputs.get("co_authors", []))

        # 必须参数检查
        if not commit_type:
            return SkillResult(
                success=False,
                summary="git.commit.message 失败：缺少必须参数 'type'",
                data={"error": "MISSING_TYPE", "valid_types": sorted(VALID_TYPES)},
            )
        if not subject:
            return SkillResult(
                success=False,
                summary="git.commit.message 失败：缺少必须参数 'subject'",
                data={"error": "MISSING_SUBJECT"},
            )

        # 格式校验（非拦截，仅警告）
        issues = validate_commit_inputs(commit_type, subject, scope)

        message = build_commit_message(
            commit_type=commit_type,
            subject=subject,
            scope=scope,
            body=body,
            breaking_change=breaking_change,
            co_authors=co_authors,
        )

        is_breaking = bool(breaking_change)
        header = message.splitlines()[0]

        return SkillResult(
            success=True,
            summary=f"生成 commit 消息：{header}",
            data={
                "message": message,
                "header": header,
                "is_breaking": is_breaking,
                "validation": {
                    "ok": len(issues) == 0,
                    "issues": issues,
                },
                "type": commit_type,
                "scope": scope,
                "subject": subject,
            },
            next_steps=[
                "使用 `smartdev git commit --message '<message>' --apply` 执行提交。"
                if not issues else
                f"注意 {len(issues)} 个格式建议：{'; '.join(issues)}"
            ],
        )
