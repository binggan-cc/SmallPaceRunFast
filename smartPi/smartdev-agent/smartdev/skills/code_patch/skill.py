"""
Skill: code.patch — 代码补丁

功能：根据任务描述生成代码修改补丁，输出为 unified diff。
风险：R1（生成补丁，不直接应用）
类型：feature / bugfix / refactor

设计决策：
- 只生成补丁，不直接修改文件（对应 protocol §6 执行前确认）
- Phase 1 用模板匹配生成补丁，Phase 5 可用 LLM 替换
- 补丁必须包含变更理由（对应 protocol §7 关键变更）

对应文档：
- smartPi/docs/smartdev-agent-core-spec.md §5.6（编码执行）
- smartPi/docs/smartdev-agent-protocol.md §3.4（不扩大改动范围）
"""

from __future__ import annotations

from pathlib import Path

from smartdev.core.patch import Patch, FilePatch, PatchAction, create_file_patch
from smartdev.models import RiskLevel, SkillResult, TaskType
from smartdev.skills.base import Skill


# ── 补丁生成策略 ──────────────────────────────────────────
# Phase 1 用模板匹配，后续可用 LLM 替换
#
# 为什么用模板而非 LLM？
# 1. Phase 1 需要确定性输出，方便测试
# 2. 模板生成的补丁每次一致，不会出现 LLM 的"幻觉"
# 3. LLM 生成的代码可能有语法错误

# 简单的变更模板：任务关键词 → 文件路径 + 修改内容
_PATCH_TEMPLATES: dict[str, list[dict]] = {
    "add_docstring": [
        {
            "description": "为模块添加 docstring",
            "file_pattern": "*.py",
            "risk": "R1",
        },
    ],
    "add_comment": [
        {
            "description": "添加注释说明",
            "file_pattern": "*.py",
            "risk": "R0",
        },
    ],
}


def _read_file_safe(file_path: Path) -> str:
    """安全读取文件内容"""
    try:
        return file_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return ""


def _generate_simple_patch(
    project_path: Path,
    task_description: str,
    target_files: list[str] | None = None,
) -> Patch:
    """生成简单补丁

    Phase 1 的策略：
    1. 如果指定了目标文件，读取并尝试生成补丁
    2. 如果没有指定目标文件，根据任务描述推断

    后续版本可以用 LLM 替换此函数。
    """
    files = []

    if target_files:
        for rel_path in target_files:
            full_path = project_path / rel_path
            if full_path.exists():
                content = _read_file_safe(full_path)
                # Phase 1: 只做文件存在性检查，不实际生成变更
                # 后续版本在这里用 LLM 生成变更
                pass

    # Phase 1 的兜底：输出一个说明性补丁
    # 告诉用户"我理解了任务，但需要更多信息来生成具体补丁"
    note_content = f"""# SmartDev Agent — 补丁说明
#
# 任务: {task_description}
# 生成时间: 自动生成
#
# 该补丁是占位符，表示 Agent 理解了任务需求。
# 实际补丁需要在具体项目上下文中生成。
"""
    files.append(FilePatch(
        file_path="smartdev_patch_note.py",
        action=PatchAction.CREATE,
        reason=f"任务「{task_description}」的补丁说明",
        new_content=note_content,
    ))

    return Patch(
        task_description=task_description,
        files=files,
        risk_level="R1",
        reasoning=f"为任务「{task_description}」生成补丁说明",
    )


class CodePatchSkill(Skill):
    """代码补丁 Skill

    根据任务描述生成代码修改补丁，不直接应用。

    使用示例：
        context = ProjectContext(
            project_path=Path("/path/to/project"),
            task_description="添加错误处理",
        )
        skill = Skill.create("code.patch")
        result = skill.run(context)
        # result.data["diff"] — unified diff 格式的补丁
    """

    name = "code.patch"
    description = "根据任务描述生成代码修改补丁（不直接应用）"
    risk_level = RiskLevel.R1
    task_type = TaskType.FEATURE

    def can_run(self, context) -> bool:
        """前置条件：有任务描述"""
        return (
            context.project_path.exists()
            and context.project_path.is_dir()
            and bool(context.task_description.strip())
        )

    def run(self, context, inputs: dict | None = None) -> SkillResult:
        """执行补丁生成"""
        project = context.project_path
        task_description = context.task_description
        target_files = (inputs or {}).get("target_files")

        # 生成补丁
        patch = _generate_simple_patch(project, task_description, target_files)

        # 转换为 unified diff
        diff = patch.to_unified_diff()

        # 摘要
        summary_parts = [
            f"补丁生成完成：{task_description}",
            f"文件数: {patch.file_count}",
            f"总变更: +{patch.total_added} -{patch.total_removed}",
            f"风险等级: {patch.risk_level}",
        ]

        return SkillResult(
            success=True,
            summary="\n".join(summary_parts),
            data={
                "task_description": task_description,
                "patch_summary": patch.summary(),
                "diff": diff,
                "file_count": patch.file_count,
                "total_added": patch.total_added,
                "total_removed": patch.total_removed,
                "risk_level": patch.risk_level,
            },
            risks=[
                f"R1 操作：补丁已生成，需用户确认后应用",
                "补丁为占位符，实际项目需要更精确的补丁生成",
            ],
            next_steps=[
                "请审查补丁内容（unified diff）",
                "确认无误后，使用 git apply 或手动应用",
                "应用后运行测试验证",
            ],
        )
