"""
Skill: diff.explain — Patch 级差异解释（R0 只读）

功能：对 patch 文件列表和 diff 内容做确定性结构化解释：
      - 逻辑分组（按目录层级将文件分组）
      - 测试伴随（检查是否有对应测试文件）
      - 依赖匹配（manifest 变更 ↔ 源码变更）
      - 跨模块检测
      - 审查顺序建议

风险：R0（只读，不修改任何文件）

设计约束（docs/phase-11b-design.md §3.5）：
- 确定性规则引擎，不调用模型
- 与 git.diff.explain 互补：git.diff.explain 面向仓库级 working tree，
  diff.explain 面向显式传入的 patch 文件列表和 diff 内容
- 无 git 环境也能运行（基于显式输入）
- 支持消费 base_signals（如 git.diff.explain 既有输出）作为补充信号
"""

from __future__ import annotations

from pathlib import Path

from smartdev.core.guard_diff_explain import DiffExplainResult, explain_diff
from smartdev.models import RiskLevel, SkillResult, TaskType
from smartdev.skills.base import Skill


class DiffExplainPatchSkill(Skill):
    """Patch 级差异解释 Skill（R0 只读）

    对 patch 文件列表和可选 diff 内容做确定性结构化解释。
    输出逻辑分组、测试伴随、依赖匹配、跨模块检测和审查顺序建议。

    inputs 参数：
        patch_files:  list[str]      — 变更文件列表（必需）
        diff_content: str | None     — unified diff 文本（可选）
        project_path: str | Path | None — 项目根目录（可选）
        base_signals: dict | None    — 外部既有信号（可选，合并但不覆盖本地信号）

    使用示例：
        result = Skill.create("diff.explain").run(context, {
            "patch_files": ["core/git.py", "tests/test_git.py"],
            "diff_content": "...unified diff...",
        })
    """

    name = "diff.explain"
    description = "Patch 级差异解释：逻辑分组/测试伴随/依赖匹配/跨模块检测/审查顺序建议"
    risk_level = RiskLevel.R0
    task_type = TaskType.DIAGNOSE

    def can_run(self, context) -> bool:
        # diff.explain 不依赖 git，任何时候都能运行
        return True

    def run(self, context, inputs: dict | None = None) -> SkillResult:
        inputs = inputs or {}

        patch_files: list[str] = inputs.get("patch_files", [])
        diff_content: str | None = inputs.get("diff_content")
        project_path_raw = inputs.get("project_path")
        base_signals: dict | None = inputs.get("base_signals")

        # 处理 project_path：支持 str 和 Path
        project_path: Path | None = None
        if project_path_raw:
            if isinstance(project_path_raw, str):
                project_path = Path(project_path_raw)
            elif isinstance(project_path_raw, Path):
                project_path = project_path_raw

        if not patch_files:
            return SkillResult(
                success=True,
                summary="diff.explain：无 patch 文件，跳过分析",
                data={
                    "summary": {
                        "files_changed": 0,
                        "insertions": 0,
                        "deletions": 0,
                        "logical_groups": 0,
                    },
                    "signals": {
                        "touches_tests": False,
                        "touches_docs": False,
                        "touches_dependency_manifest": False,
                        "touches_protected_path": False,
                        "protected_path_hits": [],
                        "touches_core": False,
                        "touches_mcp": False,
                        "cross_module": False,
                        "cross_module_count": 0,
                        "has_diff_content": False,
                    },
                    "file_categories": {
                        "source": [], "test": [], "doc": [],
                        "manifest": [], "config": [],
                        "core": [], "mcp": [], "other": [],
                    },
                    "logical_groups": [],
                    "risk_hints": [],
                    "test_coverage": {
                        "has_related_tests": False,
                        "test_files_touched": 0,
                        "untested_changed_modules": [],
                        "covered_modules": [],
                    },
                    "suggested_review_order": [],
                },
            )

        result: DiffExplainResult = explain_diff(
            patch_files=patch_files,
            diff_content=diff_content,
            project_path=project_path,
            base_signals=base_signals,
        )

        # 构建 next_steps
        next_steps: list[str] = []
        if result.risk_hints:
            next_steps.append(
                f"检测到 {len(result.risk_hints)} 个风险信号：{'; '.join(result.risk_hints)}"
            )
        if result.test_coverage.get("untested_changed_modules"):
            untested = "、".join(result.test_coverage["untested_changed_modules"])
            next_steps.append(f"建议为 {untested} 补充测试")
        if result.signals.get("cross_module"):
            next_steps.append(
                "跨模块变更建议拆分为多次小改动以减少风险"
            )
        if not result.risk_hints and not result.test_coverage.get("untested_changed_modules"):
            next_steps.append("变更结构清晰，可按建议顺序审查。")

        # 构建摘要
        n = result.summary["files_changed"]
        groups = result.summary["logical_groups"]
        parts = [f"diff.explain：{n} 个文件，{groups} 个逻辑分组"]
        if result.summary["insertions"] or result.summary["deletions"]:
            parts.append(
                f"+{result.summary['insertions']} -{result.summary['deletions']} 行"
            )
        if result.risk_hints:
            parts.append(f"{len(result.risk_hints)} 个风险信号")

        return SkillResult(
            success=True,
            summary="，".join(parts),
            data=result.to_dict(),
            risks=result.risk_hints,
            next_steps=next_steps,
        )
