"""
Capability Snapshot — 三种能力快照导出器

功能：
─────
Phase 11C Step 2 的核心交付物。
把"项目当前具备什么能力"导出为确定性 JSON，
作为 Doc Steward 工具链的事实基础（对应 phase-11c-design.md §4.3 §4.4）。

三种快照：
─────────
1. skill_snapshot  — 从 Skill.get_registry() + skill.yaml 导出
2. cli_snapshot    — 从 cli.py argparse 结构内省导出
3. mcp_snapshot    — 从 mcp/server.py _TOOLS 列表导出

设计约束：
─────────
- 零外部依赖（标准库 + 已有内部模块）
- 纯只读，不修改任何文件（R0）
- 不依赖 MCP 包是否安装（mcp_snapshot 在 mcp 未安装时返回 empty）
- cli_snapshot 用 argparse 内省，不 import main()，避免副作用

对应文档：
- docs/phase-11c-design.md §4.3（Skill Registry Snapshot）
- docs/phase-11c-design.md §4.4（CLI Capability Snapshot）
- docs/phase-11c-design.md §7 Step 2
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ── 数据模型 ──────────────────────────────────────────────


@dataclass
class SkillEntry:
    """单个 Skill 的快照条目。

    Attributes:
        name:        Skill 唯一标识（如 "git.status"）
        risk:        风险等级（"R0" / "R1" / "R2" / "R3"）
        task_type:   任务类型（"diagnose" / "plan" 等）
        description: Skill 功能描述
        inputs:      从 skill.yaml 读取的输入参数列表（可选字段 + 必需字段）
        outputs:     从 skill.yaml 读取的输出字段列表
    """
    name: str
    risk: str
    task_type: str
    description: str
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "risk": self.risk,
            "task_type": self.task_type,
            "description": self.description,
            "inputs": self.inputs,
            "outputs": self.outputs,
        }


@dataclass
class SkillSnapshot:
    """Skill 注册表快照。

    Attributes:
        generated_at: ISO 8601 时间戳
        skill_count:  已注册 Skill 数量
        skills:       Skill 条目列表（按 name 排序）
    """
    generated_at: str
    skill_count: int
    skills: list[SkillEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at,
            "skill_count": self.skill_count,
            "skills": [s.to_dict() for s in self.skills],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict) -> "SkillSnapshot":
        skills = [
            SkillEntry(
                name=s.get("name", ""),
                risk=s.get("risk", "R0"),
                task_type=s.get("task_type", "diagnose"),
                description=s.get("description", ""),
                inputs=list(s.get("inputs", [])),
                outputs=list(s.get("outputs", [])),
            )
            for s in data.get("skills", [])
        ]
        return cls(
            generated_at=data.get("generated_at", ""),
            skill_count=data.get("skill_count", len(skills)),
            skills=skills,
        )


@dataclass
class CliCommandEntry:
    """单个 CLI 命令的快照条目。

    Attributes:
        command:     完整命令路径（如 "smartdev git commit"）
        description: 命令帮助文本
        args:        参数名称列表（如 ["--message", "--apply"]）
    """
    command: str
    description: str
    args: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "command": self.command,
            "description": self.description,
            "args": self.args,
        }


@dataclass
class CliSnapshot:
    """CLI 能力快照。

    Attributes:
        generated_at:   ISO 8601 时间戳
        command_count:  命令总数
        commands:       命令条目列表（按 command 排序）
    """
    generated_at: str
    command_count: int
    commands: list[CliCommandEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at,
            "command_count": self.command_count,
            "commands": [c.to_dict() for c in self.commands],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict) -> "CliSnapshot":
        commands = [
            CliCommandEntry(
                command=c.get("command", ""),
                description=c.get("description", ""),
                args=list(c.get("args", [])),
            )
            for c in data.get("commands", [])
        ]
        return cls(
            generated_at=data.get("generated_at", ""),
            command_count=data.get("command_count", len(commands)),
            commands=commands,
        )


@dataclass
class McpToolEntry:
    """单个 MCP 工具的快照条目。

    Attributes:
        name:        工具名称（如 "smartdev_git_status"）
        description: 工具描述
        required:    必需参数列表
        optional:    可选参数列表
    """
    name: str
    description: str
    required: list[str] = field(default_factory=list)
    optional: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "required": self.required,
            "optional": self.optional,
        }


@dataclass
class McpSnapshot:
    """MCP 工具快照。

    Attributes:
        generated_at: ISO 8601 时间戳
        tool_count:   工具总数
        available:    mcp 包是否已安装
        tools:        工具条目列表（按 name 排序）
    """
    generated_at: str
    tool_count: int
    available: bool
    tools: list[McpToolEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at,
            "tool_count": self.tool_count,
            "available": self.available,
            "tools": [t.to_dict() for t in self.tools],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict) -> "McpSnapshot":
        tools = [
            McpToolEntry(
                name=t.get("name", ""),
                description=t.get("description", ""),
                required=list(t.get("required", [])),
                optional=list(t.get("optional", [])),
            )
            for t in data.get("tools", [])
        ]
        return cls(
            generated_at=data.get("generated_at", ""),
            tool_count=data.get("tool_count", len(tools)),
            available=bool(data.get("available", True)),
            tools=tools,
        )


# ── 内部工具 ──────────────────────────────────────────────


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _load_skill_yaml(skill_dir: Path) -> dict:
    """读取 skill.yaml，解析失败时返回空 dict。"""
    yaml_path = skill_dir / "skill.yaml"
    if not yaml_path.exists():
        return {}
    try:
        import re
        text = yaml_path.read_text(encoding="utf-8")
        # 轻量 YAML 解析：只提取 inputs / outputs 两个列表字段
        # 不引入 PyYAML（零依赖原则），用正则 + 行解析
        return _parse_skill_yaml_lite(text)
    except (OSError, UnicodeDecodeError):
        return {}


def _parse_skill_yaml_lite(text: str) -> dict:
    """极简 YAML 解析器，只提取 inputs/outputs 字段。

    支持格式：
        inputs:
          required:
            - project_path
          optional:
            - recent_commit_count
        outputs:
          - branch
          - is_dirty

    不支持锚点、多行字符串等高级特性——skill.yaml 的格式固定，无需通用解析。
    """
    result: dict[str, Any] = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # 顶级 inputs: 块
        if stripped == "inputs:":
            inputs: list[str] = []
            i += 1
            while i < len(lines):
                l = lines[i]
                s = l.strip()
                if not s or s.startswith("#"):
                    i += 1
                    continue
                # 子块 required:/optional:
                if s in ("required:", "optional:"):
                    i += 1
                    while i < len(lines):
                        inner = lines[i]
                        si = inner.strip()
                        if si.startswith("- "):
                            item = si[2:].split("#")[0].strip()
                            if item:
                                inputs.append(item)
                            i += 1
                        elif si and not si.startswith("#") and not si.startswith("- "):
                            break
                        else:
                            i += 1
                    continue
                # 直接列表项
                if s.startswith("- "):
                    item = s[2:].split("#")[0].strip()
                    if item:
                        inputs.append(item)
                    i += 1
                    continue
                # 非缩进行：退出 inputs 块
                if not l.startswith(" ") and not l.startswith("\t"):
                    break
                i += 1
            result["inputs"] = inputs
            continue

        # 顶级 outputs: 块
        if stripped == "outputs:":
            outputs: list[str] = []
            i += 1
            while i < len(lines):
                l = lines[i]
                s = l.strip()
                if not s or s.startswith("#"):
                    i += 1
                    continue
                if s.startswith("- "):
                    item = s[2:].split("#")[0].strip()
                    if item:
                        outputs.append(item)
                    i += 1
                    continue
                if not l.startswith(" ") and not l.startswith("\t"):
                    break
                i += 1
            result["outputs"] = outputs
            continue

        i += 1
    return result


def _extract_argparse_args(parser_or_subparser) -> list[str]:
    """从 argparse parser 提取参数名列表。"""
    args: list[str] = []
    for action in parser_or_subparser._actions:
        # 跳过内置的 -h/--help 和 positional subparsers action
        if action.option_strings:
            # 优先取长选项名
            long_opts = [o for o in action.option_strings if o.startswith("--")]
            if long_opts:
                args.append(long_opts[0])
            else:
                args.append(action.option_strings[0])
        elif action.dest not in ("help", "==SUPPRESS==") and hasattr(action, "choices") and action.choices is None:
            # positional argument（非 subparsers）
            if action.dest != "==SUPPRESS==":
                args.append(action.dest)
    return args


def _parser_has_own_args(sub_parser) -> bool:
    """检查 parser 是否有非 subparser 的有效参数（即自身是一个有效命令）。

    例如 `smartdev run` 有 --project/--task/--target 的同时还有 new 子命令，
    此时 run 自身（workflow 模式）也应作为一个独立命令出现。
    """
    for a in sub_parser._actions:
        if hasattr(a, "_name_parser_map"):
            continue  # 跳过子命令 action
        if a.dest in ("help", "==SUPPRESS=="):
            continue  # 跳过 help action
        # option_strings 非空 → 是一个可选参数
        if a.option_strings:
            return True
        # 没有 option_strings → positional 参数
        # subparsers action 必有 _name_parser_map，上面已过滤
        # 其他 positional（如 run_id）→ 视为有效参数
        if not hasattr(a, "_name_parser_map"):
            return True
    return False


def _walk_subparsers(parser, prefix: str, commands: list[CliCommandEntry]) -> None:
    """递归遍历 argparse subparsers，收集所有叶子命令。

    规则：
    1. 无子命令 → 直接作为叶子命令
    2. 有子命令 + 无自身参数 → 只递归进入子命令（如 git/manifest/snapshot）
    3. 有子命令 + 有自身参数 → 递归进入子命令 + 也输出自身（如 run workflow）
    """
    for action in parser._actions:
        if not hasattr(action, "_name_parser_map"):
            continue
        for sub_name, sub_parser in action._name_parser_map.items():
            full_command = f"{prefix} {sub_name}".strip()
            description = sub_parser.description or sub_parser._defaults.get("func", None)
            # 优先用 description，否则用 help
            desc_str = sub_parser.description or ""
            if not desc_str:
                # 尝试从父 subparsers 的 help 获取
                for a in parser._actions:
                    if hasattr(a, "_name_parser_map") and sub_name in a._name_parser_map:
                        choices_actions = getattr(a, "_choices_actions", [])
                        for ca in choices_actions:
                            if ca.dest == sub_name:
                                desc_str = ca.help or ""
                                break
                        break

            # 检查是否还有子命令
            has_sub = any(hasattr(a, "_name_parser_map") for a in sub_parser._actions)
            if has_sub:
                # 情况 3：父命令有自身参数 → 也作为独立命令输出
                if _parser_has_own_args(sub_parser):
                    args = _extract_argparse_args(sub_parser)
                    commands.append(CliCommandEntry(
                        command=full_command,
                        description=desc_str.strip(),
                        args=args,
                    ))
                # 递归进入子命令
                _walk_subparsers(sub_parser, full_command, commands)
            else:
                args = _extract_argparse_args(sub_parser)
                commands.append(CliCommandEntry(
                    command=full_command,
                    description=desc_str.strip(),
                    args=args,
                ))


# ── 公开 API ──────────────────────────────────────────────


def build_skill_snapshot(project_path: Path | None = None) -> SkillSnapshot:
    """从 Skill.get_registry() 构建 Skill 快照。

    同时尝试从每个 Skill 的 skill.yaml 读取 inputs/outputs 字段。
    skill.yaml 不存在时退回到空列表（不崩溃）。

    参数：
        project_path: 项目根目录（用于定位 skill.yaml 目录），可为 None

    返回：
        SkillSnapshot（未持久化）
    """
    # 触发所有 Skill 注册
    import smartdev.skills  # noqa: F401
    from smartdev.skills.base import Skill

    registry = Skill.get_registry()

    # 尝试找到 skills/ 目录（用于读 skill.yaml）
    skills_base_dir: Path | None = None
    if project_path is not None:
        candidate = project_path / "smartdev" / "skills"
        if candidate.exists():
            skills_base_dir = candidate
    if skills_base_dir is None:
        # 从当前包路径推断
        try:
            import smartdev.skills as _sk_pkg
            skills_base_dir = Path(_sk_pkg.__file__).parent
        except Exception:
            pass

    entries: list[SkillEntry] = []
    for name in sorted(registry.keys()):
        skill_cls = registry[name]
        skill_obj = skill_cls()
        desc = skill_obj.describe()

        # 尝试从 skill.yaml 读取 inputs/outputs
        inputs: list[str] = []
        outputs: list[str] = []
        if skills_base_dir is not None:
            # skill 目录名 = name 中的点替换为下划线
            dir_name = name.replace(".", "_")
            skill_dir = skills_base_dir / dir_name
            yaml_data = _load_skill_yaml(skill_dir)
            inputs = yaml_data.get("inputs", [])
            outputs = yaml_data.get("outputs", [])

        entries.append(SkillEntry(
            name=name,
            risk=desc["risk_level"],
            task_type=desc["task_type"],
            description=desc["description"],
            inputs=inputs,
            outputs=outputs,
        ))

    return SkillSnapshot(
        generated_at=_now_iso(),
        skill_count=len(entries),
        skills=entries,
    )


def build_cli_snapshot() -> CliSnapshot:
    """从 cli.py argparse 结构内省构建 CLI 快照。

    不调用 main()，只构建 parser 并遍历子命令。

    返回：
        CliSnapshot（未持久化）
    """
    # 动态构建 parser（复用 cli.py 里的注册逻辑）
    import argparse as _ap
    import sys as _sys

    # 保存 sys.argv，防止 argparse 读取测试参数
    original_argv = _sys.argv
    _sys.argv = ["smartdev"]

    try:
        from smartdev.cli import main as _  # noqa: F401，触发导入但不执行
        # 直接重建 parser，和 cli.main() 里一致
        parser = _build_cli_parser()
    finally:
        _sys.argv = original_argv

    commands: list[CliCommandEntry] = []
    _walk_subparsers(parser, "smartdev", commands)
    commands.sort(key=lambda c: c.command)

    return CliSnapshot(
        generated_at=_now_iso(),
        command_count=len(commands),
        commands=commands,
    )


def _build_cli_parser():
    """重建 CLI argparse parser（与 cli.main() 保持一致，仅构建不执行）。

    为什么单独提取而不直接 import cli.main？
    main() 包含 sys.exit()，直接调用会终止进程。
    这里只做 parser 构建，供内省使用。
    """
    import argparse

    # 延迟导入避免循环
    from smartdev import __version__

    parser = argparse.ArgumentParser(
        prog="smartdev",
        description="SmartDev Agent — 项目开发与仓库改进 AI Agent",
    )
    parser.add_argument("--version", action="version", version=f"smartdev {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    # scan
    scan_p = subparsers.add_parser("scan", help="扫描项目目录，识别技术栈、入口文件和文档状态",
                                    description="扫描项目目录，识别技术栈、入口文件和文档状态")
    scan_p.add_argument("--project", "-p", required=True)
    scan_p.add_argument("--depth", "-d", type=int)
    scan_p.add_argument("--verbose", "-v", action="store_true")

    # plan
    plan_p = subparsers.add_parser("plan", help="将需求拆解为三档方案",
                                    description="将需求拆解为三档方案")
    plan_p.add_argument("--project", "-p", required=True)
    plan_p.add_argument("--task", "-t", required=True)

    # list
    subparsers.add_parser("list", help="列出所有可用 Skill",
                           description="列出所有可用 Skill")

    # diagnose
    diag_p = subparsers.add_parser("diagnose", help="诊断项目：加载适配器 + 扫描项目",
                                    description="诊断项目：加载适配器 + 扫描项目")
    diag_p.add_argument("--project", "-p", required=True)

    # run（Phase 5 workflow + Phase 11D run new）
    run_p = subparsers.add_parser("run", help="执行工作流 / 管理运行产物",
                                   description="执行工作流 / 管理运行产物")
    run_p.add_argument("--project", "-p", default=".")
    run_p.add_argument("--task", "-t", default="")
    run_p.add_argument("--target", default="")
    run_sub = run_p.add_subparsers(dest="run_command")

    run_new_p = run_sub.add_parser("new", help="创建新的 run artifact 目录",
                                    description="创建新的 run artifact 目录（.smartdev/runs/<id>/）")
    run_new_p.add_argument("run_id")
    run_new_p.add_argument("--project", "-p", default=".")
    run_new_p.add_argument("--task", "-t", default="")
    run_new_p.add_argument("--force", "-f", action="store_true")
    run_new_p.add_argument("--allowed-paths", nargs="*")
    run_new_p.add_argument("--denied-paths", nargs="*")
    run_new_p.add_argument("--max-files", type=int)
    run_new_p.add_argument("--protected-paths", nargs="*")

    # index
    idx_p = subparsers.add_parser("index", help="建立项目代码索引",
                                   description="建立项目代码索引（文件 + 工件）")
    idx_p.add_argument("--project", "-p", required=True)
    idx_p.add_argument("--force", "-f", action="store_true")

    # search
    srch_p = subparsers.add_parser("search", help="搜索文件和工件",
                                    description="搜索文件和工件")
    srch_p.add_argument("--project", "-p", required=True)
    srch_p.add_argument("query")
    srch_p.add_argument("--limit", "-l", type=int, default=20)

    # impact
    imp_p = subparsers.add_parser("impact", help="分析变更影响范围",
                                   description="分析变更影响范围")
    imp_p.add_argument("--project", "-p", required=True)
    imp_p.add_argument("target")
    imp_p.add_argument("--depth", "-d", type=int, default=3)

    # mcp
    mcp_p = subparsers.add_parser("mcp", help="启动 MCP Server",
                                   description="启动 MCP Server（供外部 Agent 通过 stdio 调用）")
    mcp_p.add_argument("--project", "-p", required=True)

    # git
    git_p = subparsers.add_parser("git", help="Git 治理命令",
                                   description="Git 治理命令（commit/tag，默认 dry-run）")
    git_sub = git_p.add_subparsers(dest="git_command")

    gc_p = git_sub.add_parser("commit", help="创建 git commit（默认 dry-run；--apply 才写 Git 历史）",
                               description="创建 git commit（默认 dry-run；--apply 才写 Git 历史，R2）")
    gc_p.add_argument("--project", "-p", default=".")
    gc_p.add_argument("--message", "-m", required=True)
    gc_p.add_argument("--files", "-f", nargs="*")
    gc_p.add_argument("--apply", action="store_true")

    gt_p = git_sub.add_parser("tag", help="创建 git tag（默认 dry-run；--apply 才写 Git 历史）",
                               description="创建 git tag（默认 dry-run；--apply 才写 Git 历史，R2）")
    gt_p.add_argument("--project", "-p", default=".")
    gt_p.add_argument("--version", "-v", required=True)
    gt_p.add_argument("--message", "-m", default=None)
    gt_p.add_argument("--apply", action="store_true")

    # manifest（Phase 11C Step 1）
    mf_p = subparsers.add_parser("manifest", help="生成 / 查看 Change Manifest",
                                  description="生成 / 查看 Change Manifest（文档一致性检查的事实基础）")
    mf_sub = mf_p.add_subparsers(dest="manifest_command")

    mfd_p = mf_sub.add_parser("diff", help="从当前工作区 git diff 生成 ChangeManifest",
                               description="从当前工作区 git diff 生成 ChangeManifest（working_tree_diff 来源）")
    mfd_p.add_argument("--project", "-p", default=".")
    mfd_p.add_argument("--run-id", dest="run_id", default=None)
    mfd_p.add_argument("--save", action="store_true")

    mfl_p = mf_sub.add_parser("last", help="展示最近一次已保存的 ChangeManifest",
                               description="展示最近一次已保存的 ChangeManifest")
    mfl_p.add_argument("--project", "-p", default=".")

    mfs_p = mf_sub.add_parser("show", help="按 run_id 查看指定 ChangeManifest",
                               description="按 run_id 查看指定 ChangeManifest")
    mfs_p.add_argument("--project", "-p", default=".")
    mfs_p.add_argument("run_id")

    # snapshot（Phase 11C Step 2）
    snap_p = subparsers.add_parser("snapshot", help="导出能力快照（skill / cli / mcp）",
                                    description="导出能力快照（skill / cli / mcp），供 Doc Steward 使用")
    snap_sub = snap_p.add_subparsers(dest="snapshot_command")

    snsk_p = snap_sub.add_parser("skills", help="导出 Skill 注册表快照",
                                  description="导出 Skill 注册表快照（从 Skill.get_registry() 内省）")
    snsk_p.add_argument("--project", "-p", default=".")
    snsk_p.add_argument("--save", action="store_true")

    sncl_p = snap_sub.add_parser("cli", help="导出 CLI 命令快照",
                                  description="导出 CLI 命令快照（从 argparse 结构内省）")
    sncl_p.add_argument("--project", "-p", default=".")
    sncl_p.add_argument("--save", action="store_true")

    snmc_p = snap_sub.add_parser("mcp", help="导出 MCP 工具快照",
                                  description="导出 MCP 工具快照（从 mcp/server.py 内省）")
    snmc_p.add_argument("--project", "-p", default=".")
    snmc_p.add_argument("--save", action="store_true")

    return parser


def build_mcp_snapshot() -> McpSnapshot:
    """从 mcp/server.py 的 _TOOLS 列表构建 MCP 工具快照。

    mcp 包未安装时返回 available=False 的空快照（不崩溃）。

    返回：
        McpSnapshot（未持久化）
    """
    tools: list[McpToolEntry] = []
    available = False

    try:
        # 尝试导入 mcp 包（可选依赖）
        import mcp  # noqa: F401
        available = True
    except ImportError:
        # mcp 包未安装，返回空快照
        return McpSnapshot(
            generated_at=_now_iso(),
            tool_count=0,
            available=False,
            tools=[],
        )

    # 通过 create_server 内省 _TOOLS
    # 不实际启动 server，只构建并立即解构
    try:
        from smartdev.mcp.server import create_server
        from pathlib import Path as _Path
        # 传一个不存在的路径——我们只需要 _TOOLS 列表，不跑任何 handler
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            server = create_server(_Path(tmp))

        # create_server 注册了 list_tools handler，通过内省提取 _TOOLS
        # 注：直接解析 server.py 源码中的 _TOOLS 更健壮
        tools = _extract_tools_from_server_module()
    except Exception:
        tools = []

    tools.sort(key=lambda t: t.name)
    return McpSnapshot(
        generated_at=_now_iso(),
        tool_count=len(tools),
        available=available,
        tools=tools,
    )


def _extract_tools_from_server_module() -> list[McpToolEntry]:
    """从 mcp/server.py 的源码级内省提取工具列表。

    直接访问 create_server 函数的局部变量 _TOOLS 比运行 asyncio 更安全。
    通过反射 create_server 的字节码不可靠，这里用替代方案：
    在一个最小 mock 环境下调用 create_server，捕获注册的工具列表。
    """
    import types

    entries: list[McpToolEntry] = []

    # 用 monkeypatch 方式：临时替换 mcp.types.Tool 为记录器
    try:
        import mcp.types as mcp_types
        original_tool_cls = mcp_types.Tool

        recorded: list = []

        class _CaptureTool:
            """代替 mcp.types.Tool，记录构造参数。"""
            def __init__(self, name="", description="", inputSchema=None, **kwargs):
                self._name = name
                self._description = description
                self._schema = inputSchema or {}
                recorded.append(self)

        mcp_types.Tool = _CaptureTool  # type: ignore

        try:
            # 重新导入以触发 create_server 重建（不缓存）
            import importlib
            import smartdev.mcp.server as _srv_mod
            importlib.reload(_srv_mod)

            import tempfile
            from pathlib import Path as _P
            with tempfile.TemporaryDirectory() as tmp:
                _srv_mod.create_server(_P(tmp))
        except Exception:
            pass
        finally:
            mcp_types.Tool = original_tool_cls
            # 恢复 server 模块
            try:
                import smartdev.mcp.server as _srv_mod2
                importlib.reload(_srv_mod2)
            except Exception:
                pass

        for tool in recorded:
            schema = tool._schema or {}
            props = schema.get("properties", {})
            required_set = set(schema.get("required", []))
            required_params = [k for k in props if k in required_set]
            optional_params = [k for k in props if k not in required_set]
            entries.append(McpToolEntry(
                name=tool._name,
                description=tool._description,
                required=required_params,
                optional=optional_params,
            ))

    except Exception:
        pass

    return entries


# ── 持久化 ────────────────────────────────────────────────


def save_snapshot(snapshot_dict: dict, name: str, runs_dir: Path, run_id: str) -> Path:
    """把快照 JSON 写入 .smartdev/runs/<run_id>/<name>-snapshot.json。

    参数：
        snapshot_dict: 快照的 to_dict() 结果
        name:          快照名称（"skill" / "cli" / "mcp"）
        runs_dir:      .smartdev/runs/ 目录
        run_id:        运行 ID

    返回：
        写入的文件绝对路径
    """
    runs_dir = Path(runs_dir)
    out_dir = runs_dir / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / f"{name}-snapshot.json"
    out_path.write_text(
        json.dumps(snapshot_dict, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return out_path
