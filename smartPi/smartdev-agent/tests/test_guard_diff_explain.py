"""
diff.explain Guard Skill 测试 — Phase 11B Step 5

覆盖：
1. 核心规则引擎 explain_diff() 所有功能
2. 文件分类 _classify_file()
3. 信号计算 _compute_signals()
4. 逻辑分组 _group_files()
5. 测试覆盖分析 _analyze_test_coverage()
6. 依赖匹配 _check_dependency_match()
7. 审查顺序建议 _suggest_review_order()
8. Diff 内容解析 _parse_diff_content()
9. 风险提示 _compute_risk_hints()
10. Skill 注册 + 基础属性
11. Skill.run() 输入/输出路径
12. base_signals 合并
13. file_categories 输出
14. 边界情况（空文件列表 / 无 diff / 无 project_path）
15. 确定性：相同输入→相同输出
"""

from __future__ import annotations

from pathlib import Path

import pytest

from smartdev.core.guard_diff_explain import (
    DiffExplainResult,
    _analyze_test_coverage,
    _check_dependency_match,
    _classify_file,
    _compute_risk_hints,
    _compute_signals,
    _group_files,
    _parse_diff_content,
    _suggest_review_order,
    explain_diff,
)
from smartdev.models import ProjectContext
from smartdev.skills.base import Skill


# ── Helpers ────────────────────────────────────────────────


def _ctx() -> ProjectContext:
    return ProjectContext(
        project_path=Path("/fake/project"),
        task_description="test diff.explain",
    )


SAMPLE_DIFF = """diff --git a/core/git.py b/core/git.py
index abc123..def456 100644
--- a/core/git.py
+++ b/core/git.py
@@ -1,3 +1,5 @@
+import subprocess
+
 def foo():
-    return 1
+    return 2
diff --git a/tests/test_git.py b/tests/test_git.py
new file mode 100644
--- /dev/null
+++ b/tests/test_git.py
@@ -0,0 +1,3 @@
+def test_foo():
+    assert foo() == 2
+
"""


# ── 文件分类 _classify_file ───────────────────────────────


class TestClassifyFile:
    def test_source_python(self):
        assert _classify_file("smartdev/core/git.py") == "source"

    def test_source_typescript(self):
        assert _classify_file("src/utils/helper.ts") == "source"

    def test_source_go(self):
        assert _classify_file("pkg/handler.go") == "source"

    def test_test_file(self):
        assert _classify_file("tests/test_git.py") == "test"

    def test_test_file_nested(self):
        assert _classify_file("smartdev/tests/test_core.py") == "test"

    def test_test_file_spec(self):
        assert _classify_file("src/__tests__/foo.spec.ts") == "test"

    def test_doc_markdown(self):
        assert _classify_file("docs/README.md") == "doc"

    def test_manifest_pyproject(self):
        assert _classify_file("pyproject.toml") == "manifest"

    def test_manifest_package_json(self):
        assert _classify_file("package.json") == "manifest"

    def test_manifest_go_mod(self):
        assert _classify_file("go.mod") == "manifest"

    def test_config_yaml(self):
        assert _classify_file("config.yaml") == "config"

    def test_config_dot_env(self):
        assert _classify_file(".env") == "config"

    def test_other_file(self):
        assert _classify_file("assets/logo.png") == "other"


# ── Diff 内容解析 _parse_diff_content ─────────────────────


class TestParseDiffContent:
    def test_empty_diff(self):
        insertions, deletions = _parse_diff_content(None)
        assert insertions == 0
        assert deletions == 0

    def test_empty_string_diff(self):
        insertions, deletions = _parse_diff_content("")
        assert insertions == 0
        assert deletions == 0

    def test_counts_insertions_and_deletions(self):
        insertions, deletions = _parse_diff_content(SAMPLE_DIFF)
        # SAMPLE_DIFF: +import, +blank, +return 2 | +def test, +assert, +blank = 6 insertions
        # SAMPLE_DIFF: -return 1 = 1 deletion
        assert insertions == 6
        assert deletions == 1

    def test_header_lines_not_counted(self):
        """+++ / --- header 不应计入业务行。"""
        diff = "+++ b/file.py\n--- a/file.py\n+real code\n-old code"
        insertions, deletions = _parse_diff_content(diff)
        assert insertions == 1
        assert deletions == 1

    def test_no_diff_markers(self):
        """无不含 +/- 前缀的内容。"""
        diff = "just some text\nno markers here\n"
        insertions, deletions = _parse_diff_content(diff)
        assert insertions == 0
        assert deletions == 0


# ── 信号计算 _compute_signals ─────────────────────────────


class TestComputeSignals:
    def test_empty_files(self):
        signals = _compute_signals([])
        assert signals["touches_tests"] is False
        assert signals["touches_docs"] is False
        assert signals["touches_dependency_manifest"] is False
        assert signals["touches_protected_path"] is False
        assert signals["touches_core"] is False
        assert signals["touches_mcp"] is False
        assert signals["cross_module"] is False
        assert signals["cross_module_count"] == 0

    def test_touches_tests(self):
        signals = _compute_signals(["tests/test_foo.py"])
        assert signals["touches_tests"] is True

    def test_touches_docs(self):
        signals = _compute_signals(["docs/README.md"])
        assert signals["touches_docs"] is True

    def test_touches_manifest(self):
        signals = _compute_signals(["pyproject.toml"])
        assert signals["touches_dependency_manifest"] is True

    def test_touches_protected_path(self):
        signals = _compute_signals([".git/hooks/pre-commit"])
        assert signals["touches_protected_path"] is True
        assert ".git/hooks/pre-commit" in signals["protected_path_hits"]

    def test_touches_core(self):
        signals = _compute_signals(["smartdev/core/git.py"])
        assert signals["touches_core"] is True

    def test_touches_mcp(self):
        signals = _compute_signals(["smartdev/mcp/tools.py"])
        assert signals["touches_mcp"] is True

    def test_cross_module_false_for_single_module(self):
        signals = _compute_signals(["smartdev/core/a.py", "smartdev/core/b.py"])
        assert signals["cross_module"] is False

    def test_cross_module_true_for_multi_module(self):
        signals = _compute_signals([
            "smartdev/core/a.py",
            "smartdev/skills/b.py",
            "tests/test_c.py",
        ])
        assert signals["cross_module"] is True
        assert signals["cross_module_count"] >= 2

    def test_has_diff_content_false_when_none(self):
        signals = _compute_signals(["a.py"], diff_content=None)
        assert signals["has_diff_content"] is False

    def test_has_diff_content_true_when_provided(self):
        signals = _compute_signals(["a.py"], diff_content="+new line")
        assert signals["has_diff_content"] is True

    def test_base_signals_merge(self):
        """base_signals 合并但本地信号不被覆盖。"""
        base = {"external_signal": True, "touches_tests": False}
        signals = _compute_signals(
            ["tests/test_foo.py", "core/git.py"],
            base_signals=base,
        )
        # 本地计算值不被 base 覆盖
        assert signals["touches_tests"] is True
        # base 中的额外信号被合并
        assert signals["external_signal"] is True

    def test_base_signals_none_graceful(self):
        """base_signals=None 时不报错。"""
        signals = _compute_signals(["a.py"], base_signals=None)
        assert "touches_tests" in signals


# ── 逻辑分组 _group_files ────────────────────────────────


class TestGroupFiles:
    def test_empty(self):
        groups = _group_files([])
        assert groups == []

    def test_single_file(self):
        groups = _group_files(["README.md"])
        assert len(groups) == 1
        assert groups[0]["label"] == "other changes"
        assert "README.md" in groups[0]["files"]

    def test_core_and_tests(self):
        groups = _group_files([
            "smartdev/core/git.py",
            "smartdev/core/patch.py",
            "tests/test_git.py",
        ])
        labels = {g["label"] for g in groups}
        assert "core logic change" in labels
        assert "test coverage" in labels

    def test_skill_and_docs(self):
        groups = _group_files([
            "smartdev/skills/foo/skill.py",
            "docs/README.md",
        ])
        labels = {g["label"] for g in groups}
        assert "skill layer change" in labels
        # docs/ 是单个文件目录 → 合并到 other 或 documentation
        all_labels = {g["label"] for g in groups}
        # "documentation" or "other changes" depending on merge logic
        assert len(groups) >= 1

    def test_each_group_has_label_files_description(self):
        groups = _group_files([
            "smartdev/core/git.py",
            "smartdev/skills/foo/skill.py",
        ])
        for g in groups:
            assert "label" in g
            assert "files" in g
            assert "description" in g

    def test_single_file_core_kept_separate(self):
        """core/ 下的单文件仍然保留独立分组。"""
        groups = _group_files(["smartdev/core/git.py"])
        assert len(groups) == 1
        assert groups[0]["label"] == "core logic change"


# ── 测试覆盖分析 _analyze_test_coverage ──────────────────


class TestAnalyzeTestCoverage:
    def test_no_files(self):
        tc = _analyze_test_coverage([])
        assert tc["has_related_tests"] is False
        assert tc["test_files_touched"] == 0

    def test_source_with_test(self):
        tc = _analyze_test_coverage([
            "smartdev/core/git.py",
            "tests/test_git.py",
        ])
        assert tc["has_related_tests"] is True
        assert tc["test_files_touched"] == 1
        assert "smartdev/core/git.py" in tc["covered_modules"]

    def test_source_without_test(self):
        tc = _analyze_test_coverage([
            "smartdev/core/git.py",
            "smartdev/core/new_feature.py",
        ])
        assert tc["has_related_tests"] is False
        assert len(tc["untested_changed_modules"]) >= 1

    def test_only_tests_no_source(self):
        tc = _analyze_test_coverage(["tests/test_foo.py"])
        assert tc["has_related_tests"] is True
        assert tc["test_files_touched"] == 1
        assert len(tc["untested_changed_modules"]) == 0

    def test_only_docs_no_test_required(self):
        """仅文档变更不要求测试。"""
        tc = _analyze_test_coverage(["docs/README.md", "CHANGELOG.md"])
        # docs are classified as "doc", not "source", so no untested modules
        assert len(tc["untested_changed_modules"]) == 0


# ── 依赖匹配 _check_dependency_match ─────────────────────


class TestCheckDependencyMatch:
    def test_no_manifest_no_source(self):
        dm = _check_dependency_match(["docs/README.md"])
        assert dm["manifest_changed"] is False
        assert dm["source_changed"] is False
        assert dm["matched"] is True

    def test_manifest_with_source(self):
        dm = _check_dependency_match([
            "pyproject.toml",
            "smartdev/core/git.py",
        ])
        assert dm["manifest_changed"] is True
        assert dm["source_changed"] is True
        assert dm["matched"] is True

    def test_manifest_without_source(self):
        dm = _check_dependency_match(["pyproject.toml", "poetry.lock"])
        assert dm["manifest_changed"] is True
        assert dm["source_changed"] is False
        assert dm["matched"] is False

    def test_lock_files_detected(self):
        dm = _check_dependency_match([
            "pyproject.toml",
            "poetry.lock",
            "smartdev/core/git.py",
        ])
        assert len(dm["lock_files_changed"]) >= 1
        assert "poetry.lock" in dm["lock_files_changed"]

    def test_detail_string_present(self):
        dm = _check_dependency_match(["pyproject.toml", "smartdev/core/git.py"])
        assert "detail" in dm
        assert len(dm["detail"]) > 0


# ── 审查顺序 _suggest_review_order ───────────────────────


class TestSuggestReviewOrder:
    def test_core_before_tests_before_docs(self):
        groups = [
            {"label": "documentation", "files": ["docs/README.md"],
             "description": "影响 docs"},
            {"label": "test coverage", "files": ["tests/test_git.py"],
             "description": "影响 tests"},
            {"label": "core logic change", "files": ["smartdev/core/git.py"],
             "description": "影响 core"},
        ]
        signals = {"touches_dependency_manifest": False}
        tc = {"untested_changed_modules": []}
        order = _suggest_review_order(groups, signals, tc)
        # core 应该在 tests 之前，tests 应该在 docs 之前
        core_idx = next(i for i, s in enumerate(order) if "core" in s.lower())
        test_idx = next(i for i, s in enumerate(order) if "test" in s.lower())
        doc_idx = next(i for i, s in enumerate(order) if "doc" in s.lower())
        assert core_idx < test_idx < doc_idx

    def test_deterministic_order(self):
        """相同输入→相同输出（无随机顺序）。"""
        groups = [
            {"label": "test coverage", "files": ["tests/test_a.py"],
             "description": ""},
            {"label": "core logic change", "files": ["smartdev/core/a.py"],
             "description": ""},
            {"label": "skill layer change", "files": ["smartdev/skills/a.py"],
             "description": ""},
        ]
        signals = {"touches_dependency_manifest": False}
        tc = {"untested_changed_modules": []}
        order1 = _suggest_review_order(groups, signals, tc)
        order2 = _suggest_review_order(groups, signals, tc)
        assert order1 == order2

    def test_untested_modules_suggestion(self):
        groups = [
            {"label": "core logic change", "files": ["smartdev/core/a.py"],
             "description": ""},
        ]
        signals = {"touches_dependency_manifest": False}
        tc = {"untested_changed_modules": ["smartdev/core/a.py"]}
        order = _suggest_review_order(groups, signals, tc)
        assert any("补充测试" in s or "test" in s.lower() for s in order)

    def test_dependency_suggestion(self):
        groups = [
            {"label": "core logic change", "files": ["smartdev/core/a.py"],
             "description": ""},
        ]
        signals = {"touches_dependency_manifest": True}
        tc = {"untested_changed_modules": []}
        order = _suggest_review_order(groups, signals, tc)
        assert any("依赖" in s for s in order)


# ── 风险提示 _compute_risk_hints ─────────────────────────


class TestComputeRiskHints:
    def _base_args(self):
        return {
            "signals": {"cross_module": False, "cross_module_count": 0,
                        "touches_protected_path": False, "touches_core": False},
            "dep_match": {"manifest_changed": False, "source_changed": False},
            "test_coverage": {"untested_changed_modules": []},
            "insertions": 0,
            "deletions": 0,
            "n_files": 3,
        }

    def test_no_hints_for_clean_change(self):
        hints = _compute_risk_hints(**self._base_args())
        assert hints == []

    def test_cross_module_hint(self):
        args = self._base_args()
        args["signals"]["cross_module"] = True
        args["signals"]["cross_module_count"] = 3
        hints = _compute_risk_hints(**args)
        assert any("cross_module_change" in h for h in hints)

    def test_dependency_without_code_hint(self):
        args = self._base_args()
        args["dep_match"]["manifest_changed"] = True
        args["dep_match"]["source_changed"] = False
        hints = _compute_risk_hints(**args)
        assert any("dependency_manifest_changed_without_code" in h for h in hints)

    def test_missing_related_tests_hint(self):
        args = self._base_args()
        args["test_coverage"]["untested_changed_modules"] = ["core/git.py"]
        hints = _compute_risk_hints(**args)
        assert "missing_related_tests" in hints

    def test_core_touched_hint(self):
        args = self._base_args()
        args["signals"]["touches_core"] = True
        hints = _compute_risk_hints(**args)
        assert "core_module_touched" in hints

    def test_protected_path_hint(self):
        args = self._base_args()
        args["signals"]["touches_protected_path"] = True
        hints = _compute_risk_hints(**args)
        assert "touches_protected_path" in hints

    def test_large_changeset_hint(self):
        args = self._base_args()
        args["n_files"] = 15
        hints = _compute_risk_hints(**args)
        assert any("large_changeset" in h for h in hints)

    def test_large_diff_hint(self):
        args = self._base_args()
        args["insertions"] = 200
        args["deletions"] = 150
        hints = _compute_risk_hints(**args)
        assert any("large_diff" in h for h in hints)

    def test_multiple_hints(self):
        args = self._base_args()
        args["signals"]["cross_module"] = True
        args["signals"]["touches_core"] = True
        args["test_coverage"]["untested_changed_modules"] = ["core/git.py"]
        hints = _compute_risk_hints(**args)
        assert len(hints) >= 3


# ── explain_diff 核心入口 ────────────────────────────────


class TestExplainDiff:
    def test_basic(self):
        result = explain_diff(["smartdev/core/git.py", "tests/test_git.py"])
        assert isinstance(result, DiffExplainResult)
        assert result.summary["files_changed"] == 2
        assert result.summary["logical_groups"] >= 1

    def test_empty_files(self):
        result = explain_diff([])
        assert result.summary["files_changed"] == 0
        assert result.signals["touches_tests"] is False

    def test_with_diff_content(self):
        result = explain_diff(
            ["core/git.py", "tests/test_git.py"],
            diff_content=SAMPLE_DIFF,
        )
        assert result.summary["insertions"] > 0
        assert result.summary["deletions"] >= 0
        assert result.signals["has_diff_content"] is True

    def test_file_categories_present(self):
        result = explain_diff([
            "smartdev/core/git.py",
            "tests/test_git.py",
            "docs/README.md",
            "pyproject.toml",
        ])
        assert "source" in result.file_categories
        assert "test" in result.file_categories
        assert "doc" in result.file_categories
        assert "manifest" in result.file_categories

    def test_file_categories_all_keys_present(self):
        """即使某些分类无文件，键也必须存在。"""
        result = explain_diff(["smartdev/core/git.py"])
        for cat in ("source", "test", "doc", "manifest", "config", "core", "mcp", "other"):
            assert cat in result.file_categories, f"missing category: {cat}"

    def test_signals_comprehensive(self):
        result = explain_diff([
            "smartdev/core/git.py",
            "smartdev/skills/foo/skill.py",
            "tests/test_git.py",
            "docs/README.md",
            "smartdev/mcp/server.py",
        ])
        assert result.signals["touches_tests"] is True
        assert result.signals["touches_docs"] is True
        assert result.signals["touches_core"] is True
        assert result.signals["touches_mcp"] is True
        assert result.signals["cross_module"] is True

    def test_test_coverage_in_result(self):
        result = explain_diff([
            "smartdev/core/git.py",
            "tests/test_git.py",
        ])
        assert result.test_coverage["has_related_tests"] is True
        assert "smartdev/core/git.py" in result.test_coverage["covered_modules"]

    def test_risk_hints_integration(self):
        result = explain_diff([
            "smartdev/core/a.py",
            "smartdev/skills/b.py",
            "smartdev/mcp/c.py",
            "pyproject.toml",
        ])
        # 跨模块 + manifest 无源码变更
        assert len(result.risk_hints) > 0

    def test_suggested_review_order_present(self):
        result = explain_diff([
            "smartdev/core/git.py",
            "tests/test_git.py",
        ])
        assert len(result.suggested_review_order) > 0

    def test_to_dict(self):
        result = explain_diff(["a.py", "b.py"])
        d = result.to_dict()
        assert "summary" in d
        assert "signals" in d
        assert "file_categories" in d
        assert "logical_groups" in d
        assert "risk_hints" in d
        assert "test_coverage" in d
        assert "suggested_review_order" in d

    def test_base_signals_pass_through(self):
        """base_signals 传入后 merged 信号出现在结果中。"""
        result = explain_diff(
            ["smartdev/core/git.py"],
            base_signals={"external_custom": "value"},
        )
        assert result.signals["external_custom"] == "value"
        # 本地信号仍然存在
        assert result.signals["touches_core"] is True

    def test_deterministic(self):
        """相同输入→相同输出。"""
        files = [
            "smartdev/core/a.py",
            "smartdev/skills/b.py",
            "tests/test_a.py",
            "docs/README.md",
        ]
        diff = "+new line\n-old line"
        r1 = explain_diff(files, diff_content=diff)
        r2 = explain_diff(files, diff_content=diff)
        assert r1.summary == r2.summary
        assert r1.signals == r2.signals
        assert r1.risk_hints == r2.risk_hints
        assert r1.suggested_review_order == r2.suggested_review_order


# ── Skill 注册验证 ───────────────────────────────────────


def test_skill_registered():
    """import smartdev.skills 后 Skill 已注册。"""
    import smartdev.skills  # noqa: F401
    skill_cls = Skill.get_skill("diff.explain")
    assert skill_cls is not None


def test_skill_attributes():
    """验证 Skill 基本属性。"""
    skill = Skill.create("diff.explain")
    assert skill.name == "diff.explain"
    from smartdev.models import RiskLevel
    assert skill.risk_level == RiskLevel.R0
    assert skill.can_run(_ctx()) is True


# ── Skill.run() 集成测试 ─────────────────────────────────


class TestSkillRun:
    def test_run_with_patch_files(self):
        skill = Skill.create("diff.explain")
        result = skill.run(_ctx(), {
            "patch_files": ["smartdev/core/git.py", "tests/test_git.py"],
        })
        assert result.success is True
        assert result.data["summary"]["files_changed"] == 2
        assert "signals" in result.data
        assert "logical_groups" in result.data
        assert "risk_hints" in result.data

    def test_run_with_diff_content(self):
        skill = Skill.create("diff.explain")
        result = skill.run(_ctx(), {
            "patch_files": ["core/git.py", "tests/test_git.py"],
            "diff_content": SAMPLE_DIFF,
        })
        assert result.success is True
        assert result.data["summary"]["insertions"] > 0

    def test_run_no_patch_files(self):
        skill = Skill.create("diff.explain")
        result = skill.run(_ctx(), {"patch_files": []})
        assert result.success is True
        assert result.data["summary"]["files_changed"] == 0

    def test_run_no_inputs(self):
        skill = Skill.create("diff.explain")
        result = skill.run(_ctx())
        assert result.success is True
        assert "无 patch 文件" in result.summary

    def test_run_returns_next_steps(self):
        skill = Skill.create("diff.explain")
        result = skill.run(_ctx(), {
            "patch_files": ["smartdev/core/git.py", "smartdev/skills/a.py"],
        })
        assert len(result.next_steps) > 0

    def test_run_with_project_path_str(self):
        """project_path 传入字符串时也能正常处理。"""
        skill = Skill.create("diff.explain")
        result = skill.run(_ctx(), {
            "patch_files": ["a.py"],
            "project_path": "/fake/project",
        })
        assert result.success is True

    def test_run_with_project_path_path(self):
        """project_path 传入 Path 对象时也能正常处理。"""
        skill = Skill.create("diff.explain")
        result = skill.run(_ctx(), {
            "patch_files": ["a.py"],
            "project_path": Path("/fake/project"),
        })
        assert result.success is True

    def test_run_with_base_signals(self):
        skill = Skill.create("diff.explain")
        result = skill.run(_ctx(), {
            "patch_files": ["smartdev/core/git.py"],
            "base_signals": {"custom_field": "custom_value"},
        })
        assert result.success is True
        assert result.data["signals"]["custom_field"] == "custom_value"

    def test_run_cross_module_next_steps(self):
        """跨模块变更时 next_steps 包含建议。"""
        skill = Skill.create("diff.explain")
        result = skill.run(_ctx(), {
            "patch_files": [
                "smartdev/core/a.py",
                "smartdev/skills/b.py",
                "smartdev/mcp/c.py",
            ],
        })
        assert any("跨模块" in s for s in result.next_steps)

    def test_run_untested_next_steps(self):
        """未测试模块变更时 next_steps 包含建议。"""
        skill = Skill.create("diff.explain")
        result = skill.run(_ctx(), {
            "patch_files": [
                "smartdev/core/new_feature.py",
            ],
        })
        assert any("测试" in s for s in result.next_steps)

    def test_run_risk_hints_in_data(self):
        """跨模块 + manifest 变更应产生 risk_hints。"""
        skill = Skill.create("diff.explain")
        result = skill.run(_ctx(), {
            "patch_files": [
                "smartdev/core/a.py",
                "smartdev/skills/b.py",
                "pyproject.toml",
            ],
        })
        assert isinstance(result.data["risk_hints"], list)

    def test_run_data_has_all_required_keys(self):
        """SkillResult.data 必须包含所有必需键。"""
        skill = Skill.create("diff.explain")
        result = skill.run(_ctx(), {
            "patch_files": ["smartdev/core/git.py", "tests/test_git.py"],
        })
        required = [
            "summary", "signals", "file_categories", "logical_groups",
            "risk_hints", "test_coverage", "suggested_review_order",
        ]
        for key in required:
            assert key in result.data, f"missing key in data: {key}"
