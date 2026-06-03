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

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    sys.exit(args.func(args))
