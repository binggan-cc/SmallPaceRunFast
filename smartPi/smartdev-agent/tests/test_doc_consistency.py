"""
doc.consistency Skill 测试 — Phase 11C Step 4

覆盖：
1. Skill 注册验证 + R0
2. can_run()
3. 无问题时返回 issue_count=0
4. Rule 1：stale_capability（skill 数量超出文档 / CLI 命令未文档化）
5. Rule 2：phase_status_mismatch（CHANGELOG vs pyproject.toml 版本 / Phase mentions）
6. Rule 3：capability_overpromise（❌ 声明 vs 其他文档）
7. Rule 4：stale_test_baseline（progress.md 数字 vs 其他文档）
8. Rule 5：public_surface_changed_docs_not_updated（manifest 后文档未更新）
9. 单条规则失败不阻断其他规则
10. 输入快照不传时自动生成（最简调用）
11. ConsistencyIssue.to_dict 结构
12. severity_summary 统计
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from smartdev.models import ProjectContext
from smartdev.skills.base import Skill
from smartdev.skills.doc_consistency.skill import (
    ConsistencyIssue,
    DocConsistencySkill,
    _rule1_stale_capability,
    _rule2_phase_status,
    _rule3_capability_overpromise,
    _rule4_test_baseline,
    _rule5_public_surface,
)


# ── Helpers ────────────────────────────────────────────────


def _ctx(path: Path) -> ProjectContext:
    return ProjectContext(project_path=path)


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _minimal_skill_snapshot(count: int = 5) -> dict:
    return {
        "skill_count": count,
        "skills": [{"name": f"skill.{i}", "risk": "R0", "task_type": "diagnose",
                     "description": f"skill {i}", "inputs": [], "outputs": []}
                    for i in range(count)],
    }


def _minimal_cli_snapshot(commands: list[str] | None = None) -> dict:
    cmds = commands or []
    return {
        "command_count": len(cmds),
        "commands": [{"command": c, "description": "", "args": []} for c in cmds],
    }


def _minimal_doc_map(docs: list[dict] | None = None) -> dict:
    return {"doc_count": len(docs or []), "docs": docs or [], "generated_at": "2026-01-01T00:00:00Z"}


# ── 注册验证 ──────────────────────────────────────────────


def test_skill_registered():
    import smartdev.skills  # noqa: F401
    skill = Skill.get_skill("doc.consistency")
    assert skill is not None
    assert skill.name == "doc.consistency"


def test_skill_is_r0():
    from smartdev.models import RiskLevel
    assert DocConsistencySkill.risk_level == RiskLevel.R0


# ── can_run ───────────────────────────────────────────────


def test_can_run_true(tmp_path: Path):
    assert DocConsistencySkill().can_run(_ctx(tmp_path)) is True


def test_can_run_false(tmp_path: Path):
    assert DocConsistencySkill().can_run(_ctx(tmp_path / "no_such")) is False


# ── 无问题路径 ────────────────────────────────────────────


class TestNoIssues:
    def test_success(self, tmp_path: Path):
        result = Skill.create("doc.consistency").run(_ctx(tmp_path), {
            "skill_snapshot": _minimal_skill_snapshot(3),
            "cli_snapshot": _minimal_cli_snapshot(),
            "doc_map": _minimal_doc_map(),
        })
        assert result.success is True

    def test_zero_issues(self, tmp_path: Path):
        result = Skill.create("doc.consistency").run(_ctx(tmp_path), {
            "skill_snapshot": _minimal_skill_snapshot(3),
            "cli_snapshot": _minimal_cli_snapshot(),
            "doc_map": _minimal_doc_map(),
        })
        assert result.data["issue_count"] == 0

    def test_docs_not_required(self, tmp_path: Path):
        result = Skill.create("doc.consistency").run(_ctx(tmp_path), {
            "skill_snapshot": _minimal_skill_snapshot(3),
            "cli_snapshot": _minimal_cli_snapshot(),
            "doc_map": _minimal_doc_map(),
        })
        assert result.data["docs_required"] is False

    def test_issues_list_empty(self, tmp_path: Path):
        result = Skill.create("doc.consistency").run(_ctx(tmp_path), {
            "skill_snapshot": _minimal_skill_snapshot(3),
            "cli_snapshot": _minimal_cli_snapshot(),
            "doc_map": _minimal_doc_map(),
        })
        assert result.data["issues"] == []


# ── Rule 1：stale_capability ──────────────────────────────


class TestRule1:
    def test_skill_count_gap_triggers_issue(self):
        """skill_snapshot 有 20 个 Skill，但文档中 skill_name mentions 只有 3 个。"""
        snap = _minimal_skill_snapshot(20)
        cli = _minimal_cli_snapshot()
        # doc_map 中 skill_name mentions 为空
        doc_map = _minimal_doc_map([{
            "path": "README.md",
            "headings": [],
            "mentions": {"skill_name": ["repo.scan", "git.status", "risk.check"]},
            "last_modified": "2026-01-01T00:00:00Z",
            "size_bytes": 100,
        }])
        issues = _rule1_stale_capability(snap, cli, doc_map)
        types = [i.type for i in issues]
        assert "stale_capability" in types

    def test_small_gap_no_issue(self):
        """skill_count=5，文档提及 3 个 — 差值 2，在容差内，不触发。"""
        snap = _minimal_skill_snapshot(5)
        cli = _minimal_cli_snapshot()
        doc_map = _minimal_doc_map([{
            "path": "README.md",
            "headings": [],
            "mentions": {"skill_name": ["a.b", "c.d", "e.f"]},
            "last_modified": "2026-01-01T00:00:00Z",
            "size_bytes": 100,
        }])
        issues = _rule1_stale_capability(snap, cli, doc_map)
        skill_issues = [i for i in issues if i.code_fact and "Skill" in i.code_fact
                        and "CLI" not in i.code_fact]
        assert len(skill_issues) == 0

    def test_undocumented_cli_command_triggers(self):
        """CLI 有 smartdev manifest diff，但文档中没有提及。"""
        snap = _minimal_skill_snapshot(3)
        cli = _minimal_cli_snapshot(["smartdev scan", "smartdev manifest diff"])
        doc_map = _minimal_doc_map([{
            "path": "README.md",
            "headings": [],
            "mentions": {"cli_command": ["smartdev scan"]},
            "last_modified": "2026-01-01T00:00:00Z",
            "size_bytes": 100,
        }])
        issues = _rule1_stale_capability(snap, cli, doc_map)
        cli_issues = [i for i in issues if "CLI" in i.code_fact]
        assert len(cli_issues) > 0

    def test_no_cli_issues_when_all_mentioned(self):
        """所有 CLI 命令都在 doc_map 里有对应提及。"""
        snap = _minimal_skill_snapshot(3)
        cli = _minimal_cli_snapshot(["smartdev scan"])
        doc_map = _minimal_doc_map([{
            "path": "README.md",
            "headings": [],
            "mentions": {"cli_command": ["smartdev scan"]},
            "last_modified": "2026-01-01T00:00:00Z",
            "size_bytes": 100,
        }])
        issues = _rule1_stale_capability(snap, cli, doc_map)
        cli_issues = [i for i in issues if "CLI" in (i.code_fact or "")]
        assert len(cli_issues) == 0

    def test_issue_has_required_fields(self):
        snap = _minimal_skill_snapshot(20)
        cli = _minimal_cli_snapshot()
        doc_map = _minimal_doc_map()
        issues = _rule1_stale_capability(snap, cli, doc_map)
        for issue in issues:
            assert issue.rule == "rule1"
            assert issue.type != ""
            assert issue.severity in ("high", "medium", "low")
            assert issue.doc != ""


# ── Rule 2：phase_status_mismatch ──────────────────────────


class TestRule2:
    def test_version_mismatch_triggers(self, tmp_path: Path):
        """CHANGELOG 最新版本 v0.3.0 但 pyproject.toml 写 0.4.0。"""
        _write(tmp_path / "pyproject.toml", '[project]\nversion = "0.4.0"\n')
        doc_map = _minimal_doc_map([{
            "path": "CHANGELOG.md",
            "headings": [],
            "mentions": {},
            "last_modified": "2026-01-01T00:00:00Z",
            "size_bytes": 100,
            "latest_version": "v0.3.0",
        }])
        issues = _rule2_phase_status(doc_map, tmp_path)
        types = [i.type for i in issues]
        assert "phase_status_mismatch" in types

    def test_unreleased_no_version_issue(self, tmp_path: Path):
        """CHANGELOG 最新是 Unreleased — 不触发版本不一致。"""
        _write(tmp_path / "pyproject.toml", '[project]\nversion = "0.4.0"\n')
        doc_map = _minimal_doc_map([{
            "path": "CHANGELOG.md",
            "headings": [],
            "mentions": {},
            "last_modified": "2026-01-01T00:00:00Z",
            "size_bytes": 100,
            "latest_version": "Unreleased",
        }])
        issues = _rule2_phase_status(doc_map, tmp_path)
        version_issues = [i for i in issues if "version" in i.doc_claim.lower()
                          or "pyproject" in i.code_fact.lower()]
        assert len(version_issues) == 0

    def test_matching_version_no_issue(self, tmp_path: Path):
        """CHANGELOG v0.4.0 与 pyproject.toml 0.4.0 一致 — 不触发。"""
        _write(tmp_path / "pyproject.toml", '[project]\nversion = "0.4.0"\n')
        doc_map = _minimal_doc_map([{
            "path": "CHANGELOG.md",
            "headings": [],
            "mentions": {},
            "last_modified": "2026-01-01T00:00:00Z",
            "size_bytes": 100,
            "latest_version": "v0.4.0",
        }])
        issues = _rule2_phase_status(doc_map, tmp_path)
        assert len(issues) == 0

    def test_phase_missing_in_claude_triggers(self, tmp_path: Path):
        """progress.md 提及 Phase 11C 但 CLAUDE.md 没有提及。"""
        doc_map = _minimal_doc_map([
            {
                "path": "docs/development-progress.md",
                "headings": [],
                "mentions": {"phase": ["Phase 11A", "Phase 11C"]},
                "last_modified": "2026-01-01T00:00:00Z",
                "size_bytes": 200,
            },
            {
                "path": "CLAUDE.md",
                "headings": [],
                "mentions": {"phase": ["Phase 11A"]},
                "last_modified": "2026-01-01T00:00:00Z",
                "size_bytes": 100,
            },
        ])
        issues = _rule2_phase_status(doc_map, tmp_path)
        phase_issues = [i for i in issues if i.type == "phase_status_mismatch"
                        and "CLAUDE.md" in i.doc]
        assert len(phase_issues) > 0

    def test_no_issue_when_no_pyproject(self, tmp_path: Path):
        """pyproject.toml 不存在 — 不触发版本不一致。"""
        doc_map = _minimal_doc_map([{
            "path": "CHANGELOG.md",
            "headings": [],
            "mentions": {},
            "last_modified": "2026-01-01T00:00:00Z",
            "size_bytes": 100,
            "latest_version": "v0.3.0",
        }])
        issues = _rule2_phase_status(doc_map, tmp_path)
        # 无 pyproject.toml，版本规则不触发
        version_issues = [i for i in issues if "pyproject" in i.code_fact.lower()]
        assert len(version_issues) == 0


# ── Rule 3：capability_overpromise ─────────────────────────


class TestRule3:
    def test_dont_do_in_design_but_mentioned_elsewhere(self, tmp_path: Path):
        """设计文档声明 ❌ 不做 auto apply，但 README 里提了 auto apply。"""
        _write(tmp_path / "docs" / "phase-11-design.md",
               "## 不做的事\n❌ 不做 auto apply patch\n❌ 不做 auto commit\n")
        _write(tmp_path / "README.md",
               "# SmartDev\n\nSupports auto apply patch feature.\n")
        doc_map = _minimal_doc_map([
            {
                "path": "docs/phase-11-design.md",
                "headings": ["## 不做的事"],
                "mentions": {},
                "last_modified": "2026-01-01T00:00:00Z",
                "size_bytes": 100,
            },
            {
                "path": "README.md",
                "headings": [],
                "mentions": {},
                "last_modified": "2026-01-01T00:00:00Z",
                "size_bytes": 100,
            },
        ])
        issues = _rule3_capability_overpromise(doc_map, tmp_path)
        overpromise = [i for i in issues if i.type == "capability_overpromise"]
        assert len(overpromise) > 0

    def test_no_design_doc_no_issue(self, tmp_path: Path):
        """没有 design doc — 规则 3 不触发。"""
        doc_map = _minimal_doc_map([{
            "path": "README.md",
            "headings": [],
            "mentions": {},
            "last_modified": "2026-01-01T00:00:00Z",
            "size_bytes": 100,
        }])
        issues = _rule3_capability_overpromise(doc_map, tmp_path)
        assert len(issues) == 0

    def test_no_dont_do_in_design_no_issue(self, tmp_path: Path):
        """design doc 没有 ❌ 声明 — 不触发。"""
        _write(tmp_path / "docs" / "phase-11-design.md",
               "## Goals\nBuild a great tool.\n")
        doc_map = _minimal_doc_map([{
            "path": "docs/phase-11-design.md",
            "headings": [],
            "mentions": {},
            "last_modified": "2026-01-01T00:00:00Z",
            "size_bytes": 100,
        }])
        issues = _rule3_capability_overpromise(doc_map, tmp_path)
        assert len(issues) == 0

    def test_issue_severity_is_high(self, tmp_path: Path):
        """规则 3 触发的 issue severity 必须是 high。"""
        _write(tmp_path / "docs" / "phase-11-design.md",
               "❌ 不做 auto_commit feature\n")
        _write(tmp_path / "README.md",
               "auto_commit feature is supported.\n")
        doc_map = _minimal_doc_map([
            {"path": "docs/phase-11-design.md", "headings": [], "mentions": {},
             "last_modified": "2026-01-01T00:00:00Z", "size_bytes": 100},
            {"path": "README.md", "headings": [], "mentions": {},
             "last_modified": "2026-01-01T00:00:00Z", "size_bytes": 100},
        ])
        issues = _rule3_capability_overpromise(doc_map, tmp_path)
        for i in issues:
            assert i.severity == "high"


# ── Rule 4：stale_test_baseline ───────────────────────────


class TestRule4:
    def test_stale_baseline_triggers(self):
        """progress.md 记录 1063 passed，CLAUDE.md 还写着 637 passed。"""
        doc_map = _minimal_doc_map([
            {
                "path": "docs/development-progress.md",
                "headings": [],
                "mentions": {"test_baseline": ["1063 passed"]},
                "last_modified": "2026-06-08T00:00:00Z",
                "size_bytes": 100,
            },
            {
                "path": "CLAUDE.md",
                "headings": [],
                "mentions": {"test_baseline": ["637 passed"]},
                "last_modified": "2026-01-01T00:00:00Z",
                "size_bytes": 100,
            },
        ])
        issues = _rule4_test_baseline(doc_map)
        stale = [i for i in issues if i.type == "stale_test_baseline"]
        assert len(stale) > 0

    def test_close_numbers_no_issue(self):
        """progress 有 1063，CLAUDE.md 有 1050 — 差值 13，在容差内，不触发。"""
        doc_map = _minimal_doc_map([
            {
                "path": "docs/development-progress.md",
                "headings": [],
                "mentions": {"test_baseline": ["1063 passed"]},
                "last_modified": "2026-06-08T00:00:00Z",
                "size_bytes": 100,
            },
            {
                "path": "CLAUDE.md",
                "headings": [],
                "mentions": {"test_baseline": ["1050 passed"]},
                "last_modified": "2026-01-01T00:00:00Z",
                "size_bytes": 100,
            },
        ])
        issues = _rule4_test_baseline(doc_map)
        assert len(issues) == 0

    def test_no_progress_doc_no_issue(self):
        """没有 progress.md — 规则 4 不触发。"""
        doc_map = _minimal_doc_map([{
            "path": "CLAUDE.md",
            "headings": [],
            "mentions": {"test_baseline": ["637 passed"]},
            "last_modified": "2026-01-01T00:00:00Z",
            "size_bytes": 100,
        }])
        issues = _rule4_test_baseline(doc_map)
        assert len(issues) == 0

    def test_issue_severity_is_low(self):
        doc_map = _minimal_doc_map([
            {
                "path": "docs/development-progress.md",
                "headings": [],
                "mentions": {"test_baseline": ["1063 passed"]},
                "last_modified": "2026-06-08T00:00:00Z",
                "size_bytes": 100,
            },
            {
                "path": "CLAUDE.md",
                "headings": [],
                "mentions": {"test_baseline": ["637 passed"]},
                "last_modified": "2026-01-01T00:00:00Z",
                "size_bytes": 100,
            },
        ])
        issues = _rule4_test_baseline(doc_map)
        for i in issues:
            assert i.severity == "low"


# ── Rule 5：public_surface_changed_docs_not_updated ────────


class TestRule5:
    def _make_manifest(self, ts: str, public_changed: bool = True) -> dict:
        return {
            "public_surface_changed": public_changed,
            "timestamp": ts,
            "changed_files": ["smartdev/cli.py"],
        }

    def _make_doc_map_with_old_readme(self, readme_ts: str) -> dict:
        return _minimal_doc_map([{
            "path": "README.md",
            "headings": [],
            "mentions": {},
            "last_modified": readme_ts,
            "size_bytes": 100,
        }])

    def test_old_readme_triggers(self):
        """manifest 时间戳是 2026-06-08，README 是 2026-01-01 — 触发。"""
        manifest = self._make_manifest("2026-06-08T12:00:00Z")
        doc_map = self._make_doc_map_with_old_readme("2026-01-01T00:00:00Z")
        issues = _rule5_public_surface(doc_map, manifest)
        types = [i.type for i in issues]
        assert "public_surface_changed_docs_not_updated" in types

    def test_updated_readme_no_issue(self):
        """README 比 manifest 更新 — 不触发。"""
        manifest = self._make_manifest("2026-06-08T10:00:00Z")
        doc_map = self._make_doc_map_with_old_readme("2026-06-08T12:00:00Z")
        issues = _rule5_public_surface(doc_map, manifest)
        assert len(issues) == 0

    def test_no_public_surface_change_no_issue(self):
        """manifest.public_surface_changed=False — 不触发。"""
        manifest = self._make_manifest("2026-06-08T12:00:00Z", public_changed=False)
        doc_map = self._make_doc_map_with_old_readme("2026-01-01T00:00:00Z")
        issues = _rule5_public_surface(doc_map, manifest)
        assert len(issues) == 0

    def test_empty_manifest_no_issue(self):
        """change_manifest 为空 — 不触发。"""
        doc_map = self._make_doc_map_with_old_readme("2026-01-01T00:00:00Z")
        issues = _rule5_public_surface(doc_map, {})
        assert len(issues) == 0

    def test_issue_severity_is_medium(self):
        manifest = self._make_manifest("2026-06-08T12:00:00Z")
        doc_map = self._make_doc_map_with_old_readme("2026-01-01T00:00:00Z")
        issues = _rule5_public_surface(doc_map, manifest)
        for i in issues:
            assert i.severity == "medium"


# ── 单条规则失败不阻断其他规则 ────────────────────────────


class TestRuleIsolation:
    def test_skill_runs_despite_bad_inputs(self, tmp_path: Path):
        """传入不完整的快照，Skill 仍应返回 success=True。"""
        result = Skill.create("doc.consistency").run(_ctx(tmp_path), {
            "skill_snapshot": {},
            "cli_snapshot": {},
            "doc_map": {},
        })
        assert result.success is True

    def test_no_manifest_skips_rule5(self, tmp_path: Path):
        """不传 change_manifest — 规则 5 静默跳过。"""
        result = Skill.create("doc.consistency").run(_ctx(tmp_path), {
            "skill_snapshot": _minimal_skill_snapshot(),
            "cli_snapshot": _minimal_cli_snapshot(),
            "doc_map": _minimal_doc_map(),
        })
        rule5_issues = [i for i in result.data["issues"]
                        if i.get("rule") == "rule5"]
        assert len(rule5_issues) == 0


# ── 最简调用（自动生成快照）──────────────────────────────


class TestAutoGenerate:
    def test_minimal_call_succeeds(self, tmp_path: Path):
        """不传任何快照，Skill 自动生成并运行。"""
        result = Skill.create("doc.consistency").run(_ctx(tmp_path))
        assert result.success is True
        assert "issue_count" in result.data
        assert "issues" in result.data

    def test_minimal_call_has_generated_at(self, tmp_path: Path):
        result = Skill.create("doc.consistency").run(_ctx(tmp_path))
        assert "T" in result.data["generated_at"]


# ── ConsistencyIssue.to_dict 结构 ─────────────────────────


class TestConsistencyIssueModel:
    def test_to_dict_required_keys(self):
        issue = ConsistencyIssue(
            rule="rule1",
            type="stale_capability",
            severity="medium",
            doc="README.md",
            code_fact="18 skills registered",
            doc_claim="only 3 mentioned",
        )
        d = issue.to_dict()
        assert set(d.keys()) >= {"rule", "type", "severity", "doc", "code_fact", "doc_claim"}

    def test_suggestion_included_when_set(self):
        issue = ConsistencyIssue(
            rule="rule1", type="stale_capability", severity="medium",
            doc="README.md", code_fact="x", doc_claim="y",
            suggestion="Update README",
        )
        d = issue.to_dict()
        assert "suggestion" in d
        assert d["suggestion"] == "Update README"

    def test_suggestion_absent_when_empty(self):
        issue = ConsistencyIssue(
            rule="rule1", type="stale_capability", severity="medium",
            doc="README.md", code_fact="x", doc_claim="y",
        )
        d = issue.to_dict()
        assert "suggestion" not in d


# ── severity_summary 统计 ─────────────────────────────────


class TestSeveritySummary:
    def test_counts_correct(self, tmp_path: Path):
        """手动构造包含各严重度问题的场景，验证 severity_summary。"""
        # 触发 rule 1（medium）和 rule 4（low）
        doc_map = _minimal_doc_map([
            {
                "path": "docs/development-progress.md",
                "headings": [],
                "mentions": {"test_baseline": ["1063 passed"]},
                "last_modified": "2026-06-08T00:00:00Z",
                "size_bytes": 100,
            },
            {
                "path": "CLAUDE.md",
                "headings": [],
                "mentions": {"test_baseline": ["500 passed"]},
                "last_modified": "2026-01-01T00:00:00Z",
                "size_bytes": 100,
            },
        ])
        result = Skill.create("doc.consistency").run(_ctx(tmp_path), {
            "skill_snapshot": _minimal_skill_snapshot(20),  # 触发 rule1 medium
            "cli_snapshot": _minimal_cli_snapshot(),
            "doc_map": doc_map,
        })
        summary = result.data["severity_summary"]
        assert "high" in summary
        assert "medium" in summary
        assert "low" in summary
        # rule4 应该触发 low
        assert summary["low"] >= 1
