"""
技术栈检测器

设计原理：
─────────
通过"标记文件"检测项目使用了哪些技术。每个技术对应一组标记文件，
当标记文件存在且内容匹配时，判定该项目使用了该技术。

为什么用标记文件检测而非解析 AST / 静态分析？
────────────────────────────────────────────
1. Phase 1 需要快速、低开销的检测，不需要精确到"用了哪个 API"
2. 标记文件检测的准确率已经够用于"项目诊断"场景
3. 后续可以叠加更精确的检测器（如解析 package.json 的 dependencies）

检测层级：
─────────
  Level 1: 语言/运行时  — Python, Node.js, TypeScript
  Level 2: 框架/库      — FastAPI, Vue, React, Vite
  Level 3: 工具/平台    — Chrome Extension, Docker, Git

对应文档：
- smartPi/docs/smartdev-agent-core-spec.md §5.1（项目诊断 — 技术栈识别维度）
- smartPi/docs/smartdev-agent-core-spec.md §9.1（Chrome Extension Adapter）
- smartPi/docs/smartdev-agent-core-spec.md §9.2（FastAPI Adapter）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TechMatch:
    """单项技术检测结果

    Attributes:
        name: 技术名称，如 "Python", "Chrome Extension MV3"
        category: 分类：language / framework / tool / platform
        confidence: 置信度 0.0-1.0，基于标记文件数量
        evidence: 判定依据，如 ["requirements.txt", "pyproject.toml"]
    """
    name: str
    category: str          # language | framework | tool | platform
    confidence: float      # 0.0 ~ 1.0
    evidence: list[str] = field(default_factory=list)


@dataclass
class TechStackResult:
    """技术栈检测总结果"""
    languages: list[TechMatch] = field(default_factory=list)
    frameworks: list[TechMatch] = field(default_factory=list)
    tools: list[TechMatch] = field(default_factory=list)
    platforms: list[TechMatch] = field(default_factory=list)

    def all_techs(self) -> list[TechMatch]:
        """返回所有检测到的技术，按 category 分组"""
        return self.languages + self.frameworks + self.tools + self.platforms

    def tech_names(self) -> list[str]:
        """返回所有技术名称列表，适合放入 ProjectContext.tech_stack"""
        return [t.name for t in self.all_techs()]


# ── 检测函数 ──────────────────────────────────────────────
# 每个函数接收项目根目录，返回 TechMatch 或 None
# 为什么用函数而非类？
#   Phase 1 的检测逻辑是无状态的，函数足够
#   后续如果需要配置化（如用户指定跳过某些检测），再升级为类


def _detect_python(project: Path) -> TechMatch | None:
    """检测 Python 项目"""
    markers = []
    if (project / "pyproject.toml").exists():
        markers.append("pyproject.toml")
    if (project / "setup.py").exists():
        markers.append("setup.py")
    if (project / "setup.cfg").exists():
        markers.append("setup.cfg")
    if (project / "requirements.txt").exists():
        markers.append("requirements.txt")
    if (project / "Pipfile").exists():
        markers.append("Pipfile")

    if not markers:
        return None

    # 置信度：标记文件越多越确定
    confidence = min(1.0, 0.4 + len(markers) * 0.15)
    return TechMatch(
        name="Python",
        category="language",
        confidence=confidence,
        evidence=markers,
    )


def _detect_nodejs(project: Path) -> TechMatch | None:
    """检测 Node.js 项目"""
    pkg = project / "package.json"
    if not pkg.exists():
        return None

    markers = ["package.json"]

    # 检查 lock 文件提高置信度
    if (project / "package-lock.json").exists():
        markers.append("package-lock.json")
    if (project / "yarn.lock").exists():
        markers.append("yarn.lock")
    if (project / "pnpm-lock.yaml").exists():
        markers.append("pnpm-lock.yaml")

    confidence = min(1.0, 0.5 + len(markers) * 0.15)
    return TechMatch(
        name="Node.js",
        category="language",
        confidence=confidence,
        evidence=markers,
    )


def _detect_typescript(project: Path) -> TechMatch | None:
    """检测 TypeScript"""
    markers = []
    if (project / "tsconfig.json").exists():
        markers.append("tsconfig.json")

    # 从 package.json 检查 typescript 依赖
    pkg = project / "package.json"
    if pkg.exists():
        try:
            import json
            data = json.loads(pkg.read_text(encoding="utf-8"))
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            if "typescript" in deps:
                markers.append("typescript in dependencies")
        except (json.JSONDecodeError, OSError):
            pass

    if not markers:
        return None

    confidence = min(1.0, 0.5 + len(markers) * 0.25)
    return TechMatch(
        name="TypeScript",
        category="language",
        confidence=confidence,
        evidence=markers,
    )


def _detect_chrome_extension(project: Path) -> TechMatch | None:
    """检测 Chrome Extension（Manifest V3）

    对应 core-spec §9.1 的 Chrome Extension Adapter 检查项：
    1. manifest.json 存在
    2. manifest_version == 3
    3. 有 background.service_worker 或 action 字段
    """
    manifest_path = project / "manifest.json"
    if not manifest_path.exists():
        return None

    try:
        import json
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    markers = ["manifest.json"]

    # 检查 manifest_version
    mv = data.get("manifest_version")
    if mv == 3:
        markers.append("manifest_version=3")
    elif mv == 2:
        markers.append("manifest_version=2")
    else:
        return None  # 没有明确的 manifest_version，不算 Chrome Extension

    # 检查关键字段
    if "service_worker" in data.get("background", {}):
        markers.append("background.service_worker")
    if "action" in data:
        markers.append("action")
    if "side_panel" in data:
        markers.append("side_panel")
    if "content_scripts" in data:
        markers.append("content_scripts")

    confidence = min(1.0, 0.4 + len(markers) * 0.12)
    version_label = f"Chrome Extension MV{mv}"
    return TechMatch(
        name=version_label,
        category="platform",
        confidence=confidence,
        evidence=markers,
    )


def _detect_fastapi(project: Path) -> TechMatch | None:
    """检测 FastAPI 项目

    对应 core-spec §9.2 的 FastAPI Adapter 检查项。
    策略：检查 Python 依赖中是否包含 fastapi。
    """
    markers = []

    # 从 requirements.txt 检查
    req = project / "requirements.txt"
    if req.exists():
        try:
            content = req.read_text(encoding="utf-8").lower()
            if "fastapi" in content:
                markers.append("requirements.txt (fastapi)")
        except OSError:
            pass

    # 从 pyproject.toml 检查
    pyproject = project / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text(encoding="utf-8").lower()
            if "fastapi" in content:
                markers.append("pyproject.toml (fastapi)")
        except OSError:
            pass

    # 检查典型入口文件
    for name in ["main.py", "app.py", "server.py"]:
        if (project / name).exists():
            try:
                content = (project / name).read_text(encoding="utf-8")
                if "FastAPI" in content or "from fastapi" in content:
                    markers.append(f"{name} (FastAPI import)")
                    break
            except OSError:
                pass

    if not markers:
        return None

    confidence = min(1.0, 0.4 + len(markers) * 0.2)
    return TechMatch(
        name="FastAPI",
        category="framework",
        confidence=confidence,
        evidence=markers,
    )


def _detect_vue(project: Path) -> TechMatch | None:
    """检测 Vue.js"""
    markers = []

    pkg = project / "package.json"
    if pkg.exists():
        try:
            import json
            data = json.loads(pkg.read_text(encoding="utf-8"))
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            if "vue" in deps:
                markers.append("vue in dependencies")
            if "@vue/cli-service" in deps:
                markers.append("@vue/cli-service")
        except (json.JSONDecodeError, OSError):
            pass

    if (project / "vue.config.js").exists():
        markers.append("vue.config.js")
    if (project / "vite.config.ts").exists() or (project / "vite.config.js").exists():
        # Vite 项目也可能用 Vue，需要进一步检查
        pass

    if not markers:
        return None

    confidence = min(1.0, 0.5 + len(markers) * 0.25)
    return TechMatch(
        name="Vue.js",
        category="framework",
        confidence=confidence,
        evidence=markers,
    )


def _detect_react(project: Path) -> TechMatch | None:
    """检测 React"""
    markers = []

    pkg = project / "package.json"
    if pkg.exists():
        try:
            import json
            data = json.loads(pkg.read_text(encoding="utf-8"))
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            if "react" in deps:
                markers.append("react in dependencies")
            if "react-dom" in deps:
                markers.append("react-dom in dependencies")
            if "next" in deps:
                markers.append("next (Next.js)")
        except (json.JSONDecodeError, OSError):
            pass

    if not markers:
        return None

    confidence = min(1.0, 0.5 + len(markers) * 0.2)
    return TechMatch(
        name="React",
        category="framework",
        confidence=confidence,
        evidence=markers,
    )


def _detect_docker(project: Path) -> TechMatch | None:
    """检测 Docker"""
    markers = []
    if (project / "Dockerfile").exists():
        markers.append("Dockerfile")
    if (project / "docker-compose.yml").exists():
        markers.append("docker-compose.yml")
    if (project / "docker-compose.yaml").exists():
        markers.append("docker-compose.yaml")
    if (project / ".dockerignore").exists():
        markers.append(".dockerignore")

    if not markers:
        return None

    confidence = min(1.0, 0.5 + len(markers) * 0.2)
    return TechMatch(
        name="Docker",
        category="tool",
        confidence=confidence,
        evidence=markers,
    )


def _detect_git(project: Path) -> TechMatch | None:
    """检测 Git 仓库"""
    if (project / ".git").exists():
        return TechMatch(
            name="Git",
            category="tool",
            confidence=1.0,
            evidence=[".git"],
        )
    return None


def _detect_vite(project: Path) -> TechMatch | None:
    """检测 Vite 构建工具"""
    markers = []
    if (project / "vite.config.ts").exists():
        markers.append("vite.config.ts")
    if (project / "vite.config.js").exists():
        markers.append("vite.config.js")
    if (project / "vite.config.mjs").exists():
        markers.append("vite.config.mjs")

    pkg = project / "package.json"
    if pkg.exists():
        try:
            import json
            data = json.loads(pkg.read_text(encoding="utf-8"))
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            if "vite" in deps:
                markers.append("vite in dependencies")
        except (json.JSONDecodeError, OSError):
            pass

    if not markers:
        return None

    confidence = min(1.0, 0.5 + len(markers) * 0.2)
    return TechMatch(
        name="Vite",
        category="tool",
        confidence=confidence,
        evidence=markers,
    )


def _detect_tailwind(project: Path) -> TechMatch | None:
    """检测 Tailwind CSS"""
    markers = []
    if (project / "tailwind.config.js").exists():
        markers.append("tailwind.config.js")
    if (project / "tailwind.config.ts").exists():
        markers.append("tailwind.config.ts")

    pkg = project / "package.json"
    if pkg.exists():
        try:
            import json
            data = json.loads(pkg.read_text(encoding="utf-8"))
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            if "tailwindcss" in deps:
                markers.append("tailwindcss in dependencies")
        except (json.JSONDecodeError, OSError):
            pass

    if not markers:
        return None

    confidence = min(1.0, 0.5 + len(markers) * 0.2)
    return TechMatch(
        name="Tailwind CSS",
        category="framework",
        confidence=confidence,
        evidence=markers,
    )


# ── 主入口 ────────────────────────────────────────────────

# 所有检测函数的注册表
# 为什么用列表而非自动注册？
#   Phase 1 检测器数量有限（<15 个），显式列表更清晰
#   后续如果检测器增多，可以改为扫描 detectors/ 目录自动发现

_DETECTORS = [
    # Language
    _detect_python,
    _detect_nodejs,
    _detect_typescript,
    # Framework
    _detect_fastapi,
    _detect_vue,
    _detect_react,
    _detect_tailwind,
    # Tool
    _detect_docker,
    _detect_vite,
    # Platform
    _detect_chrome_extension,
    # Infrastructure
    _detect_git,
]


def detect_tech_stack(project_path: Path) -> TechStackResult:
    """检测项目技术栈

    参数：
        project_path: 项目根目录路径

    返回：
        TechStackResult，包含按类别分组的检测结果

    使用示例：
        result = detect_tech_stack(Path("/path/to/project"))
        print(result.tech_names())  # ["Python", "FastAPI", "Git"]
    """
    result = TechStackResult()

    for detector in _DETECTORS:
        match = detector(project_path)
        if match is None:
            continue

        if match.category == "language":
            result.languages.append(match)
        elif match.category == "framework":
            result.frameworks.append(match)
        elif match.category == "tool":
            result.tools.append(match)
        elif match.category == "platform":
            result.platforms.append(match)

    return result
