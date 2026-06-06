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
