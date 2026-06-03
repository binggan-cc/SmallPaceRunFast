"""
Skill: architecture.map — 架构分析

功能：分析项目模块之间的依赖关系，检测循环依赖，识别核心模块。
风险：R0（只读，不修改任何文件）
类型：analyze

data 字段结构：
{
    "modules": [{"name": "...", "path": "...", "imports": [...], "line_count": 42}],
    "dependency_graph": {"module_a": ["module_b", "module_c"]},
    "circular_deps": [["a", "b", "a"]],
    "core_modules": ["模块名"],   # 被引用最多的模块
    "external_deps": ["外部包名"],
    "summary": {
        "total_modules": 10,
        "total_lines": 500,
        "max_depth": 3,
        "has_circular": false
    }
}
"""

from __future__ import annotations

from pathlib import Path

from smartdev.detectors.modules import detect_modules
from smartdev.models import RiskLevel, SkillResult, TaskType
from smartdev.skills.base import Skill


def _find_core_modules(modules, top_n: int = 5) -> list[str]:
    """识别核心模块（被引用次数最多的模块）

    为什么选"被引用次数"？
    被 import 次数越多的模块，说明其他模块越依赖它，
    它就是架构中的"枢纽"。修改这类模块需要特别谨慎。
    """
    from collections import Counter

    ref_count = Counter()
    for m in modules:
        for imp in m.internal_imports:
            ref_count[imp] += 1

    return [name for name, _ in ref_count.most_common(top_n)]


def _find_external_deps(modules) -> list[str]:
    """收集所有外部依赖"""
    external = set()
    for m in modules:
        external.update(m.external_imports)
    return sorted(external)


class ArchitectureMapSkill(Skill):
    """架构分析 Skill

    分析项目模块之间的依赖关系，检测循环依赖，识别核心模块。

    使用示例：
        context = ProjectContext(project_path=Path("/path/to/project"))
        skill = Skill.create("architecture.map")
        result = skill.run(context)
    """

    name = "architecture.map"
    description = "分析项目模块之间的依赖关系，检测循环依赖，识别核心模块"
    risk_level = RiskLevel.R0
    task_type = TaskType.ANALYZE

    def can_run(self, context) -> bool:
        """前置条件：项目路径存在且包含 Python 文件"""
        if not context.project_path.exists() or not context.project_path.is_dir():
            return False
        # 检查是否有 Python 文件
        return any(context.project_path.rglob("*.py"))

    def run(self, context, inputs: dict | None = None) -> SkillResult:
        """执行架构分析"""
        project = context.project_path

        # 模块分析
        analysis = detect_modules(project)

        # 识别核心模块
        core_modules = _find_core_modules(analysis.modules)

        # 构建依赖图（只输出内部依赖）
        dependency_graph = {
            m.name: m.internal_imports
            for m in analysis.modules
            if m.internal_imports
        }

        # 统计
        total_lines = sum(m.line_count for m in analysis.modules)
        has_circular = len(analysis.circular_deps) > 0

        # 摘要
        summary_parts = [
            f"架构分析完成：{project.name}",
            f"模块数：{len(analysis.modules)}",
            f"代码行数：{total_lines}",
            f"核心模块：{', '.join(core_modules[:3]) or '无'}",
            f"循环依赖：{'有 ' + str(len(analysis.circular_deps)) + ' 个' if has_circular else '无'}",
        ]

        # 风险
        risks = []
        if has_circular:
            risks.append(f"发现 {len(analysis.circular_deps)} 个循环依赖")
        for m in analysis.modules:
            if m.line_count > 500:
                risks.append(f"{m.name} 有 {m.line_count} 行，建议拆分")

        return SkillResult(
            success=True,
            summary="\n".join(summary_parts),
            data={
                "modules": [
                    {
                        "name": m.name,
                        "path": m.path,
                        "imports": m.internal_imports,
                        "line_count": m.line_count,
                    }
                    for m in analysis.modules
                ],
                "dependency_graph": dependency_graph,
                "circular_deps": analysis.circular_deps,
                "core_modules": core_modules,
                "external_deps": _find_external_deps(analysis.modules),
                "summary": {
                    "total_modules": len(analysis.modules),
                    "total_lines": total_lines,
                    "max_depth": max((m.name.count(".") for m in analysis.modules), default=0),
                    "has_circular": has_circular,
                },
            },
            risks=risks,
            next_steps=[
                "建议运行 token.audit 检查设计令牌一致性",
                "如有循环依赖，建议规划重构",
            ] if not has_circular else [
                "优先解决循环依赖问题",
                "循环依赖可能导致导入顺序问题和测试困难",
            ],
        )
