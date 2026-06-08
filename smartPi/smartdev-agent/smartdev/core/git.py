"""
GitService — Git 底层封装

设计原理：
─────────
Phase 11A Git Governance 的唯一 subprocess 接触点。
所有 git Skill 和 git CLI Command 都通过此模块与系统 git 交互。

为什么不用 GitPython？
──────────────────────
保持 SmartDev 零外部依赖原则。git 是系统级工具，假设已存在；
不存在时返回 GitNotAvailable，不抛未处理异常，不自动安装。

安全约定：
──────────
- subprocess 调用一律使用列表参数，不用 shell=True 字符串拼接，防止注入
- commit() / tag() 仅供 CLI Command 调用，git Skill 层不导入这两个方法
- 所有只读方法不修改任何文件，副作用为零

对应文档：
- docs/phase-11-design.md §3 Q2、§4.2
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


# ── 异常 ──────────────────────────────────────────────────


class GitNotAvailable(Exception):
    """系统未安装 git 或当前目录不是 git 仓库。

    调用方应捕获此异常并返回 GIT_NOT_FOUND 错误，不允许崩溃。
    """


# ── 数据模型 ──────────────────────────────────────────────


@dataclass
class GitFileChange:
    """单个文件的变更记录。

    Attributes:
        path:         相对于项目根的文件路径
        status:       git porcelain 状态码（M / A / D / R / ?? 等）
        staged:       是否已 stage（index 区）
        added_lines:  新增行数（来自 --numstat）
        deleted_lines: 删除行数
    """
    path: str
    status: str
    staged: bool
    added_lines: int = 0
    deleted_lines: int = 0


@dataclass
class GitStatus:
    """git status 的结构化输出。

    Attributes:
        branch:         当前分支名（detached HEAD 时为空字符串）
        is_dirty:       是否有未提交的变更（staged 或 unstaged）
        staged:         已 stage 的文件变更
        unstaged:       未 stage 的文件变更
        untracked:      未跟踪的文件路径
        recent_commits: 最近提交摘要（git log --oneline）
    """
    branch: str
    is_dirty: bool
    staged: list[GitFileChange] = field(default_factory=list)
    unstaged: list[GitFileChange] = field(default_factory=list)
    untracked: list[str] = field(default_factory=list)
    recent_commits: list[str] = field(default_factory=list)


@dataclass
class GitDiff:
    """git diff 的结构化输出。

    Attributes:
        files:       各文件的变更记录
        insertions:  总新增行数
        deletions:   总删除行数
        staged:      是否是 staged diff（--cached）
    """
    files: list[GitFileChange] = field(default_factory=list)
    insertions: int = 0
    deletions: int = 0
    staged: bool = False


# ── policy 数据模型 ───────────────────────────────────────


@dataclass
class GitPolicy:
    """git-policy.json 的结构化表示。

    不存在配置文件时使用安全默认值。
    """
    protected_branches: list[str] = field(default_factory=lambda: ["main", "master"])
    commit_convention: str = "conventional"
    require_tests_before_commit: bool = False
    require_changelog_for_phase: bool = True
    max_files_per_commit: int = 12
    changelog_file: str = "CHANGELOG.md"
    version_files: list[str] = field(default_factory=lambda: ["pyproject.toml"])
    forbid_push: bool = True
    forbid_force_push: bool = True
    forbid_reset_hard: bool = True
    forbid_rebase: bool = True
    forbid_merge_apply: bool = True


# ── policy 加载 ───────────────────────────────────────────

_POLICY_FILENAMES = [
    ".smartdev/git-policy.json",
    "smartdev.git.json",
]


def load_git_policy(project_path: Path) -> GitPolicy:
    """从项目加载 git-policy.json，不存在时使用安全默认值。

    路径优先级：.smartdev/git-policy.json > smartdev.git.json

    只覆盖配置文件中明确指定的字段，缺失字段保留默认值。
    解析失败（格式错误）时退回默认值并静默处理。
    """
    policy = GitPolicy()
    for name in _POLICY_FILENAMES:
        candidate = project_path / name
        if candidate.exists():
            try:
                raw = json.loads(candidate.read_text(encoding="utf-8"))
                _apply_policy_dict(policy, raw)
            except (OSError, ValueError):
                pass  # 解析失败退回默认值
            break
    return policy


def _apply_policy_dict(policy: GitPolicy, raw: dict) -> None:
    """把 JSON dict 中的字段覆写到 policy，缺失字段保留默认值。"""
    branch = raw.get("branch", {})
    if "protected" in branch:
        policy.protected_branches = list(branch["protected"])

    commit = raw.get("commit", {})
    if "convention" in commit:
        policy.commit_convention = str(commit["convention"])
    if "require_tests_before_commit" in commit:
        policy.require_tests_before_commit = bool(commit["require_tests_before_commit"])
    if "require_changelog_for_phase" in commit:
        policy.require_changelog_for_phase = bool(commit["require_changelog_for_phase"])
    if "max_files_per_commit" in commit:
        policy.max_files_per_commit = int(commit["max_files_per_commit"])

    release = raw.get("release", {})
    if "changelog_file" in release:
        policy.changelog_file = str(release["changelog_file"])
    if "version_files" in release:
        policy.version_files = list(release["version_files"])

    dangerous = raw.get("dangerous", {})
    if "forbid_push" in dangerous:
        policy.forbid_push = bool(dangerous["forbid_push"])
    if "forbid_force_push" in dangerous:
        policy.forbid_force_push = bool(dangerous["forbid_force_push"])
    if "forbid_reset_hard" in dangerous:
        policy.forbid_reset_hard = bool(dangerous["forbid_reset_hard"])
    if "forbid_rebase" in dangerous:
        policy.forbid_rebase = bool(dangerous["forbid_rebase"])
    if "forbid_merge_apply" in dangerous:
        policy.forbid_merge_apply = bool(dangerous["forbid_merge_apply"])


# ── GitService ────────────────────────────────────────────


class GitService:
    """Git 底层操作封装。

    所有方法都通过 subprocess 调用系统 git，不引入外部依赖。
    只读方法（status / diff / current_branch 等）供 git Skill 调用。
    写操作（commit / tag）仅供 CLI Command 调用。

    使用方式：
        svc = GitService(project_path)
        if not svc.is_available():
            # 返回 GIT_NOT_FOUND，不继续执行
            ...
        status = svc.status()
    """

    def __init__(self, project_path: Path) -> None:
        self._project_path = Path(project_path)

    # ── 可用性检测 ────────────────────────────────────────

    def is_available(self) -> bool:
        """检查 git 命令存在且当前目录是 git 仓库。

        不抛异常，失败一律返回 False。
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=str(self._project_path),
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False
        except OSError:
            return False

    # ── 只读查询方法 ──────────────────────────────────────

    def current_branch(self) -> str:
        """返回当前分支名；detached HEAD 时返回空字符串。

        Raises:
            GitNotAvailable: git 不可用时
        """
        out = self._run(["git", "branch", "--show-current"])
        return out.strip()

    def status(self, recent_commit_count: int = 10) -> GitStatus:
        """返回完整的 git status 快照。

        Raises:
            GitNotAvailable: git 不可用时
        """
        branch = self.current_branch()

        # --porcelain=v1: 每行两字符状态码 + 路径
        porcelain = self._run(["git", "status", "--porcelain=v1"])
        staged: list[GitFileChange] = []
        unstaged: list[GitFileChange] = []
        untracked: list[str] = []

        for line in porcelain.splitlines():
            if not line:
                continue
            x, y, path = line[0], line[1], line[3:]
            # porcelain=v1: 第一字符=index，第二字符=worktree
            if x == "?" and y == "?":
                untracked.append(path)
            else:
                if x != " " and x != "?":
                    staged.append(GitFileChange(
                        path=path, status=x, staged=True
                    ))
                if y != " " and y != "?":
                    unstaged.append(GitFileChange(
                        path=path, status=y, staged=False
                    ))

        recent = self._recent_commits(n=recent_commit_count)
        is_dirty = bool(staged or unstaged)

        return GitStatus(
            branch=branch,
            is_dirty=is_dirty,
            staged=staged,
            unstaged=unstaged,
            untracked=untracked,
            recent_commits=recent,
        )

    def diff(self, staged: bool = False) -> GitDiff:
        """返回 worktree（或 index）diff 的结构化摘要。

        Args:
            staged: True 时使用 --cached（对比 index vs HEAD）

        Raises:
            GitNotAvailable: git 不可用时
        """
        cmd_numstat = ["git", "diff", "--numstat"]
        cmd_name_status = ["git", "diff", "--name-status"]
        if staged:
            cmd_numstat.insert(2, "--cached")
            cmd_name_status.insert(2, "--cached")

        numstat_out = self._run(cmd_numstat)
        name_status_out = self._run(cmd_name_status)

        # name-status: 状态码 TAB 路径
        status_map: dict[str, str] = {}
        for line in name_status_out.splitlines():
            if not line:
                continue
            parts = line.split("\t", 1)
            if len(parts) == 2:
                status_map[parts[1]] = parts[0][0]  # 取第一个字符（R100 → R）

        # numstat: added TAB deleted TAB path（二进制文件为 - -）
        files: list[GitFileChange] = []
        total_ins = total_del = 0
        for line in numstat_out.splitlines():
            if not line:
                continue
            parts = line.split("\t", 2)
            if len(parts) < 3:
                continue
            add_s, del_s, path = parts
            try:
                added = int(add_s)
                deleted = int(del_s)
            except ValueError:
                added = deleted = 0  # 二进制文件
            total_ins += added
            total_del += deleted
            files.append(GitFileChange(
                path=path,
                status=status_map.get(path, "M"),
                staged=staged,
                added_lines=added,
                deleted_lines=deleted,
            ))

        return GitDiff(
            files=files,
            insertions=total_ins,
            deletions=total_del,
            staged=staged,
        )

    def tags(self) -> list[str]:
        """返回所有 tag 名称列表（按字母序）。

        Raises:
            GitNotAvailable: git 不可用时
        """
        out = self._run(["git", "tag"])
        return sorted(line for line in out.splitlines() if line)

    def log_oneline(self, n: int = 20, branch: str | None = None) -> list[str]:
        """返回最近 n 条提交的 oneline 摘要。

        Args:
            n:      返回数量上限
            branch: 指定分支，None 时用当前分支

        Raises:
            GitNotAvailable: git 不可用时
        """
        cmd = ["git", "log", "--oneline", f"-{n}"]
        if branch:
            cmd.append(branch)
        out = self._run(cmd)
        return [line for line in out.splitlines() if line]

    def show_file_at_head(self, rel_path: str) -> str | None:
        """读取 HEAD 里某文件的内容，文件不存在返回 None。

        Raises:
            GitNotAvailable: git 不可用时
        """
        try:
            out = self._run(["git", "show", f"HEAD:{rel_path}"])
            return out
        except GitNotAvailable:
            return None

    # ── 执行类方法（仅供 CLI Command 调用，Skill 层不导入）──

    def commit(self, message: str, files: list[str] | None = None) -> str:
        """执行 git commit。

        ⚠️ 写 Git 历史。仅供 `smartdev git commit --apply` CLI Command 调用。
        Skill 层禁止导入此方法。

        Args:
            message: commit message
            files:   要 stage 的文件路径列表；None 时只提交已 staged 的文件

        Returns:
            git commit 输出（含 commit hash 摘要）

        Raises:
            GitNotAvailable: git 不可用时
            subprocess.CalledProcessError: git commit 返回非零
        """
        if files:
            self._run(["git", "add", "--"] + files)
        out = self._run(["git", "commit", "-m", message])
        return out

    def tag(self, name: str, message: str | None = None) -> str:
        """执行 git tag。

        ⚠️ 写 Git 历史。仅供 `smartdev git tag --apply` CLI Command 调用。
        Skill 层禁止导入此方法。

        Args:
            name:    tag 名称
            message: 附注 tag 消息；None 时创建轻量 tag

        Returns:
            git tag 输出

        Raises:
            GitNotAvailable: git 不可用时
            subprocess.CalledProcessError: git tag 返回非零
        """
        if message:
            out = self._run(["git", "tag", "-a", name, "-m", message])
        else:
            out = self._run(["git", "tag", name])
        return out

    # ── 内部工具 ──────────────────────────────────────────

    def _run(self, cmd: list[str]) -> str:
        """执行 git 命令，返回 stdout 字符串。

        Raises:
            GitNotAvailable: git 未安装（FileNotFoundError）或非 git 仓库
        """
        try:
            result = subprocess.run(
                cmd,
                cwd=str(self._project_path),
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise GitNotAvailable(
                    f"git command failed (rc={result.returncode}): "
                    f"{' '.join(cmd)}\n{result.stderr.strip()}"
                )
            return result.stdout
        except FileNotFoundError:
            raise GitNotAvailable("git is not installed or not found in PATH")
        except OSError as e:
            raise GitNotAvailable(f"git command error: {e}")

    def _recent_commits(self, n: int) -> list[str]:
        """内部调用，返回最近 n 条 oneline 摘要，出错时静默返回空列表。"""
        try:
            return self.log_oneline(n=n)
        except GitNotAvailable:
            return []
