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
    result = engine.run(project_path, task=task, target=getattr(args, "target", "") or "")

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


def _cmd_git_commit(args: argparse.Namespace) -> int:
    """git commit — 默认 dry-run，--apply 才真正写 Git 历史（R2）

    设计约束（phase-11-design.md §4.4）：
    - 默认 dry-run：只输出"将要执行什么"，不创建 commit
    - --apply：调用 GitService.commit()，真正写 Git 历史
    - protected branch 拒绝（除非 policy 明确允许）
    - 不做 push / merge / rebase / reset
    - 执行后写审计到 .smartdev/index.sqlite runs 表
    """
    import json as _json
    import time as _time

    from smartdev.core.git import GitNotAvailable, GitService, load_git_policy

    project_path = Path(args.project).resolve()
    if not project_path.exists():
        print(f"错误: 项目路径不存在: {project_path}", file=sys.stderr)
        return 1

    message: str = args.message
    files: list[str] = args.files or []
    apply: bool = args.apply

    svc = GitService(project_path)
    if not svc.is_available():
        print("错误: git 不可用或当前目录不是 git 仓库", file=sys.stderr)
        return 1

    policy = load_git_policy(project_path)

    # ── 当前状态 ──────────────────────────────────────────
    try:
        branch = svc.current_branch()
        status = svc.status(recent_commit_count=0)
    except GitNotAvailable as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1

    # ── policy 检查 ───────────────────────────────────────
    policy_issues: list[str] = []

    if branch in policy.protected_branches:
        policy_issues.append(
            f"✗ 拒绝：当前分支 '{branch}' 是 protected branch "
            f"（policy.branch.protected = {policy.protected_branches}）"
        )

    staged_count = len(status.staged)
    total_files = len(files) if files else staged_count
    if total_files > policy.max_files_per_commit:
        policy_issues.append(
            f"⚠ 警告：变更文件数 {total_files} 超过 "
            f"policy.max_files_per_commit={policy.max_files_per_commit}"
        )

    # ── dry-run 输出 ──────────────────────────────────────
    print(f"Will commit:")
    print(f"  branch:  {branch}")
    if files:
        print(f"  files:   {files}")
    else:
        staged_paths = [f["path"] for f in
                        [{"path": f.path} for f in status.staged]]
        print(f"  files:   {staged_paths if staged_paths else '(已 stage 的文件)'}")
    print(f"  message: {message}")
    print(f"  policy checks:")

    has_blocker = any("✗" in i for i in policy_issues)
    if not policy_issues:
        print(f"    ✓ branch not protected")
        print(f"    ✓ files ({total_files}) <= max_files_per_commit ({policy.max_files_per_commit})")
    else:
        for issue in policy_issues:
            print(f"    {issue}")

    print()

    # ── blocker 时拒绝 ────────────────────────────────────
    if has_blocker:
        print("Commit 被拒绝（存在 policy blocker）。修复上述问题后重试。")
        return 1

    if not apply:
        print("No commit created. Add --apply to execute.")
        return 0

    # ── 执行 commit ───────────────────────────────────────
    print("执行 git commit...")
    try:
        out = svc.commit(message=message, files=files if files else None)
        print(out)
    except GitNotAvailable as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"错误: git commit 失败: {e}", file=sys.stderr)
        return 1

    # ── 审计 ──────────────────────────────────────────────
    _write_git_audit(project_path, "git.commit", {
        "branch": branch,
        "message": message,
        "files": files,
        "policy_warnings": [i for i in policy_issues if "⚠" in i],
    })

    print("\n✅ Commit 创建成功。")
    return 0


def _cmd_git_tag(args: argparse.Namespace) -> int:
    """git tag — 默认 dry-run，--apply 才真正打 tag（R2）

    设计约束（phase-11-design.md §4.4）：
    - 默认 dry-run：只输出"将要执行什么"，不创建 tag
    - --apply：调用 GitService.tag()，真正写 Git 历史
    - tag 名称格式建议 vX.Y.Z（不强制）
    - 不做 push
    """
    from smartdev.core.git import GitNotAvailable, GitService, load_git_policy

    project_path = Path(args.project).resolve()
    if not project_path.exists():
        print(f"错误: 项目路径不存在: {project_path}", file=sys.stderr)
        return 1

    version: str = args.version
    tag_message: str | None = args.message or None
    apply: bool = args.apply

    svc = GitService(project_path)
    if not svc.is_available():
        print("错误: git 不可用或当前目录不是 git 仓库", file=sys.stderr)
        return 1

    try:
        branch = svc.current_branch()
        existing_tags = svc.tags()
    except GitNotAvailable as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1

    # ── 重复 tag 检查 ─────────────────────────────────────
    policy_issues: list[str] = []
    if version in existing_tags:
        policy_issues.append(f"✗ 拒绝：tag '{version}' 已存在")

    tag_type = "annotated" if tag_message else "lightweight"

    # ── dry-run 输出 ──────────────────────────────────────
    print(f"Will tag:")
    print(f"  version: {version}")
    print(f"  type:    {tag_type}")
    print(f"  branch:  {branch}")
    if tag_message:
        print(f"  message: {tag_message}")
    print(f"  policy checks:")

    has_blocker = any("✗" in i for i in policy_issues)
    if not policy_issues:
        print(f"    ✓ tag '{version}' does not exist")
    else:
        for issue in policy_issues:
            print(f"    {issue}")

    print()

    if has_blocker:
        print("Tag 被拒绝（存在 policy blocker）。修复上述问题后重试。")
        return 1

    if not apply:
        print("No tag created. Add --apply to execute.")
        return 0

    # ── 执行 tag ──────────────────────────────────────────
    print("执行 git tag...")
    try:
        svc.tag(name=version, message=tag_message)
        print(f"tag '{version}' 创建成功。")
    except GitNotAvailable as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"错误: git tag 失败: {e}", file=sys.stderr)
        return 1

    # ── 审计 ──────────────────────────────────────────────
    _write_git_audit(project_path, "git.tag", {
        "version": version,
        "tag_type": tag_type,
        "branch": branch,
        "message": tag_message,
    })

    print(f"\n✅ Tag '{version}' 创建成功。")
    return 0


def _write_git_audit(project_path: Path, task: str, payload: dict) -> None:
    """写 git 执行审计到 .smartdev/index.sqlite runs 表（若索引存在）。

    复用 code.apply 的审计模式，失败时静默处理。
    """
    import json as _json
    import sqlite3
    import time as _time

    db_path = project_path / ".smartdev" / "index.sqlite"
    if not db_path.exists():
        return
    try:
        run_id = f"{task}-{int(_time.time())}"
        summary = _json.dumps(payload, ensure_ascii=False)
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT OR REPLACE INTO runs (id, task, created_at, summary_json) VALUES (?, ?, ?, ?)",
            (run_id, task,
             _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
             summary),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # 审计失败不阻断主流程


def _cmd_snapshot(args: argparse.Namespace) -> int:
    """snapshot — 导出能力快照（skill / cli / mcp）（Phase 11C Step 2）

    子命令：
      skills  —— 从 Skill.get_registry() + skill.yaml 导出 JSON
      cli     —— 从 argparse 结构内省导出 JSON
      mcp     —— 从 mcp/server.py _TOOLS 列表导出 JSON

    设计约束（phase-11c-design.md §4.3 §4.4）：
    - 纯只读，R0，不修改任何文件
    - mcp 包未安装时 mcp 快照返回 available=False（不崩溃）
    - --save 把快照写入 .smartdev/runs/<timestamp>/，不影响源码
    """
    import time as _time

    from smartdev.core.snapshot import (
        build_cli_snapshot,
        build_mcp_snapshot,
        build_skill_snapshot,
        save_snapshot,
    )

    project_path = Path(args.project).resolve()
    if not project_path.exists():
        print(f"错误: 项目路径不存在: {project_path}", file=sys.stderr)
        return 1

    subcmd = getattr(args, "snapshot_command", None)
    do_save: bool = getattr(args, "save", False)
    runs_dir = project_path / ".smartdev" / "runs"
    run_id = f"snapshot-{_time.strftime('%Y%m%d-%H%M%S')}"

    if subcmd == "skills":
        snap = build_skill_snapshot(project_path)
        if do_save:
            out = save_snapshot(snap.to_dict(), "skill", runs_dir, run_id)
            print(f"✅ Skill Snapshot 已保存: {out}")
            print()
        print(snap.to_json())
        return 0

    if subcmd == "cli":
        snap = build_cli_snapshot()
        if do_save:
            out = save_snapshot(snap.to_dict(), "cli", runs_dir, run_id)
            print(f"✅ CLI Snapshot 已保存: {out}")
            print()
        print(snap.to_json())
        return 0

    if subcmd == "mcp":
        snap = build_mcp_snapshot()
        if do_save:
            out = save_snapshot(snap.to_dict(), "mcp", runs_dir, run_id)
            print(f"✅ MCP Snapshot 已保存: {out}")
            print()
        print(snap.to_json())
        return 0

    print(f"错误: 未知子命令 '{subcmd}'", file=sys.stderr)
    return 1


def _cmd_manifest(args: argparse.Namespace) -> int:
    """manifest — 生成 / 查看 Change Manifest（Phase 11C Step 1）

    子命令：
      diff   —— 从当前工作区 git diff 生成 ChangeManifest（working_tree_diff 来源）
      last   —— 展示最近一次已保存的 ChangeManifest
      show   —— 按 run_id 查看指定 ChangeManifest

    设计约束（phase-11c-design.md §4.1）：
    - diff / show 只写 .smartdev/runs/<run_id>/change-manifest.json，不动源码
    - last / show 只读，零副作用
    - git 不可用时 diff 返回空 manifest（不崩溃）
    """
    import json as _json

    from smartdev.core.manifest import (
        load_latest_manifest,
        load_manifest,
        manifest_from_git_diff,
        save_manifest,
    )

    project_path = Path(args.project).resolve()
    if not project_path.exists():
        print(f"错误: 项目路径不存在: {project_path}", file=sys.stderr)
        return 1

    runs_dir = project_path / ".smartdev" / "runs"
    subcmd = getattr(args, "manifest_command", None)

    # ── diff 子命令 ───────────────────────────────────────
    if subcmd == "diff" or subcmd is None:
        run_id = getattr(args, "run_id", None) or None
        m = manifest_from_git_diff(project_path, run_id=run_id)

        if args.save:
            out_path = save_manifest(m, runs_dir)
            print(f"✅ Change Manifest 已保存: {out_path}")
            print()

        print(m.to_json())
        return 0

    # ── last 子命令 ───────────────────────────────────────
    if subcmd == "last":
        m = load_latest_manifest(runs_dir)
        if m is None:
            print("未找到任何 Change Manifest（.smartdev/runs/ 为空）", file=sys.stderr)
            return 1
        print(m.to_json())
        return 0

    # ── show 子命令 ───────────────────────────────────────
    if subcmd == "show":
        run_id = args.run_id
        m = load_manifest(run_id, runs_dir)
        if m is None:
            print(f"未找到 run_id='{run_id}' 的 Change Manifest", file=sys.stderr)
            return 1
        print(m.to_json())
        return 0

    print(f"错误: 未知子命令 '{subcmd}'", file=sys.stderr)
    return 1


def _cmd_mcp(args: argparse.Namespace) -> int:
    """启动 MCP Server（供外部 Agent 通过 stdio 调用）"""
    # 先检查 mcp 包，未安装时给出提示
    try:
        import mcp  # noqa: F401
    except ImportError:
        print(
            "错误: MCP Server 需要安装 mcp 包。\n"
            "请运行: pip install smartdev-agent[mcp]\n"
            "或直接: pip install mcp",
            file=sys.stderr,
        )
        return 1

    project_path = Path(args.project).resolve()

    if not project_path.exists() or not project_path.is_dir():
        print(f"错误: 项目路径不存在或不是目录: {project_path}", file=sys.stderr)
        return 1

    from smartdev.mcp.server import run_mcp_server
    run_mcp_server(project_path)
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
    run_parser.add_argument("--target", default="", help="变更目标（文件/模块/符号），驱动影响分析（需先建索引）")
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

    # mcp 命令（Phase 10 新增）
    mcp_parser = subparsers.add_parser(
        "mcp",
        help="启动 MCP Server（供外部 Agent 通过 stdio 调用，需 pip install mcp）",
    )
    mcp_parser.add_argument("--project", "-p", required=True, help="项目根目录路径")
    mcp_parser.set_defaults(func=_cmd_mcp)

    # git 命令组（Phase 11A 新增）
    git_parser = subparsers.add_parser(
        "git",
        help="Git 治理命令（commit/tag，默认 dry-run，--apply 才执行）",
    )
    git_subparsers = git_parser.add_subparsers(dest="git_command", help="git 子命令")

    # git commit
    git_commit_parser = git_subparsers.add_parser(
        "commit",
        help="创建 git commit（默认 dry-run；--apply 才写 Git 历史，R2）",
    )
    git_commit_parser.add_argument("--project", "-p", default=".", help="项目根目录路径（默认当前目录）")
    git_commit_parser.add_argument("--message", "-m", required=True, help="commit message")
    git_commit_parser.add_argument("--files", "-f", nargs="*", help="要 stage 的文件路径（不指定则使用已 staged 文件）")
    git_commit_parser.add_argument("--apply", action="store_true", help="真正执行 commit（不加此参数为 dry-run）")
    git_commit_parser.set_defaults(func=_cmd_git_commit)

    # git tag
    git_tag_parser = git_subparsers.add_parser(
        "tag",
        help="创建 git tag（默认 dry-run；--apply 才写 Git 历史，R2）",
    )
    git_tag_parser.add_argument("--project", "-p", default=".", help="项目根目录路径（默认当前目录）")
    git_tag_parser.add_argument("--version", "-v", required=True, help="tag 名称（如 v0.4.0）")
    git_tag_parser.add_argument("--message", "-m", default=None, help="附注 tag 消息（不指定则创建轻量 tag）")
    git_tag_parser.add_argument("--apply", action="store_true", help="真正执行 tag（不加此参数为 dry-run）")
    git_tag_parser.set_defaults(func=_cmd_git_tag)

    git_parser.set_defaults(func=lambda a: (git_parser.print_help(), sys.exit(1)))

    # manifest 命令组（Phase 11C Step 1 新增）
    manifest_parser = subparsers.add_parser(
        "manifest",
        help="生成 / 查看 Change Manifest（文档一致性检查的事实基础）",
    )
    manifest_subparsers = manifest_parser.add_subparsers(
        dest="manifest_command", help="manifest 子命令"
    )

    # manifest diff — 从工作区 diff 生成
    manifest_diff_parser = manifest_subparsers.add_parser(
        "diff",
        help="从当前工作区 git diff 生成 ChangeManifest（working_tree_diff 来源）",
    )
    manifest_diff_parser.add_argument(
        "--project", "-p", default=".", help="项目根目录路径（默认当前目录）"
    )
    manifest_diff_parser.add_argument(
        "--run-id", dest="run_id", default=None,
        help="指定 run_id（默认自动生成）",
    )
    manifest_diff_parser.add_argument(
        "--save", action="store_true",
        help="把生成的 manifest 保存到 .smartdev/runs/<run_id>/",
    )
    manifest_diff_parser.set_defaults(func=_cmd_manifest, manifest_command="diff")

    # manifest last — 查看最近一次 manifest
    manifest_last_parser = manifest_subparsers.add_parser(
        "last",
        help="展示最近一次已保存的 ChangeManifest",
    )
    manifest_last_parser.add_argument(
        "--project", "-p", default=".", help="项目根目录路径（默认当前目录）"
    )
    manifest_last_parser.set_defaults(func=_cmd_manifest, manifest_command="last")

    # manifest show — 按 run_id 查看
    manifest_show_parser = manifest_subparsers.add_parser(
        "show",
        help="按 run_id 查看指定 ChangeManifest",
    )
    manifest_show_parser.add_argument(
        "--project", "-p", default=".", help="项目根目录路径（默认当前目录）"
    )
    manifest_show_parser.add_argument("run_id", help="要查看的 run_id")
    manifest_show_parser.set_defaults(func=_cmd_manifest, manifest_command="show")

    manifest_parser.set_defaults(
        func=lambda a: (manifest_parser.print_help(), sys.exit(1))
    )

    # snapshot 命令组（Phase 11C Step 2 新增）
    snapshot_parser = subparsers.add_parser(
        "snapshot",
        help="导出能力快照（skill / cli / mcp），供 Doc Steward 使用",
    )
    snapshot_subparsers = snapshot_parser.add_subparsers(
        dest="snapshot_command", help="snapshot 子命令"
    )

    # snapshot skills
    snap_skills_parser = snapshot_subparsers.add_parser(
        "skills",
        help="导出 Skill 注册表快照（从 Skill.get_registry() + skill.yaml 内省）",
    )
    snap_skills_parser.add_argument(
        "--project", "-p", default=".", help="项目根目录路径（默认当前目录）"
    )
    snap_skills_parser.add_argument(
        "--save", action="store_true",
        help="把快照保存到 .smartdev/runs/<timestamp>/skill-snapshot.json",
    )
    snap_skills_parser.set_defaults(func=_cmd_snapshot, snapshot_command="skills")

    # snapshot cli
    snap_cli_parser = snapshot_subparsers.add_parser(
        "cli",
        help="导出 CLI 命令快照（从 argparse 结构内省）",
    )
    snap_cli_parser.add_argument(
        "--project", "-p", default=".", help="项目根目录路径（默认当前目录）"
    )
    snap_cli_parser.add_argument(
        "--save", action="store_true",
        help="把快照保存到 .smartdev/runs/<timestamp>/cli-snapshot.json",
    )
    snap_cli_parser.set_defaults(func=_cmd_snapshot, snapshot_command="cli")

    # snapshot mcp
    snap_mcp_parser = snapshot_subparsers.add_parser(
        "mcp",
        help="导出 MCP 工具快照（从 mcp/server.py 内省，mcp 未安装时返回 available=false）",
    )
    snap_mcp_parser.add_argument(
        "--project", "-p", default=".", help="项目根目录路径（默认当前目录）"
    )
    snap_mcp_parser.add_argument(
        "--save", action="store_true",
        help="把快照保存到 .smartdev/runs/<timestamp>/mcp-snapshot.json",
    )
    snap_mcp_parser.set_defaults(func=_cmd_snapshot, snapshot_command="mcp")

    snapshot_parser.set_defaults(
        func=lambda a: (snapshot_parser.print_help(), sys.exit(1))
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    sys.exit(args.func(args))
