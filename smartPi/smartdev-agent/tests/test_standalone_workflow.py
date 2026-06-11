"""
test_standalone_workflow.py — Phase 11 Closeout Step 4: Standalone 烟测

端到端验证 SmartDev standalone 使用闭环：
  1. smartdev run new        → 创建 task-card.md / scope.json / agent-output/ / review/
  2. smartdev run report     → 写入 code-agent-result.md / changed-files.txt / test-report.txt
  3. smartdev run handoff-*  → 生成 code / doc / reviewer pack
  4. smartdev run context    → 读取已生成 pack
  5. smartdev guard run      → 基于显式输入返回结构化结果
  6. smartdev run scope-check → 验证 changed_files 在 scope 内

原则：
- 使用临时目录 + 显式输入，不依赖 git 工作区状态
- 使用 core API 调用（不走 subprocess），保持快速
- 零模型调用、零 MCP、零网络
- 测试断言关键产物内容，不只文件存在
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from smartdev.core.guard_runner import run_guard_runner
from smartdev.core.handoff_code import generate_code_agent_pack
from smartdev.core.handoff_doc import generate_doc_steward_pack
from smartdev.core.handoff_review import generate_reviewer_pack
from smartdev.core.run_artifact import ScopeConfig, create_run_artifact
from smartdev.core.run_report import write_run_report
from smartdev.core.scope_gate import check_scope


# ── Fixtures ─────────────────────────────────────────────────


@pytest.fixture
def project():
    """创建最小项目骨架的临时目录。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir)
        # 最小项目骨架（handoff doc/review 各数据源需要）
        (p / "smartdev").mkdir()
        (p / "smartdev" / "__init__.py").write_text("")
        (p / "CLAUDE.md").write_text(
            "# CLAUDE.md\n\n## 当前阶段\n\nPhase 11 Closeout Step 4\n\n"
            "测试基线：1903 passed, 1 skipped\n",
            encoding="utf-8",
        )
        (p / "README.md").write_text("# Standalone Smoke Test Project\n", encoding="utf-8")
        (p / "docs").mkdir()
        (p / "docs" / "development-progress.md").write_text(
            "# SmartDev Agent 开发进度\n\n"
            "> 测试基线：1903 passed, 1 skipped\n\n"
            "## 当前阶段 — Phase 11 全部完成\n",
            encoding="utf-8",
        )
        yield p


# ── Run Artifact 创建 ────────────────────────────────────────


class TestStandaloneRunArtifact:
    """Step 1: smartdev run new — 创建 run artifact 目录结构。"""

    def test_creates_full_structure(self, project):
        scope = ScopeConfig(allowed_paths=["smartdev/", "tests/"])
        run_dir, err = create_run_artifact(
            project, "e2e", task="端到端烟测验证", scope=scope,
        )
        assert err is None
        assert run_dir.exists()
        assert (run_dir / "task-card.md").exists()
        assert (run_dir / "scope.json").exists()
        assert (run_dir / "agent-output").is_dir()
        assert (run_dir / "review").is_dir()

    def test_task_card_contains_task(self, project):
        scope = ScopeConfig(allowed_paths=["smartdev/", "tests/"])
        run_dir, err = create_run_artifact(
            project, "e2e-task", task="修复登录页面超时", scope=scope,
        )
        assert err is None
        content = (run_dir / "task-card.md").read_text("utf-8")
        assert "修复登录页面超时" in content

    def test_scope_json_has_all_fields(self, project):
        scope = ScopeConfig(allowed_paths=["src/"], max_files=5)
        run_dir, err = create_run_artifact(project, "e2e-scope", scope=scope)
        assert err is None
        import json
        data = json.loads((run_dir / "scope.json").read_text("utf-8"))
        assert data["allowed_paths"] == ["src/"]
        assert data["max_files"] == 5
        assert "denied_paths" in data
        assert "protected_paths" in data


# ── Code Agent Report ────────────────────────────────────────


class TestStandaloneRunReport:
    """Step 2: smartdev run report — 写入 agent-output 产物。"""

    def _setup(self, project: Path):
        scope = ScopeConfig(allowed_paths=["smartdev/", "tests/"])
        _, err = create_run_artifact(project, "e2e-rpt", scope=scope, force=True)
        assert err is None

    def test_writes_all_agent_output_files(self, project):
        self._setup(project)
        result = write_run_report(
            project, "e2e-rpt",
            changed_files=["smartdev/__init__.py", "tests/test_x.py"],
            test_command="echo '1903 passed, 1 skipped'",
            status="completed",
        )
        assert result.error is None
        ao = project / ".smartdev" / "runs" / "e2e-rpt" / "agent-output"
        assert (ao / "code-agent-result.md").exists()
        assert (ao / "changed-files.txt").exists()
        assert (ao / "test-report.txt").exists()

    def test_changed_files_content(self, project):
        self._setup(project)
        write_run_report(
            project, "e2e-rpt",
            changed_files=["smartdev/core/a.py", "tests/test_a.py"],
        )
        cf = project / ".smartdev" / "runs" / "e2e-rpt" / "agent-output" / "changed-files.txt"
        content = cf.read_text("utf-8")
        assert "smartdev/core/a.py" in content
        assert "tests/test_a.py" in content

    def test_test_report_content(self, project):
        self._setup(project)
        write_run_report(
            project, "e2e-rpt", test_command="echo '42 passed'",
        )
        tr = project / ".smartdev" / "runs" / "e2e-rpt" / "agent-output" / "test-report.txt"
        assert "42 passed" in tr.read_text("utf-8")

    def test_code_agent_result_has_required_sections(self, project):
        self._setup(project)
        write_run_report(project, "e2e-rpt", status="completed")
        ca = project / ".smartdev" / "runs" / "e2e-rpt" / "agent-output" / "code-agent-result.md"
        content = ca.read_text("utf-8")
        assert "## Status" in content
        assert "## Implemented" in content
        assert "## Changed Files" in content
        assert "## Tests" in content
        assert "## Open Questions" in content


# ── Handoff Pack 生成 ─────────────────────────────────────────


class TestStandaloneHandoffPacks:
    """Step 3: smartdev run handoff-* — 生成三类角色 pack。"""

    CHANGED = ["smartdev/__init__.py"]

    def _setup(self, project: Path):
        scope = ScopeConfig(allowed_paths=["smartdev/", "tests/"])
        _, err = create_run_artifact(
            project, "e2e-ho", task="端到端 handoff 测试", scope=scope,
            force=True,
        )
        assert err is None
        # 先写入 agent-output（handoff doc/review 会消费）
        write_run_report(
            project, "e2e-ho",
            changed_files=self.CHANGED,
            test_command="echo '1903 passed'",
            status="completed",
        )

    def test_generates_code_agent_pack(self, project):
        self._setup(project)
        result = generate_code_agent_pack(
            project, "e2e-ho", changed_files=self.CHANGED,
        )
        assert result.error is None
        content = result.output_path.read_text("utf-8")
        assert "Code Agent Pack" in content
        assert "角色激活前言" in content
        assert "端到端 handoff 测试" in content
        assert "你是 SmartDev 协作模式中的 Code Agent" in content
        # 应包含禁止项
        assert "绝对不能" in content

    def test_generates_doc_steward_pack(self, project):
        self._setup(project)
        result = generate_doc_steward_pack(project, "e2e-ho")
        assert result.error is None
        content = result.output_path.read_text("utf-8")
        assert "Doc Steward Pack" in content
        assert "你是 SmartDev 协作模式中的 Doc Steward" in content
        # Step 3 合约：doc pack 应消费 agent-output
        assert "Agent Output" in content

    def test_generates_reviewer_pack(self, project):
        self._setup(project)
        result = generate_reviewer_pack(
            project, "e2e-ho", changed_files=self.CHANGED,
        )
        assert result.error is None
        content = result.output_path.read_text("utf-8")
        assert "Reviewer Pack" in content
        assert "你是 SmartDev 协作模式中的 Reviewer" in content
        # Step 3 合约：review pack 应消费 agent-output 三文件
        assert "Code Agent Result" in content
        assert "Agent Changed Files" in content
        assert "Agent Test Report" in content

    def test_all_three_packs_under_budget(self, project):
        self._setup(project)
        code = generate_code_agent_pack(project, "e2e-ho", changed_files=self.CHANGED)
        doc = generate_doc_steward_pack(project, "e2e-ho")
        review = generate_reviewer_pack(project, "e2e-ho", changed_files=self.CHANGED)
        # 所有 pack 应非空且在合理预算内
        assert 500 < code.char_count < 50000
        assert 500 < doc.char_count < 100000
        assert 500 < review.char_count < 50000


# ── Run Context ──────────────────────────────────────────────


class TestStandaloneRunContext:
    """Step 4: smartdev run context — 读取已生成 pack。"""

    def _setup(self, project: Path):
        scope = ScopeConfig(allowed_paths=["smartdev/", "tests/"])
        _, err = create_run_artifact(project, "e2e-ctx", scope=scope, force=True)
        assert err is None
        write_run_report(project, "e2e-ctx", status="completed")
        generate_code_agent_pack(project, "e2e-ctx", changed_files=["smartdev/__init__.py"])
        generate_doc_steward_pack(project, "e2e-ctx")
        generate_reviewer_pack(project, "e2e-ctx", changed_files=["smartdev/__init__.py"])

    def test_all_three_packs_readable(self, project):
        self._setup(project)
        handoff = project / ".smartdev" / "runs" / "e2e-ctx" / "handoff"
        for name in ["code-agent-pack.md", "doc-steward-pack.md", "reviewer-pack.md"]:
            pack = handoff / name
            assert pack.exists()
            content = pack.read_text("utf-8")
            assert len(content) > 100

    def test_code_agent_pack_has_required_sections(self, project):
        self._setup(project)
        content = (
            project / ".smartdev" / "runs" / "e2e-ctx" / "handoff" / "code-agent-pack.md"
        ).read_text("utf-8")
        assert "当前任务" in content or "## 1." in content
        assert "修改范围" in content or "## 2." in content
        assert "验收标准" in content
        assert "禁止项" in content

    def test_reviewer_pack_has_output_format(self, project):
        self._setup(project)
        content = (
            project / ".smartdev" / "runs" / "e2e-ctx" / "handoff" / "reviewer-pack.md"
        ).read_text("utf-8")
        assert "risk_level: R0 / R1 / R2 / R3" in content
        assert "approval: approve / request_changes / block" in content


# ── Guard Runner ──────────────────────────────────────────────


class TestStandaloneGuardRunner:
    """Step 5: smartdev guard run — 基于显式输入运行 Guard。"""

    CHANGED = ["smartdev/__init__.py", "tests/test_a.py"]
    DIFF = "@@ -0,0 +1,3 @@\n+import os\n+\n+def foo():\n+    pass\n"

    def _setup(self, project: Path):
        scope = ScopeConfig(allowed_paths=["smartdev/", "tests/"])
        _, err = create_run_artifact(project, "e2e-guard", scope=scope, force=True)
        assert err is None

    def test_runs_all_five_guards(self, project):
        self._setup(project)
        result = run_guard_runner(
            project,
            changed_files=self.CHANGED,
            diff_content=self.DIFF,
            run_id="e2e-guard",
        )
        # 5 个 Guard: change.budget / dev.guard / dependency.guard /
        #             security.review / diff.explain
        assert len(result.selected) == 5
        assert len(result.guards) == 5
        assert result.run_id == "e2e-guard"

    def test_all_guards_return_structured_result(self, project):
        self._setup(project)
        result = run_guard_runner(
            project,
            changed_files=self.CHANGED,
            diff_content=self.DIFF,
        )
        for name, entry in result.guards.items():
            assert isinstance(entry.passed, bool), (
                f"Guard {name}: passed should be bool, got {type(entry.passed)}"
            )
            assert isinstance(entry.summary, str), (
                f"Guard {name}: summary should be str"
            )

    def test_select_specific_guards(self, project):
        self._setup(project)
        result = run_guard_runner(
            project,
            changed_files=self.CHANGED,
            diff_content=self.DIFF,
            select=["change.budget", "dev.guard"],
        )
        assert result.selected == ["change.budget", "dev.guard"]
        assert len(result.guards) == 2

    def test_empty_changed_files_ok(self, project):
        """空变更列表不崩溃。"""
        self._setup(project)
        result = run_guard_runner(
            project, changed_files=[], diff_content="",
        )
        # 不应抛异常
        assert result.selected
        assert len(result.guards) == len(result.selected)


# ── Scope Gate ────────────────────────────────────────────────


class TestStandaloneScopeGate:
    """Step 6: smartdev run scope-check — 验证 changed_files 在 scope 内。"""

    CHANGED = ["smartdev/core/new_feature.py", "tests/test_new_feature.py"]

    def _setup(self, project: Path):
        scope = ScopeConfig(allowed_paths=["smartdev/", "tests/"])
        _, err = create_run_artifact(project, "e2e-sg", scope=scope, force=True)
        assert err is None

    def test_passes_for_allowed_files(self, project):
        self._setup(project)
        result = check_scope(project, "e2e-sg", self.CHANGED)
        assert result.passed is True
        assert result.error is None
        assert len(result.violations) == 0

    def test_violates_for_denied_files(self, project):
        self._setup(project)
        result = check_scope(project, "e2e-sg", ["__pycache__/foo.pyc"])
        assert result.passed is False
        assert len(result.violations) > 0

    def test_missing_run_id_reports_error(self, project):
        result = check_scope(project, "nonexistent", self.CHANGED)
        assert result.passed is False
        assert result.error is not None


# ── 完整闭环烟测 ─────────────────────────────────────────────


class TestFullStandaloneWorkflow:
    """一次完整 standalone 协作循环，全部走 core API。"""

    CHANGED = ["smartdev/__init__.py"]
    DIFF = "@@ -0,0 +1 @@\n+# SmartDev standalone smoke test\n"

    def test_full_e2e_workflow(self):
        """完整端到端闭环：run new → report → handoff → context → guard → scope"""
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)

            # ── 准备最小项目 ──────────────────────────────
            (p / "smartdev").mkdir()
            (p / "smartdev" / "__init__.py").write_text("")
            (p / "CLAUDE.md").write_text(
                "# CLAUDE\n\n## 当前阶段\n\nPhase 11 Closeout Step 4\n\n"
                "测试基线：1903 passed\n", encoding="utf-8",
            )
            (p / "README.md").write_text("# Smoke Test\n", encoding="utf-8")
            (p / "docs").mkdir()
            (p / "docs" / "development-progress.md").write_text(
                "# Progress\n\n测试基线：1903 passed\n", encoding="utf-8",
            )

            # ── 1. run new ───────────────────────────────
            scope = ScopeConfig(allowed_paths=["smartdev/", "tests/"])
            run_dir, err = create_run_artifact(
                p, "full-e2e", task="完整闭环烟测", scope=scope,
            )
            assert err is None
            assert (run_dir / "task-card.md").exists()
            assert (run_dir / "scope.json").exists()
            assert (run_dir / "agent-output").is_dir()
            assert (run_dir / "review").is_dir()

            # ── 2. run report ────────────────────────────
            report = write_run_report(
                p, "full-e2e",
                changed_files=self.CHANGED,
                test_command="echo '1903 passed, 1 skipped'",
                status="completed",
            )
            assert report.error is None
            ao = run_dir / "agent-output"
            assert (ao / "code-agent-result.md").exists()
            assert (ao / "changed-files.txt").exists()
            assert (ao / "test-report.txt").exists()

            # agent-output 内容验证
            ca = (ao / "code-agent-result.md").read_text("utf-8")
            assert "## Status" in ca
            assert "completed" in ca
            assert "## Implemented" in ca
            assert "## Changed Files" in ca
            assert "## Tests" in ca
            assert "## Open Questions" in ca

            cf = (ao / "changed-files.txt").read_text("utf-8")
            assert self.CHANGED[0] in cf

            tr = (ao / "test-report.txt").read_text("utf-8")
            assert "1903 passed" in tr

            # ── 3. handoff-* ─────────────────────────────
            code = generate_code_agent_pack(
                p, "full-e2e", changed_files=self.CHANGED,
            )
            assert code.error is None
            assert code.char_count > 500
            code_pack = code.output_path.read_text("utf-8")
            assert "Code Agent Pack" in code_pack
            assert "完整闭环烟测" in code_pack

            doc = generate_doc_steward_pack(p, "full-e2e")
            assert doc.error is None
            assert doc.char_count > 500
            doc_pack = doc.output_path.read_text("utf-8")
            assert "Doc Steward Pack" in doc_pack
            assert "Agent Output" in doc_pack  # 消费 agent-output

            review = generate_reviewer_pack(
                p, "full-e2e", changed_files=self.CHANGED,
            )
            assert review.error is None
            assert review.char_count > 500
            review_pack = review.output_path.read_text("utf-8")
            assert "Reviewer Pack" in review_pack
            # Step 3 合约：消费 agent-output 三文件
            assert "Code Agent Result" in review_pack
            assert "Agent Changed Files" in review_pack
            assert "Agent Test Report" in review_pack

            # ── 4. run context ───────────────────────────
            handoff = run_dir / "handoff"
            for name in ["code-agent-pack.md", "doc-steward-pack.md", "reviewer-pack.md"]:
                pack = handoff / name
                assert pack.exists()
                assert len(pack.read_text("utf-8")) > 100

            # ── 5. guard run ─────────────────────────────
            guard = run_guard_runner(
                p,
                changed_files=self.CHANGED,
                diff_content=self.DIFF,
                run_id="full-e2e",
            )
            assert len(guard.selected) == 5
            assert len(guard.guards) == 5
            for name, entry in guard.guards.items():
                assert isinstance(entry.passed, bool), f"Guard {name}: passed should be bool"
                assert isinstance(entry.summary, str), f"Guard {name}: summary should be str"

            # ── 6. scope-check ────────────────────────────
            sg = check_scope(p, "full-e2e", self.CHANGED)
            assert sg.passed is True
            assert sg.error is None

            # ── 回归：缺失 run_id 时的错误 ──────────────
            sg_bad = check_scope(p, "no-such-run", self.CHANGED)
            assert sg_bad.passed is False
