"""
test_run_report.py — smartdev run report 聚焦测试

覆盖：
- --changed-files 写入 changed-files.txt
- --auto-changed-files 从 git diff 推断
- --tests 运行测试命令并写入 test-report.txt
- --status 更新 code-agent-result.md
- 从模板生成 code-agent-result.md
- 缺失 run_id 错误
- 不修改源码文件
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from smartdev.core.run_artifact import ScopeConfig, create_run_artifact
from smartdev.core.run_report import RunReportResult, write_run_report


@pytest.fixture
def tmp_project():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def _setup_run(tmp_project: Path, run_id: str = "rp-test"):
    """创建 run artifact（含 agent-output/ 目录）。"""
    scope = ScopeConfig(allowed_paths=["smartdev/", "tests/"])
    _, err = create_run_artifact(tmp_project, run_id, scope=scope, force=True)
    if err:
        raise RuntimeError(f"Failed: {err}")


# ── changed-files.txt ────────────────────────────────────────


class TestChangedFiles:
    def test_explicit_changed_files(self, tmp_project):
        _setup_run(tmp_project, "cf1")
        result = write_run_report(
            tmp_project, "cf1",
            changed_files=["smartdev/core/a.py", "tests/test_a.py"],
        )
        assert result.error is None
        cf_path = tmp_project / ".smartdev" / "runs" / "cf1" / "agent-output" / "changed-files.txt"
        assert cf_path.exists()
        content = cf_path.read_text(encoding="utf-8")
        assert "smartdev/core/a.py" in content
        assert "tests/test_a.py" in content

    def test_auto_changed_files_skips_without_git(self, tmp_project):
        """非 git 项目优雅跳过。"""
        _setup_run(tmp_project, "cf2")
        result = write_run_report(
            tmp_project, "cf2", auto_changed_files=True,
        )
        assert result.error is None
        has_skipped = any("changed-files.txt" in s for s in result.skipped)
        # 在临时目录（非 git repo）中应跳过
        assert has_skipped


# ── test-report.txt ──────────────────────────────────────────


class TestTestReport:
    def test_runs_test_command(self, tmp_project):
        _setup_run(tmp_project, "tr1")
        result = write_run_report(
            tmp_project, "tr1",
            test_command="echo '3 passed'",
        )
        assert result.error is None
        tr_path = tmp_project / ".smartdev" / "runs" / "tr1" / "agent-output" / "test-report.txt"
        assert tr_path.exists()
        content = tr_path.read_text(encoding="utf-8")
        assert "3 passed" in content

    def test_command_with_errors_still_writes_report(self, tmp_project):
        """即使命令失败，输出仍写入 test-report.txt。"""
        _setup_run(tmp_project, "tr2")
        result = write_run_report(
            tmp_project, "tr2",
            test_command="echo 'FAIL' && exit 1",
        )
        assert result.error is None
        tr_path = tmp_project / ".smartdev" / "runs" / "tr2" / "agent-output" / "test-report.txt"
        assert tr_path.exists()
        content = tr_path.read_text(encoding="utf-8")
        assert "FAIL" in content


# ── code-agent-result.md ─────────────────────────────────────


class TestCodeAgentResult:
    def test_generates_from_template_if_missing(self, tmp_project):
        _setup_run(tmp_project, "ca1")
        result = write_run_report(tmp_project, "ca1")
        assert result.error is None
        ca_path = tmp_project / ".smartdev" / "runs" / "ca1" / "agent-output" / "code-agent-result.md"
        assert ca_path.exists()
        content = ca_path.read_text(encoding="utf-8")
        assert "Code Agent Result" in content
        assert "## Status" in content
        assert "completed" in content

    def test_does_not_overwrite_existing(self, tmp_project):
        _setup_run(tmp_project, "ca2")
        # 第一次写入
        write_run_report(tmp_project, "ca2")
        # 手动修改
        ca_path = tmp_project / ".smartdev" / "runs" / "ca2" / "agent-output" / "code-agent-result.md"
        original = ca_path.read_text(encoding="utf-8")
        ca_path.write_text("# Custom content\n", encoding="utf-8")
        # 第二次写入不应覆盖
        write_run_report(tmp_project, "ca2")
        content = ca_path.read_text(encoding="utf-8")
        assert content == "# Custom content\n"

    def test_status_updates_existing(self, tmp_project):
        _setup_run(tmp_project, "ca3")
        # 先生成模板
        write_run_report(tmp_project, "ca3", status="partial")
        ca_path = tmp_project / ".smartdev" / "runs" / "ca3" / "agent-output" / "code-agent-result.md"
        content = ca_path.read_text(encoding="utf-8")
        assert "partial" in content
        # 更新状态
        write_run_report(tmp_project, "ca3", status="completed")
        content = ca_path.read_text(encoding="utf-8")
        assert "completed" in content

    def test_blocked_status(self, tmp_project):
        _setup_run(tmp_project, "ca4")
        result = write_run_report(tmp_project, "ca4", status="blocked")
        assert result.error is None
        ca_path = tmp_project / ".smartdev" / "runs" / "ca4" / "agent-output" / "code-agent-result.md"
        assert "blocked" in ca_path.read_text(encoding="utf-8")


# ── 错误和边缘 ────────────────────────────────────────────────


class TestRunReportErrors:
    def test_missing_run_dir(self, tmp_project):
        result = write_run_report(tmp_project, "no-such-run")
        assert result.error is not None
        assert "不存在" in result.error

    def test_files_written_tracks_all(self, tmp_project):
        _setup_run(tmp_project, "fw1")
        result = write_run_report(
            tmp_project, "fw1",
            changed_files=["a.py"],
            test_command="echo ok",
            status="completed",
        )
        assert result.error is None
        assert any("changed-files.txt" in f for f in result.files_written)
        assert any("test-report.txt" in f for f in result.files_written)
        assert any("code-agent-result.md" in f for f in result.files_written)


# ── 不修改源码 ────────────────────────────────────────────────


class TestRunReportSafe:
    def test_only_writes_under_agent_output(self, tmp_project):
        _setup_run(tmp_project, "safe1")
        before = {
            str(f.relative_to(tmp_project))
            for f in tmp_project.rglob("*")
            if f.is_file() and ".smartdev" not in str(f)
        }
        write_run_report(
            tmp_project, "safe1",
            changed_files=["a.py"],
            test_command="echo ok",
        )
        after = {
            str(f.relative_to(tmp_project))
            for f in tmp_project.rglob("*")
            if f.is_file() and ".smartdev" not in str(f)
        }
        assert before == after


# ── RunReportResult ───────────────────────────────────────────


class TestRunReportResult:
    def test_to_dict(self):
        result = RunReportResult(
            output_dir=Path("/tmp/agent-output"),
            files_written=["changed-files.txt", "test-report.txt"],
            skipped=["report: 超时"],
        )
        d = result.to_dict()
        assert d["output_dir"] == "/tmp/agent-output"
        assert len(d["files_written"]) == 2
        assert len(d["skipped"]) == 1

    def test_to_dict_with_error(self):
        result = RunReportResult(error="run 目录不存在")
        d = result.to_dict()
        assert d["output_dir"] is None
        assert d["error"] == "run 目录不存在"
