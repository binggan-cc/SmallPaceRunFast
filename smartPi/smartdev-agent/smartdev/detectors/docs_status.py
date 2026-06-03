"""
文档状态检测器

设计原理：
─────────
检测项目中常见文档的存在性和基本质量（非空、有内容）。
用于 Agent 诊断时判断"文档是否完整"。

为什么只检查存在性而不检查内容质量？
─────────────────────────────────
1. Phase 1 是只读诊断，不做深度分析
2. 内容质量判断需要 LLM，留给后续 Skill（如 repo.diagnose）
3. 存在性检查已经能回答"缺什么文档"这个核心问题

对应文档：
- smartPi/docs/smartdev-agent-core-spec.md §5.8（文档与知识沉淀）
- smartPi/docs/smartdev-agent-core-spec.md §13.5（文档验收标准）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DocStatus:
    """单个文档的检测状态

    Attributes:
        name: 文档名称，如 "README.md"
        path: 文档相对于项目根的路径
        exists: 是否存在
        is_empty: 是否为空文件（存在但无内容）
        size_bytes: 文件大小（字节），不存在时为 0
    """
    name: str
    path: str
    exists: bool
    is_empty: bool = False
    size_bytes: int = 0


@dataclass
class DocsStatusResult:
    """文档状态检测总结果"""
    docs: list[DocStatus] = field(default_factory=list)

    @property
    def missing_docs(self) -> list[DocStatus]:
        """缺失的文档"""
        return [d for d in self.docs if not d.exists]

    @property
    def existing_docs(self) -> list[DocStatus]:
        """已存在的文档"""
        return [d for d in self.docs if d.exists]

    @property
    def empty_docs(self) -> list[DocStatus]:
        """存在但为空的文档"""
        return [d for d in self.docs if d.exists and d.is_empty]

    @property
    def coverage_rate(self) -> float:
        """文档覆盖率（0.0 ~ 1.0）"""
        if not self.docs:
            return 0.0
        return len(self.existing_docs) / len(self.docs)


# ── 常见项目文档清单 ──────────────────────────────────────
# 对应 core-spec §5.8 和 §13.5 的文档类型
# 为什么选这些？
#   它们是开源项目和商业项目中最常见的文档，
#   缺失任何一个都可能影响项目可维护性。

_COMMON_DOCS = [
    # 基础文档
    ("README.md", "README.md"),
    ("CONTRIBUTING.md", "CONTRIBUTING.md"),
    ("CHANGELOG.md", "CHANGELOG.md"),
    ("LICENSE", "LICENSE"),
    # 开发文档
    ("docs/architecture.md", "docs/architecture.md"),
    ("docs/api.md", "docs/api.md"),
    ("docs/setup.md", "docs/setup.md"),
    # 进度文档（SmartDev 特色）
    ("docs/development-progress.md", "docs/development-progress.md"),
    # 知识沉淀
    ("docs/bug-notes.md", "docs/bug-notes.md"),
    ("docs/adr.md", "docs/adr.md"),
]


def detect_docs_status(project_path: Path) -> DocsStatusResult:
    """检测项目文档状态

    参数：
        project_path: 项目根目录路径

    返回：
        DocsStatusResult，包含所有常见文档的存在性状态

    使用示例：
        result = detect_docs_status(Path("/path/to/project"))
        print(f"覆盖率: {result.coverage_rate:.0%}")
        for doc in result.missing_docs:
            print(f"  缺失: {doc.name}")
    """
    result = DocsStatusResult()

    for name, rel_path in _COMMON_DOCS:
        full_path = project_path / rel_path
        exists = full_path.exists()

        is_empty = False
        size_bytes = 0
        if exists:
            try:
                size_bytes = full_path.stat().st_size
                is_empty = size_bytes == 0
            except OSError:
                pass

        result.docs.append(DocStatus(
            name=name,
            path=rel_path,
            exists=exists,
            is_empty=is_empty,
            size_bytes=size_bytes,
        ))

    return result
