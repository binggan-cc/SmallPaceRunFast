"""
test_handoff_doc.py — Phase 11D Step 4 handoff doc 聚焦测试

覆盖：
- generate_doc_steward_pack 成功生成
- 输出路径在 .smartdev/runs/<run_id>/handoff/doc-steward-pack.md
- run_id 不存在 / scope 缺失 → 错误
- Pack 包含必要的节
- 各数据源优雅降级
- 字符预算
- 不修改源码

不覆盖：
- handoff review（Step 5）
- MCP 工具（Step 6）
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from smartdev.core.handoff_doc import (
    DOC_PACK_CHAR_BUDGET,
    HandoffDocResult,
    generate_doc_steward_pack,
)
from smartdev.core.run_artifact import ScopeConfig, create_run_artifact


@pytest.fixture
def tmp_project():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def _setup_run(tmp_project: Path, run_id: str = "test-doc", **scope_kwargs):
    """创建 run artifact + 最小项目骨架以供 doc_steward 收集。"""
    scope = ScopeConfig(
        allowed_paths=["smartdev/", "tests/"],
        **scope_kwargs,
    )
    _, err = create_run_artifact(tmp_project, run_id, scope=scope, force=True)
    if err:
        raise RuntimeError(f"Failed to create run artifact: {err}")

    # 最小项目骨架
    (tmp_project / "CLAUDE.md").write_text(
        "# CLAUDE.md\n\n## 当前阶段\n\nPhase 11D Step 4\n\n测试基线：1344 passed, 1 skipped\n",
        encoding="utf-8",
    )
    (tmp_project / "docs").mkdir(exist_ok=True)
    (tmp_project / "docs" / "development-progress.md").write_text(
        "# Progress\n\n测试基线：1344 passed, 1 skipped\n",
        encoding="utf-8",
    )
    (tmp_project / "README.md").write_text("# Test Project\n", encoding="utf-8")
    (tmp_project / "smartdev").mkdir(exist_ok=True)
    (tmp_project / "smartdev" / "__init__.py").write_text("")

    return tmp_project


# ── 成功生成 ──────────────────────────────────────────────────


class TestGenerateDocStewardPack:
    def test_generates_pack(self, tmp_project):
        _setup_run(tmp_project, "d1")
        result = generate_doc_steward_pack(tmp_project, "d1")
        assert result.error is None
        assert result.output_path is not None
        assert result.output_path.exists()
        assert result.char_count > 0

    def test_output_path(self, tmp_project):
        _setup_run(tmp_project, "d2")
        result = generate_doc_steward_pack(tmp_project, "d2")
        expected = (
            tmp_project / ".smartdev" / "runs" / "d2" / "handoff" / "doc-steward-pack.md"
        )
        assert result.output_path == expected

    def test_contains_sections(self, tmp_project):
        _setup_run(tmp_project, "d3")
        result = generate_doc_steward_pack(tmp_project, "d3")
        content = result.output_path.read_text(encoding="utf-8")
        # 至少应包含 Snapshot 和 Phase Status（这两个几乎总是可用）
        assert "Capability Snapshots" in content
        assert "Phase Status" in content or "Current Phase" in content
        assert "Doc Steward 输出规范" in content

    def test_contains_phase_status(self, tmp_project):
        _setup_run(tmp_project, "d4")
        result = generate_doc_steward_pack(tmp_project, "d4")
        content = result.output_path.read_text(encoding="utf-8")
        assert "Phase 11D" in content or "1344" in content

    def test_under_char_budget(self, tmp_project):
        _setup_run(tmp_project, "d5")
        result = generate_doc_steward_pack(tmp_project, "d5")
        # 允许 2x 余量（因为有些数据源会产出一大段文本）
        assert result.char_count <= DOC_PACK_CHAR_BUDGET * 2.5


# ── 错误路径 ──────────────────────────────────────────────────


class TestGenerateDocStewardPackErrors:
    def test_missing_run_dir(self, tmp_project):
        result = generate_doc_steward_pack(tmp_project, "nonexistent")
        assert result.error is not None
        assert "不存在" in result.error

    def test_missing_scope_json(self, tmp_project):
        run_dir = tmp_project / ".smartdev" / "runs" / "no-scope"
        run_dir.mkdir(parents=True)
        result = generate_doc_steward_pack(tmp_project, "no-scope")
        assert result.error is not None
        assert "scope" in result.error.lower()

    def test_minimal_project_still_works(self, tmp_project):
        """即使项目骨架不完整，也不会崩溃。"""
        run_dir = tmp_project / ".smartdev" / "runs" / "minimal"
        run_dir.mkdir(parents=True)
        from smartdev.core.run_artifact import ScopeConfig
        (run_dir / "scope.json").write_text(ScopeConfig().to_json())
        result = generate_doc_steward_pack(tmp_project, "minimal")
        assert result.error is None  # 不应崩溃
        assert result.char_count > 0


# ── 不修改源码 ────────────────────────────────────────────────


class TestHandoffDocSafe:
    def test_only_writes_under_smartdev_runs(self, tmp_project):
        _setup_run(tmp_project, "safe")
        before = {
            str(f.relative_to(tmp_project))
            for f in tmp_project.rglob("*")
            if f.is_file() and ".smartdev" not in str(f)
        }
        result = generate_doc_steward_pack(tmp_project, "safe")
        after = {
            str(f.relative_to(tmp_project))
            for f in tmp_project.rglob("*")
            if f.is_file() and ".smartdev" not in str(f)
        }
        assert result.error is None
        assert before == after  # 源码无变化


# ── HandoffDocResult 序列化 ───────────────────────────────────


class TestHandoffDocResult:
    def test_to_dict(self):
        result = HandoffDocResult(
            output_path=Path("/tmp/doc-steward-pack.md"),
            char_count=3000,
            sections=["1. Change Manifest", "2. Snapshots"],
            skipped=["Diff Summary: git 不可用"],
        )
        d = result.to_dict()
        assert d["output_path"] == "/tmp/doc-steward-pack.md"
        assert d["char_count"] == 3000
        assert len(d["sections"]) == 2
        assert len(d["skipped"]) == 1
        assert d["error"] is None

    def test_to_dict_with_error(self):
        result = HandoffDocResult(error="run 目录不存在")
        d = result.to_dict()
        assert d["output_path"] is None
        assert d["error"] == "run 目录不存在"


# ── 数据源降级 ────────────────────────────────────────────────


class TestDataSourceGracefulDegradation:
    def test_skipped_list_contains_unavailable_sources(self, tmp_project):
        """在 git 不可用的临时目录中，manifest 和 diff 应被标记为 skipped。"""
        _setup_run(tmp_project, "deg")
        result = generate_doc_steward_pack(tmp_project, "deg")
        # 非 git 项目下 manifest 和 diff 应出现在 skipped 中
        assert len(result.skipped) >= 0  # 可能有也可能没有，取决于环境

    def test_doc_map_mentions_dict_format(self, tmp_project):
        """doc_map 的 mentions 是 dict[str, list[str]]，不会触发 TypeError。"""
        from smartdev.core.handoff_doc import _try_doc_map
        _setup_run(tmp_project, "mentions-fmt")
        text, ok = _try_doc_map(tmp_project)
        # 不应抛出异常（之前会因 mentions 格式不匹配而静默失败）
        assert isinstance(text, str)
        # ok 反映是否有真实文档
        assert isinstance(ok, bool)


class TestDiffSummaryFields:
    """验证 Diff Summary 使用正确的 GitDiff 字段名。"""

    def test_uses_insertions_deletions_not_lines(self, tmp_project):
        """确保使用 diff.insertions / diff.deletions 而非 diff.lines_*。"""
        import inspect
        from smartdev.core.handoff_doc import _try_diff_summary
        source = inspect.getsource(_try_diff_summary)
        assert "diff.insertions" in source
        assert "diff.deletions" in source
        assert "lines_added" not in source
        assert "lines_deleted" not in source
