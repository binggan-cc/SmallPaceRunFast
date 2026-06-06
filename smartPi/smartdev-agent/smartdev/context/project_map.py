"""
SmartDev Agent 项目地图导出

设计原理：
─────────
从 index.sqlite 读取 artifacts / relations 数据，
组合成人类可读的项目地图（JSON + Markdown）。

这是索引结果的导出物，服务开发判断：
- 哪些模块被最多文件依赖（hotspots）
- 哪些是外部依赖
- 哪些 import 未解析
- 项目整体结构概览

借鉴来源：
- Understand-Anything 的 architecture-analyzer：生成架构摘要
- 理念：索引数据不只是给 Agent 用，也要能给人看

对应文档：
- next-phase-code-intelligence.md §8.3（project.map 设计）
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from smartdev.context.index_store import IndexStore


@dataclass
class ModuleInfo:
    """模块信息"""
    id: str
    file_path: str
    name: str
    imports: list[str] = field(default_factory=list)       # 该模块 import 的模块
    imported_by: list[str] = field(default_factory=list)   # import 该模块的文件
    artifact_count: int = 0


@dataclass
class HotspotInfo:
    """高依赖模块"""
    target: str
    dependent_count: int
    risk: str
    importers: list[str] = field(default_factory=list)


@dataclass
class ExternalDepInfo:
    """外部依赖"""
    name: str
    dependent_count: int
    importers: list[str] = field(default_factory=list)


@dataclass
class ProjectMap:
    """项目地图"""
    project_name: str
    generated_at: str
    summary: dict
    modules: list[ModuleInfo]
    hotspots: list[HotspotInfo]
    external_dependencies: list[ExternalDepInfo]
    unresolved_imports: list[dict]

    def to_json(self) -> str:
        """导出为 JSON 字符串"""
        return json.dumps({
            "project": {
                "name": self.project_name,
                "generated_at": self.generated_at,
                "summary": self.summary,
            },
            "modules": [
                {
                    "id": m.id,
                    "file_path": m.file_path,
                    "name": m.name,
                    "imports": m.imports,
                    "imported_by": m.imported_by,
                    "artifact_count": m.artifact_count,
                }
                for m in self.modules
            ],
            "hotspots": [
                {
                    "target": h.target,
                    "dependent_count": h.dependent_count,
                    "risk": h.risk,
                    "importers": h.importers[:10],
                }
                for h in self.hotspots
            ],
            "external_dependencies": [
                {
                    "name": e.name,
                    "dependent_count": e.dependent_count,
                    "importers": e.importers[:10],
                }
                for e in self.external_dependencies
            ],
            "unresolved_imports": self.unresolved_imports,
        }, indent=2, ensure_ascii=False)

    def to_markdown(self) -> str:
        """导出为 Markdown 摘要"""
        lines = [
            f"# {self.project_name} — Project Map",
            "",
            f"*Generated: {self.generated_at}*",
            "",
            "## Overview",
            "",
            f"- Files: {self.summary.get('files', 0)}",
            f"- Artifacts: {self.summary.get('artifacts', 0)}",
            f"- Relations: {self.summary.get('relations', 0)}",
            f"- Languages: {self.summary.get('languages', [])}",
            "",
        ]

        # Hotspots
        if self.hotspots:
            lines.append("## Most Imported Internal Modules")
            lines.append("")
            lines.append("| Module | Dependents | Risk |")
            lines.append("|--------|-----------|------|")
            for h in self.hotspots[:10]:
                lines.append(f"| `{h.target}` | {h.dependent_count} | {h.risk} |")
            lines.append("")

        # External dependencies
        if self.external_dependencies:
            lines.append("## External Dependencies")
            lines.append("")
            lines.append("| Package | Used By |")
            lines.append("|---------|---------|")
            for e in self.external_dependencies[:10]:
                lines.append(f"| `{e.name}` | {e.dependent_count} files |")
            lines.append("")

        # Unresolved
        if self.unresolved_imports:
            lines.append("## Unresolved Imports")
            lines.append("")
            for u in self.unresolved_imports[:5]:
                lines.append(f"- `{u.get('module', '?')}` in {u.get('file', '?')}")
            lines.append("")

        # Validation focus
        lines.append("## Suggested Validation Focus")
        lines.append("")
        if self.hotspots:
            top = self.hotspots[0]
            lines.append(f"1. Core module `{top.target}` has {top.dependent_count} dependents — verify changes carefully")
        lines.append(f"2. Run full test suite: `python -m pytest tests/ -q`")
        lines.append("")

        return "\n".join(lines)


def generate_project_map(store: IndexStore, project_name: str = "project") -> ProjectMap:
    """从 IndexStore 生成项目地图

    参数：
        store: 已建立索引的 IndexStore
        project_name: 项目名称

    返回：
        ProjectMap
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1. 统计
    stats = store.stats()

    # 2. 收集 module artifacts 和 import relations
    conn = store.connect()

    # 获取所有 module artifacts
    module_rows = conn.execute(
        "SELECT id, name, file_path FROM artifacts WHERE type = 'code:module'"
    ).fetchall()

    # 获取所有 imports relations
    import_rels = conn.execute(
        "SELECT source_id, target_id, metadata_json FROM relations WHERE type = 'imports'"
    ).fetchall()

    # 获取 external modules
    external_rows = conn.execute(
        "SELECT id, name FROM artifacts WHERE type = 'external_module'"
    ).fetchall()

    # 获取 unresolved
    unresolved_rows = conn.execute(
        "SELECT id, name, file_path FROM artifacts WHERE type = 'unresolved_module'"
    ).fetchall()

    # 3. 构建 module 信息
    modules: dict[str, ModuleInfo] = {}
    for row in module_rows:
        modules[row["id"]] = ModuleInfo(
            id=row["id"],
            file_path=row["file_path"],
            name=row["name"],
        )

    # 4. 填充 import 关系
    # outgoing: source module imports target
    # incoming: target is imported by source
    for rel in import_rels:
        source_id = rel["source_id"]
        target_id = rel["target_id"]
        meta = json.loads(rel["metadata_json"]) if rel["metadata_json"] else {}
        module_name = meta.get("module", target_id)

        # outgoing
        if source_id in modules:
            modules[source_id].imports.append(module_name)

        # incoming（查找 target 对应的 module）
        for mid, minfo in modules.items():
            if target_id == mid or target_id == f"module:{minfo.name}":
                # source_file 从 source_id 提取
                source_file = ""
                if source_id.startswith("code:module:"):
                    source_file = source_id[len("code:module:"):]
                elif source_id in modules:
                    source_file = modules[source_id].file_path
                minfo.imported_by.append(source_file)

    # 5. 计算 hotspots（被最多文件 import 的模块）
    hotspot_counts: dict[str, list[str]] = {}
    for rel in import_rels:
        target_id = rel["target_id"]
        meta = json.loads(rel["metadata_json"]) if rel["metadata_json"] else {}
        # Phase 6.3 Step 4.2: 优先使用 normalized target_id（避免 ../types 和 ./types 被拆开统计）
        if target_id.startswith("code:module:"):
            module_name = target_id[len("code:module:"):]  # e.g., "src/types.ts"
        else:
            module_name = meta.get("module", target_id)
        source_file = ""
        if rel["source_id"].startswith("code:module:"):
            source_file = rel["source_id"][len("code:module:"):]
        elif rel["source_id"] in modules:
            source_file = modules[rel["source_id"]].file_path

        if module_name not in hotspot_counts:
            hotspot_counts[module_name] = []
        if source_file and source_file not in hotspot_counts[module_name]:
            hotspot_counts[module_name].append(source_file)

    hotspots = []
    for module_name, importers in sorted(hotspot_counts.items(), key=lambda x: -len(x[1])):
        # 跳过外部模块（单独统计）
        if any(module_name == e["name"] for e in external_rows):
            continue
        if len(importers) >= 2:  # 至少 2 个文件 import 才算 hotspot
            risk = "R2" if len(importers) >= 5 else "R1"
            hotspots.append(HotspotInfo(
                target=module_name,
                dependent_count=len(importers),
                risk=risk,
                importers=importers,
            ))

    # 6. 外部依赖统计
    external_deps: dict[str, list[str]] = {}
    for rel in import_rels:
        target_id = rel["target_id"]
        if not target_id.startswith("external:"):
            continue
        ext_name = target_id.split(":", 2)[-1]  # external:python:pathlib → pathlib
        meta = json.loads(rel["metadata_json"]) if rel["metadata_json"] else {}
        source_file = ""
        if rel["source_id"].startswith("code:module:"):
            source_file = rel["source_id"][len("code:module:"):]
        elif rel["source_id"] in modules:
            source_file = modules[rel["source_id"]].file_path

        if ext_name not in external_deps:
            external_deps[ext_name] = []
        if source_file and source_file not in external_deps[ext_name]:
            external_deps[ext_name].append(source_file)

    external_info = [
        ExternalDepInfo(
            name=name,
            dependent_count=len(importers),
            importers=importers,
        )
        for name, importers in sorted(external_deps.items(), key=lambda x: -len(x[1]))
    ]

    # 7. unresolved imports
    unresolved = [
        {"module": u["name"], "file": u["file_path"]}
        for u in unresolved_rows
    ]

    # 8. 组装
    summary = {
        "files": stats["files"],
        "artifacts": stats["artifacts"],
        "relations": stats["relations"],
        "languages": [l["language"] for l in stats.get("languages", [])],
        "modules": len(modules),
        "hotspots": len(hotspots),
        "external_deps": len(external_info),
        "unresolved": len(unresolved),
    }

    return ProjectMap(
        project_name=project_name,
        generated_at=now,
        summary=summary,
        modules=list(modules.values()),
        hotspots=hotspots,
        external_dependencies=external_info,
        unresolved_imports=unresolved,
    )


def save_project_map(project_map: ProjectMap, output_dir: Path) -> dict[str, Path]:
    """保存项目地图到文件

    返回：
        生成的文件路径
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "project-map.json"
    md_path = output_dir / "architecture-summary.md"

    json_path.write_text(project_map.to_json(), encoding="utf-8")
    md_path.write_text(project_map.to_markdown(), encoding="utf-8")

    return {
        "json": json_path,
        "markdown": md_path,
    }
