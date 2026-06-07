"""
Patch — 代码补丁数据模型

设计原理：
─────────
Patch 是代码修改的最小可审查单元。每个 Patch 包含：
- 修改了哪些文件
- 每个文件的具体变更（行级 diff）
- 变更的理由和风险

为什么用 Patch 而非直接 Edit？
─────────────────────────────
1. Patch 可以被用户预览和审查
2. Patch 可以被拒绝（不执行）
3. Patch 可以被回滚（git revert）
4. 对应 protocol §6 执行前确认

为什么不用 unified diff 格式？
─────────────────────────────
unified diff 是文本格式，解析复杂。用结构化的数据模型更易处理。
如果需要输出给 git apply，可以转换为 unified diff。

对应文档：
- smartPi/docs/smartdev-agent-core-spec.md §5.6（编码执行）
- smartPi/docs/smartdev-agent-protocol.md §8（任务粒度规范）
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class PatchAction(Enum):
    """补丁操作类型"""
    CREATE = "create"    # 创建新文件
    MODIFY = "modify"    # 修改已有文件
    DELETE = "delete"    # 删除文件


@dataclass
class LineChange:
    """单行变更

    Attributes:
        line_number: 行号
        action: 操作（add/remove/keep）
        content: 行内容
    """
    line_number: int
    action: str      # add | remove | keep
    content: str


@dataclass
class FilePatch:
    """单个文件的补丁

    Attributes:
        file_path: 文件路径
        action: 操作类型
        reason: 修改理由
        changes: 行级变更列表
        old_content: 原始内容（modify/delete 时有值）
        new_content: 新内容（create/modify 时有值）
        old_hash: propose 时原文件内容 SHA256（P0-2，apply 前校验防 TOCTOU）
        old_size: propose 时原文件字节大小
        old_mtime: propose 时原文件修改时间
    """
    file_path: str
    action: PatchAction
    reason: str = ""
    changes: list[LineChange] = field(default_factory=list)
    old_content: str = ""
    new_content: str = ""
    old_hash: str = ""
    old_size: int = 0
    old_mtime: float = 0.0

    @property
    def added_lines(self) -> int:
        return sum(1 for c in self.changes if c.action == "add")

    @property
    def removed_lines(self) -> int:
        return sum(1 for c in self.changes if c.action == "remove")

    def to_unified_diff(self) -> str:
        """转换为 unified diff 格式"""
        lines = [f"--- a/{self.file_path}", f"+++ b/{self.file_path}"]

        if self.action == PatchAction.CREATE:
            lines.append(f"@@ -0,0 +1,{len(self.new_content.splitlines())} @@")
            for line in self.new_content.splitlines():
                lines.append(f"+{line}")
        elif self.action == PatchAction.DELETE:
            lines.append(f"@@ -1,{len(self.old_content.splitlines())} +0,0 @@")
            for line in self.old_content.splitlines():
                lines.append(f"-{line}")
        else:
            # MODIFY — 输出变更行
            for change in self.changes:
                if change.action == "add":
                    lines.append(f"+{change.content}")
                elif change.action == "remove":
                    lines.append(f"-{change.content}")

        return "\n".join(lines)

    def summary(self) -> str:
        """变更摘要"""
        if self.action == PatchAction.CREATE:
            return f"创建 {self.file_path} (+{len(self.new_content.splitlines())} 行)"
        elif self.action == PatchAction.DELETE:
            return f"删除 {self.file_path}"
        else:
            return f"修改 {self.file_path} (+{self.added_lines} -{self.removed_lines})"


@dataclass
class Patch:
    """完整补丁

    一个任务可能涉及多个文件的修改，每个文件一个 FilePatch。

    Attributes:
        task_description: 任务描述
        files: 文件补丁列表
        risk_level: 风险等级
        reasoning: 变更理由
        patch_id: 补丁唯一标识（P0-1，propose 持久化用；空表示未持久化）
        affected_files: impact 分析得到的受影响文件（Step 2 填充）
        created_at: 生成时间（ISO 字符串）
    """
    task_description: str
    files: list[FilePatch] = field(default_factory=list)
    risk_level: str = "R1"
    reasoning: str = ""
    patch_id: str = ""
    affected_files: list[str] = field(default_factory=list)
    created_at: str = ""

    @property
    def file_count(self) -> int:
        return len(self.files)

    @property
    def total_added(self) -> int:
        return sum(f.added_lines for f in self.files)

    @property
    def total_removed(self) -> int:
        return sum(f.removed_lines for f in self.files)

    def to_unified_diff(self) -> str:
        """转换为完整的 unified diff"""
        parts = []
        for fp in self.files:
            parts.append(fp.to_unified_diff())
        return "\n\n".join(parts)

    def summary(self) -> str:
        """补丁摘要"""
        lines = [
            f"补丁: {self.task_description}",
            f"文件数: {self.file_count}",
            f"总变更: +{self.total_added} -{self.total_removed}",
            f"风险等级: {self.risk_level}",
        ]
        for fp in self.files:
            lines.append(f"  - {fp.summary()}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """序列化为可 JSON 化的 dict（P0-1 持久化用）"""
        return {
            "patch_id": self.patch_id,
            "task_description": self.task_description,
            "risk_level": self.risk_level,
            "reasoning": self.reasoning,
            "affected_files": self.affected_files,
            "created_at": self.created_at,
            "files": [
                {
                    "file_path": fp.file_path,
                    "action": fp.action.value,
                    "reason": fp.reason,
                    "old_content": fp.old_content,
                    "new_content": fp.new_content,
                    "old_hash": fp.old_hash,
                    "old_size": fp.old_size,
                    "old_mtime": fp.old_mtime,
                }
                for fp in self.files
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Patch":
        """从 dict 反序列化（P0-1 加载用）

        行级 changes 不持久化，加载后从 old/new content 重算（保证一致）。
        """
        files = []
        for fd in data.get("files", []):
            old_content = fd.get("old_content", "")
            new_content = fd.get("new_content", "")
            changes = compute_line_changes(
                old_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
            )
            files.append(FilePatch(
                file_path=fd["file_path"],
                action=PatchAction(fd["action"]),
                reason=fd.get("reason", ""),
                changes=changes,
                old_content=old_content,
                new_content=new_content,
                old_hash=fd.get("old_hash", ""),
                old_size=fd.get("old_size", 0),
                old_mtime=fd.get("old_mtime", 0.0),
            ))
        return cls(
            task_description=data.get("task_description", ""),
            files=files,
            risk_level=data.get("risk_level", "R1"),
            reasoning=data.get("reasoning", ""),
            patch_id=data.get("patch_id", ""),
            affected_files=data.get("affected_files", []),
            created_at=data.get("created_at", ""),
        )


# ── Diff 生成工具 ──────────────────────────────────────────


def compute_line_changes(old_lines: list[str], new_lines: list[str]) -> list[LineChange]:
    """计算两组文本的行级差异

    使用简单的 LCS（最长公共子序列）算法。
    为什么不用 difflib？标准库的 difflib 可以用，但这里需要
    结构化的 LineChange 输出，自定义更灵活。

    参数：
        old_lines: 原始文本行
        new_lines: 新文本行

    返回：
        LineChange 列表
    """
    # 简单的 diff：逐行比较
    # 后续可以用 LCS 优化
    changes = []
    max_len = max(len(old_lines), len(new_lines))

    for i in range(max_len):
        old_line = old_lines[i] if i < len(old_lines) else None
        new_line = new_lines[i] if i < len(new_lines) else None

        if old_line == new_line:
            if old_line is not None:
                changes.append(LineChange(
                    line_number=i + 1,
                    action="keep",
                    content=old_line,
                ))
        else:
            if old_line is not None:
                changes.append(LineChange(
                    line_number=i + 1,
                    action="remove",
                    content=old_line,
                ))
            if new_line is not None:
                changes.append(LineChange(
                    line_number=i + 1,
                    action="add",
                    content=new_line,
                ))

    return changes


def create_file_patch(
    file_path: str,
    old_content: str,
    new_content: str,
    reason: str = "",
) -> FilePatch:
    """创建文件补丁

    参数：
        file_path: 文件路径
        old_content: 原始内容
        new_content: 新内容
        reason: 修改理由

    返回：
        FilePatch
    """
    if not old_content and new_content:
        action = PatchAction.CREATE
    elif old_content and not new_content:
        action = PatchAction.DELETE
    else:
        action = PatchAction.MODIFY

    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)
    changes = compute_line_changes(old_lines, new_lines)

    return FilePatch(
        file_path=file_path,
        action=action,
        reason=reason,
        changes=changes,
        old_content=old_content,
        new_content=new_content,
    )


# ── Phase 9 Step 1A: 可审查草案基础设施 ────────────────────
#
# 本步只做"生成 + 持久化 + 校验元数据"，不写盘、不 apply。
# apply / rollback 在 Step 1B 实现。


def compute_content_hash(content: str) -> str:
    """计算文本内容的 SHA256（用于 P0-2 apply 前一致性校验）"""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


# 路径安全（P0-3）：propose 阶段就过滤，apply 阶段二次校验
_SKIP_DIRS = {
    ".git", ".smartdev", "node_modules", "dist", "build",
    "venv", ".venv", "__pycache__", ".pytest_cache",
    ".mypy_cache", "target", "vendor",
}

_BINARY_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".pdf", ".zip", ".gz", ".tar", ".so", ".dylib", ".dll",
    ".pyc", ".pyo", ".bin", ".exe", ".o", ".a", ".lib",
    ".mp3", ".mp4", ".mov", ".wav", ".sqlite", ".db",
}

_MAX_PATCH_FILE_SIZE = 1 * 1024 * 1024  # 1MB，超大文件不纳入 patch


def is_safe_target(rel_path: str, project_path: Path) -> tuple[bool, str]:
    """判断相对路径是否可安全纳入 patch（P0-3）。

    返回 (是否安全, 拒绝原因)。propose 与 apply 都应调用。

    拒绝：
    - path traversal（解析后逃出 project_path）
    - 命中跳过目录（.git / .smartdev / node_modules / ...）
    - 二进制扩展名
    - symlink（默认不处理）
    """
    # 跳过目录
    parts = Path(rel_path).parts
    for part in parts:
        if part in _SKIP_DIRS:
            return False, f"位于跳过目录 {part}/"
        if part == "..":
            return False, "包含 path traversal（..）"

    abs_path = (project_path / rel_path).resolve()
    project_resolved = project_path.resolve()

    # symlink（已存在的）默认跳过 —— 必须在 resolve 前用原始路径判断
    raw_path = project_path / rel_path
    if raw_path.is_symlink():
        return False, "symlink（默认不处理）"

    # 逃逸校验：解析后必须仍在 project_path 内
    try:
        abs_path.relative_to(project_resolved)
    except ValueError:
        return False, "路径逃逸到 project_path 外部"

    # 二进制扩展名
    if abs_path.suffix.lower() in _BINARY_EXTS:
        return False, f"二进制文件类型 {abs_path.suffix}"

    return True, ""


def build_find_replace_patch(
    project_path: Path,
    find: str,
    replace: str,
    include_glob: str = "**/*",
    regex: bool = False,
) -> Patch:
    """跨文件 find → replace，生成 Patch 草案（不落地）。

    确定性补丁生成器（无 LLM）。命中行级 diff 复用 create_file_patch。
    每个 FilePatch 记录 old_hash/size/mtime（P0-2）。
    路径安全过滤见 is_safe_target（P0-3）。

    参数：
        project_path: 项目根目录
        find: 查找串
        replace: 替换串
        include_glob: 文件匹配 glob（默认所有文件）
        regex: 是否将 find 当作正则

    返回：
        Patch（仅含实际发生变更的文件）
    """
    import re as _re

    project_path = Path(project_path)
    pattern = _re.compile(find) if regex else None

    files: list[FilePatch] = []
    for abs_path in sorted(project_path.glob(include_glob)):
        if not abs_path.is_file():
            continue
        rel_path = str(abs_path.relative_to(project_path))

        safe, _reason = is_safe_target(rel_path, project_path)
        if not safe:
            continue

        try:
            if abs_path.stat().st_size > _MAX_PATCH_FILE_SIZE:
                continue
            old_content = abs_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        if regex:
            new_content = pattern.sub(replace, old_content)
        else:
            if find not in old_content:
                continue
            new_content = old_content.replace(find, replace)

        if new_content == old_content:
            continue  # 无变更，跳过

        fp = create_file_patch(
            file_path=rel_path,
            old_content=old_content,
            new_content=new_content,
            reason=f"find-replace: '{find}' → '{replace}'",
        )
        # 记录 hash 元数据（P0-2）
        stat = abs_path.stat()
        fp.old_hash = compute_content_hash(old_content)
        fp.old_size = stat.st_size
        fp.old_mtime = stat.st_mtime
        files.append(fp)

    return Patch(
        task_description=f"find-replace: '{find}' → '{replace}'",
        files=files,
        risk_level="R1",
        reasoning=f"跨文件替换 '{find}' 为 '{replace}'（glob={include_glob}, regex={regex}）",
    )


def generate_patch_id(patch: Patch) -> str:
    """为 patch 生成唯一 id（时间戳 + 内容 hash 前 8 位）。"""
    content_sig = "|".join(
        f"{fp.file_path}:{fp.old_hash}:{compute_content_hash(fp.new_content)}"
        for fp in patch.files
    )
    digest = hashlib.sha256(content_sig.encode("utf-8")).hexdigest()[:8]
    ts = time.strftime("%Y%m%d-%H%M%S")
    return f"{ts}-{digest}"


def save_patch(patch: Patch, patches_dir: Path) -> str:
    """持久化 Patch 到 .smartdev/patches/{patch_id}.json（P0-1）。

    若 patch 未设 patch_id / created_at，则自动生成。
    返回 patch_id。
    """
    patches_dir = Path(patches_dir)
    patches_dir.mkdir(parents=True, exist_ok=True)

    if not patch.created_at:
        patch.created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if not patch.patch_id:
        patch.patch_id = generate_patch_id(patch)

    out_path = patches_dir / f"{patch.patch_id}.json"
    out_path.write_text(
        json.dumps(patch.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return patch.patch_id


def load_patch(patch_id: str, patches_dir: Path) -> Patch | None:
    """从 .smartdev/patches/{patch_id}.json 加载 Patch（P0-1）。

    不存在 / 解析失败 → None。
    """
    patch_file = Path(patches_dir) / f"{patch_id}.json"
    if not patch_file.exists():
        return None
    try:
        data = json.loads(patch_file.read_text(encoding="utf-8"))
        return Patch.from_dict(data)
    except (OSError, ValueError, KeyError):
        return None
