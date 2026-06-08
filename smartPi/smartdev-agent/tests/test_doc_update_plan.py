"""
doc.update.plan Skill 测试 — Phase 11C Step 5

覆盖：
1. Skill 注册验证 + R0
2. can_run()
3. 空 issues → 无更新项
4. update_kind 分类（status_sync / capability_boundary / expression_alignment）
5. priority 计算（取最高 severity）
6. no_change_items（设计文档 / CHANGELOG）
7. suggestions 生成（stale_test_baseline / phase_status_mismatch / stale_capability 等）
8. 多 issue 同一文档合并
9. update_items 按 priority 排序
10. 最简调用（自动运行 doc.consistency）
11. 传入 consistency_issues 跳过 doc.consistency
12. build_update_plan 单元测试
13. UpdateItem.to_dict / NoChangeItem.to_dict 结构
14. next_steps 建议
"""

from __future__ import annotations

from pathlib import Path

import pytest

from smartdev.models import ProjectContext
from smartdev.skills.base import Skill
from smartdev.skills.doc_update_plan.skill import (
    NoChangeItem,
    UpdateItem,
    DocUpdatePlanSkill,
    _build_suggestion,
    _is_no_change_doc,
    build_update_plan,
)


# ── Helpers ────────────────────────────────────────────────


def _ctx(path: Path) -> ProjectContext:
    return ProjectContext(project_path=path)


def _issue(type_: str, severity: str, doc: str,
           code_fact: str = "code fact", doc_claim: str = "doc claim") -> dict:
    return {
        "rule": "rule1",
        "type": type_,
        "severity": severity,
        "doc": doc,
        "code_fact": code_fact,
        "doc_claim": doc_claim,
    }


# ── 注册验证 ──────────────────────────────────────────────


def test_skill_registered():
    import smartdev.skills  # noqa: F401
    skill = Skill.get_skill("doc.update.plan")
    assert skill is not None
    assert skill.name == "doc.update.plan"


def test_skill_is_r0():
    from smartdev.models import RiskLevel
    assert DocUpdatePlanSkill.risk_level == RiskLevel.R0


# ── can_run ───────────────────────────────────────────────


def test_can_run_true(tmp_path: Path):
    assert DocUpdatePlanSkill().can_run(_ctx(tmp_path)) is True


def test_can_run_false(tmp_path: Path):
    assert DocUpdatePlanSkill().can_run(_ctx(tmp_path / "no_such")) is False


# ── 空 issues ─────────────────────────────────────────────


class TestNoIssues:
    def test_success(self, tmp_path: Path):
        result = Skill.create("doc.update.plan").run(_ctx(tmp_path), {
            "consistency_issues": []
        })
        assert result.success is True

    def test_zero_update_count(self, tmp_path: Path):
        result = Skill.create("doc.update.plan").run(_ctx(tmp_path), {
            "consistency_issues": []
        })
        assert result.data["update_count"] == 0

    def test_empty_update_items(self, tmp_path: Path):
        result = Skill.create("doc.update.plan").run(_ctx(tmp_path), {
            "consistency_issues": []
        })
        assert result.data["update_items"] == []

    def test_summary_no_update(self, tmp_path: Path):
        result = Skill.create("doc.update.plan").run(_ctx(tmp_path), {
            "consistency_issues": []
        })
        assert "无需更新" in result.summary or "一致" in result.summary


# ── update_kind 分类 ──────────────────────────────────────


class TestUpdateKind:
    def test_stale_baseline_is_status_sync(self, tmp_path: Path):
        issues = [_issue("stale_test_baseline", "low", "CLAUDE.md")]
        update_items, _ = build_update_plan(issues)
        non_no_change = [i for i in update_items if i.doc == "CLAUDE.md"]
        assert len(non_no_change) == 1
        assert non_no_change[0].update_kind == "status_sync"

    def test_phase_mismatch_is_status_sync(self, tmp_path: Path):
        issues = [_issue("phase_status_mismatch", "medium", "CLAUDE.md")]
        update_items, _ = build_update_plan(issues)
        items = [i for i in update_items if i.doc == "CLAUDE.md"]
        assert items[0].update_kind == "status_sync"

    def test_stale_capability_is_capability_boundary(self):
        issues = [_issue("stale_capability", "medium", "README.md")]
        update_items, _ = build_update_plan(issues)
        items = [i for i in update_items if i.doc == "README.md"]
        assert items[0].update_kind == "capability_boundary"

    def test_overpromise_is_capability_boundary(self):
        issues = [_issue("capability_overpromise", "high", "README.md")]
        update_items, _ = build_update_plan(issues)
        items = [i for i in update_items if i.doc == "README.md"]
        assert items[0].update_kind == "capability_boundary"

    def test_public_surface_is_capability_boundary(self):
        issues = [_issue("public_surface_changed_docs_not_updated", "medium", "README.md")]
        update_items, _ = build_update_plan(issues)
        items = [i for i in update_items if i.doc == "README.md"]
        assert items[0].update_kind == "capability_boundary"

    def test_mixed_kinds_takes_highest_priority_kind(self):
        """同一文档同时有 status_sync 和 capability_boundary — 取 capability_boundary。"""
        issues = [
            _issue("stale_test_baseline", "low", "README.md"),
            _issue("stale_capability", "medium", "README.md"),
        ]
        update_items, _ = build_update_plan(issues)
        items = [i for i in update_items if i.doc == "README.md"]
        assert items[0].update_kind == "capability_boundary"


# ── priority 计算 ─────────────────────────────────────────


class TestPriority:
    def test_high_severity_gives_high_priority(self):
        issues = [_issue("capability_overpromise", "high", "README.md")]
        update_items, _ = build_update_plan(issues)
        items = [i for i in update_items if i.doc == "README.md"]
        assert items[0].priority == "high"

    def test_low_severity_gives_low_priority(self):
        issues = [_issue("stale_test_baseline", "low", "CLAUDE.md")]
        update_items, _ = build_update_plan(issues)
        items = [i for i in update_items if i.doc == "CLAUDE.md"]
        assert items[0].priority == "low"

    def test_mixed_severities_takes_highest(self):
        """同一文档有 low 和 medium issue — priority 应为 medium。"""
        issues = [
            _issue("stale_test_baseline", "low", "CLAUDE.md"),
            _issue("phase_status_mismatch", "medium", "CLAUDE.md"),
        ]
        update_items, _ = build_update_plan(issues)
        items = [i for i in update_items if i.doc == "CLAUDE.md"]
        assert items[0].priority == "medium"


# ── no_change_items ───────────────────────────────────────


class TestNoChangeItems:
    def test_design_doc_no_change(self):
        issues = [_issue("stale_capability", "medium", "docs/phase-11-design.md")]
        _, no_change = build_update_plan(issues)
        docs = [i.doc for i in no_change]
        assert "docs/phase-11-design.md" in docs

    def test_changelog_no_change(self):
        issues = [_issue("phase_status_mismatch", "medium", "CHANGELOG.md")]
        _, no_change = build_update_plan(issues)
        docs = [i.doc for i in no_change]
        assert "CHANGELOG.md" in docs

    def test_readme_is_not_no_change(self):
        issues = [_issue("stale_capability", "medium", "README.md")]
        _, no_change = build_update_plan(issues)
        docs = [i.doc for i in no_change]
        assert "README.md" not in docs

    def test_no_change_has_reason(self):
        issues = [_issue("stale_capability", "medium", "docs/phase-11-design.md")]
        _, no_change = build_update_plan(issues)
        for item in no_change:
            assert item.reason != ""


# ── _is_no_change_doc ─────────────────────────────────────


class TestIsNoChangeDoc:
    def test_design_md(self):
        is_nc, reason = _is_no_change_doc("docs/phase-11c-design.md")
        assert is_nc is True
        assert reason != ""

    def test_changelog(self):
        is_nc, _ = _is_no_change_doc("CHANGELOG.md")
        assert is_nc is True

    def test_readme_not_no_change(self):
        is_nc, _ = _is_no_change_doc("README.md")
        assert is_nc is False

    def test_claude_md_not_no_change(self):
        is_nc, _ = _is_no_change_doc("CLAUDE.md")
        assert is_nc is False


# ── suggestions 生成 ──────────────────────────────────────


class TestBuildSuggestion:
    def test_stale_baseline_has_numbers(self):
        issue = _issue("stale_test_baseline", "low", "CLAUDE.md",
                       code_fact="1102 passed", doc_claim="637 passed")
        sugg = _build_suggestion(issue)
        assert "637" in sugg and "1102" in sugg

    def test_phase_mismatch_version(self):
        issue = _issue("phase_status_mismatch", "medium", "CHANGELOG.md",
                       code_fact="pyproject.toml version = 0.4.0",
                       doc_claim="CHANGELOG latest = v0.3.0")
        sugg = _build_suggestion(issue)
        assert "0.4.0" in sugg or "版本" in sugg

    def test_stale_capability_mentions_cli(self):
        issue = _issue("stale_capability", "medium", "README.md",
                       code_fact="CLI 有 17 条命令，其中 2 条未在文档中提及",
                       doc_claim="未提及的命令：smartdev manifest diff")
        sugg = _build_suggestion(issue)
        assert "CLI" in sugg or "命令" in sugg

    def test_overpromise_mentions_design(self):
        issue = _issue("capability_overpromise", "high", "README.md",
                       code_fact="design.md 声明不做 auto apply",
                       doc_claim="README.md 提到 auto apply")
        sugg = _build_suggestion(issue)
        assert "过度" in sugg or "❌" in sugg or "设计" in sugg


# ── 多 issue 同一文档合并 ─────────────────────────────────


class TestMultiIssuesMerge:
    def test_same_doc_merged_to_one_item(self):
        issues = [
            _issue("stale_test_baseline", "low", "CLAUDE.md"),
            _issue("phase_status_mismatch", "medium", "CLAUDE.md"),
        ]
        update_items, _ = build_update_plan(issues)
        claude_items = [i for i in update_items if i.doc == "CLAUDE.md"]
        assert len(claude_items) == 1

    def test_merged_item_has_multiple_reasons(self):
        issues = [
            _issue("stale_test_baseline", "low", "CLAUDE.md",
                   code_fact="1102 passed", doc_claim="637 passed"),
            _issue("phase_status_mismatch", "medium", "CLAUDE.md",
                   code_fact="phase 11C", doc_claim="phase 11A"),
        ]
        update_items, _ = build_update_plan(issues)
        claude_items = [i for i in update_items if i.doc == "CLAUDE.md"]
        assert len(claude_items[0].reasons) >= 1

    def test_merged_item_has_multiple_issue_types(self):
        issues = [
            _issue("stale_test_baseline", "low", "CLAUDE.md"),
            _issue("phase_status_mismatch", "medium", "CLAUDE.md"),
        ]
        update_items, _ = build_update_plan(issues)
        claude_items = [i for i in update_items if i.doc == "CLAUDE.md"]
        assert len(claude_items[0].issues) == 2


# ── update_items 排序 ─────────────────────────────────────


class TestSorting:
    def test_high_priority_first(self):
        issues = [
            _issue("stale_test_baseline", "low", "CLAUDE.md"),
            _issue("capability_overpromise", "high", "README.md"),
            _issue("phase_status_mismatch", "medium", "docs/guide.md"),
        ]
        update_items, _ = build_update_plan(issues)
        priorities = [i.priority for i in update_items]
        order = {"high": 0, "medium": 1, "low": 2}
        assert priorities == sorted(priorities, key=lambda p: order.get(p, 2))


# ── 最简调用（自动运行 doc.consistency）────────────────────


class TestAutoRun:
    def test_minimal_call_succeeds(self, tmp_path: Path):
        result = Skill.create("doc.update.plan").run(_ctx(tmp_path))
        assert result.success is True

    def test_minimal_call_has_generated_at(self, tmp_path: Path):
        result = Skill.create("doc.update.plan").run(_ctx(tmp_path))
        assert "T" in result.data["generated_at"]

    def test_minimal_call_issue_count_input(self, tmp_path: Path):
        result = Skill.create("doc.update.plan").run(_ctx(tmp_path))
        assert "issue_count_input" in result.data


# ── 传入 consistency_issues ───────────────────────────────


class TestPassIssues:
    def test_passes_through_correctly(self, tmp_path: Path):
        """传入 3 个 issues，输出 update_items 应该只包含可更新的文档。"""
        issues = [
            _issue("stale_test_baseline", "low", "CLAUDE.md"),
            _issue("stale_capability", "medium", "README.md"),
            _issue("stale_capability", "medium", "docs/phase-11-design.md"),  # no_change
        ]
        result = Skill.create("doc.update.plan").run(_ctx(tmp_path), {
            "consistency_issues": issues
        })
        update_docs = [i["doc"] for i in result.data["update_items"]]
        no_change_docs = [i["doc"] for i in result.data["no_change_items"]]
        assert "CLAUDE.md" in update_docs
        assert "README.md" in update_docs
        assert "docs/phase-11-design.md" in no_change_docs

    def test_issue_count_input_matches(self, tmp_path: Path):
        issues = [_issue("stale_test_baseline", "low", "CLAUDE.md")]
        result = Skill.create("doc.update.plan").run(_ctx(tmp_path), {
            "consistency_issues": issues
        })
        assert result.data["issue_count_input"] == 1


# ── UpdateItem.to_dict / NoChangeItem.to_dict ─────────────


class TestModelDict:
    def test_update_item_keys(self):
        item = UpdateItem(
            doc="README.md",
            update_kind="status_sync",
            priority="medium",
            reasons=["r1"],
            suggestions=["s1"],
            issues=["stale_capability"],
        )
        d = item.to_dict()
        assert set(d.keys()) >= {"doc", "update_kind", "update_kind_label",
                                   "priority", "reasons", "suggestions", "issues"}

    def test_update_item_kind_label(self):
        item = UpdateItem(
            doc="README.md", update_kind="status_sync",
            priority="low", reasons=[], suggestions=[], issues=[],
        )
        d = item.to_dict()
        assert "状态同步" in d["update_kind_label"]

    def test_no_change_item_keys(self):
        item = NoChangeItem(doc="CHANGELOG.md", reason="历史记录")
        d = item.to_dict()
        assert set(d.keys()) == {"doc", "reason"}


# ── next_steps ────────────────────────────────────────────


class TestNextSteps:
    def test_no_issues_next_step(self, tmp_path: Path):
        result = Skill.create("doc.update.plan").run(_ctx(tmp_path), {
            "consistency_issues": []
        })
        assert any("无需更新" in s or "继续" in s for s in result.next_steps)

    def test_has_patch_propose_suggestion(self, tmp_path: Path):
        issues = [_issue("stale_test_baseline", "low", "CLAUDE.md")]
        result = Skill.create("doc.update.plan").run(_ctx(tmp_path), {
            "consistency_issues": issues
        })
        assert any("patch" in s.lower() or "propose" in s.lower() for s in result.next_steps)
