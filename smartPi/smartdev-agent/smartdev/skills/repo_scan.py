"""
Skill: repo.scan — 仓库扫描

功能：扫描项目目录，识别技术栈、入口文件和文档状态。
风险：R0（只读，不修改任何文件）
类型：diagnose

这是 SmartDev Agent 的第一个 Skill，对应 agent.md §4 的 Phase 1 目标：
"不改代码，只读项目"。

data 字段结构：
{
    "project_path": "/path/to/project",
    "tech_stack": {
        "languages": [...],
        "frameworks": [...],
        "tools": [...],
        "platforms": [...]
    },
    "entrypoints": [...],
    "docs_status": {
        "coverage_rate": 0.6,
        "missing": [...],
        "existing": [...]
    },
    "directory_tree": "..."   # 简化的目录结构文本
}
"""

from __future__ import annotations

from pathlib import Path

from smartdev.detectors.docs_status import detect_docs_status
from smartdev.detectors.entrypoints import detect_entrypoints
from smartdev.detectors.tech_stack import detect_tech_stack
from smartdev.models import RiskLevel, SkillResult, TaskType
from smartdev.skills.base import Skill


# ── 目录树扫描 ────────────────────────────────────────────
# 为什么需要目录树？
#   Agent 需要一个项目结构的"鸟瞰图"来理解模块划分
#   完整递归扫描太慢且信息过载，只扫 2 层 + 常见文件

# 需要跳过的目录（太大、无意义）
_SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    ".pytest_cache", ".mypy_cache", ".tox", "dist", "build",
    ".next", ".nuxt", ".cache", ".parcel-cache",
    "coverage", ".nyc_output",
}

# 需要跳过的文件（太大、无意义）
_SKIP_FILES = {
    "*.pyc", "*.pyo", "*.pyd", "*.so", "*.dylib",
    "*.o", "*.a", "*.lib",
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "poetry.lock", "Pipfile.lock",
    ".DS_Store", "Thumbs.db",
}


def _build_directory_tree(root: Path, max_depth: int = 2) -> str:
    """构建简化的目录树

    只展开 2 层深度，跳过 _SKIP_DIRS 中的目录。
    输出格式类似 `tree` 命令但更紧凑。

    参数：
        root: 项目根目录
        max_depth: 最大展开深度，默认 2

    返回：
        目录树文本
    """
    lines = []

    def _scan(directory: Path, prefix: str, depth: int) -> None:
        if depth > max_depth:
            return

        try:
            entries = sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name))
        except PermissionError:
            return

        # 过滤
        entries = [
            e for e in entries
            if e.name not in _SKIP_DIRS
            and not e.name.startswith(".")
            and e.name not in ("node_modules", "__pycache__")
        ]

        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            connector = "└── " if is_last else "├── "
            child_prefix = prefix + ("    " if is_last else "│   ")

            if entry.is_dir():
                lines.append(f"{prefix}{connector}{entry.name}/")
                _scan(entry, child_prefix, depth + 1)
            else:
                lines.append(f"{prefix}{connector}{entry.name}")

    lines.append(root.name + "/")
    _scan(root, "", 1)
    return "\n".join(lines)


# ── Skill 实现 ────────────────────────────────────────────


class RepoScanSkill(Skill):
    """仓库扫描 Skill

    扫描项目目录，识别技术栈、入口文件和文档状态。
    不修改任何文件，只读操作。

    使用示例：
        from smartdev.models import ProjectContext
        from smartdev.skills.base import Skill

        context = ProjectContext(project_path=Path("/path/to/project"))
        skill = Skill.create("repo.scan")

        if skill.can_run(context):
            result = skill.run(context)
            print(result.summary)
            print(result.data)
    """

    name = "repo.scan"
    description = "扫描项目目录，识别技术栈、入口文件和文档状态"
    risk_level = RiskLevel.R0
    task_type = TaskType.DIAGNOSE

    def can_run(self, context) -> bool:
        """前置条件：项目路径必须存在且是目录"""
        return (
            context.project_path.exists()
            and context.project_path.is_dir()
        )

    def run(self, context, inputs: dict | None = None) -> SkillResult:
        """执行仓库扫描

        参数：
            context: ProjectContext，必须包含 project_path
            inputs: 可选参数
                - max_depth: 目录树最大深度，默认 2
                - include_patterns: 未使用（预留）
                - exclude_patterns: 未使用（预留）

        返回：
            SkillResult，data 包含完整的扫描结果
        """
        project = context.project_path
        max_depth = (inputs or {}).get("max_depth", 2)

        # 1. 技术栈检测
        tech_stack = detect_tech_stack(project)

        # 2. 入口文件检测
        entrypoints = detect_entrypoints(project)

        # 3. 文档状态检测
        docs_status = detect_docs_status(project)

        # 4. 目录树扫描
        directory_tree = _build_directory_tree(project, max_depth=max_depth)

        # 5. 组装 SkillResult
        tech_summary = ", ".join(tech_stack.tech_names()) or "未识别到已知技术栈"

        summary_parts = [
            f"扫描完成：{project.name}",
            f"技术栈：{tech_summary}",
            f"入口文件：{len(entrypoints.entrypoints)} 个",
            f"文档覆盖率：{docs_status.coverage_rate:.0%}",
        ]

        # 收集风险（只读 Skill 不会产生代码风险，但可以指出项目问题）
        risks = []
        if docs_status.missing_docs:
            missing_names = [d.name for d in docs_status.missing_docs[:5]]
            risks.append(f"缺失文档: {', '.join(missing_names)}")
        if docs_status.empty_docs:
            empty_names = [d.name for d in docs_status.empty_docs]
            risks.append(f"空文档: {', '.join(empty_names)}")

        # 收集下一步建议
        next_steps = []
        if not entrypoints.entrypoints:
            next_steps.append("未检测到入口文件，建议确认项目结构")
        if docs_status.coverage_rate < 0.5:
            next_steps.append("文档覆盖率较低，建议补充 README 和 CONTRIBUTING")
        if tech_stack.languages:
            next_steps.append("建议运行 repo.diagnose 进行深入诊断")

        return SkillResult(
            success=True,
            summary="\n".join(summary_parts),
            data={
                "project_path": str(project),
                "tech_stack": {
                    "languages": [
                        {"name": t.name, "confidence": t.confidence, "evidence": t.evidence}
                        for t in tech_stack.languages
                    ],
                    "frameworks": [
                        {"name": t.name, "confidence": t.confidence, "evidence": t.evidence}
                        for t in tech_stack.frameworks
                    ],
                    "tools": [
                        {"name": t.name, "confidence": t.confidence, "evidence": t.evidence}
                        for t in tech_stack.tools
                    ],
                    "platforms": [
                        {"name": t.name, "confidence": t.confidence, "evidence": t.evidence}
                        for t in tech_stack.platforms
                    ],
                },
                "entrypoints": [
                    {"name": e.name, "path": e.path, "type": e.type, "source": e.source}
                    for e in entrypoints.entrypoints
                ],
                "docs_status": {
                    "coverage_rate": docs_status.coverage_rate,
                    "existing": [d.name for d in docs_status.existing_docs],
                    "missing": [d.name for d in docs_status.missing_docs],
                    "empty": [d.name for d in docs_status.empty_docs],
                },
                "directory_tree": directory_tree,
            },
            risks=risks,
            next_steps=next_steps,
        )
