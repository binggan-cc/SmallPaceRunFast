"""
Phase 9 Step 3 — code.apply Skill 测试

验证：
1. 自动注册 + 元数据
2. patch_id 必须
3. patch_not_found 处理
4. 正常 apply（写盘 + 备份 + changed_files）
5. hash 不一致 → 拒绝（P0-2）
6. protected_paths → 拒绝
7. R3 未提供确认 → 拒绝（P0-4）
8. R3 提供正确确认 → 应用
9. 审计（runs 表写入）
10. 不落地（未调 code.apply 时文件不变）
"""

from pathlib import Path

import pytest

from smartdev.models import ProjectContext, RiskLevel, TaskType
from smartdev.skills.base import Skill


class TestCodeApplyMeta:
    def test_registered(self):
        import smartdev.skills  # noqa: F401
        assert "code.apply" in Skill.get_registry()

    def test_metadata(self):
        skill = Skill.create("code.apply")
        assert skill.risk_level == RiskLevel.R2
        assert skill.task_type == TaskType.FEATURE


class TestCodeApplyInputs:
    def test_missing_patch_id(self, tmp_path: Path):
        skill = Skill.create("code.apply")
        result = skill.run(ProjectContext(project_path=tmp_path, task_description=""), {})
        assert result.success is False
        assert "patch_id" in result.data.get("error", "")

    def test_patch_not_found(self, tmp_path: Path):
        skill = Skill.create("code.apply")
        result = skill.run(
            ProjectContext(project_path=tmp_path, task_description=""),
            {"patch_id": "nonexistent-id-xyz"},
        )
        assert result.success is False
        assert "patch_not_found" in result.data.get("error", "")


class TestCodeApplySuccess:
    def _setup(self, tmp_path: Path):
        """建立带索引的项目 + propose patch_id，返回 (project, patch_id)"""
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "a.css").write_text("color: #22C55E;\n")
        (proj / "b.css").write_text("bg: #22C55E;\n")

        # propose
        from smartdev.skills.base import Skill as _Skill
        import smartdev.skills  # noqa: F401

        context = ProjectContext(project_path=proj, task_description="统一主色")
        propose_result = _Skill.create("code.patch").run(context, {
            "find": "#22C55E",
            "replace": "var(--accent)",
            "glob": "**/*.css",
        })
        patch_id = propose_result.data["patch_id"]
        return proj, patch_id

    def test_apply_writes_files(self, tmp_path: Path):
        proj, patch_id = self._setup(tmp_path)
        skill = Skill.create("code.apply")
        result = skill.run(ProjectContext(project_path=proj, task_description=""), {
            "patch_id": patch_id,
        })
        assert result.success
        assert "var(--accent)" in (proj / "a.css").read_text()
        assert "var(--accent)" in (proj / "b.css").read_text()

    def test_apply_creates_backup(self, tmp_path: Path):
        proj, patch_id = self._setup(tmp_path)
        original = (proj / "a.css").read_text()
        skill = Skill.create("code.apply")
        result = skill.run(ProjectContext(project_path=proj, task_description=""), {
            "patch_id": patch_id,
        })
        backup_dir = Path(result.data["backup_path"])
        assert (backup_dir / "a.css").exists()
        assert (backup_dir / "a.css").read_text() == original

    def test_apply_changed_files(self, tmp_path: Path):
        proj, patch_id = self._setup(tmp_path)
        skill = Skill.create("code.apply")
        result = skill.run(ProjectContext(project_path=proj, task_description=""), {
            "patch_id": patch_id,
        })
        assert len(result.changed_files) == 2

    def test_apply_audits_runs_table(self, tmp_path: Path):
        """apply 后审计记录写入 runs 表（若索引存在）"""
        proj, patch_id = self._setup(tmp_path)
        # 建立索引使审计生效
        from smartdev.context.project_index import ProjectIndex
        idx = ProjectIndex(proj)
        idx.index()
        idx.close()

        skill = Skill.create("code.apply")
        skill.run(ProjectContext(project_path=proj, task_description=""), {
            "patch_id": patch_id,
        })

        # 检查 runs 表
        import sqlite3
        conn = sqlite3.connect(str(proj / ".smartdev" / "index.sqlite"))
        rows = conn.execute(
            "SELECT task FROM runs WHERE task = 'code.apply'"
        ).fetchall()
        conn.close()
        assert len(rows) >= 1


class TestCodeApplyGuards:
    def _make_patch(self, proj: Path) -> str:
        import smartdev.skills  # noqa: F401

        (proj / "a.css").write_text("color: #22C55E;\n")
        context = ProjectContext(project_path=proj, task_description="test")
        result = Skill.create("code.patch").run(context, {
            "find": "#22C55E",
            "replace": "v",
            "glob": "**/*.css",
        })
        return result.data["patch_id"]

    def test_hash_mismatch_rejected(self, tmp_path: Path):
        """propose 后文件被修改 → apply 拒绝（P0-2）"""
        proj = tmp_path / "proj"
        proj.mkdir()
        patch_id = self._make_patch(proj)

        # 模拟文件在 propose/apply 之间被外部改动
        (proj / "a.css").write_text("totally different content\n")

        skill = Skill.create("code.apply")
        result = skill.run(ProjectContext(project_path=proj, task_description=""), {
            "patch_id": patch_id,
        })
        assert result.success is False
        assert result.data["rejected_files"]

    def test_protected_path_rejected(self, tmp_path: Path):
        """patch 命中 .git → 拒绝"""
        from smartdev.core.patch import Patch, FilePatch, PatchAction, save_patch

        proj = tmp_path / "proj"
        proj.mkdir()
        fp = FilePatch(
            file_path=".git/config",
            action=PatchAction.MODIFY,
            reason="test",
            old_content="x\n",
            new_content="y\n",
        )
        patch = Patch(task_description="bad", files=[fp])
        patches_dir = proj / ".smartdev" / "patches"
        patch_id = save_patch(patch, patches_dir)

        skill = Skill.create("code.apply")
        result = skill.run(ProjectContext(project_path=proj, task_description=""), {
            "patch_id": patch_id,
        })
        assert result.success is False
        assert "protected_path" in result.data.get("error", "")

    def test_r3_without_confirm_rejected(self, tmp_path: Path):
        """R3 patch 未提供确认串 → 拒绝"""
        from smartdev.core.patch import Patch, FilePatch, PatchAction, save_patch

        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "a.py").write_text("x = 1\n")
        fp = FilePatch(
            file_path="a.py",
            action=PatchAction.MODIFY,
            reason="test",
            old_content="x = 1\n",
            new_content="x = 2\n",
        )
        from smartdev.core.patch import compute_content_hash
        fp.old_hash = compute_content_hash("x = 1\n")
        patch = Patch(task_description="r3 test", files=[fp], risk_level="R3")
        patch_id = save_patch(patch, proj / ".smartdev" / "patches")

        skill = Skill.create("code.apply")
        result = skill.run(ProjectContext(project_path=proj, task_description=""), {
            "patch_id": patch_id,
            # 不提供 confirm_risk_r3
        })
        assert result.success is False
        assert "r3_confirmation_required" in result.data.get("error", "")

    def test_r3_with_correct_confirm_applies(self, tmp_path: Path):
        """R3 patch 提供正确确认串 → 应用"""
        from smartdev.core.patch import (
            Patch, FilePatch, PatchAction, save_patch, compute_content_hash
        )

        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "a.py").write_text("x = 1\n")
        fp = FilePatch(
            file_path="a.py",
            action=PatchAction.MODIFY,
            reason="test",
            old_content="x = 1\n",
            new_content="x = 2\n",
        )
        fp.old_hash = compute_content_hash("x = 1\n")
        patch = Patch(task_description="r3 apply", files=[fp], risk_level="R3")
        patch_id = save_patch(patch, proj / ".smartdev" / "patches")

        skill = Skill.create("code.apply")
        result = skill.run(ProjectContext(project_path=proj, task_description=""), {
            "patch_id": patch_id,
            "confirm_risk_r3": "APPLY R3",
        })
        assert result.success
        assert (proj / "a.py").read_text() == "x = 2\n"
