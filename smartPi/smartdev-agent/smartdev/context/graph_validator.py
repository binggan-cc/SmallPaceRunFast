"""
SmartDev Agent 图谱校验器

设计原理：
─────────
验证 index.sqlite 中 artifacts / relations 数据的健康度。
不做自动修复，只输出校验报告。

校验项（v0）：
1. Orphan source: relation.source_id 在 artifacts 表中不存在
2. Orphan target: relation.target_id 在 artifacts 表中不存在（external/unresolved 除外）
3. Duplicate relation: source_id + target_id + type 重复
4. Missing metadata: imports relation 缺少关键字段
5. Suspicious hotspot: 某 target 被过多模块 import
6. Unresolved summary: 统计未解析的 import

借鉴来源：
- CodeGraph 的 graph validation
- 理念：先验证图谱可信，再扩展语言覆盖

对应文档：
- next-phase-code-intelligence.md §8.3（graph.validate 设计）
"""

from __future__ import annotations

from dataclasses import dataclass, field

from smartdev.context.index_store import IndexStore


@dataclass
class ValidationIssue:
    """校验问题"""
    severity: str  # "error" / "warning" / "info"
    category: str  # "orphan_source" / "orphan_target" / "duplicate" / "missing_metadata" / "hotspot" / "unresolved"
    message: str
    details: dict = field(default_factory=dict)


@dataclass
class GraphValidationResult:
    """图谱校验结果"""
    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)
    info: list[ValidationIssue] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    @property
    def is_healthy(self) -> bool:
        """图谱是否健康（无 error）"""
        return len(self.errors) == 0

    def to_markdown(self) -> str:
        """导出为 Markdown 校验报告"""
        lines = [
            "# Graph Validation Report",
            "",
            "## Summary",
            "",
            f"- Artifacts: {self.stats.get('artifacts', 0)}",
            f"- Relations: {self.stats.get('relations', 0)}",
            f"- Errors: {len(self.errors)}",
            f"- Warnings: {len(self.warnings)}",
            f"- Info: {len(self.info)}",
            "",
        ]

        if self.errors:
            lines.append("## Errors")
            lines.append("")
            for issue in self.errors:
                lines.append(f"- **[{issue.category}]** {issue.message}")
            lines.append("")

        if self.warnings:
            lines.append("## Warnings")
            lines.append("")
            for issue in self.warnings:
                lines.append(f"- **[{issue.category}]** {issue.message}")
            lines.append("")

        if self.info:
            lines.append("## Info")
            lines.append("")
            for issue in self.info:
                lines.append(f"- **[{issue.category}]** {issue.message}")
            lines.append("")

        # Unresolved relative imports (Phase 6.3 Step 4.2)
        unresolved_rel = [w for w in self.warnings if w.category == "unresolved_relative_import"]
        if unresolved_rel:
            lines.append("## Unresolved Relative Imports (Internal)")
            lines.append("")
            for issue in unresolved_rel:
                lines.append(f"- {issue.message}")
            lines.append("")

        # Hotspots
        hotspot_issues = [i for i in self.warnings if i.category == "hotspot"]
        if hotspot_issues:
            lines.append("## Hotspots")
            lines.append("")
            for issue in hotspot_issues:
                lines.append(f"- {issue.message}")
            lines.append("")

        # Unresolved
        unresolved_issues = [i for i in self.info if i.category == "unresolved"]
        if unresolved_issues:
            lines.append("## Unresolved Imports")
            lines.append("")
            for issue in unresolved_issues:
                lines.append(f"- {issue.message}")
            lines.append("")

        return "\n".join(lines)


def validate_graph(store: IndexStore, hotspot_threshold: int = 20) -> GraphValidationResult:
    """校验图谱数据健康度

    参数：
        store: 已建立索引的 IndexStore
        hotspot_threshold: hotspot 告警阈值（某 target 被 N 个以上模块 import 时告警）

    返回：
        GraphValidationResult
    """
    result = GraphValidationResult()
    conn = store.connect()

    # 统计
    artifact_count = conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0]
    relation_count = conn.execute("SELECT COUNT(*) FROM relations").fetchone()[0]
    result.stats = {
        "artifacts": artifact_count,
        "relations": relation_count,
    }

    # 构建 artifact ID 集合
    artifact_ids = {
        row[0] for row in conn.execute("SELECT id FROM artifacts").fetchall()
    }

    # 构建 relation 去重检查集合
    seen_relations: set[tuple] = set()

    # 构建 target → importers 映射（用于 hotspot 检查）
    target_importers: dict[str, set[str]] = {}

    # 构建 unresolved 统计
    unresolved_count = 0
    external_count = 0

    # 遍历所有 relations
    relations = conn.execute(
        "SELECT source_id, target_id, type, metadata_json FROM relations"
    ).fetchall()

    for rel in relations:
        source_id = rel["source_id"]
        target_id = rel["target_id"]
        rel_type = rel["type"]
        meta_str = rel["metadata_json"]
        meta = __import__("json").loads(meta_str) if meta_str else {}

        # ── 0. Unresolved relative import（Phase 6.3 Step 4.2 新增）──
        # 内部相对 import 指向不存在的文件 → warning
        if meta.get("resolution_kind") == "file_not_found":
            result.warnings.append(ValidationIssue(
                severity="warning",
                category="unresolved_relative_import",
                message=(
                    f"Relative import '{meta.get('raw_specifier', target_id)}' "
                    f"in {source_id} could not be resolved to a file. "
                    f"Tried: {meta.get('tried_paths', [])}"
                ),
                details={
                    "source_id": source_id,
                    "target_id": target_id,
                    "raw_specifier": meta.get("raw_specifier", ""),
                    "tried_paths": meta.get("tried_paths", []),
                },
            ))

        # ── 1. Orphan source ──
        if source_id not in artifact_ids:
            # code:module: 格式的 source 由 artifact_extractor 创建
            # 如果不存在，说明 extraction 有问题
            if not source_id.startswith("external:") and not source_id.startswith("unresolved:"):
                result.errors.append(ValidationIssue(
                    severity="error",
                    category="orphan_source",
                    message=f"Relation source_id '{source_id}' not found in artifacts table",
                    details={"source_id": source_id, "target_id": target_id},
                ))

        # ── 2. Orphan target ──
        # 统计 external/unresolved（无论是否在 artifacts 表中）
        if target_id.startswith("external:"):
            external_count += 1
        elif target_id.startswith("unresolved:"):
            unresolved_count += 1
        elif target_id not in artifact_ids:
            result.warnings.append(ValidationIssue(
                severity="warning",
                category="orphan_target",
                message=f"Relation target_id '{target_id}' not found in artifacts table",
                details={"source_id": source_id, "target_id": target_id},
            ))

        # ── 3. Duplicate relation ──
        key = (source_id, target_id, rel_type)
        if key in seen_relations:
            result.warnings.append(ValidationIssue(
                severity="warning",
                category="duplicate",
                message=f"Duplicate relation: {source_id} → {target_id} [{rel_type}]",
                details={"source_id": source_id, "target_id": target_id, "type": rel_type},
            ))
        else:
            seen_relations.add(key)

        # ── 4. Missing metadata ──
        if rel_type == "imports":
            required_fields = ["module", "import_kind", "confidence"]
            missing = [f for f in required_fields if f not in meta]
            if missing:
                result.warnings.append(ValidationIssue(
                    severity="warning",
                    category="missing_metadata",
                    message=f"imports relation missing fields: {', '.join(missing)} (source: {source_id})",
                    details={"source_id": source_id, "missing": missing},
                ))

        # ── 5. Hotspot tracking ──
        if rel_type == "imports":
            if target_id not in target_importers:
                target_importers[target_id] = set()
            if source_id.startswith("code:module:"):
                target_importers[target_id].add(source_id)

    # ── 5. Hotspot warnings ──
    for target_id, importers in target_importers.items():
        if len(importers) >= hotspot_threshold:
            result.warnings.append(ValidationIssue(
                severity="warning",
                category="hotspot",
                message=f"High-dependency target '{target_id}' has {len(importers)} importers (threshold: {hotspot_threshold})",
                details={"target_id": target_id, "count": len(importers)},
            ))

    # ── 6. Unresolved summary ──
    unresolved_artifacts = conn.execute(
        "SELECT COUNT(*) FROM artifacts WHERE type = 'unresolved_module'"
    ).fetchone()[0]

    if unresolved_artifacts > 0:
        result.info.append(ValidationIssue(
            severity="info",
            category="unresolved",
            message=f"{unresolved_artifacts} unresolved import(s) in index",
            details={"count": unresolved_artifacts},
        ))

    if unresolved_count > 0:
        result.info.append(ValidationIssue(
            severity="info",
            category="unresolved",
            message=f"{unresolved_count} relation(s) point to unresolved targets",
            details={"count": unresolved_count},
        ))

    # 更新 stats
    result.stats["orphan_sources"] = len([e for e in result.errors if e.category == "orphan_source"])
    result.stats["orphan_targets"] = len([w for w in result.warnings if w.category == "orphan_target"])
    result.stats["duplicates"] = len([w for w in result.warnings if w.category == "duplicate"])
    result.stats["missing_metadata"] = len([w for w in result.warnings if w.category == "missing_metadata"])
    result.stats["hotspots"] = len([w for w in result.warnings if w.category == "hotspot"])
    result.stats["unresolved_relative_imports"] = len([w for w in result.warnings if w.category == "unresolved_relative_import"])
    result.stats["unresolved"] = unresolved_artifacts + unresolved_count
    result.stats["external"] = external_count

    return result
