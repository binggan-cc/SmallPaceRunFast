"""
Skill: code.rollback — 回滚补丁（R1）

功能：从 apply 产生的备份目录恢复文件，撤销上一次 apply。
风险：R1（恢复文件，不引入新变更）

对应文档：docs/phase-9-design.md §3 Q3（回滚方案）
"""

from __future__ import annotations

from pathlib import Path

from smartdev.core.patch import rollback_patch
from smartdev.models import RiskLevel, SkillResult, TaskType
from smartdev.skills.base import Skill


class CodeRollbackSkill(Skill):
    """补丁回滚 Skill

    从 code.apply 产生的备份目录恢复所有文件。

    inputs 参数：
        backup_path: str    必须，apply 时输出的 backup_path

    使用示例：
        result = Skill.create("code.rollback").run(context, {
            "backup_path": ".smartdev/patch_backups/20260607-123456-abcd1234",
        })
    """

    name = "code.rollback"
    description = "从备份恢复文件，撤销 code.apply 的改动（R1）"
    risk_level = RiskLevel.R1
    task_type = TaskType.FEATURE

    def can_run(self, context) -> bool:
        return (
            context.project_path.exists()
            and context.project_path.is_dir()
        )

    def run(self, context, inputs: dict | None = None) -> SkillResult:
        inputs = inputs or {}
        project = context.project_path
        backup_path_str = inputs.get("backup_path", "")

        if not backup_path_str:
            return SkillResult(
                success=False,
                summary="code.rollback 失败：必须提供 backup_path（来自 code.apply 的输出）",
                data={"error": "missing_backup_path"},
                risks=["未提供 backup_path"],
            )

        # 支持相对路径（相对于 project_path）和绝对路径
        backup_dir = Path(backup_path_str)
        if not backup_dir.is_absolute():
            backup_dir = project / backup_dir

        result = rollback_patch(backup_dir, project)

        if result.success:
            summary = (
                f"回滚成功：已恢复 {len(result.restored_files)} 个文件\n"
                f"备份来源: {backup_dir}"
            )
        else:
            summary = f"回滚失败：{'; '.join(result.errors)}"

        return SkillResult(
            success=result.success,
            summary=summary,
            data={
                "backup_path": str(backup_dir),
                "restored_files": result.restored_files,
                "errors": result.errors,
            },
            changed_files=result.restored_files,
            risks=result.errors or [],
            next_steps=(
                ["请验证文件已恢复到 apply 前的状态", "运行项目测试确认回滚正确"]
                if result.success
                else ["检查备份路径是否正确", "如备份丢失，可使用 git 恢复"]
            ),
        )
