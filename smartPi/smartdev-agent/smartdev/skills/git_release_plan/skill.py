"""
Skill: git.release.plan — 发布规划（R0 只读）

功能：读取 CHANGELOG / version 文件 / 最近 commits，推断 semver bump
      建议并输出发布检查清单。不执行任何 git 操作。
风险：R0（只读，不修改任何文件）

设计约束（phase-11-design.md §3 Q3）：
- 确定性输出，不用 LLM
- semver bump 规则基于 Conventional Commit type：
    BREAKING CHANGE / ! → major
    feat              → minor
    fix/docs/test/... → patch
    无 commits        → none
- version 文件读取：仅支持 pyproject.toml（[project].version）
  和 package.json（"version"），保持零依赖（用正则/json 解析）
- CHANGELOG 状态：检查文件是否存在、是否有 [Unreleased] 节
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from smartdev.core.git import GitNotAvailable, GitService, load_git_policy
from smartdev.models import RiskLevel, SkillResult, TaskType
from smartdev.skills.base import Skill


# ── semver bump 推导 ───────────────────────────────────────

# Conventional Commit type → bump weight
_TYPE_BUMP: dict[str, int] = {
    "feat":     2,   # minor
    "fix":      1,   # patch
    "docs":     1,
    "test":     1,
    "chore":    1,
    "build":    1,
    "refactor": 1,
    "style":    1,
    "ci":       1,
    "perf":     1,
}
_BREAKING_WEIGHT = 3   # major

# 解析 conventional commit header
_CC_RE = re.compile(
    r"^(?P<type>\w+)(?:\((?P<scope>[^)]*)\))?(?P<breaking>!)?\s*:\s*(?P<subject>.+)$"
)


def _parse_commit_line(line: str) -> dict:
    """从 git log --oneline 的一行提取 type / breaking 信号。

    格式：  <hash> <type>(<scope>)!: <subject>
    hash 是第一个 token，其余是 commit header。
    """
    parts = line.split(" ", 1)
    header = parts[1] if len(parts) == 2 else line
    m = _CC_RE.match(header.strip())
    if not m:
        return {"type": "", "breaking": False, "raw": header.strip()}
    return {
        "type": m.group("type"),
        "breaking": bool(m.group("breaking")) or "BREAKING CHANGE" in header,
        "raw": header.strip(),
    }


def _infer_bump(commits: list[str]) -> tuple[str, str]:
    """从 commit 列表推断 semver bump 类型和理由。

    Returns:
        (bump_type, reason)  bump_type: "major" | "minor" | "patch" | "none"
    """
    if not commits:
        return "none", "无新提交"

    max_weight = 0
    reasons: list[str] = []
    for line in commits:
        parsed = _parse_commit_line(line)
        if parsed["breaking"]:
            max_weight = max(max_weight, _BREAKING_WEIGHT)
            reasons.append(f"BREAKING CHANGE: {parsed['raw']}")
        weight = _TYPE_BUMP.get(parsed["type"], 1)
        max_weight = max(max_weight, weight)
        if parsed["type"] == "feat" and not parsed["breaking"]:
            reasons.append(f"feat: {parsed['raw']}")

    if max_weight >= _BREAKING_WEIGHT:
        reason = "包含 BREAKING CHANGE：" + "; ".join(reasons[:3])
        return "major", reason
    if max_weight >= 2:
        feat_count = sum(1 for c in commits if _parse_commit_line(c)["type"] == "feat")
        return "minor", f"包含 {feat_count} 个 feat commit"
    return "patch", f"仅包含 patch 级变更（{len(commits)} 个 commit）"


def _bump_version(version: str, bump: str) -> str:
    """对 semver 字符串执行 bump，保留前缀 v（若有）。

    不支持预发布标签（alpha/beta/rc），直接操作 M.N.P 部分。
    格式不合法时返回原版本。
    """
    prefix = "v" if version.startswith("v") else ""
    clean = version.lstrip("v")
    parts = clean.split(".")
    if len(parts) < 3:
        return version
    try:
        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        return version

    if bump == "major":
        return f"{prefix}{major + 1}.0.0"
    if bump == "minor":
        return f"{prefix}{major}.{minor + 1}.0"
    if bump == "patch":
        return f"{prefix}{major}.{minor}.{patch + 1}"
    return version


# ── version 文件读取 ───────────────────────────────────────


def _read_version(project_path: Path, version_files: list[str]) -> tuple[str, str]:
    """从 version_files 列表中依次尝试读取版本号。

    Returns:
        (version_string, source_file)  读取失败返回 ("", "")
    """
    for rel in version_files:
        vfile = project_path / rel
        if not vfile.exists():
            continue
        try:
            content = vfile.read_text(encoding="utf-8")
        except OSError:
            continue

        name_lower = vfile.name.lower()

        if name_lower == "pyproject.toml":
            # [project]\nversion = "x.y.z"
            m = re.search(r'^\s*version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
            if m:
                return m.group(1), rel

        elif name_lower == "package.json":
            try:
                data = json.loads(content)
                v = data.get("version", "")
                if v:
                    return v, rel
            except ValueError:
                pass

        else:
            # 通用：查找形如 version = "x.y.z" 或 VERSION = "x.y.z"
            m = re.search(r'(?i)version\s*=\s*["\']?([0-9]+\.[0-9]+\.[0-9]+[^\s"\']*)["\']?', content)
            if m:
                return m.group(1), rel

    return "", ""


# ── CHANGELOG 检查 ────────────────────────────────────────


def _check_changelog(project_path: Path, changelog_file: str) -> dict:
    """检查 CHANGELOG 文件状态。"""
    cf = project_path / changelog_file
    if not cf.exists():
        return {
            "exists": False,
            "has_unreleased": False,
            "path": changelog_file,
            "note": "CHANGELOG 文件不存在，建议在发布前创建",
        }
    try:
        content = cf.read_text(encoding="utf-8")
    except OSError:
        return {"exists": True, "has_unreleased": False, "path": changelog_file, "note": "无法读取"}

    has_unreleased = bool(re.search(r"##\s*\[?[Uu]nreleased\]?", content))
    return {
        "exists": True,
        "has_unreleased": has_unreleased,
        "path": changelog_file,
        "note": (
            "有 [Unreleased] 节，发布前记得更新版本号和日期"
            if has_unreleased
            else "无 [Unreleased] 节，建议补充本次发布内容"
        ),
    }


# ── 发布检查清单 ──────────────────────────────────────────


def _build_release_checklist(
    bump: str,
    changelog: dict,
    is_dirty: bool,
    has_patch_backups: bool,
) -> list[str]:
    items: list[str] = [
        f"确认 semver bump 类型：{bump}",
        "确认所有待发布功能已合并到发布分支",
        "运行完整测试套件，确认 0 failed",
    ]
    if not changelog["exists"]:
        items.append("⚠️  创建 CHANGELOG.md 并记录本次发布内容")
    elif changelog["has_unreleased"]:
        items.append("将 CHANGELOG 中 [Unreleased] 节重命名为新版本号和日期")
    else:
        items.append("在 CHANGELOG 中补充本次发布内容")

    items.append("更新 version 文件中的版本号")

    if is_dirty:
        items.append("⚠️  工作区有未提交变更，发布前请先提交或 stash")
    if has_patch_backups:
        items.append("检查 .smartdev/patch_backups/ 是否有未清理的备份")
    if bump == "major":
        items.append("⚠️  major bump：确认下游消费方已知晓 BREAKING CHANGE")
    items.append("使用 `smartdev git tag --version vX.Y.Z --apply` 打 tag（tag 步骤在 CLI 执行）")
    items.append("验证：git tag | grep <new_version>")
    return items


class GitReleasePlanSkill(Skill):
    """发布规划 Skill（R0 只读）

    分析 commits、版本文件、CHANGELOG，给出 semver bump 建议和发布检查清单。
    不执行任何 git 操作。

    inputs 参数：
        since_tag: str   从哪个 tag 开始统计 commits（默认最新 tag）

    使用示例：
        result = Skill.create("git.release.plan").run(context)
        result = Skill.create("git.release.plan").run(context, {"since_tag": "v0.3.0"})
    """

    name = "git.release.plan"
    description = "分析 commits/CHANGELOG/version 文件，建议 semver bump 类型和发布检查清单"
    risk_level = RiskLevel.R0
    task_type = TaskType.PLAN

    def can_run(self, context) -> bool:
        if not context.project_path.exists():
            return False
        return GitService(context.project_path).is_available()

    def run(self, context, inputs: dict | None = None) -> SkillResult:
        inputs = inputs or {}
        project = context.project_path
        since_tag: str | None = inputs.get("since_tag") or None

        svc = GitService(project)
        policy = load_git_policy(project)

        # ── 1. 读取当前版本 ──────────────────────────────
        current_version, version_source = _read_version(project, policy.version_files)

        # ── 2. 确定 since_tag（默认最新 tag）───────────
        tags = []
        try:
            tags = svc.tags()
        except GitNotAvailable as e:
            return SkillResult(
                success=False,
                summary=f"git.release.plan 失败：{e}",
                data={"error": "GIT_NOT_FOUND", "message": str(e)},
                risks=["git 不可用"],
            )

        if since_tag is None and tags:
            since_tag = tags[-1]  # 字母序最后一个（通常是最新 tag）

        # ── 3. 获取 commits ──────────────────────────────
        try:
            if since_tag:
                # git log <since_tag>..HEAD --oneline
                raw = svc._run(["git", "log", f"{since_tag}..HEAD", "--oneline"])
                commits = [l for l in raw.splitlines() if l]
            else:
                commits = svc.log_oneline(n=50)
        except GitNotAvailable:
            commits = []

        # ── 4. semver bump ──────────────────────────────
        bump, bump_reason = _infer_bump(commits)

        suggested_version = ""
        if current_version and bump != "none":
            suggested_version = _bump_version(current_version, bump)

        # ── 5. CHANGELOG 检查 ────────────────────────────
        changelog = _check_changelog(project, policy.changelog_file)

        # ── 6. 工作区脏检查 ──────────────────────────────
        is_dirty = False
        try:
            status = svc.status(recent_commit_count=0)
            is_dirty = status.is_dirty
        except GitNotAvailable:
            pass

        # ── 7. patch_backups 检查 ────────────────────────
        backup_dir = project / ".smartdev" / "patch_backups"
        has_patch_backups = backup_dir.exists() and any(backup_dir.iterdir())

        # ── 8. 发布检查清单 ──────────────────────────────
        checklist = _build_release_checklist(bump, changelog, is_dirty, has_patch_backups)

        summary_parts = [f"semver bump 建议：{bump}"]
        if current_version:
            summary_parts.append(f"当前版本：{current_version}（来自 {version_source}）")
        if suggested_version:
            summary_parts.append(f"建议版本：{suggested_version}")
        summary_parts.append(f"分析了 {len(commits)} 个 commit")

        return SkillResult(
            success=True,
            summary="\n".join(summary_parts),
            data={
                "current_version": current_version,
                "version_source": version_source,
                "suggested_bump": bump,
                "suggested_version": suggested_version,
                "bump_reason": bump_reason,
                "since_tag": since_tag,
                "recent_commits": commits[:20],
                "changelog_status": changelog,
                "release_checklist": checklist,
                "is_dirty": is_dirty,
            },
            next_steps=[
                f"建议执行 {bump} bump：{current_version} → {suggested_version}"
                if suggested_version else "无新 commit，无需发布。",
                "完成 release_checklist 后使用 `smartdev git tag --version <v> --apply` 打 tag。",
            ],
        )
