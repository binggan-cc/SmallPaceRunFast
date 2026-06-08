"""
Skill: doc.map — 文档地图（R0 只读）

功能：扫描项目文档，提取 headings / mentions / last_modified，
      输出结构化 doc_map JSON。

风险：R0（只读，不修改任何文件）

设计约束（phase-11c-design.md §4.5）：
- 扫描范围：docs/ + 项目根的 README.md / CHANGELOG.md / CLAUDE.md + 可选 extra_paths
- 零外部依赖，标准库实现
- headings：Markdown # ## ### 标题提取
- mentions：版本号 / Phase / Skill 名 / CLI 命令 / MCP 工具名等关键词出现情况
- last_modified：文件系统 mtime（ISO 格式）
- 文件不存在 / 读取失败时跳过，不崩溃

对应文档：
- docs/phase-11c-design.md §4.5（Doc Map）
- docs/phase-11c-design.md §7 Step 3
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from smartdev.models import RiskLevel, SkillResult, TaskType
from smartdev.skills.base import Skill


# ── 默认扫描配置 ──────────────────────────────────────────

# 项目根部的固定文档文件（相对路径）
_ROOT_DOC_FILES = [
    "README.md",
    "CHANGELOG.md",
    "CLAUDE.md",
    "CONTRIBUTING.md",
    "AGENTS.md",
]

# docs/ 目录下的文档扩展名
_DOC_EXTENSIONS = {".md", ".rst", ".txt"}

# 默认 mention 关键词类别（正则模式）
_DEFAULT_MENTION_PATTERNS: dict[str, str] = {
    # 版本号：vX.Y.Z 或 X.Y.Z
    "version": r"\bv?\d+\.\d+\.\d+\b",
    # Phase 引用：Phase 10 / Phase 11A 等
    "phase": r"\bPhase\s+\d+[A-Za-z]?\b",
    # 测试基线数字（N passed）
    "test_baseline": r"\b\d+\s+(?:passed|tests?)\b",
    # MCP 工具名：smartdev_xxx
    "mcp_tool": r"\bsmartdev_[a-z_]+\b",
    # CLI 命令片段：smartdev xxx
    "cli_command": r"\bsmartdev\s+[a-z]+\b",
    # Skill 名称：xxx.yyy（点号 skill 名）
    "skill_name": r"\b[a-z]+\.[a-z_]+\b",
}

# CHANGELOG 专用：提取最新版本节标题
_CHANGELOG_VERSION_RE = re.compile(
    r"^##\s+\[([^\]]+)\]", re.MULTILINE
)


# ── 数据模型 ──────────────────────────────────────────────


@dataclass
class DocEntry:
    """单个文档的地图条目。

    Attributes:
        path:          相对于项目根的文件路径
        headings:      所有 Markdown 标题列表（按出现顺序）
        mentions:      关键词 → 出现次数的字典
        last_modified: ISO 8601 格式的最后修改时间
        size_bytes:    文件字节大小
        extra:         扩展字段（如 CHANGELOG 的 latest_version）
    """
    path: str
    headings: list[str] = field(default_factory=list)
    mentions: dict[str, list[str]] = field(default_factory=dict)
    last_modified: str = ""
    size_bytes: int = 0
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {
            "path": self.path,
            "headings": self.headings,
            "mentions": self.mentions,
            "last_modified": self.last_modified,
            "size_bytes": self.size_bytes,
        }
        if self.extra:
            d.update(self.extra)
        return d


# ── 扫描工具函数 ──────────────────────────────────────────


def _extract_headings(text: str) -> list[str]:
    """提取 Markdown 标题（# / ## / ### 等），保留层级前缀。"""
    headings: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        m = re.match(r"^(#{1,6})\s+(.+)", stripped)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            headings.append(f"{'#' * level} {title}")
    return headings


def _extract_mentions(
    text: str,
    patterns: dict[str, str],
) -> dict[str, list[str]]:
    """按 patterns 提取 mention，返回 category → 去重值列表。"""
    mentions: dict[str, list[str]] = {}
    for category, pattern in patterns.items():
        try:
            found = re.findall(pattern, text)
        except re.error:
            found = []
        if found:
            # 去重，保留顺序，最多 20 个
            seen: list[str] = []
            seen_set: set[str] = set()
            for item in found:
                norm = item.strip()
                if norm not in seen_set:
                    seen_set.add(norm)
                    seen.append(norm)
                    if len(seen) >= 20:
                        break
            mentions[category] = seen
    return mentions


def _mtime_iso(path: Path) -> str:
    """返回文件的最后修改时间（ISO 8601 UTC）。"""
    try:
        ts = path.stat().st_mtime
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except OSError:
        return ""


def _scan_doc_file(
    abs_path: Path,
    rel_path: str,
    mention_patterns: dict[str, str],
) -> DocEntry | None:
    """扫描单个文档文件，返回 DocEntry；读取失败返回 None。"""
    if not abs_path.exists() or not abs_path.is_file():
        return None
    try:
        text = abs_path.read_text(encoding="utf-8", errors="replace")
        size = abs_path.stat().st_size
    except OSError:
        return None

    headings = _extract_headings(text)
    mentions = _extract_mentions(text, mention_patterns)
    mtime = _mtime_iso(abs_path)

    extra: dict = {}
    # CHANGELOG 专用：提取最新版本节
    name_lower = abs_path.name.lower()
    if name_lower.startswith("changelog"):
        versions = _CHANGELOG_VERSION_RE.findall(text)
        if versions:
            extra["latest_version"] = versions[0]
            extra["version_sections"] = versions[:10]

    return DocEntry(
        path=rel_path,
        headings=headings,
        mentions=mentions,
        last_modified=mtime,
        size_bytes=size,
        extra=extra,
    )


def _collect_doc_paths(project_path: Path, extra_paths: list[str]) -> list[tuple[Path, str]]:
    """收集所有要扫描的 (绝对路径, 相对路径) 对，去重，按路径排序。"""
    seen: set[Path] = set()
    result: list[tuple[Path, str]] = []

    def _add(abs_p: Path) -> None:
        resolved = abs_p.resolve()
        if resolved in seen:
            return
        seen.add(resolved)
        try:
            rel = str(abs_p.relative_to(project_path))
        except ValueError:
            rel = str(abs_p)
        result.append((abs_p, rel))

    # 1. 项目根固定文档
    for name in _ROOT_DOC_FILES:
        candidate = project_path / name
        _add(candidate)

    # 2. docs/ 目录下所有文档
    docs_dir = project_path / "docs"
    if docs_dir.exists() and docs_dir.is_dir():
        for p in sorted(docs_dir.rglob("*")):
            if p.is_file() and p.suffix in _DOC_EXTENSIONS:
                _add(p)

    # 3. extra_paths（用户指定）
    for ep in extra_paths:
        candidate = project_path / ep
        _add(candidate)

    result.sort(key=lambda x: x[1])
    return result


# ── Skill ─────────────────────────────────────────────────


class DocMapSkill(Skill):
    """文档地图 Skill（R0 只读）

    扫描项目文档，提取每个文档的 headings / mentions / last_modified，
    输出结构化 doc_map，供 doc.consistency 规则检查和 Doc Steward 消费。

    inputs 参数：
        extra_paths:      list[str]  额外要扫描的文件路径（相对于 project_path）
        mention_keywords: list[str]  额外的 mention 关键词（精确字符串，非正则）

    使用示例：
        result = Skill.create("doc.map").run(context)
        result = Skill.create("doc.map").run(context, {
            "extra_paths": ["WORKSPACE.md"],
            "mention_keywords": ["my-custom-tool"],
        })
    """

    name = "doc.map"
    description = "扫描项目文档，提取 headings / mentions / last_modified，输出结构化 doc_map"
    risk_level = RiskLevel.R0
    task_type = TaskType.DIAGNOSE

    def can_run(self, context) -> bool:
        return context.project_path.exists()

    def run(self, context, inputs: dict | None = None) -> SkillResult:
        inputs = inputs or {}
        project = context.project_path
        extra_paths: list[str] = list(inputs.get("extra_paths", []))
        mention_keywords: list[str] = list(inputs.get("mention_keywords", []))

        # 合并用户自定义 mention 关键词（精确词，转为正则）
        patterns = dict(_DEFAULT_MENTION_PATTERNS)
        for kw in mention_keywords:
            safe = re.escape(kw)
            patterns[f"custom:{kw}"] = rf"\b{safe}\b"

        # 收集文档路径
        doc_paths = _collect_doc_paths(project, extra_paths)

        # 扫描每个文档
        entries: list[DocEntry] = []
        skipped: list[str] = []
        for abs_path, rel_path in doc_paths:
            entry = _scan_doc_file(abs_path, rel_path, patterns)
            if entry is not None:
                entries.append(entry)
            else:
                skipped.append(rel_path)

        # 生成摘要
        generated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        n = len(entries)

        summary_lines = [
            f"文档地图：扫描 {n} 个文档",
        ]
        if skipped:
            summary_lines.append(f"跳过（不存在）：{len(skipped)} 个文件")

        # 找出 stale 文档（90 天未更新）的数量
        stale_count = 0
        now_ts = time.time()
        for e in entries:
            if e.last_modified:
                try:
                    dt = datetime.fromisoformat(e.last_modified.replace("Z", "+00:00"))
                    age_days = (now_ts - dt.timestamp()) / 86400
                    if age_days > 90:
                        stale_count += 1
                except (ValueError, OSError):
                    pass
        if stale_count:
            summary_lines.append(f"其中 {stale_count} 个文档超过 90 天未更新")

        return SkillResult(
            success=True,
            summary="\n".join(summary_lines),
            data={
                "generated_at": generated_at,
                "doc_count": n,
                "docs": [e.to_dict() for e in entries],
                "skipped": skipped,
            },
            next_steps=_build_next_steps(n, stale_count),
        )


def _build_next_steps(doc_count: int, stale_count: int) -> list[str]:
    steps: list[str] = []
    if doc_count == 0:
        steps.append("未找到任何文档，请确认项目路径是否正确。")
        return steps
    steps.append("运行 doc.consistency 检查文档与代码是否一致。")
    if stale_count:
        steps.append(
            f"{stale_count} 个文档超过 90 天未更新，建议用 doc.update.plan 生成更新建议。"
        )
    return steps
