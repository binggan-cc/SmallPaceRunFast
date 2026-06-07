"""
Skill: code.patch — 代码补丁（propose 模式）

功能：根据 find/replace 生成真实 diff，不直接应用（propose only）。
风险：R1（生成补丁，不落地）
类型：feature / bugfix / refactor

Phase 9 Step 2：真实化
- inputs 提供 find + replace → 调用 build_find_replace_patch（确定性，无 LLM）
- 可选 impact 增强：有索引则附上受影响文件和风险（复用 Phase 8）
- 持久化 patch_id（P0-1 防 TOCTOU）
- 无 find/replace inputs → 退回 legacy 占位符（零回归）

设计约束：
- 不落地（只 propose，apply 在 code.apply Skill）
- 零 LLM，确定性输出（pyproject.toml 明确零外部依赖）

对应文档：
- docs/phase-9-design.md §3（核心问题）
- smartPi/docs/smartdev-agent-core-spec.md §5.6（编码执行）
- smartPi/docs/smartdev-agent-protocol.md §3.4（不扩大范围）
"""

from __future__ import annotations

from pathlib import Path

from smartdev.core.patch import (
    Patch,
    FilePatch,
    PatchAction,
    build_find_replace_patch,
    create_file_patch,
    save_patch,
)
from smartdev.models import RiskLevel, SkillResult, TaskType
from smartdev.skills.base import Skill
from smartdev.skills._context_helper import get_index_if_available


def _legacy_placeholder(task_description: str) -> Patch:
    """Legacy 占位符补丁（无 find/replace inputs 时退回此路径）。

    保留零回归语义：现有测试中不传 find/replace 时，
    输出仍是说明性 note 补丁，不报错。
    """
    note_content = (
        f"# SmartDev Agent — 补丁说明\n"
        f"#\n"
        f"# 任务: {task_description}\n"
        f"#\n"
        f"# 请提供 find 和 replace 参数以生成真实补丁。\n"
        f"# 示例: inputs={{'find': '#22C55E', 'replace': 'var(--color-accent)'}}\n"
    )
    return Patch(
        task_description=task_description,
        files=[FilePatch(
            file_path="smartdev_patch_note.py",
            action=PatchAction.CREATE,
            reason=f"任务「{task_description}」的补丁说明（请提供 find/replace 参数）",
            new_content=note_content,
        )],
        risk_level="R1",
        reasoning="legacy 占位符：未提供 find/replace 参数",
    )


def _try_impact_for_patch(
    patch: Patch, context
) -> tuple[list[str], str]:
    """可选 impact 增强：分析受影响范围（复用 Phase 8 成果）。

    对 patch 每个命中文件查询 import 依赖方，
    合并为 affected_files 列表 + 最终风险等级。
    有索引则增强，无索引退回 patch.risk_level（零回归）。

    返回 (affected_files, final_risk_level)。
    """
    index = get_index_if_available(context.project_path)
    if index is None:
        return [], patch.risk_level

    try:
        from smartdev.context.impact_analyzer import ImpactAnalyzer
        from smartdev.models import RiskLevel
        from smartdev.skills._context_helper import max_risk

        analyzer = ImpactAnalyzer(index.store)
        affected: set[str] = set()
        max_impact_risk = RiskLevel.R0

        for fp in patch.files:
            result = analyzer.analyze_import_impact(fp.file_path)
            affected.update(result.affected_files)
            try:
                impact_risk = RiskLevel(result.risk_level)
                max_impact_risk = max_risk(max_impact_risk, impact_risk)
            except ValueError:
                pass

        # 目标文件本身也算受影响
        for fp in patch.files:
            affected.add(fp.file_path)

        final_risk = max_risk(RiskLevel(patch.risk_level), max_impact_risk)
        return sorted(affected), final_risk.value
    except Exception:
        return [], patch.risk_level
    finally:
        index.close()


class CodePatchSkill(Skill):
    """代码补丁 Skill（propose 模式）

    根据 find/replace 生成真实 diff，持久化 patch_id，不落地。

    使用示例（真实模式）：
        context = ProjectContext(project_path=..., task_description="统一主色")
        result = Skill.create("code.patch").run(context, {
            "find": "#22C55E",
            "replace": "var(--color-accent)",
            "glob": "**/*.css",       # 可选，默认 **/*
        })
        # result.data["patch_id"]      — 后续 apply 用
        # result.data["diff"]          — unified diff
        # result.data["affected_files"]— impact 分析结果（有索引时）

    使用示例（legacy / 无参数）：
        result = Skill.create("code.patch").run(context)
        # 退回说明性占位符，不报错
    """

    name = "code.patch"
    description = "根据 find/replace 生成代码补丁（propose 模式，不直接应用）"
    risk_level = RiskLevel.R1
    task_type = TaskType.FEATURE

    def can_run(self, context) -> bool:
        """前置条件：项目路径存在且有任务描述"""
        return (
            context.project_path.exists()
            and context.project_path.is_dir()
            and bool(context.task_description.strip())
        )

    def run(self, context, inputs: dict | None = None) -> SkillResult:
        """执行补丁生成（propose only）

        inputs 可选参数：
            find: str           查找串（触发真实补丁生成）
            replace: str        替换串
            glob: str           文件匹配 glob（默认 **/*）
            regex: bool         是否按正则匹配（默认 False）
            save: bool          是否持久化 patch_id（默认 True）
        """
        project = context.project_path
        task_description = context.task_description
        inputs = inputs or {}

        find = inputs.get("find", "")
        replace = inputs.get("replace", "")
        glob_pattern = inputs.get("glob", "**/*")
        use_regex = bool(inputs.get("regex", False))
        do_save = bool(inputs.get("save", True))

        # ── 路由 ──────────────────────────────────────────
        if find:
            # 真实模式：find-replace 确定性补丁
            patch = build_find_replace_patch(
                project_path=project,
                find=find,
                replace=replace,
                include_glob=glob_pattern,
                regex=use_regex,
            )
        else:
            # Legacy 模式：占位符（零回归）
            patch = _legacy_placeholder(task_description)
            do_save = False  # 占位符不持久化

        # ── Impact 增强（有索引时）──────────────────────
        affected_files: list[str] = []
        final_risk = patch.risk_level

        if find and patch.file_count > 0:
            affected_files, final_risk = _try_impact_for_patch(patch, context)
            patch.affected_files = affected_files
            patch.risk_level = final_risk

        # ── 持久化 patch_id（P0-1）──────────────────────
        patch_id = ""
        if do_save and patch.file_count > 0:
            patches_dir = project / ".smartdev" / "patches"
            patch_id = save_patch(patch, patches_dir)

        # ── 输出 ─────────────────────────────────────────
        diff = patch.to_unified_diff()
        is_real = bool(find)

        summary_parts = [
            f"补丁生成完成：{task_description}",
            f"模式: {'find-replace' if is_real else 'legacy 占位符'}",
            f"文件数: {patch.file_count}",
            f"总变更: +{patch.total_added} -{patch.total_removed}",
            f"风险等级: {final_risk}",
        ]
        if patch_id:
            summary_parts.append(f"patch_id: {patch_id}")
        if affected_files:
            summary_parts.append(f"影响文件: {len(affected_files)} 个")

        data: dict = {
            "task_description": task_description,
            "mode": "find_replace" if is_real else "legacy",
            "patch_summary": patch.summary(),
            "diff": diff,
            "file_count": patch.file_count,
            "total_added": patch.total_added,
            "total_removed": patch.total_removed,
            "risk_level": final_risk,
            "patch_id": patch_id,
        }
        if affected_files:
            data["affected_files"] = affected_files

        risks = [f"风险等级 {final_risk}：补丁已生成，需用户确认后应用（code.apply）"]
        if not is_real:
            risks.append("当前为 legacy 占位符，请提供 find/replace 参数以生成真实补丁")

        next_steps = ["请审查 diff 内容"]
        if patch_id:
            next_steps.append(f"确认无误后使用 code.apply --patch-id {patch_id} 应用补丁")
        if affected_files:
            next_steps.append(f"注意影响范围：{', '.join(affected_files[:5])}")
        next_steps.append("应用后运行测试验证")

        return SkillResult(
            success=True,
            summary="\n".join(summary_parts),
            data=data,
            risks=risks,
            next_steps=next_steps,
        )
