"""
test_handoff_review.py — Phase 11D Step 5 handoff review 聚焦测试

覆盖：
- generate_reviewer_pack 成功生成
- 输出路径在 .smartdev/runs/<run_id>/handoff/reviewer-pack.md
- run_id 不存在 / scope 缺失 → 错误
- Pack 包含必要的审查节
- 依赖变更和安全清单
- 字符预算
- 不修改源码
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from smartdev.core.handoff_review import (
    REVIEW_PACK_CHAR_BUDGET,
    HandoffReviewResult,
    _dependency_changes,
    _security_checklist,
    generate_reviewer_pack,
)
from smartdev.core.run_artifact import ScopeConfig, create_run_artifact


def _setup_run(tmp_project: Path, run_id: str = "review-test"):
    scope = ScopeConfig(allowed_paths=["smartdev/", "tests/"])
    _, err = create_run_artifact(tmp_project, run_id, scope=scope, force=True)
    if err:
        raise RuntimeError(f"Failed to create run artifact: {err}")
    (tmp_project / "smartdev").mkdir(exist_ok=True)
    (tmp_project / "smartdev" / "__init__.py").write_text("")
    return tmp_project


class TestGenerateReviewerPack:
    def test_generates_pack(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _setup_run(Path(tmpdir), "r1")
            result = generate_reviewer_pack(project, "r1")
            assert result.error is None
            assert result.output_path is not None
            assert result.output_path.exists()
            assert result.char_count > 0

    def test_output_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _setup_run(Path(tmpdir), "r2")
            result = generate_reviewer_pack(project, "r2")
            expected = project / ".smartdev" / "runs" / "r2" / "handoff" / "reviewer-pack.md"
            assert result.output_path == expected

    def test_contains_required_sections(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _setup_run(Path(tmpdir), "r3")
            result = generate_reviewer_pack(
                project,
                "r3",
                changed_files=["smartdev/core/auth.py", "pyproject.toml"],
            )
            content = result.output_path.read_text(encoding="utf-8")
            assert "Risk + Impact" in content
            assert "Changed Files" in content
            assert "Dependency Changes" in content
            assert "Security Checklist" in content
            assert "Reviewer 输出规范" in content
            assert "pyproject.toml" in content
            assert "认证/授权" in content

    def test_under_char_budget(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _setup_run(Path(tmpdir), "r4")
            result = generate_reviewer_pack(project, "r4")
            assert result.char_count <= REVIEW_PACK_CHAR_BUDGET * 1.5


class TestGenerateReviewerPackErrors:
    def test_missing_run_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = generate_reviewer_pack(Path(tmpdir), "missing")
            assert result.error is not None
            assert "不存在" in result.error

    def test_missing_scope_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)
            (project / ".smartdev" / "runs" / "no-scope").mkdir(parents=True)
            result = generate_reviewer_pack(project, "no-scope")
            assert result.error is not None
            assert "scope" in result.error.lower()


class TestReviewerPackSafe:
    def test_only_writes_under_smartdev_runs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _setup_run(Path(tmpdir), "safe")
            (project / "smartdev" / "core.py").write_text("# source\n")
            before = {
                str(f.relative_to(project))
                for f in project.rglob("*")
                if f.is_file() and ".smartdev" not in str(f)
            }
            result = generate_reviewer_pack(project, "safe")
            after = {
                str(f.relative_to(project))
                for f in project.rglob("*")
                if f.is_file() and ".smartdev" not in str(f)
            }
            assert result.error is None
            assert before == after


class TestReviewerHelpers:
    def test_dependency_changes_detects_manifest(self):
        text = _dependency_changes(["smartdev/a.py", "package.json"])
        assert "package.json" in text
        assert "依赖相关变更" in text

    def test_dependency_changes_empty(self):
        text = _dependency_changes(["smartdev/a.py"])
        assert "未检测到" in text

    def test_security_checklist_detects_sensitive_path(self):
        text = _security_checklist(["smartdev/auth/session.py"])
        assert "认证/授权" in text
        assert "输入校验" in text


class TestHandoffReviewResult:
    def test_to_dict(self):
        result = HandoffReviewResult(
            output_path=Path("/tmp/reviewer-pack.md"),
            char_count=100,
            sections=["1. Risk + Impact"],
            skipped=["Git Diff Explain: unavailable"],
        )
        d = result.to_dict()
        assert d["output_path"] == "/tmp/reviewer-pack.md"
        assert d["char_count"] == 100
        assert d["sections"] == ["1. Risk + Impact"]
        assert d["skipped"] == ["Git Diff Explain: unavailable"]
        assert d["error"] is None
