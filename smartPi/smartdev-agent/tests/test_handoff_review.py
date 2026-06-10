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


# ── Agent Output 消费契约（Phase 11 Closeout Step 3）─────────


class TestHandoffReviewConsumesAgentOutput:
    """handoff review 读取 agent-output/ 下产物的契约。"""

    @staticmethod
    def _setup_with_agent_output(tmp_path: Path, run_id: str = "rev-ao"):
        """创建含 agent-output 产物的 run artifact。"""
        from smartdev.core.run_artifact import ScopeConfig, create_run_artifact
        scope = ScopeConfig(allowed_paths=["smartdev/", "tests/"])
        run_dir, err = create_run_artifact(tmp_path, run_id, scope=scope, force=True)
        if err:
            raise RuntimeError(f"Failed to create run: {err}")
        (tmp_path / "smartdev").mkdir(exist_ok=True)
        (tmp_path / "smartdev" / "__init__.py").write_text("")
        ao_dir = run_dir / "agent-output"
        # 写入完整 agent-output 产物
        (ao_dir / "code-agent-result.md").write_text(
            "# Code Agent Result — rev-ao\n\n"
            "## Status\nblocked\n\n"
            "## Implemented\n- feature X\n\n"
            "## Changed Files\n| smartdev/core/a.py |\n\n"
            "## Tests\n2 failed\n\n"
            "## Open Questions\n需要 review 依赖变更\n",
            encoding="utf-8",
        )
        (ao_dir / "changed-files.txt").write_text(
            "smartdev/core/auth.py\ntests/test_auth.py\n",
            encoding="utf-8",
        )
        (ao_dir / "test-report.txt").write_text(
            "1897 passed, 1 skipped in 53.12s\n",
            encoding="utf-8",
        )
        return tmp_path

    def test_code_agent_result_section_present(self):
        """agent-output/code-agent-result.md 存在 → Code Agent Result 节出现。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = self._setup_with_agent_output(Path(tmpdir), "rev-ao-1")
            result = generate_reviewer_pack(project, "rev-ao-1")
            assert result.error is None
            content = result.output_path.read_text(encoding="utf-8")
            assert "Code Agent Result" in content
            assert "blocked" in content

    def test_agent_changed_files_section_present(self):
        """agent-output/changed-files.txt 存在 → Agent Changed Files 节出现。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = self._setup_with_agent_output(Path(tmpdir), "rev-ao-2")
            result = generate_reviewer_pack(project, "rev-ao-2")
            assert result.error is None
            content = result.output_path.read_text(encoding="utf-8")
            assert "Agent Changed Files" in content
            assert "smartdev/core/auth.py" in content

    def test_agent_test_report_section_present(self):
        """agent-output/test-report.txt 存在 → Agent Test Report 节出现。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = self._setup_with_agent_output(Path(tmpdir), "rev-ao-3")
            result = generate_reviewer_pack(project, "rev-ao-3")
            assert result.error is None
            content = result.output_path.read_text(encoding="utf-8")
            assert "Agent Test Report" in content
            assert "1897 passed" in content

    def test_missing_agent_output_no_error(self):
        """agent-output/ 为空 → 不报错，相关节不出现。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _setup_run(Path(tmpdir), "rev-ao-empty")
            result = generate_reviewer_pack(project, "rev-ao-empty")
            assert result.error is None
            content = result.output_path.read_text(encoding="utf-8")
            assert "Code Agent Result" not in content
            assert "Agent Changed Files" not in content
            assert "Agent Test Report" not in content
