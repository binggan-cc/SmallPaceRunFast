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

from dataclasses import dataclass, field
from enum import Enum


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
    """
    file_path: str
    action: PatchAction
    reason: str = ""
    changes: list[LineChange] = field(default_factory=list)
    old_content: str = ""
    new_content: str = ""

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
    """
    task_description: str
    files: list[FilePatch] = field(default_factory=list)
    risk_level: str = "R1"
    reasoning: str = ""

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
