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

from smartdev.detectors.modules import (
    ModuleAnalysisResult,
    ModuleInfo,
    _detect_circular_deps,
    detect_modules,
)
from smartdev.models import RiskLevel, SkillResult, TaskType
from smartdev.skills.base import Skill
from smartdev.skills._context_helper import get_index_if_available


def _safe_line_count(abs_path: Path) -> int:
    """统计非空行数（语言无关，用于 module 体量估算）。

    index 模式覆盖多语言，不能用 Python 专属的注释规则，
    统一按"非空行"近似度量，够用于"模块过大"启发式判断。
    """
    try:
        text = abs_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return 0
    return sum(1 for line in text.splitlines() if line.strip())


def _analyze_from_index(store, project_path: Path) -> ModuleAnalysisResult | None:
    """从索引 relations 构建模块依赖分析（多语言）。

    数据源：
    - code:module artifacts → 模块节点（节点标识用文件路径，跨语言统一）
    - imports relations → 依赖边（internal: code:module:{path} / external: external:lang:pkg）

    复用 detectors.modules 的 ModuleInfo + _detect_circular_deps，
    保证循环依赖检测算法与 AST 路径完全一致。

    返回 None 表示索引中无 module artifact（无法分析，调用方退回 AST）。
    """
    conn = store.connect()
    module_rows = conn.execute(
        "SELECT id, file_path FROM artifacts WHERE type = 'code:module'"
    ).fetchall()
    if not module_rows:
        return None

    result = ModuleAnalysisResult()
    modules_by_id: dict[str, ModuleInfo] = {}
    # 别名映射：把 Python 内部 import 的 module:{dotted} 形式映射到对应 module 节点
    # （JS/TS/Go 内部 import 用 code:module:{path}，无需别名；Python 用 module:{dotted}）
    alias_to_node: dict[str, ModuleInfo] = {}

    for row in module_rows:
        mid = row["id"]           # code:module:{path}
        fpath = row["file_path"]
        mi = ModuleInfo(
            name=fpath,           # 用文件路径作为节点标识
            path=fpath,
            internal_imports=[],
            external_imports=[],
            line_count=_safe_line_count(project_path / fpath),
        )
        modules_by_id[mid] = mi
        result.modules.append(mi)
        # 计算 dotted 名（Python 风格）作为别名：pkg/models.py → module:pkg.models
        dotted = fpath.rsplit(".", 1)[0].replace("/", ".").replace("\\", ".")
        alias_to_node[f"module:{dotted}"] = mi

    # imports relations → 依赖边
    import_rels = conn.execute(
        "SELECT source_id, target_id FROM relations WHERE type = 'imports'"
    ).fetchall()
    for rel in import_rels:
        src = rel["source_id"]
        tgt = rel["target_id"]
        if src not in modules_by_id:
            continue
        if tgt.startswith("code:module:"):
            # 项目内部依赖（JS/TS/Go 归一化形式）：节点标识用路径
            modules_by_id[src].internal_imports.append(tgt[len("code:module:"):])
        elif tgt.startswith("external:"):
            # external:lang:pkg → pkg
            modules_by_id[src].external_imports.append(tgt.split(":", 2)[-1])
        elif tgt.startswith("module:"):
            # Python 内部 import 占位形式：通过别名映射到 module 文件节点
            node = alias_to_node.get(tgt)
            if node is not None:
                modules_by_id[src].internal_imports.append(node.path)
            else:
                # 未解析到项目内文件 → 视为外部依赖
                modules_by_id[src].external_imports.append(tgt[len("module:"):])
        # unresolved:* 忽略

    # 去重
    for mi in result.modules:
        mi.internal_imports = list(dict.fromkeys(mi.internal_imports))
        mi.external_imports = list(dict.fromkeys(mi.external_imports))

    # 循环依赖检测（复用 AST 路径的同一算法，节点标识=路径）
    result.circular_deps = _detect_circular_deps(result.modules)

    return result


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
        """前置条件：项目路径存在；有索引或有 Python 文件

        有索引时支持多语言（Python/JS-TS/Go），无索引时退回 Python AST。
        """
        if not context.project_path.exists() or not context.project_path.is_dir():
            return False
        # 有索引 → 多语言可分析
        if (context.project_path / ".smartdev" / "index.sqlite").exists():
            return True
        # 无索引 → 退回 Python AST，需有 Python 文件
        return any(context.project_path.rglob("*.py"))

    def run(self, context, inputs: dict | None = None) -> SkillResult:
        """执行架构分析

        Phase 8 Step 2：优先用索引 relations 构建多语言依赖图，
        无索引（或索引无 module artifact）时退回 Python AST。
        """
        project = context.project_path

        # 数据源选择：索引优先，AST fallback
        analysis = None
        source = "ast"
        index = get_index_if_available(project)
        if index is not None:
            try:
                analysis = _analyze_from_index(index.store, project)
                if analysis is not None:
                    source = "index"
            except Exception:
                analysis = None
            finally:
                index.close()

        if analysis is None:
            analysis = detect_modules(project)
            source = "ast"

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
            f"数据源：{'索引（多语言）' if source == 'index' else 'Python AST'}",
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
                "source": source,
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
                    "max_depth": max(
                        (m.name.replace("/", ".").count(".") for m in analysis.modules),
                        default=0,
                    ),
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
