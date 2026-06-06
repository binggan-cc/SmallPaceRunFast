"""
Project Adapter — 项目适配器

设计原理：
─────────
适配器是 SmartDev Agent 的扩展机制。每个适配器定义一个项目类型的
专属约束：目录结构、可编辑区域、禁止区域、技术限制、验证清单。

为什么需要适配器？
─────────────────
1. 不同项目的"安全修改范围"不同
2. Chrome Extension 有 Service Worker 限制，FastAPI 有路由限制
3. 没有适配器，Skill 不知道哪些文件能改、哪些不能改

适配器和 Skill 的关系：
─────────────────────
  Adapter = 项目地图（告诉 Skill 哪里能改）
  Skill = 可执行工具（在地图约束下执行）

对应文档：
- smartPi/docs/smartdev-agent-core-spec.md §9（项目适配器机制）
- smartPi/docs/smartdev-agent/agent.md §6（Skill 与 Adapter 的关系）
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AdapterPaths:
    """项目路径配置

    Attributes:
        source: 源代码目录
        docs: 文档目录
        tests: 测试目录
        assets: 静态资源目录
    """
    source: str = ""
    docs: str = ""
    tests: str = ""
    assets: str = ""


@dataclass
class ProjectAdapter:
    """项目适配器

    定义项目类型的专属约束，供 Skill 在执行时参考。

    Attributes:
        name: 适配器名称（如 "smartfav", "chrome_extension"）
        version: 适配器版本
        project_name: 项目名称
        project_type: 项目类型（如 "chrome-extension-local-first"）
        tech_stack: 技术栈列表
        paths: 目录结构
        editable_regions: 可修改区域列表
        cautious_regions: 谨慎修改区域列表
        forbidden_regions: 禁止修改区域列表
        constraints: 技术约束列表
        validation_checklists: 验证清单
        known_issues: 已知问题列表
        current_priorities: 当前优先任务
    """
    name: str = ""
    version: str = "1.0"
    project_name: str = ""
    project_type: str = ""
    tech_stack: list[str] = field(default_factory=list)
    paths: AdapterPaths = field(default_factory=AdapterPaths)
    editable_regions: list[str] = field(default_factory=list)
    cautious_regions: list[str] = field(default_factory=list)
    forbidden_regions: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    validation_checklists: list[str] = field(default_factory=list)
    known_issues: list[str] = field(default_factory=list)
    current_priorities: list[str] = field(default_factory=list)

    def is_editable(self, file_path: str) -> bool:
        """判断文件是否在可编辑区域内"""
        for region in self.editable_regions:
            if file_path.startswith(region) or file_path == region:
                return True
        return False

    def is_forbidden(self, file_path: str) -> bool:
        """判断文件是否在禁止区域内"""
        for region in self.forbidden_regions:
            if file_path.startswith(region) or file_path == region:
                return True
        return False

    def is_cautious(self, file_path: str) -> bool:
        """判断文件是否在谨慎修改区域内"""
        for region in self.cautious_regions:
            if file_path.startswith(region) or file_path == region:
                return True
        return False

    def describe(self) -> dict:
        """返回适配器的可读描述"""
        return {
            "name": self.name,
            "version": self.version,
            "project_name": self.project_name,
            "project_type": self.project_type,
            "tech_stack": self.tech_stack,
            "editable_count": len(self.editable_regions),
            "cautious_count": len(self.cautious_regions),
            "forbidden_count": len(self.forbidden_regions),
        }


# ── 适配器加载器 ──────────────────────────────────────────


def load_adapter(adapter_path: Path) -> ProjectAdapter:
    """从 JSON 文件加载适配器

    参数：
        adapter_path: 适配器 JSON 文件路径

    返回：
        ProjectAdapter 实例

    异常：
        FileNotFoundError: 文件不存在
        json.JSONDecodeError: JSON 格式错误
    """
    with open(adapter_path, encoding="utf-8") as f:
        data = json.load(f)

    # 解析 paths
    paths_data = data.get("paths", {})
    paths = AdapterPaths(
        source=paths_data.get("source", ""),
        docs=paths_data.get("docs", ""),
        tests=paths_data.get("tests", ""),
        assets=paths_data.get("assets", ""),
    )

    return ProjectAdapter(
        name=data.get("adapter", ""),
        version=data.get("version", "1.0"),
        project_name=data.get("project", {}).get("name", ""),
        project_type=data.get("project", {}).get("type", ""),
        tech_stack=data.get("project", {}).get("tech_stack", []),
        paths=paths,
        editable_regions=data.get("editable_regions", []),
        cautious_regions=data.get("cautious_regions", []),
        forbidden_regions=data.get("forbidden_regions", []),
        constraints=data.get("constraints", []),
        validation_checklists=data.get("validation", []),
        known_issues=data.get("known_issues", []),
        current_priorities=data.get("current_priorities", []),
    )


def find_adapter(project_path: Path, adapters_dir: Path | None = None) -> ProjectAdapter | None:
    """尝试自动检测项目类型并加载适配器

    策略：
    1. 检查项目根目录是否有 adapter.json
    2. 检查 adapters_dir 中是否有匹配项目类型的适配器

    参数：
        project_path: 项目根目录
        adapters_dir: 适配器目录（默认 smartdev/adapters/）

    返回：
        匹配的 ProjectAdapter，未找到返回 None
    """
    # 策略 1：项目自带适配器
    local_adapter = project_path / "adapter.json"
    if local_adapter.exists():
        return load_adapter(local_adapter)

    # 策略 2：从 adapters 目录匹配
    if adapters_dir is None:
        adapters_dir = Path(__file__).parent.parent / "adapters"

    if not adapters_dir.exists():
        return None

    # 检测项目类型
    project_type = _detect_project_type(project_path)

    # 查找匹配的适配器
    for adapter_file in adapters_dir.glob("*.json"):
        try:
            adapter = load_adapter(adapter_file)
            if adapter.project_type == project_type:
                return adapter
        except (json.JSONDecodeError, FileNotFoundError):
            continue

    return None


def _detect_project_type(project_path: Path) -> str:
    """检测项目类型

    返回项目类型字符串，用于匹配适配器。
    """
    # Chrome Extension
    manifest = project_path / "manifest.json"
    if manifest.exists():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            if "manifest_version" in data:
                return "chrome-extension"
        except (json.JSONDecodeError, OSError):
            pass

    # FastAPI
    for name in ["main.py", "app.py", "server.py"]:
        fp = project_path / name
        if fp.exists():
            try:
                content = fp.read_text(encoding="utf-8")
                if "FastAPI" in content or "from fastapi" in content:
                    return "fastapi"
            except OSError:
                pass

    # Python CLI
    if (project_path / "pyproject.toml").exists():
        return "python-cli"

    # Node.js
    if (project_path / "package.json").exists():
        return "nodejs"

    return "generic"
