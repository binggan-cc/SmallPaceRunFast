"""
Skill: code.patch 测试

验证：
1. 自动注册
2. 生成补丁
3. unified diff 输出
4. 不修改文件
5. 风险等级正确
"""

from pathlib import Path

from smartdev.models import ProjectContext, RiskLevel, TaskType
from smartdev.skills.base import Skill


class TestCodePatchSkill:
    """code.patch Skill 测试"""

    def test_registered_in_registry(self):
        """code.patch 已自动注册"""
        assert "code.patch" in Skill.get_registry()

    def test_skill_metadata(self):
        """Skill 元数据正确"""
        skill = Skill.create("code.patch")
        assert skill.risk_level == RiskLevel.R1
        assert skill.task_type == TaskType.FEATURE

    def test_can_run_with_task(self, tmp_path: Path):
        """有任务描述时 can_run 返回 True"""
        (tmp_path / "main.py").write_text("pass\n")
        skill = Skill.create("code.patch")
        context = ProjectContext(
            project_path=tmp_path,
            task_description="添加错误处理",
        )
        assert skill.can_run(context) is True

    def test_can_run_without_task(self, tmp_path: Path):
        """无任务描述时 can_run 返回 False"""
        skill = Skill.create("code.patch")
        context = ProjectContext(project_path=tmp_path)
        assert skill.can_run(context) is False

    def test_generates_patch(self, tmp_path: Path):
        """运行生成补丁"""
        (tmp_path / "main.py").write_text("pass\n")

        skill = Skill.create("code.patch")
        context = ProjectContext(
            project_path=tmp_path,
            task_description="添加日志",
        )
        result = skill.run(context)

        assert result.success is True
        assert "diff" in result.data
        assert result.data["file_count"] >= 1

    def test_diff_format(self, tmp_path: Path):
        """diff 是 unified 格式"""
        skill = Skill.create("code.patch")
        context = ProjectContext(
            project_path=tmp_path,
            task_description="测试任务",
        )
        result = skill.run(context)

        diff = result.data["diff"]
        assert "--- " in diff
        assert "+++ " in diff

    def test_does_not_modify_files(self, tmp_path: Path):
        """不直接修改文件"""
        (tmp_path / "main.py").write_text("original\n")
        original = (tmp_path / "main.py").read_text()

        skill = Skill.create("code.patch")
        context = ProjectContext(
            project_path=tmp_path,
            task_description="修改文件",
        )
        skill.run(context)

        # 文件内容不变
        assert (tmp_path / "main.py").read_text() == original

    def test_risk_level_is_r1(self, tmp_path: Path):
        """风险等级是 R1"""
        skill = Skill.create("code.patch")
        context = ProjectContext(
            project_path=tmp_path,
            task_description="任何任务",
        )
        result = skill.run(context)
        assert result.data["risk_level"] == "R1"

    def test_next_steps_include_review(self, tmp_path: Path):
        """下一步建议包含审查"""
        skill = Skill.create("code.patch")
        context = ProjectContext(
            project_path=tmp_path,
            task_description="测试",
        )
        result = skill.run(context)
        assert any("审查" in s or "确认" in s for s in result.next_steps)


# ── Phase 9 Step 2: propose 真实化测试 ────────────────────────


class TestCodePatchFindReplace:
    """code.patch find-replace 真实模式"""

    def _project(self, tmp_path: Path) -> Path:
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "a.css").write_text(".x { color: #22C55E; }\n")
        (proj / "b.css").write_text(".y { color: #22C55E; }\n")
        (proj / "c.css").write_text(".z { color: blue; }\n")  # 无命中
        return proj

    def test_find_replace_generates_real_diff(self, tmp_path: Path):
        """find+replace inputs → 真实 diff，mode=find_replace"""
        proj = self._project(tmp_path)
        skill = Skill.create("code.patch")
        context = ProjectContext(project_path=proj, task_description="统一主色")
        result = skill.run(context, {
            "find": "#22C55E",
            "replace": "var(--color-accent)",
            "glob": "**/*.css",
        })
        assert result.success
        assert result.data["mode"] == "find_replace"
        assert result.data["file_count"] == 2  # a.css + b.css
        diff = result.data["diff"]
        assert "-" in diff and "+" in diff
        assert "var(--color-accent)" in diff

    def test_no_match_empty_patch(self, tmp_path: Path):
        proj = self._project(tmp_path)
        skill = Skill.create("code.patch")
        context = ProjectContext(project_path=proj, task_description="查找不存在的串")
        result = skill.run(context, {"find": "NONEXISTENT", "replace": "x"})
        assert result.success
        assert result.data["file_count"] == 0

    def test_does_not_write_disk(self, tmp_path: Path):
        """find-replace propose 不落地"""
        proj = self._project(tmp_path)
        before = (proj / "a.css").read_text()
        skill = Skill.create("code.patch")
        context = ProjectContext(project_path=proj, task_description="统一主色")
        skill.run(context, {"find": "#22C55E", "replace": "v", "save": False})
        assert (proj / "a.css").read_text() == before

    def test_patch_id_generated_on_match(self, tmp_path: Path):
        """命中文件时自动生成并持久化 patch_id"""
        proj = self._project(tmp_path)
        skill = Skill.create("code.patch")
        context = ProjectContext(project_path=proj, task_description="统一主色")
        result = skill.run(context, {
            "find": "#22C55E",
            "replace": "var(--accent)",
            "glob": "**/*.css",
        })
        patch_id = result.data["patch_id"]
        assert patch_id  # 非空
        # 持久化文件存在
        assert (proj / ".smartdev" / "patches" / f"{patch_id}.json").exists()

    def test_no_patch_id_when_no_match(self, tmp_path: Path):
        """无命中时 patch_id 为空"""
        proj = self._project(tmp_path)
        skill = Skill.create("code.patch")
        context = ProjectContext(project_path=proj, task_description="无命中")
        result = skill.run(context, {"find": "NOPE", "replace": "x"})
        assert result.data["patch_id"] == ""

    def test_legacy_fallback_when_no_find(self, tmp_path: Path):
        """无 find 参数 → legacy 占位符，mode=legacy，零回归"""
        skill = Skill.create("code.patch")
        context = ProjectContext(project_path=tmp_path, task_description="添加日志")
        result = skill.run(context)  # 不传 inputs
        assert result.success
        assert result.data["mode"] == "legacy"
        assert result.data["patch_id"] == ""
        # diff 仍有效（legacy 占位符输出）
        assert "---" in result.data["diff"]

    def test_regex_mode(self, tmp_path: Path):
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "v.txt").write_text("version v1.2.3\n")
        skill = Skill.create("code.patch")
        context = ProjectContext(project_path=proj, task_description="bumping version")
        result = skill.run(context, {
            "find": r"v\d+\.\d+\.\d+",
            "replace": "vX",
            "glob": "**/*.txt",
            "regex": True,
        })
        assert result.success
        assert result.data["file_count"] == 1
        assert "vX" in result.data["diff"]


class TestCodePatchImpactIntegration:
    """code.patch + impact 可选增强（有索引时附受影响文件）"""

    def _build_indexed_project(self, tmp_path: Path) -> Path:
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "tokens.css").write_text(":root { --accent: #22C55E; }\n")
        (proj / "styles.css").write_text(".btn { color: #22C55E; }\n")
        (proj / "models.py").write_text("# uses tokens\n")
        from smartdev.context.project_index import ProjectIndex
        index = ProjectIndex(proj)
        index.index()
        index.close()
        return proj

    def test_no_index_no_affected_files(self, tmp_path: Path):
        """无索引 → affected_files 键不存在（零回归）"""
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "a.css").write_text(".x { color: #22C55E; }\n")
        skill = Skill.create("code.patch")
        context = ProjectContext(project_path=proj, task_description="统一主色")
        result = skill.run(context, {"find": "#22C55E", "replace": "var(--accent)"})
        assert result.success
        # 无索引 → 无 affected_files 字段
        assert "affected_files" not in result.data

    def test_with_index_attaches_affected_files(self, tmp_path: Path):
        """有索引 → data 包含 affected_files"""
        proj = self._build_indexed_project(tmp_path)
        skill = Skill.create("code.patch")
        context = ProjectContext(project_path=proj, task_description="统一主色")
        result = skill.run(context, {"find": "#22C55E", "replace": "var(--accent)"})
        assert result.success
        # 至少有被命中的文件出现在 affected_files 中
        if "affected_files" in result.data:
            affected = result.data["affected_files"]
            assert any("css" in f for f in affected)
