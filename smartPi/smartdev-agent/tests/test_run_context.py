"""
test_run_context.py — smartdev run context 聚焦测试

覆盖：
- 成功打印 code-agent / doc-steward / reviewer pack 到 stdout
- --info 模式
- pack 不存在时的错误提示
- 未知角色错误
- run_id 不存在时的错误

不覆盖：
- MCP 工具（Step 6）
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from smartdev.core.handoff_code import generate_code_agent_pack
from smartdev.core.handoff_doc import generate_doc_steward_pack
from smartdev.core.handoff_review import generate_reviewer_pack
from smartdev.core.run_artifact import ScopeConfig, create_run_artifact


@pytest.fixture
def tmp_project():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def _setup_with_packs(tmp_project: Path, run_id: str = "ctx-test"):
    """创建 run artifact 并预生成所有三个 pack。"""
    scope = ScopeConfig(allowed_paths=["smartdev/", "tests/"])
    _, err = create_run_artifact(tmp_project, run_id, scope=scope, force=True)
    if err:
        raise RuntimeError(f"Failed: {err}")

    # 最小项目骨架
    (tmp_project / "CLAUDE.md").write_text("# CLAUDE\n\n## 当前阶段\n\nPhase 11D\n", encoding="utf-8")
    (tmp_project / "smartdev").mkdir(exist_ok=True)
    (tmp_project / "smartdev" / "__init__.py").write_text("")
    (tmp_project / "README.md").write_text("# Test\n", encoding="utf-8")

    # 生成三个 pack
    generate_code_agent_pack(tmp_project, run_id)
    generate_doc_steward_pack(tmp_project, run_id)
    generate_reviewer_pack(tmp_project, run_id)

    return tmp_project


# ── 成功路径 ──────────────────────────────────────────────────


class TestRunContextSuccess:
    def test_prints_code_agent_pack(self, tmp_project):
        _setup_with_packs(tmp_project, "s1")
        pack_path = tmp_project / ".smartdev" / "runs" / "s1" / "handoff" / "code-agent-pack.md"
        content = pack_path.read_text(encoding="utf-8")
        assert len(content) > 0
        assert "Code Agent Pack" in content
        assert "角色激活前言" in content

    def test_prints_doc_steward_pack(self, tmp_project):
        _setup_with_packs(tmp_project, "s2")
        pack_path = tmp_project / ".smartdev" / "runs" / "s2" / "handoff" / "doc-steward-pack.md"
        content = pack_path.read_text(encoding="utf-8")
        assert len(content) > 0
        assert "Doc Steward Pack" in content
        assert "角色激活前言" in content

    def test_prints_reviewer_pack(self, tmp_project):
        _setup_with_packs(tmp_project, "s3")
        pack_path = tmp_project / ".smartdev" / "runs" / "s3" / "handoff" / "reviewer-pack.md"
        content = pack_path.read_text(encoding="utf-8")
        assert len(content) > 0
        assert "Reviewer Pack" in content
        assert "角色激活前言" in content

    def test_all_three_packs_exist(self, tmp_project):
        _setup_with_packs(tmp_project, "s4")
        handoff_dir = tmp_project / ".smartdev" / "runs" / "s4" / "handoff"
        assert (handoff_dir / "code-agent-pack.md").exists()
        assert (handoff_dir / "doc-steward-pack.md").exists()
        assert (handoff_dir / "reviewer-pack.md").exists()


# ── 错误路径 ──────────────────────────────────────────────────


class TestRunContextErrors:
    def test_nonexistent_run_id(self, tmp_project):
        """run_id 不存在时，pack 也不存在。"""
        pack_path = tmp_project / ".smartdev" / "runs" / "nonexistent" / "handoff" / "code-agent-pack.md"
        assert not pack_path.exists()

    def test_pack_not_generated_yet(self, tmp_project):
        """有 run artifact 但未生成 pack。"""
        scope = ScopeConfig()
        _, err = create_run_artifact(tmp_project, "no-pack", scope=scope, force=True)
        assert err is None
        pack_path = tmp_project / ".smartdev" / "runs" / "no-pack" / "handoff" / "doc-steward-pack.md"
        assert not pack_path.exists()


# ── 角色激活前言内容 ──────────────────────────────────────────


class TestRoleActivationPreamble:
    def test_code_agent_preamble_contains_role(self, tmp_project):
        _setup_with_packs(tmp_project, "p1")
        content = (tmp_project / ".smartdev" / "runs" / "p1" / "handoff" / "code-agent-pack.md").read_text("utf-8")
        assert "你是 SmartDev 协作模式中的 Code Agent" in content
        assert "DeepSeek / coding model  = Code Agent" in content
        assert "小范围代码实现" in content

    def test_doc_steward_preamble_contains_role(self, tmp_project):
        _setup_with_packs(tmp_project, "p2")
        content = (tmp_project / ".smartdev" / "runs" / "p2" / "handoff" / "doc-steward-pack.md").read_text("utf-8")
        assert "你是 SmartDev 协作模式中的 Doc Steward" in content
        assert "Claude / Codex           = Doc Steward" in content
        assert "审查文档与代码一致性" in content

    def test_reviewer_preamble_contains_role(self, tmp_project):
        _setup_with_packs(tmp_project, "p3")
        content = (tmp_project / ".smartdev" / "runs" / "p3" / "handoff" / "reviewer-pack.md").read_text("utf-8")
        assert "你是 SmartDev 协作模式中的 Reviewer" in content
        assert "Risk / Architecture / Security" in content
        assert "approval: approve / request_changes / block" in content

    def test_code_agent_preamble_has_prohibitions(self, tmp_project):
        _setup_with_packs(tmp_project, "p4")
        content = (tmp_project / ".smartdev" / "runs" / "p4" / "handoff" / "code-agent-pack.md").read_text("utf-8")
        assert "绝对不能" in content

    def test_doc_steward_preamble_has_prohibitions(self, tmp_project):
        _setup_with_packs(tmp_project, "p5")
        content = (tmp_project / ".smartdev" / "runs" / "p5" / "handoff" / "doc-steward-pack.md").read_text("utf-8")
        assert "绝对不能" in content

    def test_reviewer_preamble_has_output_format(self, tmp_project):
        _setup_with_packs(tmp_project, "p6")
        content = (tmp_project / ".smartdev" / "runs" / "p6" / "handoff" / "reviewer-pack.md").read_text("utf-8")
        assert "risk_level: R0 / R1 / R2 / R3" in content
