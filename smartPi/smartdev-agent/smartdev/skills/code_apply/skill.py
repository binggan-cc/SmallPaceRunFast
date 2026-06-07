"""
Skill: code.apply — 应用补丁（写盘，R2/R3）

功能：加载已持久化的 patch_id → 权限门校验 → apply_patch() → 审计。
风险：R2（多文件写盘）/ R3（命中核心模块/protected_path 时）

设计约束（phase-9-design.md P0-1~P0-4）：
- 必须使用已 propose 的 patch（加载 patch_id），不重新扫描（防 TOCTOU）
- apply 前校验 old_hash（P0-2）
- 路径安全（P0-3）
- R3 强确认：inputs["confirm_risk_r3"] == "APPLY R3"（P0-4）
- protected_paths 命中 → 拒绝
- 写盘后审计记录到 runs 表
- 禁止绕过此 Skill 直调 core.patch.apply_patch()

对应文档：docs/phase-9-design.md §3、§4
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from smartdev.core.patch import apply_patch, load_patch
from smartdev.models import RiskLevel, SkillResult, TaskType
from smartdev.skills.base import Skill


# protected_paths 来自 adapter；若无 adapter 使用通用保护名单
_DEFAULT_PROTECTED = {
    ".git", ".smartdev", "node_modules",
    "dist", "build", "target", "vendor",
}

_R3_CONFIRM_TOKEN = "APPLY R3"


def _is_protected(file_path: str, protected: set[str]) -> bool:
    """检查文件路径的第一个目录段是否在 protected 集合中。"""
    first = Path(file_path).parts[0] if Path(file_path).parts else ""
    return first in protected or file_path in protected


def _get_protected_paths(context) -> set[str]:
    """从 adapter 或环境获取 protected paths。"""
    # 若后续 adapter 机制扩展，可从 context.adapter_name 加载 JSON
    return _DEFAULT_PROTECTED


def _write_audit(project_path: Path, patch_id: str,
                 applied_files: list[str], backup_path: str) -> None:
    """写审计记录到 .smartdev/index.sqlite runs 表（若索引存在）。"""
    db_path = project_path / ".smartdev" / "index.sqlite"
    if not db_path.exists():
        return
    try:
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        run_id = f"apply-{patch_id}-{int(time.time())}"
        summary = json.dumps({
            "patch_id": patch_id,
            "applied_files": applied_files,
            "backup_path": backup_path,
        }, ensure_ascii=False)
        conn.execute(
            "INSERT OR REPLACE INTO runs (id, task, created_at, summary_json) VALUES (?, ?, ?, ?)",
            (run_id, "code.apply", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), summary),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # 审计失败不阻断 apply


class CodeApplySkill(Skill):
    """代码补丁应用 Skill（写盘，R2/R3）

    加载 patch_id → 权限校验 → 写盘 → 审计。
    首个真正修改用户代码的 Skill。

    inputs 参数：
        patch_id: str           必须，已 propose 的 patch_id
        confirm_risk_r3: str    仅当风险 R3 时必须提供 "APPLY R3"（P0-4）
        backup_subdir: str      备份子目录名（默认使用 patch_id）

    使用示例：
        result = Skill.create("code.apply").run(context, {
            "patch_id": "20260607-123456-abcd1234",
        })
    """

    name = "code.apply"
    description = "应用已持久化的 patch 到磁盘（R2，需 patch_id）"
    risk_level = RiskLevel.R2
    task_type = TaskType.FEATURE

    def can_run(self, context) -> bool:
        return (
            context.project_path.exists()
            and context.project_path.is_dir()
        )

    def run(self, context, inputs: dict | None = None) -> SkillResult:
        inputs = inputs or {}
        project = context.project_path
        patch_id = inputs.get("patch_id", "")
        confirm_r3 = inputs.get("confirm_risk_r3", "")
        backup_subdir = inputs.get("backup_subdir", patch_id or "latest")

        # ── 1. patch_id 必须 ──────────────────────────────
        if not patch_id:
            return SkillResult(
                success=False,
                summary="code.apply 失败：必须提供 patch_id（来自 code.patch 的输出）",
                data={"error": "missing_patch_id"},
                risks=["未提供 patch_id"],
            )

        # ── 2. 加载 patch（P0-1：不重新扫描）─────────────
        patches_dir = project / ".smartdev" / "patches"
        patch = load_patch(patch_id, patches_dir)
        if patch is None:
            return SkillResult(
                success=False,
                summary=f"code.apply 失败：找不到 patch_id={patch_id}，请重新运行 code.patch",
                data={"error": "patch_not_found", "patch_id": patch_id},
                risks=["patch 不存在或已损坏，请重新 propose"],
            )

        # ── 3. protected_paths 校验 ───────────────────────
        protected = _get_protected_paths(context)
        protected_hits = [
            fp.file_path for fp in patch.files
            if _is_protected(fp.file_path, protected)
        ]
        if protected_hits:
            return SkillResult(
                success=False,
                summary=(
                    f"code.apply 拒绝：patch 命中 protected_paths: {protected_hits}。"
                    "这些路径需要人工处理。"
                ),
                data={"error": "protected_path", "rejected": protected_hits},
                risks=[f"protected_path 拒绝: {protected_hits}"],
            )

        # ── 4. 确定实际风险等级 ───────────────────────────
        # patch 的 risk_level（由 propose 时 impact 分析填充）
        is_r3 = (patch.risk_level == "R3")

        # ── 5. R3 强确认（P0-4）──────────────────────────
        if is_r3 and confirm_r3 != _R3_CONFIRM_TOKEN:
            return SkillResult(
                success=False,
                summary=(
                    f"code.apply 拒绝：风险等级 R3，需要强确认。\n"
                    f"请在 inputs 中提供 confirm_risk_r3='{_R3_CONFIRM_TOKEN}' 后重试。"
                ),
                data={
                    "error": "r3_confirmation_required",
                    "required_token": _R3_CONFIRM_TOKEN,
                    "risk_level": "R3",
                    "affected_files": patch.affected_files,
                },
                risks=["R3 操作需要强确认，未提供确认串"],
            )

        # ── 6. 执行 apply（backup + P0-2 hash 校验 + 写盘）
        backup_dir = project / ".smartdev" / "patch_backups" / backup_subdir
        apply_result = apply_patch(patch, project, backup_dir)

        # ── 7. 审计 ───────────────────────────────────────
        if apply_result.applied_files:
            _write_audit(project, patch_id, apply_result.applied_files, str(backup_dir))

        # ── 8. 输出 ───────────────────────────────────────
        if apply_result.success:
            summary = (
                f"补丁应用成功：{patch.task_description}\n"
                f"已应用 {len(apply_result.applied_files)} 个文件\n"
                f"备份路径: {backup_dir}"
            )
            next_steps = [
                "请运行项目测试验证变更",
                f"如需回滚，运行 code.rollback --backup-path {backup_dir}",
            ]
        else:
            summary = (
                f"补丁应用{'部分失败' if apply_result.applied_files else '失败'}："
                f"{apply_result.summary()}"
            )
            next_steps = [
                f"检查被拒绝的文件: {[p for p, _ in apply_result.rejected_files]}",
                "如需，重新运行 code.patch propose 并重试",
            ]

        return SkillResult(
            success=apply_result.success,
            summary=summary,
            data={
                "patch_id": patch_id,
                "applied_files": apply_result.applied_files,
                "skipped_files": [p for p, _ in apply_result.skipped_files],
                "rejected_files": [(p, r) for p, r in apply_result.rejected_files],
                "backup_path": str(backup_dir),
                "risk_level": patch.risk_level,
                "errors": apply_result.errors,
            },
            changed_files=apply_result.applied_files,
            risks=apply_result.errors or (
                [f"R{patch.risk_level} 写盘操作，备份路径: {backup_dir}"]
                if apply_result.success else []
            ),
            next_steps=next_steps,
        )
