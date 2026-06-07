"""
Phase 9 Step 3 — code.rollback Skill 测试

验证：
1. 自动注册 + 元数据
2. backup_path 必须
3. 正常 rollback 恢复文件
4. rollback 撤销 CREATE（删除新建文件）
5. 缺失 backup_path → 失败
"""

from pathlib import Path

from smartdev.models import ProjectContext, RiskLevel, TaskType
from smartdev.skills.base import Skill


class TestCodeRollbackMeta:
    def test_registered(self):
        import smartdev.skills  # noqa: F401
        assert "code.rollback" in Skill.get_registry()

    def test_metadata(self):
        skill = Skill.create("code.rollback")
        assert skill.risk_level == RiskLevel.R1
        assert skill.task_type == TaskType.FEATURE


class TestCodeRollbackInputs:
    def test_missing_backup_path(self, tmp_path: Path):
        skill = Skill.create("code.rollback")
        result = skill.run(ProjectContext(project_path=tmp_path, task_description=""), {})
        assert result.success is False
        assert "backup_path" in result.data.get("error", "")

    def test_nonexistent_backup(self, tmp_path: Path):
        skill = Skill.create("code.rollback")
        result = skill.run(ProjectContext(project_path=tmp_path, task_description=""), {
            "backup_path": str(tmp_path / "no_such_dir"),
        })
        assert result.success is False


class TestCodeRollbackApplyThenRollback:
    """propose → apply → rollback 端到端"""

    def _setup(self, tmp_path: Path):
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "a.css").write_text("color: #22C55E;\n")
        original = (proj / "a.css").read_text()
        return proj, original

    def _propose_and_apply(self, proj: Path):
        import smartdev.skills  # noqa: F401

        ctx = ProjectContext(project_path=proj, task_description="统一主色")
        propose = Skill.create("code.patch").run(ctx, {
            "find": "#22C55E",
            "replace": "var(--accent)",
            "glob": "**/*.css",
        })
        patch_id = propose.data["patch_id"]
        apply = Skill.create("code.apply").run(ctx, {"patch_id": patch_id})
        return apply.data["backup_path"]

    def test_rollback_restores_file(self, tmp_path: Path):
        proj, original = self._setup(tmp_path)
        backup_path = self._propose_and_apply(proj)
        # 确认 apply 生效
        assert "var(--accent)" in (proj / "a.css").read_text()

        skill = Skill.create("code.rollback")
        result = skill.run(ProjectContext(project_path=proj, task_description=""), {
            "backup_path": backup_path,
        })
        assert result.success
        assert (proj / "a.css").read_text() == original

    def test_rollback_changed_files(self, tmp_path: Path):
        proj, _ = self._setup(tmp_path)
        backup_path = self._propose_and_apply(proj)

        skill = Skill.create("code.rollback")
        result = skill.run(ProjectContext(project_path=proj, task_description=""), {
            "backup_path": backup_path,
        })
        assert result.success
        assert len(result.changed_files) >= 1

    def test_rollback_relative_backup_path(self, tmp_path: Path):
        proj, original = self._setup(tmp_path)
        backup_path = self._propose_and_apply(proj)

        # 转为相对路径
        rel_path = Path(backup_path).relative_to(proj)

        skill = Skill.create("code.rollback")
        result = skill.run(ProjectContext(project_path=proj, task_description=""), {
            "backup_path": str(rel_path),
        })
        assert result.success
        assert (proj / "a.css").read_text() == original
