"""
SmartDev Agent CLI 入口

设计原理：
─────────
CLI 是 Agent 与用户交互的入口。Phase 1 只实现两个核心命令：
- scan: 调用 repo.scan 扫描项目
- plan: 调用 task.plan 生成三档方案
- list: 列出所有可用 Skill

为什么用 argparse 而非 click/typer？
──────────────────────────────────
Phase 1 零外部依赖，argparse 是标准库。
后续如果命令增多，可以迁移到 click。

对应文档：
- smartPi/docs/smartdev-agent/agent.md §14（最小 CLI：4 个命令）
- smartPi/docs/smartdev-agent-protocol.md §6（执行前输出）
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from smartdev import __version__
from smartdev.core.reporter import format_execution_header
from smartdev.core.risk import RiskController
from smartdev.models import ProjectContext


def _cmd_scan(args: argparse.Namespace) -> int:
    """执行 repo.scan 命令"""
    from smartdev.skills.base import Skill

    project_path = Path(args.project).resolve()

    # 构建上下文
    context = ProjectContext(project_path=project_path)

    # 获取 Skill
    try:
        skill = Skill.create("repo.scan")
    except KeyError as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1

    # 风险检查
    controller = RiskController()
    controller.enforce(skill.risk_level)

    # 前置条件检查
    if not skill.can_run(context):
        print(f"错误: 项目路径不存在或不是目录: {project_path}", file=sys.stderr)
        return 1

    # 执行前输出
    print(format_execution_header("repo.scan", skill.risk_level))
    print()

    # 执行
    inputs = {}
    if args.depth is not None:
        inputs["max_depth"] = args.depth

    result = skill.run(context, inputs)

    # 输出结果
    print(result.summary)
    print()

    # 输出详细信息
    if args.verbose:
        import json
        print("详细数据:")
        print(json.dumps(result.data, indent=2, ensure_ascii=False))

    # 输出风险
    if result.risks:
        print("\n发现的问题:")
        for risk in result.risks:
            print(f"  - {risk}")

    # 输出下一步
    if result.next_steps:
        print("\n下一步建议:")
        for step in result.next_steps:
            print(f"  - {step}")

    return 0


def _cmd_plan(args: argparse.Namespace) -> int:
    """执行 task.plan 命令"""
    from smartdev.skills.base import Skill

    project_path = Path(args.project).resolve()

    # 构建上下文
    context = ProjectContext(
        project_path=project_path,
        task_description=args.task,
    )

    # 获取 Skill
    try:
        skill = Skill.create("task.plan")
    except KeyError as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1

    # 风险检查
    controller = RiskController()
    controller.enforce(skill.risk_level)

    # 前置条件检查
    if not skill.can_run(context):
        print("错误: 项目路径不存在或任务描述为空", file=sys.stderr)
        return 1

    # 执行前输出
    print(format_execution_header("task.plan", skill.risk_level))
    print()

    # 执行
    result = skill.run(context)

    # 输出三档方案
    for tier_name, tier_key in [("保守方案", "conservative"), ("推荐方案", "recommended"), ("深度方案", "deep")]:
        proposal = result.data[tier_key]
        print(f"## {tier_name}")
        print(f"  描述: {proposal['description']}")
        print(f"  范围: {', '.join(proposal['scope'])}")
        print(f"  风险: {proposal['risk']}")
        print(f"  工作量: {proposal['effort']}")
        print(f"  任务数: {len(proposal['tasks'])}")
        print()

    # 输出推荐方案的任务拆解
    breakdown = result.data.get("recommended_task_breakdown", [])
    if breakdown:
        print("## 推荐方案任务拆解")
        for step in breakdown:
            print(f"  {step['step']}. {step['name']} [{step['risk']}]")
        print()

    # 输出下一步
    if result.next_steps:
        print("下一步建议:")
        for step in result.next_steps:
            print(f"  - {step}")

    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    """列出所有可用 Skill"""
    from smartdev.skills.base import Skill

    # 触发所有 Skill 注册
    import smartdev.skills  # noqa: F401

    registry = Skill.get_registry()

    print(f"SmartDev Agent v{__version__}")
    print(f"可用 Skill: {len(registry)} 个")
    print()

    for name in sorted(registry.keys()):
        skill_cls = registry[name]
        skill = skill_cls()
        desc = skill.describe()
        print(f"  {desc['name']:<20} [{desc['risk_level']}] {desc['description']}")

    return 0


def _cmd_diagnose(args: argparse.Namespace) -> int:
    """诊断项目：加载适配器 + 运行 repo.scan"""
    from smartdev.core.adapter import find_adapter
    from smartdev.skills.base import Skill

    project_path = Path(args.project).resolve()

    # 检测适配器
    adapter = find_adapter(project_path)
    if adapter:
        print(f"检测到适配器: {adapter.name} ({adapter.project_type})")
        print(f"技术栈: {', '.join(adapter.tech_stack)}")
        print(f"可编辑区域: {len(adapter.editable_regions)} 个")
        print(f"禁止区域: {len(adapter.forbidden_regions)} 个")
        if adapter.known_issues:
            print(f"已知问题: {len(adapter.known_issues)} 个")
        print()
    else:
        print("未检测到项目适配器，使用通用模式")
        print()

    # 运行 repo.scan
    context = ProjectContext(project_path=project_path)
    try:
        skill = Skill.create("repo.scan")
    except KeyError as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1

    if not skill.can_run(context):
        print(f"错误: 项目路径不存在或不是目录: {project_path}", file=sys.stderr)
        return 1

    result = skill.run(context)
    print(result.summary)

    if result.risks:
        print("\n发现的问题:")
        for risk in result.risks:
            print(f"  - {risk}")

    if adapter and adapter.current_priorities:
        print("\n适配器优先任务:")
        for priority in adapter.current_priorities:
            print(f"  - {priority}")

    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    """执行完整工作流"""
    from smartdev.core.workflow import WorkflowEngine

    project_path = Path(args.project).resolve()
    task = args.task

    engine = WorkflowEngine()
    result = engine.run(project_path, task=task)

    print(result.to_markdown())

    return 0 if result.success else 1


def _cmd_index(args: argparse.Namespace) -> int:
    """建立项目索引"""
    from smartdev.context.project_index import ProjectIndex

    project_path = Path(args.project).resolve()

    if not project_path.exists() or not project_path.is_dir():
        print(f"错误: 项目路径不存在或不是目录: {project_path}", file=sys.stderr)
        return 1

    print(f"正在建立索引: {project_path}")
    print()

    index = ProjectIndex(project_path)

    # 一步完成：scan + extract + write
    result = index.index(force=args.force)
    print(f"文件扫描完成：{result['files']} 个文件")
    print(f"  更新: {result['files_updated']}, 跳过: {result['files_skipped']}")
    print(f"Artifact 提取完成：{result['artifacts']} 个")
    print(f"Import 关系：{result['relations']} 个")
    if result["errors"]:
        print(f"  错误: {result['errors']} 个")
    print()

    # 统计
    stats = index.stats()
    print("索引统计：")
    print(f"  文件: {stats['files']}")
    print(f"  工件: {stats['artifacts']}")
    print(f"  关系: {stats['relations']}")
    if stats["languages"]:
        langs = ", ".join(f"{l['language']}({l['count']})" for l in stats["languages"])
        print(f"  语言: {langs}")
    if stats["artifact_types"]:
        types = ", ".join(f"{t['type']}({t['count']})" for t in stats["artifact_types"])
        print(f"  工件类型: {types}")
    print()
    print(f"索引文件: {index.db_path}")

    index.close()
    return 0


def _cmd_search(args: argparse.Namespace) -> int:
    """搜索文件和工件"""
    from smartdev.context.project_index import ProjectIndex

    project_path = Path(args.project).resolve()

    if not project_path.exists() or not project_path.is_dir():
        print(f"错误: 项目路径不存在或不是目录: {project_path}", file=sys.stderr)
        return 1

    db_path = project_path / ".smartdev" / "index.sqlite"
    if not db_path.exists():
        print("错误: 索引不存在，请先运行 smartdev index", file=sys.stderr)
        return 1

    index = ProjectIndex(project_path)
    results = index.search(args.query, limit=args.limit)
    index.close()

    # 输出结果
    print(f"搜索: '{args.query}'")
    print()

    if results["files"]:
        print(f"匹配文件 ({results['total_files']}):")
        for f in results["files"]:
            print(f"  {f['path']}  [{f['language']}, {f['kind']}]")
        print()

    if results["artifacts"]:
        print(f"匹配工件 ({results['total_artifacts']}):")
        for a in results["artifacts"]:
            print(f"  [{a['type']}] {a['name']}  → {a['file_path']}")
        print()

    if not results["files"] and not results["artifacts"]:
        print("未找到匹配结果")

    return 0


def _cmd_impact(args: argparse.Namespace) -> int:
    """分析变更影响"""
    from smartdev.context.impact_analyzer import ImpactAnalyzer
    from smartdev.context.project_index import ProjectIndex

    project_path = Path(args.project).resolve()

    if not project_path.exists() or not project_path.is_dir():
        print(f"错误: 项目路径不存在或不是目录: {project_path}", file=sys.stderr)
        return 1

    db_path = project_path / ".smartdev" / "index.sqlite"
    if not db_path.exists():
        print("错误: 索引不存在，请先运行 smartdev index", file=sys.stderr)
        return 1

    index = ProjectIndex(project_path)
    analyzer = ImpactAnalyzer(index.store)
    result = analyzer.analyze(args.target, max_depth=args.depth)
    index.close()

    print(result.summary)

    return 0


def main() -> None:
    """CLI 主入口"""
    parser = argparse.ArgumentParser(
        prog="smartdev",
        description="SmartDev Agent — 项目开发与仓库改进 AI Agent",
    )
    parser.add_argument("--version", action="version", version=f"smartdev {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # scan 命令
    scan_parser = subparsers.add_parser("scan", help="扫描项目目录，识别技术栈、入口文件和文档状态")
    scan_parser.add_argument("--project", "-p", required=True, help="项目根目录路径")
    scan_parser.add_argument("--depth", "-d", type=int, default=None, help="目录树最大深度（默认 2）")
    scan_parser.add_argument("--verbose", "-v", action="store_true", help="输出详细数据")
    scan_parser.set_defaults(func=_cmd_scan)

    # plan 命令
    plan_parser = subparsers.add_parser("plan", help="将需求拆解为三档方案")
    plan_parser.add_argument("--project", "-p", required=True, help="项目根目录路径")
    plan_parser.add_argument("--task", "-t", required=True, help="任务描述")
    plan_parser.set_defaults(func=_cmd_plan)

    # list 命令
    list_parser = subparsers.add_parser("list", help="列出所有可用 Skill")
    list_parser.set_defaults(func=_cmd_list)

    # diagnose 命令
    diagnose_parser = subparsers.add_parser("diagnose", help="诊断项目：加载适配器 + 扫描项目")
    diagnose_parser.add_argument("--project", "-p", required=True, help="项目根目录路径")
    diagnose_parser.set_defaults(func=_cmd_diagnose)

    # run 命令
    run_parser = subparsers.add_parser("run", help="执行完整工作流（扫描→分析→规划→清单）")
    run_parser.add_argument("--project", "-p", required=True, help="项目根目录路径")
    run_parser.add_argument("--task", "-t", default="", help="任务描述（可选）")
    run_parser.set_defaults(func=_cmd_run)

    # index 命令（Phase 6-MVP 新增）
    index_parser = subparsers.add_parser("index", help="建立项目代码索引（文件 + 工件）")
    index_parser.add_argument("--project", "-p", required=True, help="项目根目录路径")
    index_parser.add_argument("--force", "-f", action="store_true", help="强制重新索引所有文件")
    index_parser.set_defaults(func=_cmd_index)

    # search 命令（Phase 6-MVP 新增）
    search_parser = subparsers.add_parser("search", help="搜索文件和工件")
    search_parser.add_argument("--project", "-p", required=True, help="项目根目录路径")
    search_parser.add_argument("query", help="搜索词")
    search_parser.add_argument("--limit", "-l", type=int, default=20, help="最大返回数（默认 20）")
    search_parser.set_defaults(func=_cmd_search)

    # impact 命令（Phase 6-MVP 新增）
    impact_parser = subparsers.add_parser("impact", help="分析变更影响范围")
    impact_parser.add_argument("--project", "-p", required=True, help="项目根目录路径")
    impact_parser.add_argument("target", help="分析目标（文件路径或工件名称）")
    impact_parser.add_argument("--depth", "-d", type=int, default=3, help="最大分析深度（默认 3）")
    impact_parser.set_defaults(func=_cmd_impact)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    sys.exit(args.func(args))
