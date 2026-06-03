"""
入口文件检测器

设计原理：
─────────
检测项目的入口文件（启动点），帮助 Agent 理解"从哪里开始阅读代码"。

检测策略：
─────────
1. 常见入口文件名（main.py, index.js, App.vue 等）
2. package.json 的 main/scripts 字段
3. pyproject.toml 的 [project.scripts] 字段

对应文档：
- smartPi/docs/smartdev-agent-core-spec.md §5.1（项目诊断 — 目录结构维度）
- smartPi/docs/smartdev-agent/agent.md §5（repo.scan 的 outputs 包含 entrypoints）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Entrypoint:
    """入口文件信息

    Attributes:
        name: 入口名称，如 "main.py", "sidepanel"
        path: 相对于项目根的路径
        type: 入口类型：cli / web / extension / script
        source: 检测来源：filename / package_json / pyproject_toml
    """
    name: str
    path: str
    type: str        # cli | web | extension | script
    source: str      # filename | package_json | pyproject_toml


@dataclass
class EntrypointsResult:
    """入口文件检测总结果"""
    entrypoints: list[Entrypoint] = field(default_factory=list)

    def by_type(self, entry_type: str) -> list[Entrypoint]:
        """按类型筛选入口"""
        return [e for e in self.entrypoints if e.type == entry_type]


# ── 检测函数 ──────────────────────────────────────────────


def _detect_python_entrypoints(project: Path) -> list[Entrypoint]:
    """检测 Python 项目入口"""
    entrypoints = []

    # 常见 Python 入口文件
    python_entries = [
        ("main.py", "cli"),
        ("app.py", "web"),
        ("server.py", "web"),
        ("cli.py", "cli"),
        ("__main__.py", "cli"),
    ]
    for name, entry_type in python_entries:
        if (project / name).exists():
            entrypoints.append(Entrypoint(
                name=name,
                path=name,
                type=entry_type,
                source="filename",
            ))

    # 从 pyproject.toml 读取 entry points
    pyproject = project / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text(encoding="utf-8")
            # 简单解析 [project.scripts] 段
            in_scripts = False
            for line in content.splitlines():
                stripped = line.strip()
                if stripped == "[project.scripts]":
                    in_scripts = True
                    continue
                if stripped.startswith("[") and in_scripts:
                    in_scripts = False
                    continue
                if in_scripts and "=" in stripped:
                    cmd_name = stripped.split("=")[0].strip()
                    entrypoints.append(Entrypoint(
                        name=cmd_name,
                        path=f"(pyproject.toml: {stripped.strip()})",
                        type="cli",
                        source="pyproject_toml",
                    ))
        except OSError:
            pass

    return entrypoints


def _detect_nodejs_entrypoints(project: Path) -> list[Entrypoint]:
    """检测 Node.js 项目入口"""
    entrypoints = []

    pkg = project / "package.json"
    if not pkg.exists():
        return entrypoints

    try:
        import json
        data = json.loads(pkg.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return entrypoints

    # main 字段
    main = data.get("main")
    if main:
        entrypoints.append(Entrypoint(
            name="main",
            path=main,
            type="web",
            source="package_json",
        ))

    # scripts 字段
    scripts = data.get("scripts", {})
    for cmd_name in ["start", "dev", "build", "test"]:
        if cmd_name in scripts:
            entrypoints.append(Entrypoint(
                name=cmd_name,
                path=f"npm run {cmd_name}",
                type="cli",
                source="package_json",
            ))

    return entrypoints


def _detect_chrome_extension_entrypoints(project: Path) -> list[Entrypoint]:
    """检测 Chrome Extension 入口"""
    entrypoints = []

    manifest = project / "manifest.json"
    if not manifest.exists():
        return entrypoints

    try:
        import json
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return entrypoints

    # background service_worker
    bg = data.get("background", {})
    sw = bg.get("service_worker")
    if sw:
        entrypoints.append(Entrypoint(
            name="service_worker",
            path=sw,
            type="extension",
            source="filename",
        ))

    # content_scripts
    for cs in data.get("content_scripts", []):
        for js_file in cs.get("js", []):
            entrypoints.append(Entrypoint(
                name="content_script",
                path=js_file,
                type="extension",
                source="filename",
            ))

    # side_panel
    sp = data.get("side_panel", {})
    sp_path = sp.get("default_path")
    if sp_path:
        entrypoints.append(Entrypoint(
            name="side_panel",
            path=sp_path,
            type="extension",
            source="filename",
        ))

    # action popup
    action = data.get("action", {})
    popup = action.get("default_popup")
    if popup:
        entrypoints.append(Entrypoint(
            name="popup",
            path=popup,
            type="extension",
            source="filename",
        ))

    return entrypoints


# ── 主入口 ────────────────────────────────────────────────


def detect_entrypoints(project_path: Path) -> EntrypointsResult:
    """检测项目入口文件

    参数：
        project_path: 项目根目录路径

    返回：
        EntrypointsResult，包含所有检测到的入口文件

    使用示例：
        result = detect_entrypoints(Path("/path/to/project"))
        for ep in result.entrypoints:
            print(f"  {ep.name}: {ep.path} ({ep.type})")
    """
    result = EntrypointsResult()

    # 按项目类型检测（不依赖 adapter，自动判断）
    result.entrypoints.extend(_detect_python_entrypoints(project_path))
    result.entrypoints.extend(_detect_nodejs_entrypoints(project_path))
    result.entrypoints.extend(_detect_chrome_extension_entrypoints(project_path))

    return result
