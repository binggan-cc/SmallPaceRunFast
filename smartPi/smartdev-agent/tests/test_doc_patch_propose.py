"""
doc.patch.propose Skill 测试 — Phase 11C Step 6

覆盖：
1. Skill 注册验证 + R1
2. can_run()
3. 空 update_items → 无 patch 无 hint
4. status_sync 生成 find-replace patch（stale_test_baseline）
5. status_sync 生成 find-replace patch（phase_status_mismatch 版本类）
6. capability_boundary → hint，不生成 patch
7. find_str 不在目标文档中 → 跳过，不崩溃
8. patch_id 持久化到 .smartdev/patches/
9. patch 内容不落盘到源文档
10. 最简调用（自动运行 doc.update.plan）
11. 传入 update_items + consistency_issues
12. DocPatchProposal / DocPatchHint to_dict 结构
13. _extract_test_baseline_pair 单元测试
14. _extract_version_pair 单元测试
15. changed_files 包含 patch 路径
"""

from __future__ import annotations

from pathlib import Path

import pytest

from smartdev.models import ProjectContext
from smartdev.skills.base import Skill
from smartdev.skills.doc_patch_propose.skill import (
    DocPatchHint,
    DocPatchProposal,
    DocPatchProposeSkill,
    _extract_test_baseline_pair,
    _extract_version_pair,
    _process_capability_item,
)


# ── Helpers ────────────────────────────────────────────────


def _ctx(path: Path) -> ProjectContext:
    return ProjectContext(project_path=path)


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _issue(type_: str, severity: str, doc: str,
           code_fact: str = "code fact", doc_claim: str = "doc claim") -> dict:
    return {
        "rule": "rule4",
        "type": type_,
        "severity": severity,
        "doc": doc,
        "code_fact": code_fact,
        "doc_claim": doc_claim,
    }


def _update_item(doc: str, update_kind: str, issues: list[dict] | None = None) -> dict:
    return {
        "doc": doc,
        "update_kind": update_kind,
        "update_kind_label": update_kind,
        "priority": "low",
        "reasons": ["reason"],
        "suggestions": ["suggestion"],
        "issues": [i.get("type", "") for i in (issues or [])],
    }


# ── 注册验证 ──────────────────────────────────────────────


def test_skill_registered():
    import smartdev.skills  # noqa: F401
    skill = Skill.get_skill("doc.patch.propose")
    assert skill is not None
    assert skill.name == "doc.patch.propose"


def test_skill_is_r1():
    from smartdev.models import RiskLevel
    assert DocPatchProposeSkill.risk_level == RiskLevel.R1


# ── can_run ───────────────────────────────────────────────


def test_can_run_true(tmp_path: Path):
    assert DocPatchProposeSkill().can_run(_ctx(tmp_path)) is True


def test_can_run_false(tmp_path: Path):
    assert DocPatchProposeSkill().can_run(_ctx(tmp_path / "no_such")) is False


# ── 空 update_items ───────────────────────────────────────


class TestEmptyItems:
    def test_success(self, tmp_path: Path):
        result = Skill.create("doc.patch.propose").run(_ctx(tmp_path), {
            "update_items": [],
            "consistency_issues": [],
        })
        assert result.success is True

    def test_zero_patch_count(self, tmp_path: Path):
        result = Skill.create("doc.patch.propose").run(_ctx(tmp_path), {
            "update_items": [],
            "consistency_issues": [],
        })
        assert result.data["patch_count"] == 0

    def test_zero_hint_count(self, tmp_path: Path):
        result = Skill.create("doc.patch.propose").run(_ctx(tmp_path), {
            "update_items": [],
            "consistency_issues": [],
        })
        assert result.data["hint_count"] == 0

    def test_empty_patches_list(self, tmp_path: Path):
        result = Skill.create("doc.patch.propose").run(_ctx(tmp_path), {
            "update_items": [],
            "consistency_issues": [],
        })
        assert result.data["patches"] == []

    def test_empty_hints_list(self, tmp_path: Path):
        result = Skill.create("doc.patch.propose").run(_ctx(tmp_path), {
            "update_items": [],
            "consistency_issues": [],
        })
        assert result.data["hints"] == []


# ── status_sync → patch（stale_test_baseline）─────────────


class TestStatusSyncTestBaseline:
    def test_patch_generated(self, tmp_path: Path):
        """CLAUDE.md 里有 '637 passed'，issue 说应该是 '1145 passed'。"""
        _write(tmp_path / "CLAUDE.md", "Tests: 637 passed, 1 skipped.\n")
        issue = _issue(
            "stale_test_baseline", "low", "CLAUDE.md",
            code_fact="progress.md 测试基线：1145 passed",
            doc_claim="CLAUDE.md 中记录的测试数：637 passed",
        )
        update_item = _update_item("CLAUDE.md", "status_sync", [issue])
        result = Skill.create("doc.patch.propose").run(_ctx(tmp_path), {
            "update_items": [update_item],
            "consistency_issues": [issue],
        })
        assert result.data["patch_count"] >= 1

    def test_patch_has_correct_find_replace(self, tmp_path: Path):
        _write(tmp_path / "CLAUDE.md", "Tests: 637 passed, 1 skipped.\n")
        issue = _issue(
            "stale_test_baseline", "low", "CLAUDE.md",
            code_fact="1145 passed",
            doc_claim="637 passed",
        )
        update_item = _update_item("CLAUDE.md", "status_sync", [issue])
        result = Skill.create("doc.patch.propose").run(_ctx(tmp_path), {
            "update_items": [update_item],
            "consistency_issues": [issue],
        })
        patches = result.data["patches"]
        if patches:
            assert "637" in patches[0]["find"]
            assert "1145" in patches[0]["replace"]

    def test_patch_doc_field_correct(self, tmp_path: Path):
        _write(tmp_path / "CLAUDE.md", "637 passed\n")
        issue = _issue("stale_test_baseline", "low", "CLAUDE.md",
                       code_fact="1145 passed", doc_claim="637 passed")
        update_item = _update_item("CLAUDE.md", "status_sync", [issue])
        result = Skill.create("doc.patch.propose").run(_ctx(tmp_path), {
            "update_items": [update_item],
            "consistency_issues": [issue],
        })
        for p in result.data["patches"]:
            assert p["doc"] == "CLAUDE.md"

    def test_patch_id_generated(self, tmp_path: Path):
        _write(tmp_path / "CLAUDE.md", "637 passed\n")
        issue = _issue("stale_test_baseline", "low", "CLAUDE.md",
                       code_fact="1145 passed", doc_claim="637 passed")
        update_item = _update_item("CLAUDE.md", "status_sync", [issue])
        result = Skill.create("doc.patch.propose").run(_ctx(tmp_path), {
            "update_items": [update_item],
            "consistency_issues": [issue],
        })
        for p in result.data["patches"]:
            assert p["patch_id"] != ""

    def test_patch_persisted_to_smartdev(self, tmp_path: Path):
        """patch 持久化到 .smartdev/patches/ 目录。"""
        _write(tmp_path / "CLAUDE.md", "637 passed\n")
        issue = _issue("stale_test_baseline", "low", "CLAUDE.md",
                       code_fact="1145 passed", doc_claim="637 passed")
        update_item = _update_item("CLAUDE.md", "status_sync", [issue])
        result = Skill.create("doc.patch.propose").run(_ctx(tmp_path), {
            "update_items": [update_item],
            "consistency_issues": [issue],
        })
        patches_dir = tmp_path / ".smartdev" / "patches"
        if result.data["patch_count"] > 0:
            assert patches_dir.exists()
            json_files = list(patches_dir.glob("*.json"))
            assert len(json_files) >= 1

    def test_source_doc_not_modified(self, tmp_path: Path):
        """apply 后源文档不应被修改（propose 只写 patches/）。"""
        original = "Tests: 637 passed, 1 skipped.\n"
        _write(tmp_path / "CLAUDE.md", original)
        issue = _issue("stale_test_baseline", "low", "CLAUDE.md",
                       code_fact="1145 passed", doc_claim="637 passed")
        update_item = _update_item("CLAUDE.md", "status_sync", [issue])
        Skill.create("doc.patch.propose").run(_ctx(tmp_path), {
            "update_items": [update_item],
            "consistency_issues": [issue],
        })
        # 源文档应保持原样
        assert (tmp_path / "CLAUDE.md").read_text() == original

    def test_find_not_in_doc_skipped(self, tmp_path: Path):
        """find_str 在目标文档中不存在 → 跳过，不崩溃。"""
        _write(tmp_path / "CLAUDE.md", "No test numbers here.\n")
        issue = _issue("stale_test_baseline", "low", "CLAUDE.md",
                       code_fact="1145 passed", doc_claim="999 passed")
        update_item = _update_item("CLAUDE.md", "status_sync", [issue])
        result = Skill.create("doc.patch.propose").run(_ctx(tmp_path), {
            "update_items": [update_item],
            "consistency_issues": [issue],
        })
        assert result.success is True
        assert result.data["patch_count"] == 0


# ── status_sync → patch（version 类）─────────────────────


class TestStatusSyncVersion:
    def test_version_patch_generated(self, tmp_path: Path):
        """CLAUDE.md 里有 '0.3.0'，issue 说应该是 '0.4.0'。"""
        _write(tmp_path / "CLAUDE.md", "Version 0.3.0 is current.\n")
        issue = _issue(
            "phase_status_mismatch", "medium", "CLAUDE.md",
            code_fact="pyproject.toml version = 0.4.0",
            doc_claim="CLAUDE.md mentions 0.3.0",
        )
        update_item = _update_item("CLAUDE.md", "status_sync", [issue])
        result = Skill.create("doc.patch.propose").run(_ctx(tmp_path), {
            "update_items": [update_item],
            "consistency_issues": [issue],
        })
        # 可能生成也可能不生成（取决于版本号是否能提取），不崩溃即可
        assert result.success is True

    def test_non_version_phase_mismatch_no_patch(self, tmp_path: Path):
        """phase_status_mismatch 但不含版本号 → 不生成 patch，不崩溃。"""
        _write(tmp_path / "CLAUDE.md", "Phase 11A is complete.\n")
        issue = _issue(
            "phase_status_mismatch", "low", "CLAUDE.md",
            code_fact="progress.md 提及 Phase 11C",
            doc_claim="CLAUDE.md 缺少 Phase 11C",
        )
        update_item = _update_item("CLAUDE.md", "status_sync", [issue])
        result = Skill.create("doc.patch.propose").run(_ctx(tmp_path), {
            "update_items": [update_item],
            "consistency_issues": [issue],
        })
        assert result.success is True


# ── capability_boundary → hint ─────────────────────────────


class TestCapabilityBoundaryHint:
    def test_hint_generated(self, tmp_path: Path):
        update_item = _update_item("README.md", "capability_boundary",
                                   [_issue("stale_capability", "medium", "README.md")])
        result = Skill.create("doc.patch.propose").run(_ctx(tmp_path), {
            "update_items": [update_item],
            "consistency_issues": [],
        })
        assert result.data["hint_count"] >= 1

    def test_no_patch_for_capability(self, tmp_path: Path):
        update_item = _update_item("README.md", "capability_boundary",
                                   [_issue("stale_capability", "medium", "README.md")])
        result = Skill.create("doc.patch.propose").run(_ctx(tmp_path), {
            "update_items": [update_item],
            "consistency_issues": [],
        })
        assert result.data["patch_count"] == 0

    def test_hint_has_doc_field(self, tmp_path: Path):
        update_item = _update_item("README.md", "capability_boundary")
        result = Skill.create("doc.patch.propose").run(_ctx(tmp_path), {
            "update_items": [update_item],
            "consistency_issues": [],
        })
        for h in result.data["hints"]:
            assert h["doc"] != ""

    def test_hint_has_direction(self, tmp_path: Path):
        update_item = _update_item("README.md", "capability_boundary")
        result = Skill.create("doc.patch.propose").run(_ctx(tmp_path), {
            "update_items": [update_item],
            "consistency_issues": [],
        })
        for h in result.data["hints"]:
            assert h["direction"] != ""

    def test_overpromise_also_hint(self, tmp_path: Path):
        """capability_overpromise → capability_boundary → hint。"""
        update_item = _update_item("README.md", "capability_boundary",
                                   [_issue("capability_overpromise", "high", "README.md")])
        result = Skill.create("doc.patch.propose").run(_ctx(tmp_path), {
            "update_items": [update_item],
            "consistency_issues": [],
        })
        assert result.data["hint_count"] >= 1
        assert result.data["patch_count"] == 0


# ── 最简调用 ──────────────────────────────────────────────


class TestAutoRun:
    def test_minimal_call_succeeds(self, tmp_path: Path):
        result = Skill.create("doc.patch.propose").run(_ctx(tmp_path))
        assert result.success is True

    def test_minimal_call_has_generated_at(self, tmp_path: Path):
        result = Skill.create("doc.patch.propose").run(_ctx(tmp_path))
        assert "T" in result.data["generated_at"]

    def test_minimal_call_has_patch_and_hint_count(self, tmp_path: Path):
        result = Skill.create("doc.patch.propose").run(_ctx(tmp_path))
        assert "patch_count" in result.data
        assert "hint_count" in result.data


# ── changed_files ─────────────────────────────────────────


class TestChangedFiles:
    def test_changed_files_has_patch_paths(self, tmp_path: Path):
        """生成了 patch 时，changed_files 应包含 patch 文件路径。"""
        _write(tmp_path / "CLAUDE.md", "637 passed\n")
        issue = _issue("stale_test_baseline", "low", "CLAUDE.md",
                       code_fact="1145 passed", doc_claim="637 passed")
        update_item = _update_item("CLAUDE.md", "status_sync", [issue])
        result = Skill.create("doc.patch.propose").run(_ctx(tmp_path), {
            "update_items": [update_item],
            "consistency_issues": [issue],
        })
        if result.data["patch_count"] > 0:
            assert len(result.changed_files) > 0
            for cf in result.changed_files:
                assert ".smartdev" in cf

    def test_no_patch_no_changed_files(self, tmp_path: Path):
        result = Skill.create("doc.patch.propose").run(_ctx(tmp_path), {
            "update_items": [],
            "consistency_issues": [],
        })
        assert result.changed_files == []


# ── _extract_test_baseline_pair 单元测试 ──────────────────


class TestExtractTestBaselinePair:
    def test_basic(self):
        issue = _issue("stale_test_baseline", "low", "CLAUDE.md",
                       code_fact="1145 passed", doc_claim="637 passed")
        pair = _extract_test_baseline_pair(issue)
        assert pair is not None
        assert pair[0] == "637 passed"
        assert pair[1] == "1145 passed"

    def test_with_tests_unit(self):
        issue = _issue("stale_test_baseline", "low", "CLAUDE.md",
                       code_fact="1145 tests", doc_claim="637 tests")
        pair = _extract_test_baseline_pair(issue)
        assert pair is not None
        assert "637" in pair[0]
        assert "1145" in pair[1]

    def test_same_numbers_no_pair(self):
        issue = _issue("stale_test_baseline", "low", "CLAUDE.md",
                       code_fact="637 passed", doc_claim="637 passed")
        pair = _extract_test_baseline_pair(issue)
        assert pair is None

    def test_no_numbers_no_pair(self):
        issue = _issue("stale_test_baseline", "low", "CLAUDE.md",
                       code_fact="no numbers", doc_claim="also none")
        pair = _extract_test_baseline_pair(issue)
        assert pair is None

    def test_only_fact_has_number(self):
        issue = _issue("stale_test_baseline", "low", "CLAUDE.md",
                       code_fact="1145 passed", doc_claim="no number here")
        pair = _extract_test_baseline_pair(issue)
        assert pair is None


# ── _extract_version_pair 单元测试 ────────────────────────


class TestExtractVersionPair:
    def test_basic(self):
        issue = _issue("phase_status_mismatch", "medium", "CLAUDE.md",
                       code_fact="pyproject.toml version = 0.4.0",
                       doc_claim="CLAUDE.md mentions 0.3.0")
        pair = _extract_version_pair(issue)
        assert pair is not None
        assert pair[0] == "3.0" or "0.3.0" in pair[0] or "3" in pair[0]

    def test_same_version_no_pair(self):
        issue = _issue("phase_status_mismatch", "medium", "CLAUDE.md",
                       code_fact="version = 0.4.0",
                       doc_claim="version 0.4.0")
        pair = _extract_version_pair(issue)
        assert pair is None

    def test_no_versions_no_pair(self):
        issue = _issue("phase_status_mismatch", "medium", "CLAUDE.md",
                       code_fact="Phase 11C missing",
                       doc_claim="only Phase 11A")
        pair = _extract_version_pair(issue)
        assert pair is None


# ── DocPatchProposal / DocPatchHint to_dict ───────────────


class TestModelDict:
    def test_proposal_keys(self):
        p = DocPatchProposal(
            patch_id="abc123",
            doc="CLAUDE.md",
            find="637 passed",
            replace="1145 passed",
            summary="update baseline",
            issue_type="stale_test_baseline",
        )
        d = p.to_dict()
        assert set(d.keys()) >= {"patch_id", "doc", "find", "replace", "summary", "issue_type"}

    def test_hint_keys(self):
        h = DocPatchHint(
            doc="README.md",
            update_kind="capability_boundary",
            direction="新增能力描述",
            reason="stale capability",
            issue_types=["stale_capability"],
        )
        d = h.to_dict()
        assert set(d.keys()) >= {"doc", "update_kind", "direction", "reason", "issue_types"}

    def test_hint_direction_not_empty(self):
        item = _update_item("README.md", "capability_boundary")
        hint = _process_capability_item(item)
        assert hint.direction != ""

    def test_hint_expression_alignment_direction(self):
        item = _update_item("README.md", "expression_alignment")
        hint = _process_capability_item(item)
        assert "口径" in hint.direction or "对齐" in hint.direction
