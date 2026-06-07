"""
SmartDev MCP — 工具实现

Phase 10 Step 1：基础工具
    smartdev_ping            健康检查
    smartdev_version         版本信息 + 能力清单
    smartdev_list_tools      列出所有可用 MCP 工具

Phase 10 Step 2：只读 Context 工具
    smartdev_code_search     全文搜索文件和 artifact
    smartdev_code_impact     变更影响分析（import reverse lookup）
    smartdev_project_map     导出项目结构地图（JSON）
    smartdev_graph_validate  图谱健康校验

后续 Step 3–4 将在此文件追加：
    repo_scan / risk_check / architecture_map / task_plan / qa_checklist
    code_index / patch_propose

设计原则：
- 工具始终返回 list[TextContent]，不抛异常到 MCP 层
- 所有输出走 formatter.ok / formatter.error
- MCP 层只做参数解析 + Skill/Context 调用 + 格式化，不含业务逻辑
- INDEX_NOT_FOUND 是最常见错误，必须给出 suggested_tool

对应文档：
    docs/phase-10-design.md §3.3
"""

from __future__ import annotations

from pathlib import Path

from mcp.types import TextContent

from smartdev import __version__
from smartdev.mcp import formatter

# ── 辅助：检查索引是否存在 ─────────────────────────────────────────


def _index_path(project_path: Path) -> Path:
    return project_path / ".smartdev" / "index.sqlite"


def _index_missing_error(tool: str, project_path: Path) -> list[TextContent]:
    return [TextContent(
        type="text",
        text=formatter.error(
            tool,
            "INDEX_NOT_FOUND",
            f"No .smartdev/index.sqlite found at {project_path}. "
            "Run smartdev_code_index first to build the project index.",
            suggested_tool="smartdev_code_index",
        ),
    )]


# ── Step 1 工具：ping / version / list_tools ─────────────────────


async def handle_ping(arguments: dict, project_path: Path) -> list[TextContent]:
    """健康检查，确认 MCP Server 正常运行"""
    return [TextContent(
        type="text",
        text=formatter.ok("smartdev_ping", {"pong": True, "project_path": str(project_path)}),
    )]


async def handle_version(arguments: dict, project_path: Path) -> list[TextContent]:
    """返回版本信息和当前已注册的工具能力清单"""
    tools = [
        {"name": "smartdev_ping",            "permission": "READ",          "status": "available"},
        {"name": "smartdev_version",          "permission": "READ",          "status": "available"},
        {"name": "smartdev_list_tools",       "permission": "READ",          "status": "available"},
        {"name": "smartdev_code_search",      "permission": "READ",          "status": "available"},
        {"name": "smartdev_code_impact",      "permission": "READ",          "status": "available"},
        {"name": "smartdev_project_map",      "permission": "READ",          "status": "available"},
        {"name": "smartdev_graph_validate",   "permission": "READ",          "status": "available"},
        {"name": "smartdev_repo_scan",        "permission": "READ",          "status": "available"},
        {"name": "smartdev_risk_check",       "permission": "READ",          "status": "available"},
        {"name": "smartdev_architecture_map", "permission": "READ",          "status": "available"},
        {"name": "smartdev_task_plan",        "permission": "READ",          "status": "available"},
        {"name": "smartdev_qa_checklist",     "permission": "READ",          "status": "available"},
        # Step 4（待实现）
        {"name": "smartdev_code_index",       "permission": "CACHE_WRITE",   "status": "coming_soon"},
        {"name": "smartdev_patch_propose",    "permission": "PATCH_PROPOSE", "status": "coming_soon"},
    ]
    return [TextContent(
        type="text",
        text=formatter.ok("smartdev_version", {
            "version": __version__,
            "mcp_server": "SmartDev MCP Server v0",
            "project_path": str(project_path),
            "tools": tools,
        }),
    )]


async def handle_list_tools(arguments: dict, project_path: Path) -> list[TextContent]:
    """列出当前可用工具，附带权限和说明"""
    available = [
        {
            "name": "smartdev_ping",
            "permission": "READ",
            "description": "Health check. Confirms MCP Server is running.",
        },
        {
            "name": "smartdev_version",
            "permission": "READ",
            "description": "Returns version and full tool capability list.",
        },
        {
            "name": "smartdev_list_tools",
            "permission": "READ",
            "description": "Lists all available tools with permissions.",
        },
        {
            "name": "smartdev_code_search",
            "permission": "READ",
            "description": "Full-text search over indexed files and artifacts. Requires index.",
        },
        {
            "name": "smartdev_code_impact",
            "permission": "READ",
            "description": "Analyze change impact via import reverse lookup. Requires index.",
        },
        {
            "name": "smartdev_project_map",
            "permission": "READ",
            "description": "Export project structure map (modules, hotspots, external deps). Requires index.",
        },
        {
            "name": "smartdev_graph_validate",
            "permission": "READ",
            "description": "Validate graph health (orphans, duplicates, hotspots, unresolved). Requires index.",
        },
        {
            "name": "smartdev_repo_scan",
            "permission": "READ",
            "description": "Scan project: tech stack, entry points, docs status, directory tree.",
        },
        {
            "name": "smartdev_risk_check",
            "permission": "READ",
            "description": "Check task risk level. With index: impact-enhanced. Without: keyword fallback.",
        },
        {
            "name": "smartdev_architecture_map",
            "permission": "READ",
            "description": "Architecture dependency graph. With index: multi-language. Without: Python AST.",
        },
        {
            "name": "smartdev_task_plan",
            "permission": "READ",
            "description": "Generate three-tier task plan. With index: annotates affected files.",
        },
        {
            "name": "smartdev_qa_checklist",
            "permission": "READ",
            "description": "Generate structured acceptance checklist for a task.",
        },
    ]
    return [TextContent(
        type="text",
        text=formatter.ok("smartdev_list_tools", {
            "available_tools": available,
            "total": len(available),
        }),
    )]


# ── Step 2 工具：只读 Context ─────────────────────────────────────


async def handle_code_search(arguments: dict, project_path: Path) -> list[TextContent]:
    """全文搜索已索引项目的文件和 artifact"""
    if not _index_path(project_path).exists():
        return _index_missing_error("smartdev_code_search", project_path)

    query = arguments.get("query", "").strip()
    if not query:
        return [TextContent(
            type="text",
            text=formatter.error(
                "smartdev_code_search",
                "INVALID_ARGUMENT",
                "Parameter 'query' is required and must not be empty.",
            ),
        )]

    limit = int(arguments.get("limit", 20))

    try:
        from smartdev.context.project_index import ProjectIndex
        index = ProjectIndex(project_path)
        results = index.search(query, limit=limit)
        index.close()

        next_steps = []
        if results["total_files"] == 0 and results["total_artifacts"] == 0:
            next_steps.append("No results found. Try a broader search term.")
            next_steps.append("If the project was recently modified, run smartdev_code_index to refresh.")

        return [TextContent(
            type="text",
            text=formatter.ok(
                "smartdev_code_search",
                results,
                next_steps=next_steps,
            ),
        )]
    except Exception as e:
        return [TextContent(
            type="text",
            text=formatter.error(
                "smartdev_code_search",
                "INTERNAL_ERROR",
                f"Search failed: {e}",
            ),
        )]


async def handle_code_impact(arguments: dict, project_path: Path) -> list[TextContent]:
    """分析变更影响范围（基于 import relations 的 reverse lookup）"""
    if not _index_path(project_path).exists():
        return _index_missing_error("smartdev_code_impact", project_path)

    target = arguments.get("target", "").strip()
    if not target:
        return [TextContent(
            type="text",
            text=formatter.error(
                "smartdev_code_impact",
                "INVALID_ARGUMENT",
                "Parameter 'target' is required (file path, module name, or artifact name).",
            ),
        )]

    max_depth = int(arguments.get("max_depth", 3))

    try:
        from smartdev.context.impact_analyzer import ImpactAnalyzer
        from smartdev.context.project_index import ProjectIndex

        index = ProjectIndex(project_path)
        analyzer = ImpactAnalyzer(index.store)

        # 优先使用 import-relation-based 分析
        import_result = analyzer.analyze_import_impact(target)

        data = {
            "target": target,
            "resolved_target": import_result.resolved_target,
            "affected_files": import_result.affected_files,
            "direct_dependents_count": len(import_result.direct_dependents),
            "risk_level": import_result.risk_level,
            "validation_suggestions": import_result.validation_suggestions,
            "limitations": import_result.limitations,
            "summary": import_result.summary,
        }

        # 若 import 分析无结果，降级到规则型分析
        if not import_result.affected_files:
            rule_result = analyzer.analyze(target, max_depth=max_depth)
            data["fallback_analysis"] = {
                "direct_references": rule_result.direct_references[:10],
                "indirect_impacts": rule_result.indirect_impacts[:10],
                "risk_level": rule_result.risk_level,
                "verification_items": rule_result.verification_items,
            }

        index.close()

        return [TextContent(
            type="text",
            text=formatter.ok(
                "smartdev_code_impact",
                data,
                risk_level=import_result.risk_level,
                next_steps=import_result.validation_suggestions[:3],
            ),
        )]
    except Exception as e:
        return [TextContent(
            type="text",
            text=formatter.error(
                "smartdev_code_impact",
                "INTERNAL_ERROR",
                f"Impact analysis failed: {e}",
            ),
        )]


async def handle_project_map(arguments: dict, project_path: Path) -> list[TextContent]:
    """导出项目结构地图（模块 / hotspot / 外部依赖）"""
    if not _index_path(project_path).exists():
        return _index_missing_error("smartdev_project_map", project_path)

    try:
        from smartdev.context.project_index import ProjectIndex
        from smartdev.context.project_map import generate_project_map

        index = ProjectIndex(project_path)
        project_name = project_path.name
        pmap = generate_project_map(index.store, project_name=project_name)
        index.close()

        import json
        map_data = json.loads(pmap.to_json())

        return [TextContent(
            type="text",
            text=formatter.ok(
                "smartdev_project_map",
                map_data,
                next_steps=[
                    "Use smartdev_code_impact to analyze specific module dependencies.",
                    "Use smartdev_graph_validate to check graph health.",
                ],
            ),
        )]
    except Exception as e:
        return [TextContent(
            type="text",
            text=formatter.error(
                "smartdev_project_map",
                "INTERNAL_ERROR",
                f"Project map generation failed: {e}",
            ),
        )]


async def handle_graph_validate(arguments: dict, project_path: Path) -> list[TextContent]:
    """校验图谱健康度（孤立节点 / 重复 / hotspot / unresolved imports）"""
    if not _index_path(project_path).exists():
        return _index_missing_error("smartdev_graph_validate", project_path)

    try:
        from smartdev.context.graph_validator import validate_graph
        from smartdev.context.project_index import ProjectIndex

        index = ProjectIndex(project_path)
        result = validate_graph(index.store)
        index.close()

        data = {
            "is_healthy": result.is_healthy,
            "stats": result.stats,
            "errors": [
                {"category": e.category, "message": e.message}
                for e in result.errors
            ],
            "warnings": [
                {"category": w.category, "message": w.message}
                for w in result.warnings
            ],
            "info": [
                {"category": i.category, "message": i.message}
                for i in result.info
            ],
            "summary": {
                "error_count": len(result.errors),
                "warning_count": len(result.warnings),
                "info_count": len(result.info),
            },
        }

        warnings_out = []
        if result.errors:
            warnings_out.append(f"{len(result.errors)} error(s) found in graph.")
        if len(result.warnings) > 5:
            warnings_out.append(f"{len(result.warnings)} warnings — consider running smartdev_code_index to refresh.")

        return [TextContent(
            type="text",
            text=formatter.ok(
                "smartdev_graph_validate",
                data,
                warnings=warnings_out,
                risk_level="R0",
            ),
        )]
    except Exception as e:
        return [TextContent(
            type="text",
            text=formatter.error(
                "smartdev_graph_validate",
                "INTERNAL_ERROR",
                f"Graph validation failed: {e}",
            ),
        )]



# ── Step 3 工具：Skill 接入 ───────────────────────────────────────
#
# 设计原则（体现 Phase 8）：
# - Skill 已能消费 Context Layer：有索引时自动增强，无索引时退回原逻辑
# - MCP 层只传 project_path + inputs，不重新实现 Skill 业务逻辑
# - task_description 从 arguments 里取，不强制必填（可降级为通用扫描）


def _make_context(project_path: Path, task_description: str = ""):
    """构建 ProjectContext，供 Skill 调用"""
    from smartdev.models import ProjectContext
    return ProjectContext(
        project_path=project_path,
        task_description=task_description,
    )


async def handle_repo_scan(arguments: dict, project_path: Path) -> list[TextContent]:
    """扫描项目：技术栈 / 入口文件 / 文档状态 / 目录树"""
    import smartdev.skills  # noqa: F401 — 触发所有 Skill 注册
    from smartdev.skills.base import Skill

    try:
        skill = Skill.create("repo.scan")
        context = _make_context(project_path)

        if not skill.can_run(context):
            return [TextContent(
                type="text",
                text=formatter.error(
                    "smartdev_repo_scan",
                    "SKILL_CANNOT_RUN",
                    f"repo.scan cannot run: project path does not exist or is not a directory: {project_path}",
                ),
            )]

        inputs = {}
        if "max_depth" in arguments:
            inputs["max_depth"] = int(arguments["max_depth"])

        result = skill.run(context, inputs)

        return [TextContent(
            type="text",
            text=formatter.ok(
                "smartdev_repo_scan",
                {
                    "summary": result.summary,
                    "data": result.data,
                    "risks": result.risks,
                },
                next_steps=result.next_steps[:3],
            ),
        )]
    except Exception as e:
        return [TextContent(
            type="text",
            text=formatter.error("smartdev_repo_scan", "INTERNAL_ERROR", f"repo.scan failed: {e}"),
        )]


async def handle_risk_check(arguments: dict, project_path: Path) -> list[TextContent]:
    """风险检查：关键词 + 可选 impact 增强（有索引时自动升级）"""
    import smartdev.skills  # noqa: F401
    from smartdev.skills.base import Skill

    task_description = arguments.get("task_description", "").strip()

    try:
        skill = Skill.create("risk.check")
        context = _make_context(project_path, task_description)

        if not skill.can_run(context):
            return [TextContent(
                type="text",
                text=formatter.error(
                    "smartdev_risk_check",
                    "SKILL_CANNOT_RUN",
                    "risk.check requires a non-empty task_description.",
                ),
            )]

        # target 可选：有索引时触发 impact 增强
        inputs = {}
        if "target" in arguments:
            inputs["target"] = arguments["target"]

        result = skill.run(context, inputs)
        risk_level = result.data.get("risk_level", "R0")

        return [TextContent(
            type="text",
            text=formatter.ok(
                "smartdev_risk_check",
                result.data,
                risk_level=risk_level,
                warnings=result.risks[:3],
                next_steps=result.next_steps[:3],
            ),
        )]
    except Exception as e:
        return [TextContent(
            type="text",
            text=formatter.error("smartdev_risk_check", "INTERNAL_ERROR", f"risk.check failed: {e}"),
        )]


async def handle_architecture_map(arguments: dict, project_path: Path) -> list[TextContent]:
    """架构分析：依赖图 + 循环依赖（有索引时用多语言 index relations）"""
    import smartdev.skills  # noqa: F401
    from smartdev.skills.base import Skill

    try:
        skill = Skill.create("architecture.map")
        context = _make_context(project_path)

        if not skill.can_run(context):
            return [TextContent(
                type="text",
                text=formatter.error(
                    "smartdev_architecture_map",
                    "SKILL_CANNOT_RUN",
                    f"architecture.map cannot run at: {project_path}. "
                    "Either build an index first (smartdev_code_index) or ensure the project has source files.",
                ),
            )]

        result = skill.run(context)

        return [TextContent(
            type="text",
            text=formatter.ok(
                "smartdev_architecture_map",
                {
                    "summary": result.summary,
                    "data": result.data,
                },
                warnings=result.risks[:3],
                next_steps=result.next_steps[:3],
            ),
        )]
    except Exception as e:
        return [TextContent(
            type="text",
            text=formatter.error("smartdev_architecture_map", "INTERNAL_ERROR", f"architecture.map failed: {e}"),
        )]


async def handle_task_plan(arguments: dict, project_path: Path) -> list[TextContent]:
    """任务规划：三档方案 + 有索引时标注受影响文件"""
    import smartdev.skills  # noqa: F401
    from smartdev.skills.base import Skill

    task_description = arguments.get("task_description", "").strip()

    try:
        skill = Skill.create("task.plan")
        context = _make_context(project_path, task_description)

        if not skill.can_run(context):
            return [TextContent(
                type="text",
                text=formatter.error(
                    "smartdev_task_plan",
                    "SKILL_CANNOT_RUN",
                    "task.plan requires a non-empty task_description.",
                ),
            )]

        # target 可选：有索引时触发 impact 标注
        inputs = {}
        if "target" in arguments:
            inputs["target"] = arguments["target"]

        result = skill.run(context, inputs)

        return [TextContent(
            type="text",
            text=formatter.ok(
                "smartdev_task_plan",
                result.data,
                next_steps=result.next_steps[:3],
            ),
        )]
    except Exception as e:
        return [TextContent(
            type="text",
            text=formatter.error("smartdev_task_plan", "INTERNAL_ERROR", f"task.plan failed: {e}"),
        )]


async def handle_qa_checklist(arguments: dict, project_path: Path) -> list[TextContent]:
    """验收清单：按任务类型生成结构化验收条目"""
    import smartdev.skills  # noqa: F401
    from smartdev.skills.base import Skill

    task_description = arguments.get("task_description", "").strip()

    try:
        skill = Skill.create("qa.checklist")
        context = _make_context(project_path, task_description)

        if not skill.can_run(context):
            return [TextContent(
                type="text",
                text=formatter.error(
                    "smartdev_qa_checklist",
                    "SKILL_CANNOT_RUN",
                    "qa.checklist requires a non-empty task_description.",
                ),
            )]

        result = skill.run(context)

        return [TextContent(
            type="text",
            text=formatter.ok(
                "smartdev_qa_checklist",
                result.data,
                next_steps=result.next_steps[:3],
            ),
        )]
    except Exception as e:
        return [TextContent(
            type="text",
            text=formatter.error("smartdev_qa_checklist", "INTERNAL_ERROR", f"qa.checklist failed: {e}"),
        )]
