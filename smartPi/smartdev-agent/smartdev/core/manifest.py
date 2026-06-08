"""
ChangeManifest — 变更清单数据模型与生成器

功能：
─────
Phase 11C Step 1 的核心交付物。
记录"这次代码改动改了什么、改的性质、需不需要更新文档"，
作为 Doc Steward 工具链的事实基础。

三种生成来源：
────────────
1. patch_apply       — code.apply 执行后，由 apply 流程触发
2. git_commit        — git commit 执行后，由 CLI git commit --apply 触发
3. working_tree_diff — 当前工作区 diff，用于"改完还没提交"时的文档预检

设计约束：
─────────
- 零外部依赖（标准库 + core/git.py）
- 只写 .smartdev/runs/<run_id>/change-manifest.json（不动源码）
- 读取来源均为 git 状态或 patch 对象，不猜测文件意图
- public_surface_changed 检测五类公共接口文件（cli.py / mcp/tools.py / skill.yaml / pyproject.toml / *.yaml）

对应文档：
- docs/phase-11c-design.md §4.1（Change Manifest 数据模型）
- docs/phase-11c-design.md §3.2（Code Agent 输出格式）
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path


# ── 常量 ──────────────────────────────────────────────────

# 变更类型推断：文件路径 → change_type
_FEAT_DIRS = {"skills", "mcp", "core"}
_TEST_PATTERNS = {"tests/", "test_"}
_DOC_PATTERNS = {"docs/", "README", "CHANGELOG", ".md"}

# 公共接口文件（任意一个被修改 → public_surface_changed=True）
_PUBLIC_SURFACE_FILES = {
    "cli.py",
    "mcp/tools.py",
    "mcp/server.py",
    "pyproject.toml",
}
_PUBLIC_SURFACE_SUFFIXES = {".yaml"}  # skill.yaml / config.yaml

# CLI / Skill / MCP 文件特征
_CLI_FILES = {"cli.py"}
_SKILL_PATTERNS = {"skills/", "skill.py", "skill.yaml"}
_MCP_PATTERNS = {"mcp/"}


# ── 数据模型 ──────────────────────────────────────────────


@dataclass
class ChangeManifest:
    """变更清单：一次代码变更的结构化事实记录。

    Attributes:
        run_id:                 运行 ID，写入文件名和 JSON
        source:                 生成来源（patch_apply / git_commit / working_tree_diff）
        timestamp:              ISO 8601 时间戳
        changed_files:          本次变更的文件相对路径列表
        change_type:            变更类型（feature / fix / refactor / docs / test）
        risk_level:             风险等级（R0–R3）
        public_surface_changed: 是否改动了公共接口文件
        cli_changed:            是否改动了 CLI（cli.py）
        skill_changed:          是否改动了 Skill 文件
        mcp_changed:            是否改动了 MCP 相关文件
        docs_likely_needed:     是否可能需要更新文档
        validation:             建议的验证命令
        commit_message:         关联的 commit message（git_commit 来源时填入）
        patch_id:               关联的 patch ID（patch_apply 来源时填入）
    """
    run_id: str
    source: str                          # patch_apply | git_commit | working_tree_diff
    timestamp: str
    changed_files: list[str] = field(default_factory=list)
    change_type: str = "feature"         # feature | fix | refactor | docs | test
    risk_level: str = "R1"
    public_surface_changed: bool = False
    cli_changed: bool = False
    skill_changed: bool = False
    mcp_changed: bool = False
    docs_likely_needed: bool = False
    validation: list[str] = field(default_factory=list)
    commit_message: str = ""
    patch_id: str = ""

    def to_dict(self) -> dict:
        """序列化为 JSON-friendly dict。"""
        return {
            "run_id": self.run_id,
            "source": self.source,
            "timestamp": self.timestamp,
            "changed_files": self.changed_files,
            "change_type": self.change_type,
            "risk_level": self.risk_level,
            "public_surface_changed": self.public_surface_changed,
            "cli_changed": self.cli_changed,
            "skill_changed": self.skill_changed,
            "mcp_changed": self.mcp_changed,
            "docs_likely_needed": self.docs_likely_needed,
            "validation": self.validation,
            "commit_message": self.commit_message,
            "patch_id": self.patch_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ChangeManifest":
        """从 dict 反序列化。"""
        return cls(
            run_id=data.get("run_id", ""),
            source=data.get("source", "working_tree_diff"),
            timestamp=data.get("timestamp", ""),
            changed_files=list(data.get("changed_files", [])),
            change_type=data.get("change_type", "feature"),
            risk_level=data.get("risk_level", "R1"),
            public_surface_changed=bool(data.get("public_surface_changed", False)),
            cli_changed=bool(data.get("cli_changed", False)),
            skill_changed=bool(data.get("skill_changed", False)),
            mcp_changed=bool(data.get("mcp_changed", False)),
            docs_likely_needed=bool(data.get("docs_likely_needed", False)),
            validation=list(data.get("validation", [])),
            commit_message=data.get("commit_message", ""),
            patch_id=data.get("patch_id", ""),
        )

    def to_json(self, indent: int = 2) -> str:
        """序列化为 JSON 字符串。"""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


# ── 推断逻辑 ──────────────────────────────────────────────


def _infer_change_type(changed_files: list[str], commit_message: str = "") -> str:
    """从 changed_files 和 commit_message 推断 change_type。

    优先级：commit_message 前缀 > 文件路径特征
    """
    msg = commit_message.lower()
    for prefix, ct in [
        ("fix", "fix"),
        ("bug", "fix"),
        ("docs", "docs"),
        ("doc", "docs"),
        ("refactor", "refactor"),
        ("test", "test"),
        ("feat", "feature"),
        ("chore", "refactor"),
    ]:
        if msg.startswith(prefix):
            return ct

    # 文件路径特征推断
    has_test = any(
        p in f or f.startswith("test")
        for f in changed_files
        for p in _TEST_PATTERNS
    )
    has_doc = any(
        any(p in f for p in _DOC_PATTERNS)
        for f in changed_files
    )
    if has_test and not has_doc:
        return "test"
    if has_doc and not has_test:
        return "docs"

    return "feature"


def _infer_risk_level(changed_files: list[str], public_surface_changed: bool) -> str:
    """从变更文件数量和公共接口变更推断风险等级。"""
    n = len(changed_files)
    if n == 0:
        return "R0"
    if public_surface_changed or n >= 5:
        return "R2"
    if n <= 2:
        return "R1"
    return "R1"


def _check_surface_flags(changed_files: list[str]) -> dict[str, bool]:
    """检测 public_surface / cli / skill / mcp / docs 变更标志。

    返回包含布尔标志的 dict，便于 ChangeManifest 赋值。
    """
    public_surface = False
    cli_changed = False
    skill_changed = False
    mcp_changed = False

    for f in changed_files:
        f_lower = f.lower()
        f_path = Path(f)
        fname = f_path.name

        # cli
        if fname in _CLI_FILES or f == "smartdev/cli.py":
            cli_changed = True
            public_surface = True

        # mcp
        if any(p in f for p in _MCP_PATTERNS):
            mcp_changed = True
            public_surface = True

        # skill
        if any(p in f for p in _SKILL_PATTERNS):
            skill_changed = True

        # 其他公共接口文件
        if fname in _PUBLIC_SURFACE_FILES:
            public_surface = True
        if f_path.suffix in _PUBLIC_SURFACE_SUFFIXES and "skill" in f_lower:
            public_surface = True
            skill_changed = True

    return {
        "public_surface_changed": public_surface,
        "cli_changed": cli_changed,
        "skill_changed": skill_changed,
        "mcp_changed": mcp_changed,
    }


def _should_update_docs(flags: dict[str, bool], change_type: str) -> bool:
    """判断本次变更是否可能需要更新文档。"""
    if change_type == "docs":
        return False  # 本身就是文档变更
    return (
        flags["public_surface_changed"]
        or flags["cli_changed"]
        or flags["skill_changed"]
        or flags["mcp_changed"]
        or change_type in ("feature",)
    )


def _default_validation() -> list[str]:
    """返回默认验证命令列表。"""
    return ["python -m pytest -q"]


# ── 工厂函数 ──────────────────────────────────────────────


def _make_run_id(source: str) -> str:
    """生成 run_id：source + 时间戳。"""
    ts = time.strftime("%Y%m%d-%H%M%S")
    return f"{source}-{ts}"


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def manifest_from_files(
    changed_files: list[str],
    source: str,
    *,
    run_id: str | None = None,
    commit_message: str = "",
    patch_id: str = "",
    risk_level: str | None = None,
) -> ChangeManifest:
    """从文件列表创建 ChangeManifest（所有来源的通用入口）。

    参数：
        changed_files:   已变更文件的相对路径列表
        source:          来源标识（patch_apply / git_commit / working_tree_diff）
        run_id:          指定 run_id，None 则自动生成
        commit_message:  关联的 commit message（git_commit 来源时提供）
        patch_id:        关联的 patch ID（patch_apply 来源时提供）
        risk_level:      手动指定风险等级；None 则自动推断

    返回：
        ChangeManifest 实例（未持久化）
    """
    source = source or "working_tree_diff"
    run_id = run_id or _make_run_id(source)

    flags = _check_surface_flags(changed_files)
    change_type = _infer_change_type(changed_files, commit_message)
    rl = risk_level or _infer_risk_level(changed_files, flags["public_surface_changed"])
    docs_needed = _should_update_docs(flags, change_type)

    return ChangeManifest(
        run_id=run_id,
        source=source,
        timestamp=_now_iso(),
        changed_files=sorted(changed_files),
        change_type=change_type,
        risk_level=rl,
        public_surface_changed=flags["public_surface_changed"],
        cli_changed=flags["cli_changed"],
        skill_changed=flags["skill_changed"],
        mcp_changed=flags["mcp_changed"],
        docs_likely_needed=docs_needed,
        validation=_default_validation(),
        commit_message=commit_message,
        patch_id=patch_id,
    )


def manifest_from_git_diff(project_path: Path, *, run_id: str | None = None) -> ChangeManifest:
    """从当前工作区 git diff 生成 ChangeManifest（working_tree_diff 来源）。

    包含 staged + unstaged 的变更文件，用于"改完还没提交"时的文档预检。
    git 不可用时返回空 manifest（不崩溃）。

    参数：
        project_path: 项目根目录
        run_id:       指定 run_id，None 则自动生成

    返回：
        ChangeManifest 实例（未持久化）
    """
    from smartdev.core.git import GitNotAvailable, GitService

    project_path = Path(project_path)
    svc = GitService(project_path)

    changed_files: list[str] = []
    if svc.is_available():
        try:
            # staged（index vs HEAD）
            staged_diff = svc.diff(staged=True)
            changed_files.extend(f.path for f in staged_diff.files)
            # unstaged（worktree vs index）
            unstaged_diff = svc.diff(staged=False)
            changed_files.extend(f.path for f in unstaged_diff.files)
        except GitNotAvailable:
            pass

    # 去重
    changed_files = list(dict.fromkeys(changed_files))

    return manifest_from_files(
        changed_files=changed_files,
        source="working_tree_diff",
        run_id=run_id,
    )


def manifest_from_patch_apply(
    changed_files: list[str],
    patch_id: str,
    *,
    run_id: str | None = None,
) -> ChangeManifest:
    """从 code.apply 执行后的文件列表生成 ChangeManifest（patch_apply 来源）。

    参数：
        changed_files: code.apply 应用的文件列表（来自 ApplyResult.applied_files）
        patch_id:      应用的 patch ID
        run_id:        指定 run_id，None 则自动生成

    返回：
        ChangeManifest 实例（未持久化）
    """
    return manifest_from_files(
        changed_files=changed_files,
        source="patch_apply",
        run_id=run_id,
        patch_id=patch_id,
    )


def manifest_from_git_commit(
    changed_files: list[str],
    commit_message: str,
    *,
    run_id: str | None = None,
) -> ChangeManifest:
    """从 git commit 执行后的文件列表生成 ChangeManifest（git_commit 来源）。

    参数：
        changed_files:  本次 commit 包含的文件列表
        commit_message: commit message
        run_id:         指定 run_id，None 则自动生成

    返回：
        ChangeManifest 实例（未持久化）
    """
    return manifest_from_files(
        changed_files=changed_files,
        source="git_commit",
        run_id=run_id,
        commit_message=commit_message,
    )


# ── 持久化 ────────────────────────────────────────────────


def save_manifest(
    manifest: ChangeManifest,
    runs_dir: Path,
) -> Path:
    """把 ChangeManifest 写入 .smartdev/runs/<run_id>/change-manifest.json。

    参数：
        manifest: 要保存的 ChangeManifest
        runs_dir: .smartdev/runs/ 目录路径

    返回：
        写入的文件绝对路径
    """
    runs_dir = Path(runs_dir)
    out_dir = runs_dir / manifest.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / "change-manifest.json"
    out_path.write_text(manifest.to_json(), encoding="utf-8")
    return out_path


def load_manifest(run_id: str, runs_dir: Path) -> ChangeManifest | None:
    """从 .smartdev/runs/<run_id>/change-manifest.json 加载 ChangeManifest。

    不存在 / 解析失败 → None。
    """
    runs_dir = Path(runs_dir)
    manifest_path = runs_dir / run_id / "change-manifest.json"
    if not manifest_path.exists():
        return None
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        return ChangeManifest.from_dict(data)
    except (OSError, ValueError, KeyError):
        return None


def load_latest_manifest(runs_dir: Path) -> ChangeManifest | None:
    """加载 .smartdev/runs/ 下最近的 ChangeManifest（按目录 mtime 排序）。

    不存在任何 manifest → None。
    """
    runs_dir = Path(runs_dir)
    if not runs_dir.exists():
        return None

    candidates: list[tuple[float, Path]] = []
    for run_dir in runs_dir.iterdir():
        if not run_dir.is_dir():
            continue
        manifest_file = run_dir / "change-manifest.json"
        if manifest_file.exists():
            candidates.append((manifest_file.stat().st_mtime, manifest_file))

    if not candidates:
        return None

    candidates.sort(reverse=True)
    _, latest_path = candidates[0]
    try:
        data = json.loads(latest_path.read_text(encoding="utf-8"))
        return ChangeManifest.from_dict(data)
    except (OSError, ValueError, KeyError):
        return None
