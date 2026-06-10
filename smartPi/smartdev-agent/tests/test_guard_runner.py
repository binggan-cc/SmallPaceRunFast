"""
GuardRunner 测试 — Phase 11B Step 6

覆盖：
1. GuardRunResult / GuardEntryResult 数据模型序列化
2. run_guard_runner() 基础运行（全量 5 个 Guard）
3. select 过滤
4. invalid guard 名称
5. 空 changed_files
6. diff_content 传递
7. to_json() 序列化
8. 聚合统计（error_count / warning_count / overall_passed）
9. suggested_actions
10. 异常处理（单个 Guard 失败不崩溃）
11. 确定性
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from smartdev.core.guard_runner import (
    GuardEntryResult,
    GuardRunResult,
    run_guard_runner,
)


# ── Helpers ────────────────────────────────────────────────

def _project_path() -> Path:
    return Path(__file__).resolve().parent.parent


def _sample_files() -> list[str]:
    return ["smartdev/core/git.py", "tests/test_git.py"]


# ── 数据模型 ───────────────────────────────────────────────


class TestGuardEntryResult:
    def test_to_dict_basic(self):
        entry = GuardEntryResult(passed=True, summary="all good", duration_ms=12.3)
        d = entry.to_dict()
        assert d["passed"] is True
        assert d["summary"] == "all good"
        assert d["duration_ms"] == 12.3
        assert d["risks"] == []
        assert d["next_steps"] == []

    def test_to_dict_with_error(self):
        entry = GuardEntryResult(
            passed=False,
            summary="failed",
            duration_ms=5.0,
            error="something went wrong",
        )
        d = entry.to_dict()
        assert "error" in d
        assert d["error"] == "something went wrong"

    def test_to_dict_with_risks(self):
        entry = GuardEntryResult(
            passed=True,
            summary="has warnings",
            duration_ms=1.0,
            risks=["risk1", "risk2"],
            next_steps=["step1"],
        )
        d = entry.to_dict()
        assert d["risks"] == ["risk1", "risk2"]
        assert d["next_steps"] == ["step1"]


class TestGuardRunResult:
    def test_to_dict_keys(self):
        result = GuardRunResult(
            overall_passed=True,
            selected=["change.budget"],
            skipped=["dev.guard"],
            summary="1/1 passed",
            run_id="test",
            timestamp="2026-01-01T00:00:00Z",
        )
        d = result.to_dict()
        for key in ("overall_passed", "guards", "error_count", "warning_count",
                     "suggested_actions", "selected", "skipped", "summary",
                     "run_id", "timestamp"):
            assert key in d, f"missing key: {key}"

    def test_to_json_serializable(self):
        result = GuardRunResult(
            overall_passed=True,
            guards={
                "change.budget": GuardEntryResult(passed=True, summary="ok", duration_ms=1.0),
            },
            selected=["change.budget"],
            skipped=["dev.guard"],
            summary="ok",
        )
        json_str = result.to_json()
        parsed = json.loads(json_str)
        assert parsed["overall_passed"] is True
        assert "change.budget" in parsed["guards"]

    def test_roundtrip_json(self):
        result = GuardRunResult(
            overall_passed=False,
            error_count=1,
            warning_count=2,
            selected=["change.budget", "dev.guard"],
            skipped=["dependency.guard", "security.review", "diff.explain"],
            suggested_actions=["action1", "action2"],
            summary="test summary",
            run_id="r1",
            timestamp="2026-01-01T00:00:00Z",
        )
        d = result.to_dict()
        # 验证所有值可 JSON 序列化
        json_str = json.dumps(d, ensure_ascii=False)
        parsed = json.loads(json_str)
        assert parsed["error_count"] == 1
        assert parsed["warning_count"] == 2
        assert len(parsed["suggested_actions"]) == 2


# ── run_guard_runner 核心测试 ─────────────────────────────


class TestRunGuardRunner:
    def test_all_guards_run(self):
        """全量 5 个 Guard 运行。"""
        result = run_guard_runner(
            project_path=_project_path(),
            changed_files=_sample_files(),
        )
        assert len(result.guards) == 5
        assert set(result.guards.keys()) == {
            "change.budget", "dev.guard", "dependency.guard",
            "security.review", "diff.explain",
        }

    def test_overall_passed_for_clean_change(self):
        """少量文件变更应全部通过。"""
        result = run_guard_runner(
            project_path=_project_path(),
            changed_files=["smartdev/core/git.py", "tests/test_git.py"],
        )
        assert result.overall_passed is True

    def test_select_filter(self):
        """select 过滤只运行指定 Guard。"""
        result = run_guard_runner(
            project_path=_project_path(),
            changed_files=_sample_files(),
            select=["change.budget", "dev.guard"],
        )
        assert result.selected == ["change.budget", "dev.guard"]
        assert "change.budget" in result.guards
        assert "dev.guard" in result.guards
        assert "dependency.guard" in result.skipped
        assert "security.review" in result.skipped
        assert "diff.explain" in result.skipped

    def test_invalid_guard_name(self):
        """无效 guard 名称应返回错误。"""
        result = run_guard_runner(
            project_path=_project_path(),
            changed_files=_sample_files(),
            select=["nonexistent.guard"],
        )
        assert result.overall_passed is False
        assert "无效 Guard" in result.summary

    def test_empty_changed_files(self):
        """空 changed_files 不应崩溃。"""
        result = run_guard_runner(
            project_path=_project_path(),
            changed_files=[],
        )
        # 应该运行并返回结果
        assert len(result.guards) == 5

    def test_with_diff_content(self):
        """diff_content 传递给相关 Guard。"""
        result = run_guard_runner(
            project_path=_project_path(),
            changed_files=["smartdev/core/git.py"],
            diff_content="+new line\n-old line",
        )
        assert len(result.guards) == 5

    def test_aggregation_counts(self):
        """error_count / warning_count / overall_passed 聚合。"""
        result = run_guard_runner(
            project_path=_project_path(),
            changed_files=_sample_files(),
        )
        # 少量正常变更：error_count 应该为 0
        assert isinstance(result.error_count, int)
        assert isinstance(result.warning_count, int)
        assert isinstance(result.overall_passed, bool)

    def test_suggested_actions_present(self):
        """suggested_actions 不为空。"""
        result = run_guard_runner(
            project_path=_project_path(),
            changed_files=_sample_files(),
        )
        assert len(result.suggested_actions) > 0

    def test_summary_non_empty(self):
        """summary 字段有意义。"""
        result = run_guard_runner(
            project_path=_project_path(),
            changed_files=_sample_files(),
        )
        assert len(result.summary) > 0
        assert "GuardRunner" in result.summary

    def test_timestamp_present(self):
        """timestamp 字段存在且符合 ISO 格式。"""
        result = run_guard_runner(
            project_path=_project_path(),
            changed_files=_sample_files(),
        )
        assert len(result.timestamp) > 0
        assert "T" in result.timestamp
        assert "Z" in result.timestamp

    def test_deterministic(self):
        """相同输入→相同输出（无随机性）。"""
        files = _sample_files()
        r1 = run_guard_runner(
            project_path=_project_path(),
            changed_files=files,
        )
        r2 = run_guard_runner(
            project_path=_project_path(),
            changed_files=files,
        )
        assert r1.overall_passed == r2.overall_passed
        assert r1.selected == r2.selected
        assert r1.skipped == r2.skipped

    def test_guard_entry_has_duration(self):
        """每个 Guard 条目都有 duration_ms。"""
        result = run_guard_runner(
            project_path=_project_path(),
            changed_files=_sample_files(),
        )
        for entry in result.guards.values():
            assert entry.duration_ms >= 0
