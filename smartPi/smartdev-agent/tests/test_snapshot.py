"""
Capability Snapshot 测试 — Phase 11C Step 2

覆盖：
1. SkillSnapshot 数据模型序列化 / 反序列化
2. CliSnapshot 数据模型序列化 / 反序列化
3. McpSnapshot 数据模型序列化 / 反序列化
4. build_skill_snapshot：从 Skill.get_registry() 内省
5. build_cli_snapshot：从 argparse 结构内省
6. build_mcp_snapshot：mcp 可用 / 不可用路径
7. _parse_skill_yaml_lite：inputs/outputs 提取
8. save_snapshot 持久化
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from smartdev.core.snapshot import (
    CliCommandEntry,
    CliSnapshot,
    McpSnapshot,
    McpToolEntry,
    SkillEntry,
    SkillSnapshot,
    _parse_skill_yaml_lite,
    build_cli_snapshot,
    build_mcp_snapshot,
    build_skill_snapshot,
    save_snapshot,
)


# ── SkillSnapshot 数据模型 ─────────────────────────────────


class TestSkillSnapshotModel:
    def test_to_dict_keys(self):
        s = SkillSnapshot(generated_at="2026-06-08T00:00:00Z", skill_count=0)
        d = s.to_dict()
        assert set(d.keys()) == {"generated_at", "skill_count", "skills"}

    def test_roundtrip_empty(self):
        s = SkillSnapshot(generated_at="2026-06-08T00:00:00Z", skill_count=0)
        restored = SkillSnapshot.from_dict(s.to_dict())
        assert restored.skill_count == 0
        assert restored.skills == []

    def test_roundtrip_with_entries(self):
        entry = SkillEntry(
            name="git.status",
            risk="R0",
            task_type="diagnose",
            description="查询 git 状态",
            inputs=["project_path"],
            outputs=["branch", "is_dirty"],
        )
        s = SkillSnapshot(generated_at="t", skill_count=1, skills=[entry])
        restored = SkillSnapshot.from_dict(s.to_dict())
        assert restored.skill_count == 1
        assert restored.skills[0].name == "git.status"
        assert restored.skills[0].inputs == ["project_path"]
        assert restored.skills[0].outputs == ["branch", "is_dirty"]

    def test_to_json_valid(self):
        s = SkillSnapshot(generated_at="t", skill_count=0)
        parsed = json.loads(s.to_json())
        assert "skill_count" in parsed


class TestSkillEntry:
    def test_to_dict(self):
        e = SkillEntry(name="foo", risk="R1", task_type="plan", description="desc")
        d = e.to_dict()
        assert d["name"] == "foo"
        assert d["risk"] == "R1"
        assert d["inputs"] == []
        assert d["outputs"] == []


# ── CliSnapshot 数据模型 ───────────────────────────────────


class TestCliSnapshotModel:
    def test_to_dict_keys(self):
        s = CliSnapshot(generated_at="t", command_count=0)
        d = s.to_dict()
        assert set(d.keys()) == {"generated_at", "command_count", "commands"}

    def test_roundtrip(self):
        cmd = CliCommandEntry(
            command="smartdev git commit",
            description="创建 git commit",
            args=["--message", "--apply"],
        )
        s = CliSnapshot(generated_at="t", command_count=1, commands=[cmd])
        restored = CliSnapshot.from_dict(s.to_dict())
        assert restored.command_count == 1
        assert restored.commands[0].command == "smartdev git commit"
        assert "--message" in restored.commands[0].args

    def test_to_json_valid(self):
        s = CliSnapshot(generated_at="t", command_count=0)
        parsed = json.loads(s.to_json())
        assert "commands" in parsed


# ── McpSnapshot 数据模型 ───────────────────────────────────


class TestMcpSnapshotModel:
    def test_to_dict_keys(self):
        s = McpSnapshot(generated_at="t", tool_count=0, available=True)
        d = s.to_dict()
        assert set(d.keys()) == {"generated_at", "tool_count", "available", "tools"}

    def test_roundtrip(self):
        tool = McpToolEntry(
            name="smartdev_ping",
            description="Health check",
            required=[],
            optional=[],
        )
        s = McpSnapshot(generated_at="t", tool_count=1, available=True, tools=[tool])
        restored = McpSnapshot.from_dict(s.to_dict())
        assert restored.tool_count == 1
        assert restored.tools[0].name == "smartdev_ping"
        assert restored.available is True

    def test_to_json_valid(self):
        s = McpSnapshot(generated_at="t", tool_count=0, available=False)
        parsed = json.loads(s.to_json())
        assert parsed["available"] is False


# ── _parse_skill_yaml_lite ─────────────────────────────────


class TestParseSkillYamlLite:
    def test_simple_inputs_outputs(self):
        yaml = """
inputs:
  required:
    - project_path
  optional:
    - recent_commit_count
outputs:
  - branch
  - is_dirty
"""
        result = _parse_skill_yaml_lite(yaml)
        assert "project_path" in result["inputs"]
        assert "recent_commit_count" in result["inputs"]
        assert "branch" in result["outputs"]
        assert "is_dirty" in result["outputs"]

    def test_outputs_only(self):
        yaml = """
outputs:
  - summary
  - data
"""
        result = _parse_skill_yaml_lite(yaml)
        assert result["outputs"] == ["summary", "data"]
        assert result.get("inputs", []) == []

    def test_inline_comment_stripped(self):
        yaml = """
outputs:
  - branch   # 当前分支名
  - is_dirty # 是否有未提交
"""
        result = _parse_skill_yaml_lite(yaml)
        assert result["outputs"] == ["branch", "is_dirty"]

    def test_empty_yaml(self):
        result = _parse_skill_yaml_lite("")
        assert result == {}

    def test_no_inputs_outputs(self):
        yaml = """
id: foo
name: bar
risk: R0
"""
        result = _parse_skill_yaml_lite(yaml)
        assert result == {}

    def test_real_git_status_yaml(self, tmp_path: Path):
        """用真实 git_status skill.yaml 内容验证解析。"""
        yaml_content = """
inputs:
  required:
    - project_path
  optional:
    - recent_commit_count
outputs:
  - branch
  - is_dirty
  - staged
  - unstaged
  - untracked
  - recent_commits
  - summary
  - policy_hints
"""
        result = _parse_skill_yaml_lite(yaml_content)
        assert "project_path" in result["inputs"]
        assert "recent_commit_count" in result["inputs"]
        assert len(result["outputs"]) == 8


# ── build_skill_snapshot ───────────────────────────────────


class TestBuildSkillSnapshot:
    def test_returns_skill_snapshot(self):
        snap = build_skill_snapshot()
        assert isinstance(snap, SkillSnapshot)

    def test_skill_count_positive(self):
        snap = build_skill_snapshot()
        assert snap.skill_count > 0

    def test_skills_sorted_by_name(self):
        snap = build_skill_snapshot()
        names = [s.name for s in snap.skills]
        assert names == sorted(names)

    def test_all_entries_have_name(self):
        snap = build_skill_snapshot()
        for entry in snap.skills:
            assert entry.name != ""

    def test_all_entries_have_valid_risk(self):
        snap = build_skill_snapshot()
        valid_risks = {"R0", "R1", "R2", "R3"}
        for entry in snap.skills:
            assert entry.risk in valid_risks, f"{entry.name} has invalid risk {entry.risk}"

    def test_all_entries_have_description(self):
        snap = build_skill_snapshot()
        for entry in snap.skills:
            assert entry.description != "", f"{entry.name} has empty description"

    def test_git_status_skill_present(self):
        snap = build_skill_snapshot()
        names = [s.name for s in snap.skills]
        assert "git.status" in names

    def test_git_status_has_outputs_from_yaml(self):
        """git.status 应从 skill.yaml 读取 outputs 字段。"""
        snap = build_skill_snapshot()
        git_status = next((s for s in snap.skills if s.name == "git.status"), None)
        assert git_status is not None
        # outputs 来自 skill.yaml，至少有 branch
        assert "branch" in git_status.outputs

    def test_generated_at_present(self):
        snap = build_skill_snapshot()
        assert "T" in snap.generated_at  # ISO 格式

    def test_skill_count_matches_skills_list(self):
        snap = build_skill_snapshot()
        assert snap.skill_count == len(snap.skills)

    def test_to_json_roundtrip(self):
        snap = build_skill_snapshot()
        restored = SkillSnapshot.from_dict(json.loads(snap.to_json()))
        assert restored.skill_count == snap.skill_count


# ── build_cli_snapshot ─────────────────────────────────────


class TestBuildCliSnapshot:
    def test_returns_cli_snapshot(self):
        snap = build_cli_snapshot()
        assert isinstance(snap, CliSnapshot)

    def test_command_count_positive(self):
        snap = build_cli_snapshot()
        assert snap.command_count > 0

    def test_commands_sorted(self):
        snap = build_cli_snapshot()
        cmds = [c.command for c in snap.commands]
        assert cmds == sorted(cmds)

    def test_all_commands_start_with_smartdev(self):
        snap = build_cli_snapshot()
        for cmd in snap.commands:
            assert cmd.command.startswith("smartdev "), \
                f"Command '{cmd.command}' does not start with 'smartdev '"

    def test_git_commit_present(self):
        snap = build_cli_snapshot()
        cmds = [c.command for c in snap.commands]
        assert "smartdev git commit" in cmds

    def test_git_tag_present(self):
        snap = build_cli_snapshot()
        cmds = [c.command for c in snap.commands]
        assert "smartdev git tag" in cmds

    def test_manifest_diff_present(self):
        snap = build_cli_snapshot()
        cmds = [c.command for c in snap.commands]
        assert "smartdev manifest diff" in cmds

    def test_snapshot_skills_present(self):
        snap = build_cli_snapshot()
        cmds = [c.command for c in snap.commands]
        assert "smartdev snapshot skills" in cmds

    def test_git_commit_has_message_arg(self):
        snap = build_cli_snapshot()
        git_commit = next((c for c in snap.commands if c.command == "smartdev git commit"), None)
        assert git_commit is not None
        assert "--message" in git_commit.args

    def test_git_commit_has_apply_arg(self):
        snap = build_cli_snapshot()
        git_commit = next((c for c in snap.commands if c.command == "smartdev git commit"), None)
        assert git_commit is not None
        assert "--apply" in git_commit.args

    def test_command_count_matches_list(self):
        snap = build_cli_snapshot()
        assert snap.command_count == len(snap.commands)

    def test_run_new_present(self):
        """Phase 11D Step 1: smartdev run new 出现在 CLI 快照中"""
        snap = build_cli_snapshot()
        run_new = next((c for c in snap.commands if c.command == "smartdev run new"), None)
        assert run_new is not None, "smartdev run new 应出现在 CLI 快照中"
        assert "run_id" in run_new.args
        assert "--force" in run_new.args
        assert "--max-files" in run_new.args
        assert "--allowed-paths" in run_new.args

    def test_run_workflow_still_present(self):
        """Phase 11D Step 1: smartdev run（workflow 模式）仍然存在"""
        snap = build_cli_snapshot()
        run_cmd = next((c for c in snap.commands if c.command == "smartdev run"), None)
        assert run_cmd is not None, "smartdev run（workflow 模式）应仍然存在"
        assert "--project" in run_cmd.args
        assert "--task" in run_cmd.args

    def test_scope_check_present(self):
        """Phase 11D Step 2: smartdev run scope-check 出现在 CLI 快照中"""
        snap = build_cli_snapshot()
        sc = next((c for c in snap.commands if c.command == "smartdev run scope-check"), None)
        assert sc is not None, "smartdev run scope-check 应出现在 CLI 快照中"
        assert "run_id" in sc.args
        assert "--changed-files" in sc.args
        assert "--json" in sc.args

    def test_handoff_code_present(self):
        """Phase 11D Step 3: smartdev run handoff-code 出现在 CLI 快照中"""
        snap = build_cli_snapshot()
        hc = next((c for c in snap.commands if c.command == "smartdev run handoff-code"), None)
        assert hc is not None, "smartdev run handoff-code 应出现在 CLI 快照中"
        assert "run_id" in hc.args
        assert "--changed-files" in hc.args
        assert "--target" in hc.args

    def test_handoff_doc_present(self):
        """Phase 11D Step 4: smartdev run handoff-doc 出现在 CLI 快照中"""
        snap = build_cli_snapshot()
        hd = next((c for c in snap.commands if c.command == "smartdev run handoff-doc"), None)
        assert hd is not None, "smartdev run handoff-doc 应出现在 CLI 快照中"
        assert "run_id" in hd.args
        assert "--run-tests" in hd.args

    def test_handoff_review_present(self):
        """Phase 11D Step 5: smartdev run handoff-review 出现在 CLI 快照中"""
        snap = build_cli_snapshot()
        hr = next((c for c in snap.commands if c.command == "smartdev run handoff-review"), None)
        assert hr is not None, "smartdev run handoff-review 应出现在 CLI 快照中"
        assert "run_id" in hr.args
        assert "--changed-files" in hr.args

    def test_context_present(self):
        """Role activation: smartdev run context 出现在 CLI 快照中"""
        snap = build_cli_snapshot()
        ctx = next((c for c in snap.commands if c.command == "smartdev run context"), None)
        assert ctx is not None, "smartdev run context 应出现在 CLI 快照中"
        assert "run_id" in ctx.args
        assert "--role" in ctx.args
        assert "--info" in ctx.args

    def test_report_present(self):
        """Phase 11D Step 6B: smartdev run report 出现在 CLI 快照中"""
        snap = build_cli_snapshot()
        rp = next((c for c in snap.commands if c.command == "smartdev run report"), None)
        assert rp is not None, "smartdev run report 应出现在 CLI 快照中"
        assert "run_id" in rp.args
        assert "--changed-files" in rp.args
        assert "--tests" in rp.args
        assert "--status" in rp.args

    def test_to_json_roundtrip(self):
        snap = build_cli_snapshot()
        restored = CliSnapshot.from_dict(json.loads(snap.to_json()))
        assert restored.command_count == snap.command_count

    def test_generated_at_present(self):
        snap = build_cli_snapshot()
        assert "T" in snap.generated_at


# ── build_mcp_snapshot ─────────────────────────────────────


class TestBuildMcpSnapshot:
    def test_returns_mcp_snapshot(self):
        snap = build_mcp_snapshot()
        assert isinstance(snap, McpSnapshot)

    def test_available_reflects_mcp_installed(self):
        """available 应与 mcp 包是否安装一致。"""
        try:
            import mcp  # noqa: F401
            mcp_installed = True
        except ImportError:
            mcp_installed = False
        snap = build_mcp_snapshot()
        assert snap.available == mcp_installed

    def test_mcp_not_installed_returns_empty(self, monkeypatch):
        """模拟 mcp 未安装：返回 available=False，tool_count=0。"""
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "mcp":
                raise ImportError("mocked: mcp not installed")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        snap = build_mcp_snapshot()
        assert snap.available is False
        assert snap.tool_count == 0
        assert snap.tools == []

    def test_to_json_valid(self):
        snap = build_mcp_snapshot()
        parsed = json.loads(snap.to_json())
        assert "tool_count" in parsed
        assert "available" in parsed

    def test_generated_at_present(self):
        snap = build_mcp_snapshot()
        assert "T" in snap.generated_at

    def test_mcp_installed_has_tools(self):
        """如果 mcp 已安装，工具数应 > 0。"""
        try:
            import mcp  # noqa: F401
        except ImportError:
            pytest.skip("mcp not installed")
        snap = build_mcp_snapshot()
        assert snap.tool_count > 0

    def test_mcp_tools_sorted(self):
        """工具列表应按 name 排序。"""
        try:
            import mcp  # noqa: F401
        except ImportError:
            pytest.skip("mcp not installed")
        snap = build_mcp_snapshot()
        names = [t.name for t in snap.tools]
        assert names == sorted(names)

    def test_mcp_ping_tool_present(self):
        """smartdev_ping 工具应始终存在。"""
        try:
            import mcp  # noqa: F401
        except ImportError:
            pytest.skip("mcp not installed")
        snap = build_mcp_snapshot()
        names = [t.name for t in snap.tools]
        assert "smartdev_ping" in names


# ── save_snapshot 持久化 ───────────────────────────────────


class TestSaveSnapshot:
    def test_save_creates_file(self, tmp_path: Path):
        runs_dir = tmp_path / ".smartdev" / "runs"
        snap = build_skill_snapshot()
        out = save_snapshot(snap.to_dict(), "skill", runs_dir, "run-001")
        assert out.exists()
        assert out.name == "skill-snapshot.json"

    def test_save_path_contains_run_id(self, tmp_path: Path):
        runs_dir = tmp_path / ".smartdev" / "runs"
        snap = build_cli_snapshot()
        out = save_snapshot(snap.to_dict(), "cli", runs_dir, "run-cli-001")
        assert "run-cli-001" in str(out)

    def test_save_content_valid_json(self, tmp_path: Path):
        runs_dir = tmp_path / ".smartdev" / "runs"
        snap = build_skill_snapshot()
        out = save_snapshot(snap.to_dict(), "skill", runs_dir, "run-json")
        parsed = json.loads(out.read_text())
        assert "skill_count" in parsed

    def test_save_creates_parent_dirs(self, tmp_path: Path):
        """runs_dir 不存在时 save_snapshot 自动创建。"""
        runs_dir = tmp_path / "nonexistent" / "runs"
        snap = build_cli_snapshot()
        out = save_snapshot(snap.to_dict(), "cli", runs_dir, "auto-dir")
        assert out.exists()
