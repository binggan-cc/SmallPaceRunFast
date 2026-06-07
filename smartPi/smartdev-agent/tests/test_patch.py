"""
Patch 数据模型测试

验证：
1. FilePatch 创建/修改/删除
2. 行级 diff 计算
3. unified diff 输出
4. Patch 摘要
"""

from smartdev.core.patch import (
    Patch,
    PatchAction,
    FilePatch,
    LineChange,
    compute_line_changes,
    create_file_patch,
)


class TestLineChanges:
    """行级 diff 测试"""

    def test_identical_content(self):
        """相同内容无变更"""
        old = ["line1\n", "line2\n"]
        new = ["line1\n", "line2\n"]
        changes = compute_line_changes(old, new)
        assert all(c.action == "keep" for c in changes)

    def test_added_line(self):
        """新增行"""
        old = ["line1\n"]
        new = ["line1\n", "line2\n"]
        changes = compute_line_changes(old, new)
        adds = [c for c in changes if c.action == "add"]
        assert len(adds) == 1
        assert adds[0].content == "line2\n"

    def test_removed_line(self):
        """删除行"""
        old = ["line1\n", "line2\n"]
        new = ["line1\n"]
        changes = compute_line_changes(old, new)
        removes = [c for c in changes if c.action == "remove"]
        assert len(removes) == 1
        assert removes[0].content == "line2\n"


class TestFilePatch:
    """FilePatch 测试"""

    def test_create_file(self):
        """创建新文件"""
        patch = create_file_patch(
            "new.py",
            "",
            "print('hello')\n",
            reason="新增入口文件",
        )
        assert patch.action == PatchAction.CREATE
        assert patch.added_lines == 1
        assert patch.removed_lines == 0

    def test_modify_file(self):
        """修改文件"""
        patch = create_file_patch(
            "main.py",
            "x = 1\n",
            "x = 2\n",
            reason="修复变量值",
        )
        assert patch.action == PatchAction.MODIFY
        assert patch.added_lines == 1
        assert patch.removed_lines == 1

    def test_delete_file(self):
        """删除文件"""
        patch = create_file_patch(
            "old.py",
            "old code\n",
            "",
            reason="移除废弃代码",
        )
        assert patch.action == PatchAction.DELETE
        assert patch.added_lines == 0
        assert patch.removed_lines == 1

    def test_summary(self):
        """摘要包含关键信息"""
        patch = create_file_patch("a.py", "old\n", "new\n")
        summary = patch.summary()
        assert "a.py" in summary
        assert "+" in summary
        assert "-" in summary

    def test_unified_diff(self):
        """unified diff 格式正确"""
        patch = create_file_patch("a.py", "line1\n", "line1\nline2\n")
        diff = patch.to_unified_diff()
        assert "--- a/a.py" in diff
        assert "+++ b/a.py" in diff
        assert "+line2" in diff


class TestPatch:
    """完整 Patch 测试"""

    def test_patch_summary(self):
        """Patch 摘要包含文件列表"""
        file1 = create_file_patch("a.py", "old\n", "new\n")
        file2 = create_file_patch("b.py", "", "content\n")

        patch = Patch(
            task_description="修复 Bug",
            files=[file1, file2],
            risk_level="R1",
        )

        assert patch.file_count == 2
        summary = patch.summary()
        assert "a.py" in summary
        assert "b.py" in summary

    def test_patch_totals(self):
        """总变更行数正确"""
        file1 = create_file_patch("a.py", "x\n", "x\ny\nz\n")  # +2 行
        file2 = create_file_patch("b.py", "old\n", "new\n")     # -1 +1 行

        patch = Patch(task_description="test", files=[file1, file2])

        assert patch.total_added == 3  # y, z, new
        assert patch.total_removed == 1  # old (from b.py only)

    def test_patch_unified_diff(self):
        """unified diff 包含所有文件"""
        file1 = create_file_patch("a.py", "a\n", "b\n")
        file2 = create_file_patch("b.py", "x\n", "y\n")

        patch = Patch(task_description="test", files=[file1, file2])
        diff = patch.to_unified_diff()

        assert "a/a.py" in diff
        assert "a/b.py" in diff


# ── Phase 9 Step 1A: 可审查草案基础设施测试 ──────────────────

from pathlib import Path

from smartdev.core.patch import (
    build_find_replace_patch,
    compute_content_hash,
    generate_patch_id,
    is_safe_target,
    load_patch,
    save_patch,
)


class TestContentHash:
    """内容 hash（P0-2 基础）"""

    def test_hash_deterministic(self):
        assert compute_content_hash("abc") == compute_content_hash("abc")

    def test_hash_differs_on_change(self):
        assert compute_content_hash("abc") != compute_content_hash("abd")


class TestPathSafety:
    """路径安全过滤（P0-3）"""

    def test_normal_path_safe(self, tmp_path: Path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "a.py").write_text("x = 1\n")
        safe, reason = is_safe_target("src/a.py", tmp_path)
        assert safe is True

    def test_traversal_rejected(self, tmp_path: Path):
        safe, reason = is_safe_target("../outside.py", tmp_path)
        assert safe is False
        assert "traversal" in reason

    def test_skip_dir_rejected(self, tmp_path: Path):
        safe, _ = is_safe_target(".git/config", tmp_path)
        assert safe is False
        safe2, _ = is_safe_target("node_modules/pkg/index.js", tmp_path)
        assert safe2 is False
        safe3, _ = is_safe_target(".smartdev/index.sqlite", tmp_path)
        assert safe3 is False

    def test_binary_rejected(self, tmp_path: Path):
        (tmp_path / "logo.png").write_bytes(b"\x89PNG")
        safe, reason = is_safe_target("logo.png", tmp_path)
        assert safe is False
        assert "二进制" in reason

    def test_symlink_rejected(self, tmp_path: Path):
        target = tmp_path / "real.py"
        target.write_text("x = 1\n")
        link = tmp_path / "link.py"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            return  # 平台不支持 symlink，跳过
        safe, reason = is_safe_target("link.py", tmp_path)
        assert safe is False
        assert "symlink" in reason


class TestFindReplacePatch:
    """find-replace 确定性补丁生成器"""

    def _make_project(self, tmp_path: Path) -> Path:
        (tmp_path / "a.css").write_text(".x { color: #22C55E; }\n")
        (tmp_path / "b.css").write_text(".y { color: #22C55E; background: #fff; }\n")
        (tmp_path / "c.css").write_text(".z { color: blue; }\n")  # 无命中
        return tmp_path

    def test_generates_patch_for_matching_files(self, tmp_path: Path):
        self._make_project(tmp_path)
        patch = build_find_replace_patch(
            tmp_path, "#22C55E", "var(--color-accent)", include_glob="**/*.css"
        )
        # 只有 a.css / b.css 命中
        assert patch.file_count == 2
        paths = {fp.file_path for fp in patch.files}
        assert "a.css" in paths
        assert "b.css" in paths
        assert "c.css" not in paths

    def test_no_match_empty_patch(self, tmp_path: Path):
        self._make_project(tmp_path)
        patch = build_find_replace_patch(tmp_path, "NONEXISTENT", "x")
        assert patch.file_count == 0

    def test_records_hash_metadata(self, tmp_path: Path):
        self._make_project(tmp_path)
        patch = build_find_replace_patch(
            tmp_path, "#22C55E", "var(--color-accent)", include_glob="**/*.css"
        )
        for fp in patch.files:
            assert fp.old_hash  # 非空
            assert fp.old_size > 0
            assert fp.old_mtime > 0
            # old_hash 应与实际原内容一致
            assert fp.old_hash == compute_content_hash(fp.old_content)

    def test_does_not_write_disk(self, tmp_path: Path):
        self._make_project(tmp_path)
        before = (tmp_path / "a.css").read_text()
        build_find_replace_patch(tmp_path, "#22C55E", "var(--color-accent)")
        after = (tmp_path / "a.css").read_text()
        assert before == after  # propose 不落地

    def test_skips_binary_and_protected(self, tmp_path: Path):
        (tmp_path / "a.css").write_text("color: #22C55E;\n")
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "x.css").write_text("color: #22C55E;\n")
        patch = build_find_replace_patch(tmp_path, "#22C55E", "v", include_glob="**/*.css")
        paths = {fp.file_path for fp in patch.files}
        assert "a.css" in paths
        assert not any(".git" in p for p in paths)

    def test_regex_mode(self, tmp_path: Path):
        (tmp_path / "a.txt").write_text("v1.2.3\n")
        patch = build_find_replace_patch(
            tmp_path, r"v\d+\.\d+\.\d+", "vX", include_glob="**/*.txt", regex=True
        )
        assert patch.file_count == 1
        assert "vX" in patch.files[0].new_content


class TestPatchSerialization:
    """patch_id 持久化往返（P0-1）"""

    def test_save_and_load_roundtrip(self, tmp_path: Path):
        (tmp_path / "a.css").write_text("color: #22C55E;\n")
        patch = build_find_replace_patch(tmp_path, "#22C55E", "var(--accent)")
        patches_dir = tmp_path / ".smartdev" / "patches"

        patch_id = save_patch(patch, patches_dir)
        assert patch_id
        assert (patches_dir / f"{patch_id}.json").exists()

        loaded = load_patch(patch_id, patches_dir)
        assert loaded is not None
        assert loaded.patch_id == patch_id
        assert loaded.file_count == patch.file_count
        assert loaded.files[0].file_path == patch.files[0].file_path
        assert loaded.files[0].old_hash == patch.files[0].old_hash
        assert loaded.files[0].new_content == patch.files[0].new_content

    def test_load_missing_returns_none(self, tmp_path: Path):
        assert load_patch("nonexistent-id", tmp_path / "patches") is None

    def test_save_generates_patch_id_and_timestamp(self, tmp_path: Path):
        (tmp_path / "a.css").write_text("color: #22C55E;\n")
        patch = build_find_replace_patch(tmp_path, "#22C55E", "x")
        assert patch.patch_id == ""  # 生成前为空
        save_patch(patch, tmp_path / ".smartdev" / "patches")
        assert patch.patch_id != ""
        assert patch.created_at != ""

    def test_patch_id_stable_for_same_content(self, tmp_path: Path):
        (tmp_path / "a.css").write_text("color: #22C55E;\n")
        p1 = build_find_replace_patch(tmp_path, "#22C55E", "x")
        p2 = build_find_replace_patch(tmp_path, "#22C55E", "x")
        # 内容 hash 部分应一致（时间戳前缀可能不同，比对后 8 位）
        id1 = generate_patch_id(p1)
        id2 = generate_patch_id(p2)
        assert id1.split("-")[-1] == id2.split("-")[-1]
